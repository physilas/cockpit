"""Passive replay of the KNOWN profile-12 leak validation, never fresh evidence.

Run through ai.job_control with nice15. The unmodified deterministic agent
receives only its permitted current view. A tracing ModuleEnv records at most
three previous own/public decision events per terminal non-win, without
changing the public-case evaluator, its masks, RNG, rewards or policy calls.
"""
import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time
from unittest.mock import patch

import torch

from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .leak_strength_compare import _write, _report_path, atlanta_cases
from .module_training_eval import case_key
from .modules import CARDS, MODULE_ACTIONS, MODULE_SLOTS, ModuleEnv
from .public_case_eval import run_public_case
from .search_evaluate import paired_outcomes
from .train_leak import phase_fingerprint


BASE_SEED = 14_930_000
GAMES_PER_CASE = 20
SEED_STRIDE = 100
STOP_FILE = Path('runs/STOP_AI_TRAINING')
CARD_ACTIONS = frozenset(('adaptation', 'anticipation', 'swap_start', 'swap_choose',
                          'swap_cancel', 'bonus_roll', 'bonus_place', 'bonus_coffee'))
PUBLIC_KEYS = ('role', 'regular_turn', 'round_starter', 'round', 'height', 'distance',
               'attitude', 'aero_blue', 'aero_orange', 'brakes', 'coffee', 'reroll_tokens',
               'partner_remaining', 'last_round', 'holding', 'gear', 'flaps',
               'brake_progress', 'board', 'track', 'fuel', 'modules_state', 'reroll')


def check_stop():
    if STOP_FILE.exists():
        raise ValueError('Persistent training stop is active; explicit resumption is required.')


def probe_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    root = Path(__file__).resolve().parents[1]
    for name in ('ai/leak_failure_probe.py', 'ai/public_case_eval.py', 'ai/train_leak.py',
                 'ai/agents.py', 'ai/module_training_eval.py', 'ai/leak_strength_compare.py',
                 'backend/cockpit.py', 'backend/spielplan.py', 'backend/zusatzregeln.py',
                 'backend/landung.py', 'backend/wuerfel.py'):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def validate_case_seed(case, seed, games):
    """Only prefixes/chunks of the already consumed 20-game validation cohort."""
    if (case.get('airport') != 'LOG_ATL_YELLOW' or case.get('modules') != ['leak']
            or not isinstance(case.get('abilities'), (list, tuple))
            or len(case['abilities']) != 1 or case['abilities'][0] not in CARDS):
        raise ValueError('Use an official Atlanta-yellow single-card leak case.')
    start = BASE_SEED + sorted(CARDS).index(case['abilities'][0]) * SEED_STRIDE
    if (type(seed) is not int or type(games) is not int or not 1 <= games <= GAMES_PER_CASE
            or not start <= seed or seed + games > start + GAMES_PER_CASE):
        raise ValueError('Replay only the known 14,930,000+100*card validation cohorts.')


def public_view(view):
    """Explicit allowlist: no hidden hands, engine instance or RNG fields."""
    return deepcopy({key: view[key] for key in PUBLIC_KEYS if key in view})


def action_description(index):
    action = MODULE_ACTIONS[index]
    result = {'id': index, **asdict(action)}
    if action.kind in ('place', 'bonus_place'):
        result['slot_description'] = asdict(MODULE_SLOTS[action.slot])
    return result


class TraceModuleEnv(ModuleEnv):
    """Keep diagnostics out of policy inputs and original episode records."""
    def __init__(self, *args, **kwargs):
        self.probe_records = []
        self._probe_info = None
        self._tail = deque(maxlen=3)
        self._offered, self._advised, self._chosen = Counter(), Counter(), Counter()
        self._triggered = Counter()
        super().__init__(*args, **kwargs)

    def reset(self, **kwargs):
        self._tail.clear()
        self._offered.clear(); self._advised.clear(); self._chosen.clear()
        self._triggered.clear()
        return super().reset(**kwargs)

    def info(self):
        info = super().info()
        self._probe_info = info
        return info

    def step(self, selected):
        check_stop()
        view, info = self.view(), self._probe_info
        if info is None or not info['action_mask'][selected]:
            raise RuntimeError('Trace must observe an already legal evaluator action.')
        mask, reference = info['action_mask'], info['reference_action_mask']
        offered = sorted({action.kind for action, allowed in zip(MODULE_ACTIONS, mask)
                          if allowed and action.kind in CARD_ACTIONS})
        advised = sorted({action.kind for action, allowed in zip(MODULE_ACTIONS, reference)
                          if allowed and action.kind in CARD_ACTIONS})
        self._offered.update(offered); self._advised.update(advised)
        action = MODULE_ACTIONS[selected]
        if action.kind in CARD_ACTIONS:
            self._chosen[action.kind] += 1
        event = {'step': self.steps, 'public_before': public_view(view),
                 'own_hand': list(view['own_dice']), 'action': action_description(selected),
                 'legal_action_ids': [i for i, allowed in enumerate(mask) if allowed],
                 'reference_action_ids': [i for i, allowed in enumerate(reference) if allowed],
                 'reference_selected': bool(reference[selected]),
                 'card_offers': offered, 'card_reference_offers': advised}
        answer = super().step(selected)
        event['public_after'] = public_view(self.view())
        effects = []
        if action.kind in ('place', 'bonus_place'):
            slot = MODULE_SLOTS[action.slot]
            if slot.target in ('ruder', 'triebwerk'):
                pair = (0, 1) if slot.target == 'ruder' else (2, 3)
                other = view['board'][pair[1 if slot.owner == 'pilot' else 0]]
                face = view['own_dice'][action.die] if action.kind == 'place' else view['modules_state']['pending']['value']
                card = 'control' if slot.target == 'ruder' else 'mastery'
                if card in view['modules_state']['cards'] and other and face == other['value']:
                    effects.append(card)
        if (not view['modules_state']['sync_triggered']
                and event['public_after']['modules_state']['sync_triggered']):
            effects.append('synchronisation')
        # Pair triggers are counted even when the resulting resource is capped;
        # they do not claim an extra coffee/reroll beyond actual engine values.
        self._triggered.update(effects)
        event['card_pair_or_sync_triggers'] = effects
        event['outcome'] = {key: answer[-1][key] for key in ('status', 'reason', 'round', 'steps')}
        self._tail.append(event)
        return answer

    def episode_record(self, seed, ai_role, total_return):
        record = super().episode_record(seed, ai_role, total_return)
        self.probe_records.append({
            'seed': seed, 'scenario': record['scenario'], 'status': record['status'],
            'reason': record['reason'], 'round': record['round'],
            'height': record['height_remaining'],
            'card_offered_decisions': dict(self._offered),
            'card_reference_offered_decisions': dict(self._advised),
            'card_selected_actions': dict(self._chosen),
            'card_pair_or_sync_triggers': dict(self._triggered),
            'last_events': deepcopy(list(self._tail)) if record['status'] != 'gewonnen' else [],
        })
        return record


def run_probe_case(model, case, games, seed, cpu_duty_cycle=.7):
    validate_case_seed(case, seed, games)
    check_stop()
    if getattr(model, 'guide_margin', None) != 12. or model.config.get('guide_margin') != 12.:
        raise ValueError('Use the unchanged profile-12 guide-margin12 checkpoints.')
    before = weight_fingerprint(model)
    captured = []

    class CapturedEnv(TraceModuleEnv):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.append(self)

    # The evaluator's selection loop and records remain authoritative. This
    # patch only changes the local class constructor for this process/call.
    with patch('ai.public_case_eval.ModuleEnv', CapturedEnv):
        summary = run_public_case(model, case, games, seed,
                                 cpu_duty_cycle=cpu_duty_cycle, assistance_version=12)
    if weight_fingerprint(model) != before:
        raise RuntimeError('Passive instrumentation changed model weights.')
    traces = [row for env in captured for row in env.probe_records]
    if len(traces) != games or [row['seed'] for row in traces] != list(range(seed, seed + games)):
        raise RuntimeError('Trace/episode alignment changed.')
    return {'summary': summary, 'traces': traces}


def group_traces(traces):
    groups, reasons, rounds, heights = {}, Counter(), Counter(), Counter()
    offered, advised, chosen, triggered = Counter(), Counter(), Counter(), Counter()
    for trace in traces:
        offered.update(trace['card_offered_decisions'])
        advised.update(trace['card_reference_offered_decisions'])
        chosen.update(trace['card_selected_actions'])
        triggered.update(trace['card_pair_or_sync_triggers'])
        if trace['status'] == 'gewonnen':
            continue
        reason = trace['reason'] or trace['status']
        reasons[reason] += 1; rounds[str(trace['round'])] += 1; heights[str(trace['height'])] += 1
        usage = {'selected_actions': trace['card_selected_actions'],
                 'pair_or_sync_triggers': trace['card_pair_or_sync_triggers']}
        key = (reason, trace['round'], trace['height'], json.dumps(usage, sort_keys=True))
        row = groups.setdefault(key, dict(reason=reason, round=trace['round'], height=trace['height'],
            card_usage=usage, games=0, seeds=[]))
        row['games'] += 1; row['seeds'].append(trace['seed'])
    return {'loss_groups': list(groups.values()), 'losses_by_reason': dict(reasons),
            'losses_by_round': dict(rounds), 'losses_by_height': dict(heights),
            'card_offered_decisions': dict(offered), 'card_reference_offered_decisions': dict(advised),
            'card_selected_actions': dict(chosen), 'card_pair_or_sync_triggers': dict(triggered)}


def load_models(source, candidate):
    models, metadata = {}, {}
    planner, phase = planner_fingerprint(3), phase_fingerprint()
    for label, path in (('source', source), ('candidate', candidate)):
        path = Path(path)
        model, payload = load_checkpoint(path)
        config = payload.get('train_config', {})
        if (model.config.get('kind') != 'guided_residual' or model.config.get('observation_size') != 489
                or model.config.get('action_count') != 217 or model.guide_margin != 12.
                or model.config.get('guide_margin') != 12. or config.get('assistance_version') != 12
                or config.get('phase_kind') != 'new_public_module_profile_12_leak_cards'
                or config.get('planner_sha256') != planner or config.get('phase_sha256') != phase
                or config.get('eval_seed') != BASE_SEED or config.get('eval_seed_stride') != SEED_STRIDE
                or config.get('eval_games_per_case') != GAMES_PER_CASE
                or [case_key(case) for case in config.get('curriculum_cases', [])]
                != ['LOG_ATL_YELLOW|' + card for card in sorted(CARDS)]):
            raise ValueError('Use finished unchanged current profile-12/guide12 leak checkpoints.')
        steps = payload.get('total_steps')
        if type(steps) is not int or (steps != 0 if label == 'source' else steps <= 0):
            raise ValueError('Source must be warm0; candidate must contain completed new decisions.')
        models[label] = model
        metadata[label] = {'checkpoint': _report_path(path), 'checkpoint_file_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'weights_sha256': weight_fingerprint(model), 'phase_steps': steps,
            'frozen_source_weights_sha256': weight_fingerprint(model.source),
            'initial_weights_sha256': config.get('initial_weights_sha256'),
            'source_weights_sha256': config.get('source_weights_sha256'),
            'guide_margin': model.guide_margin, 'assistance_version': 12}
    warm_sha = metadata['source']['weights_sha256']
    if (any(row['initial_weights_sha256'] != warm_sha for row in metadata.values())
            or metadata['source']['source_weights_sha256'] != metadata['candidate']['source_weights_sha256']
            or metadata['source']['frozen_source_weights_sha256'] != metadata['candidate']['frozen_source_weights_sha256']):
        raise ValueError('Warm and candidate must belong to the same unchanged frozen-source phase.')
    return models, metadata


def load_validation(path, metadata):
    data = Path(path).read_bytes()
    rows = [json.loads(line) for line in data.decode().splitlines() if line.strip()]
    selected = {}
    for label, model in metadata.items():
        matching = [row for row in rows if row.get('steps') == model['phase_steps']]
        if len(matching) != 1 or matching[0].get('release_evidence') is not False:
            raise ValueError('A unique old development validation is required for each checkpoint step.')
        cases = matching[0].get('cases')
        if not isinstance(cases, dict) or set(cases) != {'LOG_ATL_YELLOW|' + card for card in CARDS}:
            raise ValueError('Each stored validation must contain exactly all six old card cases.')
        for row in cases.values():
            if (row.get('games') != GAMES_PER_CASE or type(row.get('wins')) is not int
                    or not 0 <= row['wins'] <= GAMES_PER_CASE or row.get('win_rate') != row['wins']/GAMES_PER_CASE):
                raise ValueError('Stored validation counts must match the original 20-game cohort.')
        selected[label] = cases
    return selected, hashlib.sha256(data).hexdigest()


def validation_match(summary, expected):
    keys = ('games', 'wins', 'win_rate', 'decisions', 'reference_departures', 'loss_reasons')
    return {key: {'expected': expected.get(key), 'reproduced': summary.get(key)}
            for key in keys if expected.get(key) != summary.get(key)}


_models = None


def _initialize(source, candidate, metadata, code_sha):
    global _models
    torch.set_num_threads(1)
    check_stop()
    _models, actual = load_models(source, candidate)
    if actual != metadata or probe_fingerprint() != code_sha:
        raise ValueError('Checkpoint or planning/probe sources changed before worker initialization.')


def _run(task):
    label, case, seed, games, duty = task
    return run_probe_case(_models[label], case, games, seed, duty)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('runs/leak-profile12-stage1/warm.pt'))
    parser.add_argument('--candidate', type=Path, default=Path('runs/leak-profile12-stage1/latest.pt'))
    parser.add_argument('--validation', type=Path, default=Path('runs/leak-profile12-stage1/validation.jsonl'))
    parser.add_argument('--matrix', type=Path, default=Path('ai/experiments/modules-30pct-2026-10-25/matrix.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=GAMES_PER_CASE)
    parser.add_argument('--seed', type=int, default=BASE_SEED)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args(argv)
    if (not 1 <= args.workers <= 8 or not math.isfinite(args.cpu_duty_cycle)
            or not 0 < args.cpu_duty_cycle <= .7 or args.seed != BASE_SEED
            or not 1 <= args.games <= GAMES_PER_CASE):
        parser.error('Use the known14930000 cohort,1..20 games/card,1..8 workers and duty<=.7.')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Preserve completed and partial evidence; use a new output path.')
    try:
        check_stop()
        cases = atlanta_cases(args.matrix)
        torch.set_num_threads(1)
        models, metadata = load_models(args.source, args.candidate)
        validation, validation_sha = load_validation(args.validation, metadata)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    code_sha = probe_fingerprint()
    report = dict(format=1, phase='passive_known_profile12_validation_failure_replay',
        complete=False, release_evidence=False, independent_test_used=False,
        qualification_used=False, fresh_evidence=False, repeated_development_validation=True,
        weights_changed=False, models=metadata, base_seed=BASE_SEED, games_per_case=args.games,
        case_seeds={case_key(case): BASE_SEED + ordinal * SEED_STRIDE for ordinal, case in enumerate(cases)},
        assistance_version=12, guide_margin=12., workers=args.workers, cpu_duty_cycle=args.cpu_duty_cycle,
        threads=1, clock_model='engine_wall_clock', planner_sha256=planner_fingerprint(3),
        phase_sha256=phase_fingerprint(), probe_sha256=code_sha,
        validation_path=_report_path(args.validation), validation_sha256=validation_sha,
        output_path=_report_path(args.output), max_events_per_loss=3, cases={})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(args.output, report, initial=True)
    except FileExistsError:
        parser.error('Another invocation created this output; preserve it.')
    started = time.monotonic()
    try:
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize, initargs=(args.source, args.candidate, metadata, code_sha)) as pool:
            for ordinal, case in enumerate(cases):
                check_stop()
                key = case_key(case)
                rows = report['cases'][key] = {}
                for label in ('source', 'candidate'):
                    check_stop()
                    chunk = math.ceil(args.games / args.workers)
                    tasks = [(label, case, BASE_SEED + ordinal * SEED_STRIDE + offset,
                              min(chunk, args.games-offset), args.cpu_duty_cycle)
                             for offset in range(0, args.games, chunk)]
                    outputs = list(pool.map(_run, tasks))
                    episodes = [row for output in outputs for row in output['summary']['episodes']]
                    traces = [row for output in outputs for row in output['traces']]
                    seeds = list(range(BASE_SEED+ordinal*SEED_STRIDE, BASE_SEED+ordinal*SEED_STRIDE+args.games))
                    if ([row['seed'] for row in episodes] != seeds or [row['seed'] for row in traces] != seeds
                            or any(row['case_key'] != key for row in episodes)):
                        raise RuntimeError('The replay did not preserve exact case/seed alignment.')
                    from .evaluate import summarize_episodes
                    summary = summarize_episodes(episodes)
                    summary.update(reference_departures=sum(row['reference_departures'] for row in episodes),
                                   decisions=sum(row['decisions'] for row in episodes))
                    mismatches = validation_match(summary, validation[label][key]) if args.games == GAMES_PER_CASE else None
                    rows[label] = {'summary': summary, 'traces': traces, **group_traces(traces),
                                   'old_validation_mismatches': mismatches,
                                   'full_old_validation_checked': args.games == GAMES_PER_CASE}
                    _write(args.output, report)
                    if mismatches:
                        raise RuntimeError(f'Old validation did not reproduce: {key}/{label}: {mismatches}')
                    print(json.dumps(dict(case=key, model=label, wins=summary['wins'], games=summary['games'],
                                          traced_losses=sum(row['status']!='gewonnen' for row in traces))), flush=True)
                rows['paired'] = paired_outcomes(rows['source']['summary']['episodes'], rows['candidate']['summary']['episodes'])
                _write(args.output, report)
        if (probe_fingerprint() != code_sha or hashlib.sha256(args.validation.read_bytes()).hexdigest() != validation_sha
                or load_models(args.source, args.candidate)[1] != metadata):
            raise RuntimeError('Frozen checkpoints, validation or planning/probe sources changed during replay.')
        check_stop()
        report.update(complete=True, elapsed_seconds=time.monotonic()-started)
        _write(args.output, report)
    except BaseException as exc:
        report.update(complete=False, error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic()-started)
        _write(args.output, report)
        raise


if __name__ == '__main__':
    main()
