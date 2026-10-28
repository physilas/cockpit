"""Torch-free public contract advice shared by research and future browser use.

This is a new policy, separate from existing released profile-12 behavior.
The immediate loss shield/control reservation are hard; strategic contract
recommendations are a reference prior. No hidden game instance is accepted.
"""
import math

from .actions import Action
from .contract_planner import plan_round, landing_count_possible, IDS
from .module_capacity import reserve_controls
from .module_guidance import module_guidance
from .modules import MODULE_ACTIONS
from .coherent_safety import coherent_safe_actions


def contract_masks(airport, view, raw, *, beam=24, margin=1.):
    if not math.isfinite(margin) or margin<0:
        raise ValueError('Contract margin must be finite and nonnegative.')
    allowed, safety = coherent_safe_actions(airport, view, raw)
    allowed = reserve_controls(view, allowed)
    if any(ok and a.kind=='swap_choose' for ok,a in zip(allowed,MODULE_ACTIONS)):
        allowed = [bool(ok and a.kind!='swap_cancel') for ok,a in zip(allowed,MODULE_ACTIONS)]
    if not any(allowed):
        return allowed,list(allowed),dict(safety=safety,ranked=0)
    ranked = plan_round(view,allowed,beam=beam)
    reference = [False]*len(allowed)
    reroll = IDS[Action('reroll_start')]
    if ranked:
        best=max(ranked.values())
        if (ranked.primary_available or not allowed[reroll] or not landing_count_possible(view)
                or safety['unavoidable_closing_loss']):
            reference=[bool(ok and ranked.get(i,-math.inf)>=best-margin) for i,ok in enumerate(allowed)]
        elif allowed[reroll] and not view['reroll'] and not view['modules_state']['pending']:
            reference[reroll]=True
    elif allowed[reroll] and not view['reroll'] and not view['modules_state']['pending']:
        reference[reroll]=True
    if not any(reference):
        _,reference=module_guidance(view,allowed)
        reference=[bool(ok and preferred) for ok,preferred in zip(allowed,reference)]
        if not any(reference):
            reference=list(allowed)
    return allowed,reference,dict(safety=safety,ranked=len(ranked),scores=ranked,
                                  objective='public_static_round_assignment',approximate=True)
