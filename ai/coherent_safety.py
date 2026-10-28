"""Do not force futile helper loops when the final die cannot rescue a loss.

The old immediate shield stays intact elsewhere. For one closing regular die
or the last black die, enumerate reachable faces and native placements. Only
if even this optimistic bound cannot avoid immediate game termination may the
policy close the loss instead of spending coffee/rerolls pointlessly.
"""
from .actions import Action
from .belief_simulator import BeliefSimulator, fork_simulation, simulation_step
from .modules import MODULE_ACTIONS
from .safety_guard import safe_actions


IDS={action:i for i,action in enumerate(MODULE_ACTIONS)}


def closing_rescue_possible(airport,view,raw):
    state=view['modules_state']
    pending=state['pending']
    total=sum(bool(v) for v in view['own_dice'])+view['partner_remaining']
    regular=total==1 and not pending and not view['reroll'] and view['partner_remaining']==0
    bonus=total==0 and pending and pending['source']=='synchronisation' and pending['value'] is not None
    if not (regular or bonus):
        return None
    die=next(i for i,v in enumerate(view['own_dice']) if v) if regular else None
    original=view['own_dice'][die] if regular else pending['value']
    costs={face:abs(face-original) for face in range(1,7) if abs(face-original)<=view['coffee']}
    if regular and raw[IDS[Action('adaptation',die=die)]]:
        for face in range(1,7):
            cost=abs(face-(7-original))
            if cost<=view['coffee']:
                costs[face]=min(costs.get(face,99),cost)
    if regular and raw[IDS[Action('reroll_start')]]:
        costs={face:0 for face in range(1,7)}
    root=BeliefSimulator(airport,view).sample(0)
    # Optimistic face reachability intentionally ignores elapsed wall time.
    # This can retain a helper, never falsely prove a timed rescue impossible.
    root.game.zusatz.deadline=None
    for face,cost in costs.items():
        changed=fork_simulation(root)
        changed.game.cockpit.kaffeetassen-=cost
        if regular:
            changed.game._wuerfel_liste(view['role'])[die].augenzahl=face
        else:
            changed.game.zusatz.offen[0]['wuerfel'].augenzahl=face
        kind='place' if regular else 'bonus_place'
        for index,ok in enumerate(changed.action_mask()):
            action=MODULE_ACTIONS[index]
            if not ok or action.kind!=kind or regular and action.die!=die:
                continue
            branch=fork_simulation(changed)
            simulation_step(branch,index)
            if branch.game.status!='verloren':
                return True
    return False


def coherent_safe_actions(airport,view,raw):
    allowed,meta=safe_actions(airport,view,raw)
    placement=lambda action:action.kind in ('place','bonus_place')
    if meta['rejected'] and not any(ok and placement(action) for ok,action in zip(allowed,MODULE_ACTIONS)):
        rescue=closing_rescue_possible(airport,view,raw)
        if rescue is False:
            closing=[bool(ok and placement(action)) for ok,action in zip(raw,MODULE_ACTIONS)]
            if any(closing):
                return closing,{**meta,'fallback':True,'unavoidable_closing_loss':True,
                                'helper_rescue_optimistic_bound':False}
    return allowed,{**meta,'unavoidable_closing_loss':False}
