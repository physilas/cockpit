"""Browser-portable profile 15; unchanged profile 13 on unaffected cases."""
from .actions import Action
from .ability_planner import IDS, plan_ability_round
from .coherent_advice import profile12_masks
from .coherent_safety import coherent_safe_actions
from .contract_planner import landing_count_possible
from .module_capacity import reserve_controls
from .public_contract import PublicContractAgent, public_contract_inputs, arbitrate_contract
from .safety_guard import safe_actions


def uses_ability_planning(view):
    state=view['modules_state']
    return 'wind' in state['modules'] or 'synchronisation' in state['cards']


def ability_inputs(airport, view, raw, *, beam=24):
    state = view['modules_state']
    if not uses_ability_planning(view):
        return public_contract_inputs(airport, view, raw, beam=beam)
    allowed, safety = coherent_safe_actions(airport, view, raw)
    allowed = reserve_controls(view, allowed)
    ranks = plan_ability_round(view, allowed, beam=beam)
    baseline_safe, _ = safe_actions(airport, view, allowed)
    baseline_mask, reference = profile12_masks(view, baseline_safe)
    best = max(ranks, key=ranks.get) if ranks else None
    forced = None
    reroll = IDS[Action('reroll_start')]
    if ranks:
        if (not ranks.primary_available and allowed[reroll] and not view['reroll']
                and not state['pending'] and not safety['unavoidable_closing_loss']
                and landing_count_possible(view)):
            forced = reroll
    elif not view['reroll'] and not state['pending'] and allowed[reroll]:
        forced = reroll
    plan = dict(version=1, baseline_mask=baseline_mask, scores={str(i):v for i,v in ranks.items()},
                best_action=best, forced_action=forced, tolerance=1., planning_mode='ability_'+ranks.mode)
    return allowed, reference, plan


class AbilityAgent:
    def __init__(self, airport, model, *, beam=24):
        from .agents import ModelAgent
        self.airport, self.agent, self.beam = airport, ModelAgent(model), beam
        self.last_report = {}
        self.fallback = PublicContractAgent(airport,model,beam=beam)

    def select(self, view, raw):
        if not uses_ability_planning(view):
            chosen=self.fallback.select(view,raw)
            self.last_report=self.fallback.last_report
            return chosen
        allowed, reference, plan = ability_inputs(self.airport, view, raw, beam=self.beam)
        baseline = self.agent.select(view, plan['baseline_mask'], reference_mask=reference)
        chosen = arbitrate_contract(baseline, allowed, plan)
        self.last_report = dict(baseline=baseline, chosen=chosen, planning_mode=plan['planning_mode'])
        return chosen
