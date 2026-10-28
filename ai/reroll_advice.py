"""Prospective final-round single-die rerolls under the public hand model.

Enumerate all six fair replacement faces. These are counterfactual own hands,
never future real RNG values. Replanning is approximate and the partner prior
is IID; this is a model-based heuristic, not a calibrated win probability.
"""
from .actions import Action
from .contract_planner import IDS, landing_count_possible, plan_round
from .modules import MODULE_ACTIONS


def landing_reroll_values(view,*,beam=12,planner=plan_round,options=None,skip_certain=False):
    if (not view['last_round'] or view['modules_state']['pending'] or view['modules_state']['swap']
            or not landing_count_possible(view)):
        return {}
    # Keep realtime's scarce deadline for actual decisions. A small late hand
    # is cheap; a fresh four-die hand requires up to24 full beam searches.
    if 'realtime' in view['modules_state']['modules'] and sum(bool(v) for v in view['own_dice'])>2:
        return {}
    root={**view,'reroll':None}
    hypothetical=[True]*len(MODULE_ACTIONS)
    kwargs=dict(beam=beam,**(options or {}))

    def value(current):
        ranks=planner(current,hypothetical,**kwargs)
        return float(getattr(ranks,'primary_value',max(ranks.values(),default=0.) if ranks.primary_available else 0.))

    scores={0:value(root)}
    if skip_certain and scores[0]>=10000.:return scores
    for die,original in enumerate(root['own_dice']):
        if not original:continue
        total=0.
        for face in range(1,7):
            changed={**root,'own_dice':list(root['own_dice'])}
            changed['own_dice'][die]=face
            total+=value(changed)
        scores[1<<die]=total/6
    return scores


def reroll_selection(view,allowed,*,beam=12,planner=plan_round,options=None):
    scores=landing_reroll_values(view,beam=beam,planner=planner,options=options)
    eligible={bits:value for bits,value in scores.items() if allowed[IDS[Action('reroll_select',subset=bits)]]}
    if not eligible:return None,scores
    # Equal scores retain more actual dice, then the lower deterministic ID.
    best=max(eligible,key=lambda bits:(eligible[bits],-bits.bit_count(),-bits))
    return IDS[Action('reroll_select',subset=best)],scores


def worthwhile_landing_reroll(view,allowed,*,beam=12,minimum_gain=100.,planner=plan_round,options=None):
    if view['reroll'] or not allowed[IDS[Action('reroll_start')]]:
        return False,{}
    scores=landing_reroll_values(view,beam=beam,planner=planner,options=options,skip_certain=True)
    return bool(scores and max(scores.values())>scores[0]+minimum_gain),scores
