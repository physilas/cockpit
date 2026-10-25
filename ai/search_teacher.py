"""Experimental late-round public search on top of an unchanged neural player.

The source controls early rounds, landings and rerolls. In the preceding two
rounds an own-hand search can rerank its moves using either the old independent
forecast or joint dice assignments. No engine, private partner hand or RNG is
available to select(). The separate joint-finish experiment also replans the
last own die, avoiding an automatic switch back to the network mid-plan.
The separate round-plain/round-risk experiments search every non-landing round,
without a future forecast; round-risk uses the existing shared control prior
and traffic capacity penalties (planner version 4). This player is not released.
"""
import time

from .agents import ModelAgent
from .joint_forecast import make_joint_forecast
from .tactics import plan_actions
from .throttle import CpuBudget


class SearchTeacher(ModelAgent):
    def __init__(self, model, *, mode='joint', beam=64, cpu_duty_cycle=1.):
        super().__init__(model)
        if mode not in ('legacy', 'joint', 'joint-finish', 'round-plain', 'round-risk') or not 1 <= beam <= 128:
            raise ValueError('Expected an explicit forecast and a bounded search beam.')
        self.mode, self.beam = mode, beam
        CpuBudget(cpu_duty_cycle)  # Validate before starting an experimental search.
        self.cpu_duty_cycle = cpu_duty_cycle
        self.considered = self.overrides = 0

    def select(self, view, mask, *, reference_mask=None):
        baseline = super().select(view, mask, reference_mask=reference_mask)
        minimum_dice = 1 if self.mode == 'joint-finish' else 2
        round_search = self.mode in ('round-plain', 'round-risk')
        if (view['reroll'] or view['height'] <= 0 or not round_search and view['height'] > 2000
                or sum(bool(d) for d in view['own_dice']) < minimum_dice):
            return baseline
        modules = view.get('modules_state', {})
        if set(modules.get('modules', [])) - {'kerosene'} or modules.get('cards'):
            raise ValueError('This experimental teacher supports base/kerosene without cards.')
        budget = CpuBudget(self.cpu_duty_cycle)
        last = time.perf_counter()
        def cooperate():
            nonlocal last
            if time.perf_counter() - last >= .02:
                budget.pause()
                last = time.perf_counter()
        planned = {**view, '_horizon': not round_search}
        if view.get('fuel', {}).get('present'):
            # plan_actions expects the shared fuel slot appended to its board.
            planned['board'] = view['board'] + ([{'value': 1, 'owner': 'pilot'}]
                                               if view['fuel']['occupied'] else [None])
            planned['_fuel_profile'] = 9
        ranks, _ = plan_actions(planned, mask, version=4 if self.mode == 'round-risk' else 3, beam=self.beam,
                                forecast_factory=(lambda v: make_joint_forecast(v, cooperate=cooperate))
                                if self.mode in ('joint', 'joint-finish') else None, cooperate=cooperate)
        ranks = {i: score for i, score in ranks.items() if mask[i]}
        if not ranks:
            return baseline
        self.considered += 1
        best = max(ranks, key=ranks.get)
        # Retain the learned choice when search scores cannot distinguish it.
        chosen = baseline if ranks.get(baseline, float('-inf')) >= ranks[best] - .25 else best
        self.overrides += chosen != baseline
        return chosen
