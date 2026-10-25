"""Public, soft intern advice; engine legality remains the caller's authority.

Training spends a regular die and issues a same-role replacement token. The
ordered public token is planned as that replacement, never as an extra die.
Only base/kerosene/realtime physics are projected into the existing planner.
This is research advice, not a module qualification or a hard legality mask.
"""
import math
import time

from .actions import Action, ROLES
from .fuel import FUEL_ACTIONS, FUEL_SLOTS
from .modules import MODULE_ACTIONS
from .tactics import plan_actions
from .throttle import CpuBudget


def intern_schedule(view):
    """Public per-round quota; future capacity is an upper bound, not a promise."""
    state = view['modules_state']
    remaining = len(state['intern'])
    fields = state['extra_fields'][:2]
    trained = sum(field is not None for field in fields)
    future = 0 if view['last_round'] else max(0, int(view['height'] // 1000))
    counts = {view['role']: sum(bool(face) for face in view['own_dice']),
              ROLES[1 - ROLES.index(view['role'])]: view['partner_remaining']}
    slots = sum(field is None and counts[role] > 0 for role, field in zip(ROLES, fields))
    minimum_now = max(0, remaining - 2 * future)
    paced_now = max(0, math.ceil((remaining + trained) / (future + 1)) - trained)
    quota = min(slots, max(minimum_now, paced_now))
    return {'remaining_tokens': remaining, 'trained_this_round': trained,
            'future_rounds': future, 'current_training_slots': slots,
            'minimum_now': minimum_now, 'recommended_now': quota,
            'public_capacity_insufficient': remaining > slots + 2 * future}


def _projection(view, own_dice):
    result = {**view, 'own_dice': list(own_dice), 'board': list(view['board']),
              '_fuel_profile': 7}
    if view['fuel']['present']:
        result['board'].append({'value': 1, 'owner': 'pilot'} if view['fuel']['occupied'] else None)
    return result


def _token_targets(view, face):
    """Exact base/fuel destination rules for an unmodified intern token."""
    for index, slot in enumerate(FUEL_SLOTS):
        if slot.owner is not None and slot.owner != view['role']:
            continue
        if slot.target == 'kerosin':
            if view['fuel']['present'] and not view['fuel']['occupied']:
                yield index
            continue
        if view['board'][index] is not None or slot.target == 'konzentration':
            continue
        if slot.target == 'fahrwerk' and face not in ((1, 2), (3, 4), (5, 6))[slot.index]:
            continue
        if slot.target in ('landeklappe', 'bremse'):
            progress = view['flaps'] if slot.target == 'landeklappe' else view['brake_progress']
            first = next((i for i, done in enumerate(progress) if not done), len(progress))
            if not progress[slot.index] and slot.index != first:
                continue
            faces = ((1, 2), (2, 3), (4, 5), (5, 6))[slot.index] if slot.target == 'landeklappe' else ((2,), (4,), (6,))[slot.index]
            if face not in faces:
                continue
        yield index


def intern_reference(view, allowed_mask, *, beam=24, cpu_duty_cycle=1.):
    """Return a nonempty allowed subset for the guided policy's SOFT reference.

    Pending tokens are mapped to a vacant virtual own-die index solely for the
    public planner. The actual game, hand, mask, and RNG are never modified.
    """
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed_mask):
        raise ValueError('Expected a schema-3 Boolean action mask.')
    if type(beam) is not int or not 1 <= beam <= 128:
        raise ValueError('Use a bounded planning beam in [1, 128].')
    original = list(allowed_mask)
    state = view['modules_state']
    if ('intern' not in state['modules'] or set(state['modules']) - {'intern', 'kerosene', 'realtime'}
            or state['swap'] or view['reroll']):
        return original
    budget = CpuBudget(cpu_duty_cycle)
    checkpoint = time.perf_counter()

    def cooperate():
        nonlocal checkpoint
        if time.perf_counter() - checkpoint >= .02:
            budget.pause()
            checkpoint = time.perf_counter()

    def rank_token(face, index, target_indices):
        dice = list(view['own_dice'])
        dice[index] = face
        first = [False] * len(FUEL_ACTIONS)
        for slot in target_indices:
            first[FUEL_ACTIONS.index(Action('place', die=index, slot=slot))] = True
        ranked, _ = plan_actions(_projection(view, dice), first, beam=beam, version=3, cooperate=cooperate)
        return ranked

    pending = state['pending']
    if pending:
        if pending['source'] != 'intern' or pending['role'] != view['role']:
            return original
        vacant = next((i for i, face in enumerate(view['own_dice']) if not face), None)
        if vacant is None:
            return original
        targets = [action.slot for allowed, action in zip(original, MODULE_ACTIONS)
                   if allowed and action.kind == 'bonus_place' and action.slot < len(FUEL_SLOTS)]
        ranked = rank_token(pending['value'], vacant, targets)
        best = max(ranked.values(), default=-math.inf)
        result = [False] * len(original)
        for index, action in enumerate(MODULE_ACTIONS):
            if original[index] and action.kind == 'bonus_place' and action.slot < len(FUEL_SLOTS):
                virtual = FUEL_ACTIONS.index(Action('place', die=vacant, slot=action.slot))
                result[index] = ranked.get(virtual, -math.inf) >= best - 4
        return result if any(result) and ranked else original
    prefix = list(original[:len(FUEL_ACTIONS)])
    regular, _ = plan_actions(_projection(view, view['own_dice']), prefix,
                              beam=beam, version=3, cooperate=cooperate)
    best_regular = max(regular.values(), default=-math.inf)
    training = {}
    if state['intern']:
        token = state['intern'][0 if view['role'] == 'pilot' else -1]
        targets = list(_token_targets(view, token))
        quality_by_replaced_face = {}
        for index, action in enumerate(MODULE_ACTIONS):
            if original[index] and action.kind == 'place' and action.slot in (21, 22):
                old_face = view['own_dice'][action.die]
                if old_face not in quality_by_replaced_face:
                    scores = rank_token(token, action.die, targets)
                    quality_by_replaced_face[old_face] = max(scores.values(), default=-math.inf)
                if math.isfinite(quality_by_replaced_face[old_face]):
                    training[index] = quality_by_replaced_face[old_face]
    best_training = max(training.values(), default=-math.inf)
    due = intern_schedule(view)['recommended_now'] > 0
    recommend_training = training and best_training > -500 and (due or best_training >= best_regular + 2)
    result = [False] * len(original)
    if recommend_training:
        for index, quality in training.items():
            result[index] = quality >= best_training - 4
    else:
        for index, quality in regular.items():
            result[index] = original[index] and quality >= best_regular - 4
        if best_regular < -100:
            reroll = MODULE_ACTIONS.index(Action('reroll_start'))
            if original[reroll]:
                result = [False] * len(original)
                result[reroll] = True
    return result if any(result) else original
