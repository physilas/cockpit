"""Research-only union of source advice and public risk proposals.

The acting network keeps its original profile-9 action mask and reference
advice. Only the search teacher may use extra, engine-legal recommendations.
No released assistance profile or checkpoint is changed by this experiment.
"""
import time

from .actions import ACTIONS
from .fuel import fuel_capacity_mask
from .modules import ModuleEnv
from .tactics import capacity_mask, plan_actions
from .throttle import CpuBudget


def risk_proposals(view, legal_mask, *, beam=64, cpu_duty_cycle=1.):
    """A small current-round shortlist from a permitted view and rule mask.

    Planner version 4 couples unknown partner controls and coffee, but remains
    an approximate partner policy. This does not assert a guaranteed win.
    """
    if view['reroll'] or view['height'] <= 0 or not any(view['own_dice']):
        return []
    modules = view.get('modules_state', {})
    if set(modules.get('modules', [])) - {'kerosene'} or modules.get('cards'):
        raise ValueError('Open risk search currently supports base/kerosene without cards.')
    mask = capacity_mask(view, legal_mask[:len(ACTIONS)], include_traffic=True) + list(legal_mask[len(ACTIONS):125])
    if view.get('fuel', {}).get('present'):
        mask = fuel_capacity_mask(view, mask)
    planned = {**view, '_horizon': False}
    if view.get('fuel', {}).get('present'):
        planned['board'] = view['board'] + ([{'value': 1, 'owner': 'pilot'}]
                                           if view['fuel']['occupied'] else [None])
        planned['_fuel_profile'] = 9
    budget, last = CpuBudget(cpu_duty_cycle), time.perf_counter()
    def cooperate():
        nonlocal last
        if time.perf_counter() - last >= .02:
            budget.pause()
            last = time.perf_counter()
    ranks, _ = plan_actions(planned, mask, version=4, beam=beam, cooperate=cooperate)
    best = max(ranks.values(), default=-10000)
    if best < -100:
        # A known poor placement must not displace the source's rescue reroll.
        return []
    return [i for i, score in ranks.items() if legal_mask[i] and score >= best - .25]


class OpenRiskEnv(ModuleEnv):
    """Expose proposals to the teacher while preserving the source's input."""
    def __init__(self, *args, proposal_beam=64, cpu_duty_cycle=1., **kwargs):
        if kwargs.get('assistance_version') != 9:
            raise ValueError('This research environment requires source assistance 9.')
        self.proposal_beam = proposal_beam
        CpuBudget(cpu_duty_cycle)
        self.cpu_duty_cycle = cpu_duty_cycle
        self._source_mask = None
        super().__init__(*args, **kwargs)

    def _assist(self, mask):
        source = super()._assist(mask)
        self._source_mask = list(source)
        if self.current_role not in self.assisted_roles:
            return source
        result = list(source)
        for i in risk_proposals(self.view(), mask, beam=self.proposal_beam, cpu_duty_cycle=self.cpu_duty_cycle):
            result[i] = True
        return result

    def info(self):
        info = super().info()
        info['source_action_mask'] = list(self._source_mask) if any(info['action_mask']) else list(info['action_mask'])
        return info
