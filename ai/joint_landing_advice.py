"""New static final-round research: all mandatory tasks share control resources.

This is a fair-hand assignment score, NOT a full sequential engine win proof.
Unknown partner coffee generation/adaptation and future black dice are omitted.
The current macro can generate exact coffee; no future resource is invented.
"""
from itertools import product
import math
import time

from .actions import Action,ROLES
from .joint_landing_prior import fair_task_value,own_options
from .module_physics import predict_rudder,predict_thrust
from .modules import MODULE_ACTIONS,MODULE_SLOTS
from .throttle import CpuBudget
from .wind_ice_advice import ACTION_IDS,_after_placement,_legal,eligible as wind_ice_eligible


GEAR=((1,2),(3,4),(5,6))
FLAPS=((1,2),(2,3),(4,5),(5,6))


def eligible(view):
    return bool(wind_ice_eligible(view) and view['last_round'] and view['height']==view['distance']==0)


def task_allocations(view):
    """Role obligations including shared lower ice cells and actual radio faces.

    Ownership of each future shared task is chosen once before partner-hand
    expectation. Radio has limited public slots; at distance0 only face1 can
    clear planes, and planes elsewhere are already unreachable this round.
    Each optional regular-brake level reserves its actual2/4/6 activation dice.
    """
    if any(cell['planes'] for cell in view['track'] if cell['distance']!=0):return ()
    counts={view['role']:sum(bool(v) for v in view['own_dice']),
            ROLES[1-ROLES.index(view['role'])]:view['partner_remaining']}
    base=[tuple(GEAR[i] for i,done in enumerate(view['gear']) if not done),
          tuple(FLAPS[i] for i,done in enumerate(view['flaps']) if not done)]
    shared=[]
    ice='ice' in view['modules_state']['modules']
    if ice:
        progress=view['modules_state']['ice_progress']
        fields=view['modules_state']['extra_fields'][2:]
        for pair in range(progress,4):
            if fields[pair*2] is None:base[0]+=((2+pair,),)
            if fields[pair*2+1] is None:shared.append((2+pair,))
    planes=next(cell['planes'] for cell in view['track'] if cell['distance']==0)
    radios=[sum(slot.target=='funk' and slot.owner==r and view['board'][i] is None
                for i,slot in enumerate(MODULE_SLOTS[:20])) for r in ROLES]
    controls=[sum(view['board'][i] is None for i in (j,j+2)) for j in range(2)]
    done_brakes=sum(view['brake_progress'])
    result=set()
    for owners in product((0,1),repeat=len(shared)):
        owned=[base[j]+tuple(t for t,owner in zip(shared,owners) if owner==j) for j in range(2)]
        for pilot_radios in range(planes+1):
            copilot_radios=planes-pilot_radios
            if pilot_radios>radios[0] or copilot_radios>radios[1]:continue
            for extra in range(1 if ice else 4-done_brakes):
                p=owned[0]+((1,),)*pilot_radios+tuple(((2,4,6)[i],) for i in range(done_brakes,done_brakes+extra))
                c=owned[1]+((1,),)*copilot_radios
                if len(p)+controls[0]>counts['pilot'] or len(c)+controls[1]>counts['kopilot']:continue
                result.add((tuple(sorted(p)),tuple(sorted(c)),extra))
    return tuple(sorted(result))


def physical_pairs(source,projected,own_r,own_t,extra_brakes):
    """Static terminal physics AFTER every reserved task is completed."""
    role=source['role'];other=ROLES[1-ROLES.index(role)]
    other_i=ROLES.index(other)
    r_known,t_known=source['board'][other_i],source['board'][other_i+2]
    result=[]
    physics={**projected,'board':source['board']}
    ice_extra=4-projected['modules_state']['ice_progress'] if 'ice' in projected['modules_state']['modules'] else 0
    for r in range(1,7):
        for t in range(1,7):
            if r_known and r_known['value']!=r or t_known and t_known['value']!=t:
                result.append(False);continue
            rudder=predict_rudder(source,**{f'{role}_value':own_r,f'{other}_value':r})
            if rudder['stalled'] or rudder['attitude']!=0:
                result.append(False);continue
            motion=predict_thrust(physics,**{f'{role}_value':own_t,f'{other}_value':t},rudder=rudder,
                additional_ice_pairs=ice_extra,additional_brakes=extra_brakes)
            result.append(not bool(motion['reason']))
    return tuple(result)


def joint_landing_plans(view,allowed,*,cpu_duty_cycle=1.):
    if len(allowed)!=len(MODULE_ACTIONS) or any(type(flag) is not bool for flag in allowed):
        raise ValueError('Require a schema3 Boolean allowed mask.')
    budget,checkpoint=CpuBudget(cpu_duty_cycle),time.perf_counter()
    if not eligible(view) or not any(allowed):return {}
    def cooperate():
        nonlocal checkpoint
        if time.perf_counter()-checkpoint>=.02:
            budget.pause();checkpoint=time.perf_counter()
    own=ROLES.index(view['role']);other=1-own
    partner_r,partner_t=view['board'][other],view['board'][other+2]
    known=dict(rudder=partner_r['value'] if partner_r else None,thrust=partner_t['value'] if partner_t else None)
    ranks,contexts={},{ }
    for die,face in enumerate(view['own_dice']):
        if not face:continue
        flip_id=ACTION_IDS[Action('adaptation',die=die)]
        for flip in (False,True):
            if flip and not allowed[flip_id]:continue
            start=7-face if flip else face
            for actual in range(1,7):
                cost=abs(actual-start)
                if cost>view['coffee']:continue
                for slot_index,slot in enumerate(MODULE_SLOTS):
                    cooperate()
                    if not _legal(view,die,slot_index,actual):continue
                    first=flip_id if flip else ACTION_IDS[Action('coffee',die=die,delta=actual-face)] if cost else ACTION_IDS[Action('place',die=die,slot=slot_index)]
                    if not allowed[first]:continue
                    projected,_=_after_placement(view,die,slot_index,actual,view['coffee']-cost)
                    if slot.target=='ruder' and partner_r:
                        rudder=predict_rudder(view,**{f'{view["role"]}_value':actual})
                        if rudder['stalled']:continue
                        projected['coffee']=predict_rudder({**view,'coffee':projected['coffee']},
                            **{f'{view["role"]}_value':actual})['coffee']
                    r,t=projected['board'][own],projected['board'][own+2]
                    hand=tuple(sorted(v for v in projected['own_dice'] if v))
                    allocations=task_allocations(projected)
                    # Context contains every projected field affecting the
                    # static obligations/physics; own slot indices are inert
                    # once their values and remaining multiset are captured.
                    key=(hand,r['value'] if r else None,t['value'] if t else None,projected['coffee'],
                         projected['brakes'],projected['modules_state']['ice_progress'],allocations)
                    if key not in contexts:
                        best=0.
                        for p_tasks,c_tasks,brakes in allocations:
                            own_tasks,partner_tasks=(p_tasks,c_tasks) if own==0 else (c_tasks,p_tasks)
                            for own_r,own_t,spending in own_options(hand,rudder=key[1],thrust=key[2],tasks=own_tasks):
                                cooperate()
                                if spending>projected['coffee']:continue
                                pairs=physical_pairs(view,projected,own_r,own_t,brakes)
                                if not any(pairs):continue
                                score=fair_task_value(pairs,view['partner_remaining'],projected['coffee']-int(spending),
                                    partner_tasks,**known,cooperate=cooperate)
                                best=max(best,score)
                        contexts[key]=best
                    ranks[first]=max(ranks.get(first,0.),contexts[key])
    budget.pause()
    return ranks


def joint_landing_reference(view,allowed,previous,*,cpu_duty_cycle=1.):
    if (len(previous)!=len(allowed) or any(type(v) is not bool for v in previous)
            or any(v and not allowed[i] for i,v in enumerate(previous))):
        raise ValueError('Require the engine-legal prior reference.')
    plans=joint_landing_plans(view,allowed,cpu_duty_cycle=cpu_duty_cycle)
    if not plans or max(plans.values())<=0:return list(previous)
    best=max(plans.values())
    return [bool(flag and plans.get(i,-math.inf)>=best-1.) for i,flag in enumerate(allowed)]
