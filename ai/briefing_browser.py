"""Additive, Torch-free briefing adapter for every existing crew/schema."""
import json
from backend import bridge
from .ability_browser import decision as legacy_decision
from .briefing import suggest, start_round, validate_plan, policy_fingerprint
from .briefing_planner import plan_briefed_round
from .actions import ACTIONS
from .fuel import FUEL_ACTIONS
from .modules import ModuleEnv, MODULE_ACTIONS
from .coherent_safety import coherent_safe_actions
from .module_capacity import reserve_controls


def decision(role=None, reroll_json='null', steps=0, max_steps=256, assistance_version=0, schema_version=1, plan_json='null'):
    base = legacy_decision(role,reroll_json,steps,max_steps,assistance_version,schema_version)
    plan = json.loads(plan_json)
    if plan is None:
        return base
    plan = validate_plan(plan,bridge.zustand())
    env = ModuleEnv(max_steps=max_steps,assistance_version=0)
    env.game, env.steps, env.reroll = bridge._spiel, steps, json.loads(reroll_json)
    view = {**env.view(), '_briefing':plan}
    actions = {1:ACTIONS,2:FUEL_ACTIONS,3:MODULE_ACTIONS}[schema_version]
    module_ids = {a:i for i,a in enumerate(MODULE_ACTIONS)}
    ids = [module_ids[a] for a in actions]
    mask = [False]*len(MODULE_ACTIONS)
    for i,allowed in zip(ids,base['action_mask']):mask[i]=allowed
    safe,_ = coherent_safe_actions(bridge._spiel.landung._flughafen_code,view,mask)
    safe = reserve_controls(view,safe)
    if not any(safe):
        return {**base,'round_plan':plan,'communication_policy':'briefing-v1','communication_sha256':policy_fingerprint()}
    ranks = plan_briefed_round(view,safe)
    if not ranks:
        return {**base,'round_plan':plan,'communication_policy':'briefing-v1','communication_sha256':policy_fingerprint()}
    allowed = [safe[i] for i in ids]
    baseline = base.get('public_plan',{}).get('baseline_mask',base['action_mask'])
    baseline = [a and b for a,b in zip(baseline,allowed)]
    if not any(baseline):baseline=allowed
    scores = {str(i):ranks[module_id] for i,module_id in enumerate(ids) if module_id in ranks and allowed[i]}
    best = max(scores,key=scores.get) if scores else None
    forced = base.get('public_plan',{}).get('forced_action') if not ranks.primary_available else None
    if forced is not None and not allowed[forced]:forced=None
    return {**base,'action_mask':allowed,'round_plan':plan,'communication_policy':'briefing-v1','communication_sha256':policy_fingerprint(),
            'public_plan':dict(version=1,baseline_mask=baseline,scores=scores,best_action=int(best) if best is not None else None,
                forced_action=forced,tolerance=1.,planning_mode='briefing_v1_'+ranks.mode)}
