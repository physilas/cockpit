"""Versioned execution for new accepted Crew-6 round strategies."""
import json
import hashlib
from functools import lru_cache
from pathlib import Path
from backend import bridge
from .ability_browser import decision as legacy_decision
from .briefing import suggest, start_round, validate_plan, policy_fingerprint
from .briefing_planner_v2 import plan_briefed_round
from .actions import ACTIONS
from .fuel import FUEL_ACTIONS
from .modules import ModuleEnv, MODULE_ACTIONS
from .coherent_safety import coherent_safe_actions
from .module_capacity import reserve_controls


@lru_cache(maxsize=1)
def execution_fingerprint():
    root=Path(__file__).resolve().parents[1]
    digest=hashlib.sha256(('briefing-v2:'+policy_fingerprint()).encode())
    for name in ('ai/briefing_planner_v2.py','ai/briefing_browser_v2.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


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
        return {**base,'round_plan':plan,'communication_policy':'briefing-v2','communication_sha256':execution_fingerprint()}
    ranks = plan_briefed_round(view,safe)
    if not ranks:
        return {**base,'round_plan':plan,'communication_policy':'briefing-v2','communication_sha256':execution_fingerprint()}
    allowed = [safe[i] for i in ids]
    baseline = base.get('public_plan',{}).get('baseline_mask',base['action_mask'])
    baseline = [a and b for a,b in zip(baseline,allowed)]
    if not any(baseline):baseline=allowed
    if base.get('public_plan',{}).get('planning_mode')=='await_public_partner_control':
        # Keep the established opening convention until the partner exposes a
        # public control. A committed engine that makes the agreed distance
        # impossible must still be excluded by the complete-hand feasibility.
        compatible=[bool(ok and ranks.primary_by_action.get(module_id,0.)>0)
                    for ok,module_id in zip(baseline,ids)]
        if any(compatible):baseline=compatible
        else:
            feasible=[bool(ok and ranks.primary_by_action.get(module_id,0.)>0) for ok,module_id in zip(allowed,ids)]
            if any(feasible):baseline=feasible
        return {**base,'action_mask':allowed,'round_plan':plan,
                'communication_policy':'briefing-v2','communication_sha256':execution_fingerprint(),
                'public_plan':dict(version=1,baseline_mask=baseline,scores={},best_action=None,
                    forced_action=None,tolerance=1.,planning_mode='briefing_v2_await_public_partner_control')}
    scores = {str(i):ranks[module_id] for i,module_id in enumerate(ids) if module_id in ranks and allowed[i]}
    best = max(scores,key=scores.get) if scores else None
    forced = base.get('public_plan',{}).get('forced_action') if not ranks.primary_available else None
    if forced is not None and not allowed[forced]:forced=None
    return {**base,'action_mask':allowed,'round_plan':plan,'communication_policy':'briefing-v2','communication_sha256':execution_fingerprint(),
            'public_plan':dict(version=1,baseline_mask=baseline,scores=scores,best_action=int(best) if best is not None else None,
                forced_action=forced,tolerance=1.,planning_mode='briefing_v2_'+ranks.mode)}
