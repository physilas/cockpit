"""Profile-12 public adaptation macros on top of profile-11 leak advice.

Adaptation turns one currently available own die to ``7-face`` once per person
per flight. A virtual hand is a planning input, never an engine copy or an
extra die. All engine-legal alternatives remain available to the policy.
"""
import math
import time

from .actions import ACTIONS, Action
from .leak_advice import leak_reference, make_leak_adjustment
from .modules import MODULE_ACTIONS
from .public_rules import legal_placement_in_view
from .tactics import plan_actions
from .throttle import CpuBudget


def virtual_first_mask(view):
    """Rebuild BASE121 first-step rules for the virtual hand's NEW faces.

    The public placement predicate includes occupancy, ownership, sequential
    upgrades, exact face requirements and mandatory-control reservations.
    Coffee uses exactly the current shared supply and the 1..6 face bound.
    No stale current-face mask, fictitious kerosene field or reroll is used.
    """
    result = []
    for action in ACTIONS:
        valid = action.kind == 'place' and legal_placement_in_view(view, action)
        if action.kind == 'coffee':
            face = view['own_dice'][action.die]
            valid = bool(face) and abs(action.delta) <= view['coffee'] and 1 <= face + action.delta <= 6
        result.append(bool(valid))
    return result


def _ordinary_reference(allowed, ranked):
    """Same profile-11 shortlist when there is no worthwhile adaptation macro."""
    best = max(ranked.values(), default=-math.inf)
    if not ranked:
        return list(allowed)
    result = [bool(legal and ranked.get(index, -math.inf) >= best - 4)
              for index, legal in enumerate(allowed)]
    reroll = MODULE_ACTIONS.index(Action('reroll_start'))
    if best < -100 and allowed[reroll]:
        result = [False] * len(allowed)
        result[reroll] = True
    return result if any(result) else list(allowed)


def leak_card_reference(view, allowed_mask, *, beam=24, cpu_duty_cycle=1.,
                        fuel_weight=3., card_cost=1.):
    """Jointly rank ordinary plans and one-flip macros as SOFT reference.

    The one-point card opportunity cost is half one retained coffee's planner
    value. A macro must strictly improve on the best ordinary plan after that
    cost: the four-point shortlist alone must not spend a flight-long card for
    a tied hand. Unknown partner faces retain the existing public v4 prior.

    Work is bounded deterministically: at most four distinct own faces, with
    beam <=24. Equal own faces share one evaluation. Cooperation pauses CPU
    use without skipping plans, so machine speed cannot change the reference.
    """
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed_mask):
        raise ValueError('Expected the schema-3 Boolean allowed mask.')
    if type(beam) is not int or not 1 <= beam <= 24:
        raise ValueError('Use a bounded public planning beam in [1,24].')
    if type(card_cost) not in (int, float) or not math.isfinite(card_cost) or not 0 < card_cost <= 4:
        raise ValueError('Use a positive card cost <=4.')
    original = list(allowed_mask)
    state = view['modules_state']
    modules = set(state['modules'])
    eligible = [(index, action) for index, action in enumerate(MODULE_ACTIONS)
                if original[index] and action.kind == 'adaptation']
    if (not any(original) or 'leak' not in modules or modules - {'leak', 'realtime'} or
            state['pending'] or state['swap'] or view['reroll'] or
            'adaptation' not in state['cards'] or not state['adaptation'].get(view['role']) or not eligible):
        return leak_reference(view, original, beam=beam, cpu_duty_cycle=cpu_duty_cycle,
                              fuel_weight=fuel_weight)
    adjustment = make_leak_adjustment(view, fuel_weight=fuel_weight)
    budget = CpuBudget(cpu_duty_cycle)
    checkpoint = time.perf_counter()

    def cooperate():
        nonlocal checkpoint
        now = time.perf_counter()
        if now - checkpoint >= .02:
            budget.pause()
            checkpoint = time.perf_counter()

    ordinary, _ = plan_actions(view, original[:len(ACTIONS)], beam=beam, version=4,
        cooperate=cooperate, thrust_score_adjustment=adjustment)
    fallback = _ordinary_reference(original, ordinary)
    best_ordinary = max(ordinary.values(), default=-math.inf)
    macros, by_face = {}, {}
    for index, action in eligible:
        face = view['own_dice'][action.die]
        if not face:
            continue
        if face not in by_face:
            changed = {**view, 'own_dice': list(view['own_dice'])}
            changed['own_dice'][action.die] = 7 - face
            cooperate()
            ranked, _ = plan_actions(changed, virtual_first_mask(changed), beam=beam, version=4,
                cooperate=cooperate, thrust_score_adjustment=adjustment)
            by_face[face] = max(ranked.values(), default=-math.inf) - card_cost
        quality = by_face[face]
        if math.isfinite(quality) and quality > best_ordinary:
            macros[index] = quality
    if not macros:
        return fallback
    ranked = {**ordinary, **macros}
    best = max(ranked.values())
    reference = [bool(legal and ranked.get(index, -math.inf) >= best - 4)
                 for index, legal in enumerate(original)]
    return reference if any(reference) else fallback
