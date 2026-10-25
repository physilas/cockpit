"""Profile-11 soft leak advice with no fictitious fuel field or extra die.

The complete own-hand planner retains its public unknown-partner prior. This
adds exact fuel consequences for each hypothetical thrust pair; it is not a
claim of exact partner inference or a qualified route/card policy.
"""
from functools import lru_cache
import math
import time

from .actions import ACTIONS, Action
from .module_physics import fuel_budget
from .modules import MODULE_ACTIONS
from .tactics import plan_actions
from .throttle import CpuBudget


def make_leak_adjustment(view, *, fuel_weight=3., shortfall_penalty=1000.):
    """Cached public pair cost, plus necessary future-survival shortfall.

    Leak is charged once, when the second thrust die is placed. Publicly
    completed pairs already paid and incur no second consumption penalty.
    One fuel per future round is only a necessary lower bound, not a promise.
    """
    if 'leak' not in view['modules_state']['modules'] or view['fuel']['present']:
        raise ValueError('Leak advice requires leak fuel, with no kerosene placement field.')
    if (not math.isfinite(fuel_weight) or not 0 <= fuel_weight <= 20 or
            not math.isfinite(shortfall_penalty) or not 100 <= shortfall_penalty <= 10000):
        raise ValueError('Use bounded public fuel and shortfall weights.')
    role = view['role']
    # Keep the at-most36 cached pair scores tied to one immutable PUBLIC
    # decision snapshot, even if a caller later reuses/mutates its view dict.
    fuel_view = {'height': view['height'], 'last_round': view['last_round'],
                 'fuel': dict(view['fuel']),
                 'board': [None if field is None else dict(field) for field in view['board'][:4]],
                 'modules_state': {'modules': list(view['modules_state']['modules'])}}

    @lru_cache(maxsize=36)
    def adjustment(own_thrust, partner_thrust):
        pilot, kopilot = ((own_thrust, partner_thrust) if role == 'pilot'
                         else (partner_thrust, own_thrust))
        budget = fuel_budget(fuel_view, pilot, kopilot)
        return (-fuel_weight * budget['current_cost']
                - shortfall_penalty * max(0, -budget['survival_margin']))

    return adjustment


def leak_reference(view, allowed_mask, *, beam=24, cpu_duty_cycle=1., fuel_weight=3.):
    """Return advice inside allowed actions, preserving all legal alternatives.

    Mixed wind/ice/intern physics, pending black dice, swaps and reroll choices
    abstain. Those retain profile10 behavior. Cards remain engine-legal but are
    not yet included as hypothetical helper steps in the ordinary-hand beam.
    """
    if len(allowed_mask) != len(MODULE_ACTIONS) or any(type(value) is not bool for value in allowed_mask):
        raise ValueError('Expected the schema-3 Boolean allowed mask.')
    if type(beam) is not int or not 1 <= beam <= 128:
        raise ValueError('Use a bounded public planning beam in [1,128].')
    original = list(allowed_mask)
    state = view['modules_state']
    modules = set(state['modules'])
    if (not any(original) or 'leak' not in modules or modules - {'leak', 'realtime'}
            or state['pending'] or state['swap'] or view['reroll']):
        return original
    adjustment = make_leak_adjustment(view, fuel_weight=fuel_weight)
    budget, checkpoint = CpuBudget(cpu_duty_cycle), time.perf_counter()

    def cooperate():
        nonlocal checkpoint
        if time.perf_counter()-checkpoint >= .02:
            budget.pause()
            checkpoint = time.perf_counter()

    # Leak deliberately uses the BASE121 actions. Marking fuel.present would
    # invent an illegal kerosene field and spend an extra shared task die.
    ranked, _ = plan_actions(view, original[:len(ACTIONS)], beam=beam, version=4,
        cooperate=cooperate, thrust_score_adjustment=adjustment)
    best = max(ranked.values(), default=-math.inf)
    if not ranked:
        return original
    result = [bool(allowed and ranked.get(index, -math.inf) >= best-4)
              for index, allowed in enumerate(original)]
    if best < -100:
        reroll = MODULE_ACTIONS.index(Action('reroll_start'))
        if original[reroll]:
            result = [False]*len(original)
            result[reroll] = True
    return result if any(result) else original
