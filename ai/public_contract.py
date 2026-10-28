"""Exact public plan/blueprint arbitration, portable to browser inference.

The network resolves blueprint preferences; the public planner overrides it
only according to the same explicit rule as ContractAgent. No tensor library
is imported by the input/arbitration functions.
"""
import math

from .actions import Action
from .coherent_advice import profile12_masks
from .coherent_safety import coherent_safe_actions
from .contract_planner import IDS,landing_count_possible,plan_round
from .module_capacity import reserve_controls
from .safety_guard import safe_actions


def public_contract_inputs(airport,view,raw,*,beam=24):
    allowed,safety=coherent_safe_actions(airport,view,raw)
    allowed=reserve_controls(view,allowed)
    ranks=plan_round(view,allowed,beam=beam)
    # Exact old ShieldedBlueprint boundary, including its no-alternative
    # fallback. The outer coherent shield already handles futile last dice.
    baseline_safe,_=safe_actions(airport,view,allowed)
    baseline_mask,reference=profile12_masks(view,baseline_safe)
    best=max(ranks,key=ranks.get) if ranks else None
    forced=None
    reroll=IDS[Action('reroll_start')]
    if ranks:
        if (not ranks.primary_available and allowed[reroll] and not view['reroll']
                and not view['modules_state']['pending'] and not safety['unavoidable_closing_loss']
                and landing_count_possible(view)):
            forced=reroll
    elif not view['reroll'] and not view['modules_state']['pending'] and allowed[reroll]:
        forced=reroll
    plan=dict(version=1,baseline_mask=baseline_mask,scores={str(i):v for i,v in ranks.items()},
              best_action=best,forced_action=forced,tolerance=1.,planning_mode=ranks.mode)
    return allowed,reference,plan


def arbitrate_contract(baseline,allowed,plan):
    if type(baseline) is not int or not 0<=baseline<len(allowed) or not allowed[baseline]:
        raise ValueError('The blueprint must choose an engine-legal action.')
    chosen=baseline
    best=plan['best_action']
    scores=plan['scores']
    if best is not None and scores.get(str(baseline),-math.inf)<scores[str(best)]-plan['tolerance']:
        chosen=best
    if plan['forced_action'] is not None:chosen=plan['forced_action']
    if type(chosen) is not int or not 0<=chosen<len(allowed) or not allowed[chosen]:
        raise ValueError('The public plan selected outside the engine mask.')
    return chosen


class PublicContractAgent:
    def __init__(self,airport,model,*,beam=24):
        from .agents import ModelAgent
        self.airport,self.agent,self.beam=airport,ModelAgent(model),beam
        self.last_report={}

    def select(self,view,raw):
        allowed,reference,plan=public_contract_inputs(self.airport,view,raw,beam=self.beam)
        baseline=self.agent.select(view,plan['baseline_mask'],reference_mask=reference)
        chosen=arbitrate_contract(baseline,allowed,plan)
        self.last_report=dict(baseline=baseline,chosen=chosen,ranks=plan['scores'],planning_mode=plan['planning_mode'])
        return chosen
