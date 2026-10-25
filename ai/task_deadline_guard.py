"""Separate necessary-count guard; no hidden hands, RNG or new terminal state.

Only when the optimistic public budget currently passes, remove placements
whose public SAME-ROUND consequence fails it. Future synchronization uncertainty
and already infeasible states abstain. Helpers and pending dialogs are retained.
Passing this bound does not prove face compatibility, sequencing or a win.
"""
import time

from .landing_task_budget import task_budget
from .modules import MODULE_ACTIONS
from .throttle import CpuBudget
from .wind_ice_advice import _after_placement,eligible


def preserve_task_budget(view,allowed,*,cpu_duty_cycle=1.):
    if len(allowed)!=len(MODULE_ACTIONS) or any(type(v) is not bool for v in allowed):
        raise ValueError('Require a schema3 Boolean action mask.')
    before=task_budget(view)
    meta=dict(eligible=False,before_budget=before,removed=[],removed_budgets={},fallback=False)
    if not eligible(view) or before['possible'] is not True or not any(allowed):
        return list(allowed),meta
    meta['eligible']=True
    budget,last=CpuBudget(cpu_duty_cycle),time.perf_counter()
    result=list(allowed)
    for index,(legal,action) in enumerate(zip(allowed,MODULE_ACTIONS)):
        if time.perf_counter()-last>=.02:
            budget.pause();last=time.perf_counter()
        if not legal or action.kind!='place':continue
        projected,_=_after_placement(view,action.die,action.slot,view['own_dice'][action.die],view['coffee'])
        after=task_budget(projected)
        if after['possible'] is False:
            result[index]=False
            meta['removed'].append(index)
            meta['removed_budgets'][str(index)]=after
    budget.pause()
    if not any(result):
        meta['fallback']=True
        return list(allowed),meta
    return result,meta
