"""Offline import of explicit human thumbs on permitted AI decisions.

Ratings are weak actor feedback, never PPO rewards, critic targets or proof of
winning play. This module does not update any model or automatically consume a
dataset during training. Different observation schemas are never padded/mixed.
"""
import argparse
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from .actions import ACTIONS, ACTION_MASK_VERSION, ROLES, SLOTS
from .observation import feature_names


@dataclass(frozen=True)
class Feedback:
    observations: tuple
    masks: tuple
    actions: tuple
    ratings: tuple
    reference_masks: tuple | None
    session_ids: tuple
    manifest: dict

    def tensors(self, device='cpu'):
        """Build an auxiliary dataset without touching policy/critic weights."""
        import torch
        result = {
            'observations': torch.tensor(self.observations, dtype=torch.float32, device=device),
            'masks': torch.tensor(self.masks, dtype=torch.bool, device=device),
            'actions': torch.tensor(self.actions, dtype=torch.long, device=device),
            'ratings': torch.tensor(self.ratings, dtype=torch.float32, device=device),
        }
        if self.reference_masks is not None:
            result['reference_masks'] = torch.tensor(self.reference_masks, dtype=torch.bool, device=device)
        return result


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _schema(version):
    if version == 3:
        from .modules import module_schema
        return module_schema()
    if version == 2:
        from .fuel import fuel_schema
        return fuel_schema()
    if version != 1:
        raise ValueError('Feedback schema must be 1, 2 or 3.')
    return {'version': 1, 'features': feature_names(),
            'actions': [asdict(action) for action in ACTIONS],
            'slots': [asdict(slot) for slot in SLOTS]}


def _timestamp(value, context):
    if not isinstance(value, str):
        raise ValueError(f'Missing {context} timestamp.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError(f'Invalid {context} timestamp.') from exc
    if parsed.tzinfo is None:
        raise ValueError(f'{context} timestamp needs a timezone.')


def _latest_sessions(paths):
    files = set()
    for source in paths:
        path = Path(source)
        if not path.exists():
            raise ValueError(f'Feedback source does not exist: {path}')
        files.update(path.rglob('*.json') if path.is_dir() else [path])
    latest = {}
    for path in sorted(files):
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('version') != 1:
            raise ValueError(f'Unknown feedback export version: {path}')
        if data.get('format') == 'flyteam-learning-session':
            sessions = [data.get('session')]
        elif data.get('format') == 'flyteam-learning-data':
            sessions = data.get('sessions')
        else:
            raise ValueError(f'Not a learning export: {path}')
        if not isinstance(sessions, list):
            raise ValueError(f'Export sessions must be a list: {path}')
        for session in sessions:
            if not isinstance(session, dict):
                raise ValueError(f'Invalid session: {path}')
            identity, revision = session.get('id'), session.get('data_revision')
            if not isinstance(identity, str) or not identity or type(revision) is not int or revision < 1:
                raise ValueError(f'Missing session identity/revision: {path}')
            # Browser batches retain schema 1 at the root; Crew 2 carries its
            # actual schema inside each session. Do not trust the batch root.
            effective_schema = session.get('schema', data.get('schema'))
            snapshot = {'session': session, 'schema': effective_schema,
                        'action_mask_version': data.get('action_mask_version')}
            previous = latest.get(identity)
            if previous and revision == previous[0] and _canonical(snapshot) != _canonical(previous[1]):
                raise ValueError(f'Conflicting feedback revision: {identity}/{revision}')
            if previous is None or revision > previous[0]:
                latest[identity] = revision, snapshot, path
    return latest


def _validate_action(action, actual, role, slots):
    if not isinstance(actual, dict) or actual.get('kind') != action['kind'] or actual.get('role') != role:
        return False
    kind = action['kind']
    if kind in ('place', 'coffee', 'adaptation', 'anticipation', 'swap_choose'):
        if actual.get('die') != action['die']:
            return False
    if kind in ('place', 'bonus_place'):
        slot = slots[action['slot']]
        if kind == 'place' and slot['owner'] not in (None, role):
            return False
        if (actual.get('target') != slot['target'] or actual.get('index') != slot['index'] or
                actual.get('radio_index', 0) != slot['radio_index']):
            return False
        if 'slot' in actual and actual['slot'] != action['slot']:
            return False
    if kind in ('coffee', 'bonus_coffee') and actual.get('delta') != action['delta']:
        return False
    if kind == 'reroll_select' and actual.get('subset') != action['subset']:
        return False
    return True


def load_feedback(paths, *, schema_version=3, airport=None, require_reference_masks=None):
    """Latest revisions, consented AI events, committed explicit nonzero thumbs.

    A later neutral/voided/revoked revision supersedes the old label. Outcome
    does not filter ratings: a good/bad move can occur in a losing game. Older
    +/-2 ratings become +/-1, so the former UI scale has no extra influence.
    Schema-3 guided feedback requires the ORIGINAL saved reference mask; it is
    never reconstructed from current planning code or fabricated from legality.
    """
    expected = _schema(schema_version)
    require_reference_masks = schema_version == 3 if require_reference_masks is None else require_reference_masks
    if type(require_reference_masks) is not bool:
        raise ValueError('require_reference_masks must be boolean.')
    observations, masks, actions, ratings, references, session_ids = [], [], [], [], [], []
    sources, fingerprint_rows = [], []
    excluded, roles, routes, rating_counts, models = Counter(), Counter(), Counter(), Counter(), Counter()
    latest = _latest_sessions(paths)
    legacy_scale = 0
    for identity, (revision, snapshot, path) in sorted(latest.items()):
        session = snapshot['session']
        if session.get('mode') != 'feedback':
            excluded['non_feedback_session'] += 1
            continue
        if airport is not None and session.get('scenario', {}).get('engine_code') != airport:
            excluded['other_route_session'] += 1
            continue
        if not session.get('consent'):
            excluded['nonconsented_session'] += 1
            continue
        consent = session['consent']
        if not isinstance(consent, dict) or consent.get('version') != '2026-10-18':
            raise ValueError(f'Unknown feedback consent: {path}')
        _timestamp(consent.get('accepted_at'), 'consent')
        if session.get('schema_version') != schema_version:
            excluded['other_schema_session'] += 1
            continue
        if (snapshot['schema'] != expected or session.get('action_mask_version') != ACTION_MASK_VERSION or
                snapshot['action_mask_version'] != ACTION_MASK_VERSION):
            raise ValueError(f'Incompatible feedback schema/action-mask version: {path}')
        human_role = session.get('human_role')
        route = session.get('scenario', {}).get('engine_code')
        if human_role not in ROLES or not isinstance(route, str) or not route:
            raise ValueError(f'Missing feedback role/route: {path}')
        events = session.get('events')
        if not isinstance(events, list):
            raise ValueError(f'Missing feedback events: {path}')
        recorded_model = session.get('model')
        recorded_model = recorded_model if isinstance(recorded_model, dict) else {}
        model_context = {key: recorded_model.get(key) if isinstance(recorded_model.get(key), str) else None
                         for key in ('id', 'fingerprint', 'run', 'checkpoint')}
        event_ids, start = set(), len(actions)
        for event in events:
            if not isinstance(event, dict):
                raise ValueError(f'Invalid feedback event: {path}')
            feedback = event.get('feedback')
            if feedback is None:
                excluded['unrated_event'] += 1
                continue
            if not isinstance(feedback, dict) or type(feedback.get('value')) is not int or abs(feedback['value']) > 2:
                raise ValueError(f'Invalid feedback value: {path}')
            if feedback['value'] == 0:
                excluded['neutral'] += 1
                continue
            if feedback.get('committed') is not True or feedback.get('explicit') is not True:
                excluded['uncommitted_or_implicit'] += 1
                continue
            if event.get('voided') is True:
                excluded['voided'] += 1
                continue
            if event.get('voided') is not False:
                raise ValueError(f'Unclear undo status: {path}')
            if event.get('actor') != 'ai':
                excluded['non_ai'] += 1
                continue
            if event.get('training_compatible') is not True:
                excluded['incompatible_event'] += 1
                continue
            action_id, decision, event_id = event.get('action_id'), event.get('decision'), event.get('id')
            if type(event_id) is not int or event_id < 0 or event_id in event_ids:
                raise ValueError(f'Invalid/duplicate rated event ID: {path}')
            event_ids.add(event_id)
            if not isinstance(decision, dict):
                raise ValueError(f'Missing rated decision: {path}')
            observation, mask, role = decision.get('observation'), decision.get('action_mask'), decision.get('role')
            if (type(action_id) is not int or not 0 <= action_id < len(expected['actions']) or
                    role not in ROLES or role == human_role or
                    not isinstance(observation, list) or len(observation) != len(expected['features']) or
                    not all(type(value) in (int, float) and math.isfinite(value) for value in observation) or
                    observation[:2] != [float(role == candidate) for candidate in ROLES] or
                    not isinstance(mask, list) or len(mask) != len(expected['actions']) or
                    not all(type(value) is bool for value in mask) or not mask[action_id]):
                raise ValueError(f'Invalid rated observation/action/mask: {path}, event {event_id}')
            if not _validate_action(expected['actions'][action_id], event.get('action'), role, expected['slots']):
                raise ValueError(f'Rated action ID disagrees with recorded move: {path}, event {event_id}')
            reference = decision.get('reference_action_mask')
            if require_reference_masks:
                if (not isinstance(reference, list) or len(reference) != len(mask) or
                        not all(type(value) is bool for value in reference) or not any(reference) or
                        any(ref and not legal for ref, legal in zip(reference, mask))):
                    raise ValueError(f'Missing/invalid saved guided reference mask: {path}, event {event_id}')
                references.append(tuple(reference))
            rating = 1 if feedback['value'] > 0 else -1
            legacy_scale += abs(feedback['value']) == 2
            observations.append(tuple(observation)); masks.append(tuple(mask))
            actions.append(action_id); ratings.append(rating)
            session_ids.append(identity)
            roles[role] += 1; routes[route] += 1; rating_counts[str(rating)] += 1
            models[_canonical(model_context).decode('utf-8')] += 1
            fingerprint_rows.append([identity, event_id, schema_version, observation, mask,
                                     reference if require_reference_masks else None, action_id, rating, model_context])
        if len(actions) > start:
            sources.append({'session_id': identity, 'revision': revision, 'path': str(path.resolve()),
                            'decisions': len(actions) - start, 'model': model_context})
    if not actions:
        raise ValueError(f'No explicit committed compatible AI feedback for schema {schema_version}.')
    manifest = {'version': 1, 'kind': 'offline_weak_actor_feedback', 'schema_version': schema_version,
                'sha256': hashlib.sha256(_canonical(fingerprint_rows)).hexdigest(),
                'sessions': len(sources), 'decisions': len(actions), 'roles': dict(roles), 'routes': dict(routes),
                'ratings': dict(rating_counts), 'legacy_scale_normalized': legacy_scale,
                'rated_models': [{**json.loads(context), 'decisions': count}
                                 for context, count in sorted(models.items())],
                'requires_saved_reference_masks': require_reference_masks, 'excluded': dict(excluded),
                'sources': sources, 'critic_targets': False, 'on_policy_rollouts': False,
                'model_updates_applied': False}
    return Feedback(tuple(observations), tuple(masks), tuple(actions), tuple(ratings),
                    tuple(references) if require_reference_masks else None, tuple(session_ids), manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+', type=Path)
    parser.add_argument('--schema-version', type=int, choices=(1, 2, 3), default=3)
    parser.add_argument('--airport')
    args = parser.parse_args()
    try:
        dataset = load_feedback(args.paths, schema_version=args.schema_version, airport=args.airport)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(dataset.manifest, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
