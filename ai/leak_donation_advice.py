"""Isolated public working-together donations; not wired into a game profile.

A donor with both controls filled can give a known safe rudder face to a
partner with exactly one die and only its rudder missing. The partner's old
face is never read or assumed: the returned die must remain usable on a free
concentration field. This narrow safety proposal is not a route-win claim or
a proof that initiating every such exchange improves the unknown old hand.
"""
import math

from .actions import Action, ROLES, SLOTS
from .leak_card_advice import leak_card_reference
from .module_physics import predict_rudder, predict_thrust
from .modules import MODULE_ACTIONS
from .public_rules import legal_placement_in_view
from .throttle import CpuBudget


def _scope(view):
    state = view['modules_state']
    modules = set(state['modules'])
    return (bool('leak' in modules) and not modules - {'leak', 'realtime'}
            and 'working-together' in state['cards'] and not state['pending']
            and not view['reroll'] and not view['fuel']['present'])


def _controls(role):
    index = ROLES.index(role)
    return index, index + 2


def _free_concentration(view):
    return any(slot.target == 'konzentration' and view['board'][index] is None
               for index, slot in enumerate(SLOTS))


def _required_targets(view):
    """Persistent own tasks; only the first braking activation is necessary."""
    result = []
    for index, slot in enumerate(SLOTS):
        if slot.owner != view['role']:
            continue
        if (slot.target == 'fahrwerk' and not view['gear'][slot.index]
                or slot.target == 'landeklappe' and not view['flaps'][slot.index]
                or slot.target == 'bremse' and view['brakes'] < 2
                and not view['brake_progress'][slot.index]):
            result.append(index)
    # Only the earliest unactivated brake is a required next task, rather than
    # counting all three future brake levels as mandatory landing work.
    brake = [index for index in result if SLOTS[index].target == 'bremse']
    if brake:
        result = [index for index in result if SLOTS[index].target != 'bremse' or index == brake[0]]
    return result


def donation_candidates(view):
    """Return safe known own-die gifts, using only own/public information.

    The unknown return contributes zero known task capacity. Future rounds
    contribute only their optimistic two ordinary optional placements per
    role; this is a necessary capacity check, not a feasibility guarantee.
    Sole known faces for currently legal required own upgrades are protected.
    """
    if not _scope(view) or view['role'] not in ROLES:
        return {}
    donor = view['role']
    recipient = ROLES[1 - ROLES.index(donor)]
    own_rudder, own_thrust = _controls(donor)
    other_rudder, other_thrust = _controls(recipient)
    board = view['board']
    if (type(view['partner_remaining']) is not int or view['partner_remaining'] != 1
            or board[own_rudder] is None or board[own_thrust] is None
            or board[other_rudder] is not None or board[other_thrust] is None
            or not _free_concentration(view)):
        return {}
    available = [index for index, face in enumerate(view['own_dice']) if face]
    if not available:
        return {}
    required = _required_targets(view)
    future = 0 if view['last_round'] else max(0, int(view['height'] // 1000))
    if len(required) > len(available) - 1 + 2 * future:
        return {}
    protected = set()
    for slot in required:
        usable = [index for index in available
                  if legal_placement_in_view(view, Action('place', die=index, slot=slot))]
        if len(usable) == 1:
            protected.add(usable[0])
    result = {}
    by_face = {}
    for index in available:
        if index in protected:
            continue
        face = view['own_dice'][index]
        if face not in by_face:
            rudder = predict_rudder(view, **{f'{recipient}_value': face})
            thrust = predict_thrust(view, rudder=rudder)
            safe = (not rudder['stalled'] and thrust['physics_safe']
                    and (not view['last_round'] or rudder['attitude'] == 0))
            by_face[face] = (rudder, thrust, safe)
        rudder, thrust, safe = by_face[face]
        if safe:
            result[index] = {'face': face, 'donor': donor, 'recipient': recipient,
                'attitude': rudder['attitude'], 'movement': thrust['attempted_movement'],
                'coffee_gain': rudder['coffee_gain'],
                'rank': (-abs(rudder['attitude']), rudder['coffee_gain'])}
    return result


def _sole_receiver_choice(view, allowed):
    """A receiver with one own die has no face-selection decision to optimize."""
    if not view['modules_state']['swap'] or not _scope(view) or not _free_concentration(view):
        return None
    role = view['role']
    own_rudder, own_thrust = _controls(role)
    other_rudder, other_thrust = _controls(ROLES[1 - ROLES.index(role)])
    board = view['board']
    available = [index for index, face in enumerate(view['own_dice']) if face]
    if (len(available) != 1 or board[own_rudder] is not None or board[own_thrust] is None
            or board[other_rudder] is None or board[other_thrust] is None):
        return None
    action = MODULE_ACTIONS.index(Action('swap_choose', die=available[0]))
    return action if allowed[action] else None


def leak_donation_reference(view, allowed_mask, *, beam=24, cpu_duty_cycle=1.,
                            fuel_weight=3., card_cost=1.):
    """Soft start/choice advice for the narrow donation; exact profile12 fallback.

    All candidates receive fixed work independent of elapsed time. Pacing only
    sleeps, and never changes a gift, legality mask or public reference result.
    This helper edits neither its input view nor the caller's allowed mask.
    """
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed_mask):
        raise ValueError('Expected the schema-3 Boolean allowed mask.')
    if type(beam) is not int or not 1 <= beam <= 24:
        raise ValueError('Use a bounded public planning beam in [1,24].')
    if type(card_cost) not in (int, float) or not math.isfinite(card_cost) or not 0 < card_cost <= 4:
        raise ValueError('Use a positive card cost <=4.')
    budget = CpuBudget(cpu_duty_cycle)
    allowed = list(allowed_mask)

    def fallback():
        return leak_card_reference(view, allowed, beam=beam, cpu_duty_cycle=cpu_duty_cycle,
                                   fuel_weight=fuel_weight, card_cost=card_cost)

    if not any(allowed) or not _scope(view):
        return fallback()
    receiver = _sole_receiver_choice(view, allowed)
    if receiver is not None:
        result = [False] * len(allowed)
        result[receiver] = True
        budget.pause()
        return result
    gifts = donation_candidates(view)
    state = view['modules_state']
    if state['swap']:
        choices = {MODULE_ACTIONS.index(Action('swap_choose', die=index)): row
                   for index, row in gifts.items()
                   if allowed[MODULE_ACTIONS.index(Action('swap_choose', die=index))]}
        if choices:
            best = max(row['rank'] for row in choices.values())
            result = [index in choices and choices[index]['rank'] == best for index in range(len(allowed))]
            budget.pause()
            return result
    else:
        start = MODULE_ACTIONS.index(Action('swap_start'))
        if state['swap_available'] and allowed[start] and gifts:
            result = [False] * len(allowed)
            result[start] = True
            budget.pause()
            return result
    return fallback()
