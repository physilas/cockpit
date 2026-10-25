"""Separate fair-hand research phase; the earlier microplans stay unchanged.

Own plans are fixed before averaging over hypothetical partner hands. Each
partner hand uses distinct control dice and only the coffee LEFT after the
own macro and own remaining controls. This optimistic best-partner model is
not a forecast of the actual private hand or a proof of natural cooperation.
"""
import math
import time

from .actions import Action, ROLES
from .module_physics import predict_rudder, predict_thrust
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .public_hand_prior import fair_control_value
from .throttle import CpuBudget
from .wind_ice_advice import (ACTION_IDS, _after_placement, _capacity_score,
    _completion_options, _legal, eligible)


def radio_capacity(source, projected):
    """Public UPPER bound after reserving each role's unfilled controls.

    No face compatibility is promised and no task can reuse a control die.
    The unknown partner's radio follow-ups remain an optimistic approximation.
    """
    own = ROLES.index(source['role'])
    result = 0
    for index, role in enumerate(ROLES):
        remaining = sum(bool(face) for face in projected['own_dice']) if index == own else source['partner_remaining']
        controls = sum(projected['board'][slot] is None for slot in (index, index + 2))
        radios = sum(slot.target == 'funk' and slot.owner == role and projected['board'][number] is None
                     for number, slot in enumerate(MODULE_SLOTS[:20]))
        result += min(max(0, remaining - controls), radios)
    return result


def pair_scores(source, projected, own_r, own_t, *, cooperate=None):
    """Score explicitly HYPOTHETICAL complete control pairs with public physics.

    Scores of pairs contradicting a published die remain irrelevant sentinels;
    the fair-hand evaluator uses exactly that already published value. Current
    wind is advanced once if the source rudder pair has not resolved yet.
    """
    role = source['role']
    other = ROLES[1 - ROLES.index(role)]
    index = ROLES.index(other)
    r_public, t_public = source['board'][index], source['board'][index + 2]
    result = []
    physics = {**projected, 'board': source['board']}
    extra_ice = 4 - projected['modules_state']['ice_progress'] if projected['last_round'] and 'ice' in projected['modules_state']['modules'] else 0
    for r in range(1, 7):
        for t in range(1, 7):
            if cooperate is not None: cooperate()
            if r_public and r_public['value'] != r or t_public and t_public['value'] != t:
                result.append(-20_000.)
                continue
            rudder = predict_rudder(source, **{f'{role}_value': own_r, f'{other}_value': r})
            motion = predict_thrust(physics, **{f'{role}_value': own_t, f'{other}_value': t},
                rudder=rudder, additional_ice_pairs=extra_ice)
            score = -10_000. * rudder['stalled']
            score -= (3000. if source['last_round'] else 2.) * abs(rudder['attitude'])
            reason = motion['reason']
            if reason == 'uebers_ziel_hinaus': score -= 4000.
            elif reason in ('zu_schnell_gelandet', 'ruder_verbotene_stellung'): score -= 3000.
            elif reason == 'kollision':
                # Thrust is resolved at ROUND END. A public spare radio can
                # still clear current traffic before then; do not treat every
                # presently occupied cell as an already inevitable collision.
                cell = next(cell for cell in projected['track'] if cell['distance'] == source['distance'])
                pending = cell['planes']
                score -= 1200. * max(0, pending - radio_capacity(source, projected)) + 30. * pending
            if not source['last_round'] and not source['holding']:
                rounds = max(1, int(source['height'] // 1000))
                wanted = min(2, math.ceil(source['distance'] / rounds))
                move = motion['attempted_movement']
                score -= 30. * abs(move - wanted)
                score -= 1500. * max(0, source['distance'] - move - 2 * (rounds - 1))
            result.append(score)
    return tuple(result)


def prior_plans(view, allowed_mask, *, cpu_duty_cycle=1.):
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed_mask):
        raise ValueError('Expected a schema-3 Boolean allowed mask.')
    budget, checkpoint = CpuBudget(cpu_duty_cycle), time.perf_counter()
    if not eligible(view) or not any(allowed_mask):
        return {}

    def cooperate():
        nonlocal checkpoint
        now = time.perf_counter()
        if now - checkpoint >= .02:
            budget.pause(); checkpoint = time.perf_counter()

    own = ROLES.index(view['role'])
    other = 1 - own
    original_r, original_t = view['board'][own], view['board'][own + 2]
    partner_r, partner_t = view['board'][other], view['board'][other + 2]
    known = {'rudder': partner_r['value'] if partner_r else None,
             'thrust': partner_t['value'] if partner_t else None}
    ranked, matrices, expected_values = {}, {}, {}
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
                    cooperate()
                    if not _legal(view, die, slot_index, actual): continue
                    placement = ACTION_IDS[Action('place', die=die, slot=slot_index)]
                    first = flip_id if flip else ACTION_IDS[Action('coffee', die=die, delta=actual - face)] if cost else placement
                    if not allowed_mask[first]: continue
                    projected, reward = _after_placement(view, die, slot_index, actual, view['coffee'] - cost)
                    r = actual if slot.target == 'ruder' else original_r['value'] if original_r else 0
                    t = actual if slot.target == 'triebwerk' else original_t['value'] if original_t else 0
                    if r and partner_r is not None:
                        rudder = predict_rudder(view, **{f'{view["role"]}_value': r})
                        if rudder['stalled']: continue
                        # Only a just-planned CURRENT second rudder gives an
                        # exact Control-card coffee. Other future bonuses are
                        # deliberately not credited before their generation.
                        if slot.target == 'ruder' and original_r is None:
                            projected['coffee'] = predict_rudder({**view, 'coffee': projected['coffee']},
                                **{f'{view["role"]}_value': r})['coffee']
                    base = reward + _capacity_score(projected, r, t) - 3. * flip
                    missing = tuple(target for target, value in (('ruder', r), ('triebwerk', t)) if not value)
                    hand = tuple(sorted(value for value in projected['own_dice'] if value))
                    best = -20_000.
                    context = (projected['aero_blue'], projected['aero_orange'], projected['brakes'],
                        projected['modules_state']['ice_progress'], tuple(cell['planes'] for cell in projected['track']),
                        radio_capacity(view, projected))
                    for faces, spending in _completion_options(hand, missing, projected['coffee']):
                        cooperate()
                        assignment = dict(zip(missing, faces))
                        own_r, own_t = assignment.get('ruder', r), assignment.get('triebwerk', t)
                        key = context, own_r, own_t
                        if key not in matrices:
                            matrices[key] = pair_scores(view, projected, own_r, own_t, cooperate=cooperate)
                        left = projected['coffee'] - spending
                        expected_key = key, left
                        if expected_key not in expected_values:
                            expected_values[expected_key] = fair_control_value(matrices[key], view['partner_remaining'],
                                left, **known, cooperate=cooperate)
                        best = max(best, expected_values[expected_key])
                    ranked[first] = max(ranked.get(first, -math.inf), base + best)
    budget.pause()
    return ranked


def prior_reference(view, allowed_mask, source_reference, *, cpu_duty_cycle=1.):
    if (len(source_reference) != len(MODULE_ACTIONS)
            or any(type(flag) is not bool for flag in source_reference)
            or any(advised and not allowed_mask[index] for index, advised in enumerate(source_reference))):
        raise ValueError('Expected an engine-legal source reference.')
    ranked = prior_plans(view, allowed_mask, cpu_duty_cycle=cpu_duty_cycle)
    if not ranked:
        return list(source_reference)
    best = max(ranked.values())
    reroll = ACTION_IDS[Action('reroll_start')]
    if best < -500 and allowed_mask[reroll]:
        return [index == reroll for index in range(len(allowed_mask))]
    result = [bool(allowed and ranked.get(index, -math.inf) >= best - 2.) for index, allowed in enumerate(allowed_mask)]
    return result if any(result) else list(source_reference)
