"""Separate public wind/ice micro-plans; no released profile uses this file.

One known own-die placement (possibly preceded by coffee/adaptation) is ranked
with a joint assignment of the remaining OWN controls. When both partner
controls are public, their physical consequences are evaluated with the exact
module projections. Unknown partner faces are never filled in or sampled.
Persistent tasks/traffic and future capacity are heuristic values, not proofs
of a winning continuation. Partner follow-up upgrades/radio may change motion.
"""
from functools import lru_cache
from itertools import permutations, product
import math
import time

from .actions import Action, ROLES
from .module_physics import predict_rudder, predict_thrust
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .throttle import CpuBudget


ACTION_IDS = {action: index for index, action in enumerate(MODULE_ACTIONS)}


@lru_cache(maxsize=2048)
def _completion_options(hand, missing, coffee):
    """Minimum shared coffee per pair from distinct remaining own dice."""
    costs = {}
    for selected in permutations(hand, len(missing)):
        for faces in product(range(1, 7), repeat=len(missing)):
            spending = sum(abs(original - target) for original, target in zip(selected, faces))
            if spending <= coffee:
                costs[faces] = min(costs.get(faces, 99), spending)
    return tuple((faces, cost) for faces, cost in costs.items())


def eligible(view):
    state = view['modules_state']
    modules = set(state['modules'])
    return (bool(modules & {'wind', 'ice'}) and not modules - {'wind', 'ice'}
            and not state['pending'] and not state['swap'] and not view['reroll'])


def _legal(view, die, slot_index, face):
    """Virtual placement legality AFTER a helper changed this own die's face.

    The initial helper/placement must additionally belong to the caller's real
    engine mask. An optimistic future synchronization never adds die capacity.
    """
    slot = MODULE_SLOTS[slot_index]
    if slot.target in ('kerosin', 'training'):
        return False
    if slot.owner is not None and slot.owner != view['role']:
        return False
    if slot_index < 20:
        if view['board'][slot_index] is not None:
            return False
    elif view['modules_state']['extra_fields'][slot_index - 21] is not None:
        return False
    remaining = sum(bool(value) for value in view['own_dice'])
    missing = sum(view['board'][index] is None for index in (ROLES.index(view['role']), ROLES.index(view['role']) + 2))
    if slot.target not in ('ruder', 'triebwerk') and remaining <= missing:
        return False
    if slot.target == 'fahrwerk':
        return face in ((1, 2), (3, 4), (5, 6))[slot.index]
    if slot.target == 'landeklappe':
        first = next((index for index, done in enumerate(view['flaps']) if not done), 4)
        return (view['flaps'][slot.index] or slot.index == first) and face in ((1, 2), (2, 3), (4, 5), (5, 6))[slot.index]
    if slot.target == 'bremse':
        first = next((index for index, done in enumerate(view['brake_progress']) if not done), 3)
        return ('ice' not in view['modules_state']['modules']
                and (view['brake_progress'][slot.index] or slot.index == first)
                and face == (2, 4, 6)[slot.index])
    if slot.target == 'eisbremse':
        return ('ice' in view['modules_state']['modules']
                and slot.index // 2 == view['modules_state']['ice_progress']
                and face == 2 + slot.index // 2)
    return slot.target in ('ruder', 'triebwerk', 'funk', 'konzentration')


def _after_placement(view, die, slot_index, face, coffee):
    """Independent public planning value, not an engine or private-hand copy."""
    slot = MODULE_SLOTS[slot_index]
    changed = {**view, 'own_dice': list(view['own_dice']), 'board': list(view['board']),
        'gear': list(view['gear']), 'flaps': list(view['flaps']),
        'brake_progress': list(view['brake_progress']), 'coffee': coffee,
        'track': [dict(cell) for cell in view['track']],
        'modules_state': {**view['modules_state'], 'extra_fields': list(view['modules_state']['extra_fields'])}}
    changed['own_dice'][die] = 0
    placed = {'value': face, 'owner': view['role']}
    if slot_index < 20:
        changed['board'][slot_index] = placed
    else:
        changed['modules_state']['extra_fields'][slot_index - 21] = placed
    reward = 0.
    if slot.target == 'fahrwerk' and not view['gear'][slot.index]:
        changed['gear'][slot.index] = True
        changed['aero_blue'] += 1
        reward = 15.
    elif slot.target == 'landeklappe' and not view['flaps'][slot.index]:
        changed['flaps'][slot.index] = True
        changed['aero_orange'] += 1
        reward = 17.
    elif slot.target == 'bremse' and not view['brake_progress'][slot.index]:
        changed['brake_progress'][slot.index] = True
        changed['brakes'] += 2
        reward = 15.
    elif slot.target == 'eisbremse':
        pair = slot.index // 2
        complete = all(changed['modules_state']['extra_fields'][2 + pair * 2 + row] is not None for row in (0, 1))
        changed['modules_state']['ice_progress'] += int(complete)
        changed['brakes'] += int(complete)
        reward = 22. + 8. * complete
    elif slot.target == 'konzentration':
        changed['coffee'] = min(3, coffee + 1)
    elif slot.target == 'funk':
        cell = next((cell for cell in changed['track'] if cell['distance'] == view['distance'] - face + 1), None)
        if cell and cell['planes']:
            cell['planes'] -= 1
            reward = 100. if face == 1 else 50. if face == 2 else 20.
    return changed, reward


def _capacity_score(view, own_r, own_t):
    future = 0 if view['last_round'] else max(0, int(view['height'] // 1000))
    role = view['role']
    own_missing = int(not own_r) + int(not own_t)
    own_spare = sum(bool(face) for face in view['own_dice']) - own_missing + 2 * future
    partner = 1 - ROLES.index(role)
    partner_missing = sum(view['board'][index] is None for index in (partner, partner + 2))
    partner_spare = view['partner_remaining'] - partner_missing + 2 * future
    gear, flaps = view['gear'].count(False), view['flaps'].count(False)
    pilot_need = gear + int('ice' not in view['modules_state']['modules'] and not any(view['brake_progress']))
    copilot_need, shared_need = flaps, 0
    if 'ice' in view['modules_state']['modules']:
        fields = view['modules_state']['extra_fields'][2:]
        # All fields clear between rounds; the persistent progress marker,
        # not occupancy of older pairs, records their completed work.
        first = view['modules_state']['ice_progress'] * 2
        pilot_need += sum(fields[index] is None for index in range(first, 8, 2))
        shared_need = sum(fields[index] is None for index in range(first + 1, 8, 2))
    own_need, partner_need = (pilot_need, copilot_need) if role == 'pilot' else (copilot_need, pilot_need)
    deficit = max(0, own_need - own_spare) + max(0, partner_need - partner_spare)
    deficit += max(0, shared_need - max(0, own_spare - own_need) - max(0, partner_spare - partner_need))
    return -800. * deficit


def _motion_score(source, projected, own_r, own_t):
    """Resolve each control only when its partner value is already public."""
    role = source['role']
    other = 1 - ROLES.index(role)
    if not own_r or source['board'][other] is None:
        return 0.
    args = {f'{role}_value': own_r}
    rudder = predict_rudder(source, **args)
    score = -10_000. * rudder['stalled']
    if source['last_round']:
        score -= 3000. * abs(rudder['attitude'])
    else:
        score -= 2. * abs(rudder['attitude'])
    if not own_t or source['board'][other + 2] is None:
        return score
    # Keep original control occupancy so newly planned rudder/wind is resolved
    # once, rather than treating a virtual just-placed pair as already paid.
    physics = {**projected, 'board': source['board']}
    extra_ice = 4 - projected['modules_state']['ice_progress'] if projected['last_round'] and 'ice' in projected['modules_state']['modules'] else 0
    motion = predict_thrust(physics, **{f'{role}_value': own_t}, rudder=rudder, additional_ice_pairs=extra_ice)
    reason = motion['reason']
    if reason == 'uebers_ziel_hinaus': score -= 4000.
    elif reason == 'zu_schnell_gelandet': score -= 3000.
    elif reason == 'ruder_verbotene_stellung': score -= 3000.
    elif reason == 'kollision': score -= 1200.
    if not source['last_round'] and not source['holding']:
        rounds = max(1, int(source['height'] // 1000))
        wanted = min(2, math.ceil(source['distance'] / rounds))
        move = motion['attempted_movement']
        score -= 30. * abs(move - wanted)
        score -= 1500. * max(0, source['distance'] - move - 2 * (rounds - 1))
    return score


def wind_ice_plans(view, allowed_mask, *, cpu_duty_cycle=1.):
    """Return first action -> public one-placement macro quality.

    At most four dice, 31 slots, six faces and two adaptation modes. Remaining
    controls consume distinct regular dice and one shared coffee budget. Their
    unknown partner pair causes abstention from motion ranking, not a hidden
    hand lookup. No future bonus or future die roll is credited.
    """
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed_mask):
        raise ValueError('Expected a schema-3 Boolean allowed mask.')
    budget, checkpoint = CpuBudget(cpu_duty_cycle), time.perf_counter()
    if not eligible(view) or not any(allowed_mask):
        return {}
    role_index = ROLES.index(view['role'])
    original_r = view['board'][role_index]
    original_t = view['board'][role_index + 2]
    ranked, motion_cache = {}, {}

    for die, face in enumerate(view['own_dice']):
        if not face: continue
        flip_id = ACTION_IDS[Action('adaptation', die=die)]
        for flip in (False, True):
            if flip and not allowed_mask[flip_id]: continue
            start_face = 7 - face if flip else face
            for actual in range(1, 7):
                cost = abs(actual - start_face)
                if cost > view['coffee']: continue
                for slot_index, slot in enumerate(MODULE_SLOTS):
                    if not _legal(view, die, slot_index, actual): continue
                    placement = ACTION_IDS[Action('place', die=die, slot=slot_index)]
                    first = flip_id if flip else ACTION_IDS[Action('coffee', die=die, delta=actual - face)] if cost else placement
                    if not allowed_mask[first]: continue
                    projected, reward = _after_placement(view, die, slot_index, actual, view['coffee'] - cost)
                    r = actual if slot.target == 'ruder' else original_r['value'] if original_r else 0
                    t = actual if slot.target == 'triebwerk' else original_t['value'] if original_t else 0
                    if r and view['board'][1 - role_index] is not None:
                        rudder = predict_rudder(view, **{f'{view["role"]}_value': r})
                        if rudder['stalled']: continue
                    base = reward + _capacity_score(projected, r, t) - 3. * flip
                    missing = tuple(target for target, value in (('ruder', r), ('triebwerk', t)) if not value)
                    hand = tuple(sorted(value for value in projected['own_dice'] if value))
                    best = -20_000.
                    # Explicit same-hand assignments: never reserve one die
                    # for both rudder and thrust or spend a coffee twice.
                    for faces, spending in _completion_options(hand, missing, projected['coffee']):
                        assignment = dict(zip(missing, faces))
                        own_r, own_t = assignment.get('ruder', r), assignment.get('triebwerk', t)
                        key = slot_index, actual, own_r, own_t
                        if key not in motion_cache:
                            motion_cache[key] = _motion_score(view, projected, own_r, own_t)
                        quality = motion_cache[key] + 1.5 * (projected['coffee'] - spending)
                        best = max(best, quality)
                    quality = base + best
                    ranked[first] = max(ranked.get(first, -math.inf), quality)
                    now = time.perf_counter()
                    if now - checkpoint >= .02:
                        budget.pause(); checkpoint = time.perf_counter()
    budget.pause()
    return ranked


def wind_ice_reference(view, allowed_mask, source_reference, *, cpu_duty_cycle=1.):
    if (len(source_reference) != len(MODULE_ACTIONS)
            or any(type(flag) is not bool for flag in source_reference)
            or any(advised and not allowed_mask[index] for index, advised in enumerate(source_reference))):
        raise ValueError('Expected an engine-legal source reference.')
    ranked = wind_ice_plans(view, allowed_mask, cpu_duty_cycle=cpu_duty_cycle)
    if not ranked:
        return list(source_reference)
    best = max(ranked.values())
    reroll = ACTION_IDS[Action('reroll_start')]
    if best < -500 and allowed_mask[reroll]:
        return [index == reroll for index in range(len(allowed_mask))]
    result = [bool(allowed and ranked.get(index, -math.inf) >= best - 2.) for index, allowed in enumerate(allowed_mask)]
    return result if any(result) else list(source_reference)
