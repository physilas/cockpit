"""Versioned communication search; released Crew 1–6 sources stay frozen.

The search and fair partner-assignment enumeration are derived from the frozen
contract/ability planners. Accepted movement replaces the default round target;
focus changes bounded whole-hand utility. Native safety masks remain authoritative.
Without an accepted plan the browser adapter delegates to the exact old profile.
"""
import math
from itertools import product, combinations
from .actions import Action, ROLES
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .assignment_belief import alternative_task_value
from .contract_planner import (Plan, PlanScores, IDS, GEAR, FLAPS, legal_target, apply_placement,
    capacity_penalty, commitment_value, partner_ice_completion, emergency_control_value,
    progress_value as base_progress_value, public_movement_target as default_movement_target)
from .ability_planner import (ability_commitment, synchronisation_value, deadline_value,
    wind_pair_values, _wind_pair_key, weighted_task_value)
from .module_physics import predict_rudder, predict_thrust, WIND_RING


def public_movement_target(view):
    return view['_briefing']['movement_preference'] if '_briefing' in view else default_movement_target(view)


def progress_value(root, view):
    plan = root['_briefing']
    focus, coordination = plan['focus'], plan['coordination']
    value = base_progress_value(root, view)
    if focus == 'radio':
        value += 70 * sum(max(0, old['planes']-new['planes']) for old,new in zip(root['track'],view['track']))
    elif focus == 'tasks':
        value += 60 * (sum(view['gear'])+sum(view['flaps'])-sum(root['gear'])-sum(root['flaps']))
    elif focus == 'coffee':
        value += 45 * (view['coffee']-root['coffee'])
    elif focus == 'fuel':
        value += 18 * (view['fuel']['remaining']-root['fuel']['remaining'])
    if coordination == 'brakes':
        value += 60 * (sum(view['brake_progress'])-sum(root['brake_progress']) + view['modules_state']['ice_progress']-root['modules_state']['ice_progress'])
    if coordination == 'level':
        own = ROLES.index(root['role'])
        rudder = view['board'][own]
        if rudder:
            other = view['board'][1-own]
            faces = [other['value']] if other else range(1,7)
            # A utility estimate over public possibilities, never a hidden face.
            value -= 20 * sum(abs(predict_rudder(root,**{f"{root['role']}_value":rudder['value'],f"{ROLES[1-own]}_value":face})['attitude']) for face in faces)/len(faces)
    return value


def ability_value(root, view, *, exact=False, wind_values=None):
    scale = 1.3 if root['_briefing']['coordination']=='synchronisation' else 1.
    value = scale*synchronisation_value(root,view,exact=exact)+deadline_value(root,view)
    if 'wind' in root['modules_state']['modules'] and not root['last_round']:
        values = wind_pair_values(root,view) if wind_values is None else wind_values
        scale = 1.15 if root['_briefing']['coordination']=='wind' else 1.
        if exact:
            groups,known = assignment_groups(root,view)
            value += scale*weighted_task_value([(pairs,tasks,values) for pairs,tasks in groups],root['partner_remaining'],view['coffee'],**known)
        else:
            value += scale*max(values,default=0.)
    return value


def assignment_groups(root,view,*,strict=True,include_optional=False):
    own=ROLES.index(root['role']);other=1-own
    r,t=view['board'][own],view['board'][own+2]
    partner_r,partner_t=view['board'][other],view['board'][other+2]
    known=dict(rudder=partner_r['value'] if partner_r else None,
               thrust=partner_t['value'] if partner_t else None)
    if r is None or t is None:
        return [],known
    responsibilities=root.get('_public_responsibilities') if strict else None
    if responsibilities:
        requested=responsibilities['radios'][root['role']]
        for face in set(requested):
            distance=root['distance']-face+1
            old=next(c['planes'] for c in root['track'] if c['distance']==distance)
            new=next(c['planes'] for c in view['track'] if c['distance']==distance)
            if old-new<requested.count(face):return [],known
        if (responsibilities['fuel_role']==root['role'] and responsibilities['payment_target']<6
                and not view['fuel']['occupied']):
            return [],known
    modules=set(view['modules_state']['modules'])
    radios=sum(slot.target=='funk' and slot.owner==ROLES[other] and view['board'][i] is None
               for i,slot in enumerate(MODULE_SLOTS[:20]))
    target=public_movement_target(root)
    groups={}
    extra_range=(range(4-sum(view['brake_progress']))
                 if root['last_round'] and own==1 and 'ice' not in modules else (0,))
    gear_options=[()]
    if (root.get('_partner_gears') and own==1 and not root['last_round'] and not root['holding']
            and target==0):
        missing=[i for i,done in enumerate(view['gear']) if not done]
        controls=sum(view['board'][i] is None for i in (0,2))
        spare=max(0,root['partner_remaining']-controls-len(view.get('_partner_tasks',())))
        gear_options.extend(subset for n in range(1,min(spare,len(missing))+1) for subset in combinations(missing,n))
    for pr in range(1,7):
        for pt in range(1,7):
            if partner_r and partner_r['value']!=pr or partner_t and partner_t['value']!=pt:
                continue
            rudder=predict_rudder(root,**{f'{root["role"]}_value':r['value'],f'{ROLES[other]}_value':pr})
            if rudder['stalled'] or root['last_round'] and rudder['attitude']!=0:
                continue
            for extra,gear_subset in product(extra_range,gear_options):
                physics={**view,'board':list(root['board']),
                         'track':[dict(cell,planes=0) for cell in view['track']]}
                physics['aero_blue']+=len(gear_subset)
                if view.get('_leak_paid'):
                    physics['board'][2:4]=view['board'][2:4]
                fuel_tasks=()
                payment=None
                future_fuel=0 if root['last_round'] or not strict else root['height']//1000
                prescribed_fuel=(responsibilities and responsibilities['fuel_role']==ROLES[other]
                                  and responsibilities['payment_target']<6)
                if ('kerosene' in modules and 'leak' not in modules and not view['fuel']['occupied']
                        and (view['fuel']['remaining']-6<=future_fuel or prescribed_fuel)):
                    maximum=min(6,view['fuel']['remaining']-future_fuel-1)
                    if prescribed_fuel:maximum=min(maximum,responsibilities['payment_target'])
                    if maximum<1:
                        continue
                    fuel_tasks=(tuple(range(1,maximum+1)),)
                    payment=1
                motion=predict_thrust(physics,**{f'{root["role"]}_value':t['value'],f'{ROLES[other]}_value':pt},
                                      rudder=rudder,kerosene_payment=payment,additional_brakes=extra)
                if motion['reason'] or strict and not motion['fuel'].get('necessary_survival',True):
                    continue
                move=motion['movement']
                if strict and not root['last_round'] and move!=target:
                    continue
                future=0 if root['last_round'] else max(0,root['height']//1000-1)
                maximum=1 if 'wind' not in modules and view['aero_orange']>12 else 2
                if (strict and root['distance']-move>maximum*future
                        and not root['holding'] and not root['last_round']):
                    continue
                required=[]
                impossible=False
                for cell in view['track']:
                    if not cell['planes']:
                        continue
                    if cell['distance']>root['distance']:
                        if strict:
                            impossible=True;break
                        continue
                    if cell['distance']>root['distance']-move or root['last_round']:
                        face=root['distance']-cell['distance']+1
                        if not 1<=face<=6:
                            impossible=True;break
                        required.extend([(face,)]*cell['planes'])
                if impossible or len(required)>radios:
                    continue
                required.extend(fuel_tasks)
                required.extend(GEAR[i] for i in gear_subset)
                if root['last_round'] or include_optional:
                    required.extend(view.get('_partner_tasks',()))
                if extra:
                    first=sum(view['brake_progress'])
                    required.extend(((2,4,6)[i],) for i in range(first,first+extra))
                if strict and root['last_round']:
                    if any(not done for done in (view['gear'] if own==0 else view['flaps'])):
                        continue
                    required.extend(GEAR[i] for i,done in enumerate(view['gear']) if not done)
                    required.extend(FLAPS[i] for i,done in enumerate(view['flaps']) if not done)
                    if 'ice' in modules and view['modules_state']['ice_progress']<4:
                        continue
                    if view['modules_state']['intern']:
                        continue
                tasks=tuple(sorted(required))
                groups.setdefault(tasks,[False]*36)[(pr-1)*6+pt-1]=True
    return [(tuple(pairs),tasks) for tasks,pairs in groups.items()],known


def final_value(root,view,cache,*,details=False):
    own=ROLES.index(root['role']);other=1-own
    r,t=view['board'][own],view['board'][own+2]
    if r is None or t is None:
        return (0.,0.,-30000.,-30000.) if details else -30000.
    key=(r['value'],t['value'],view['coffee'],view['aero_blue'],view['aero_orange'],view['brakes'],
         tuple(None if view['board'][i] is None else view['board'][i]['value'] for i in (other,other+2)),
         tuple(view['board'][i] is not None for i in (4,5,6)),tuple(c['planes'] for c in view['track']),
         view['fuel']['remaining'],view['fuel']['occupied'],view.get('_leak_paid',False),
         view['modules_state']['ice_progress'],tuple(view['gear']),tuple(view['flaps']),
         tuple(view['brake_progress']),tuple(view['modules_state']['intern']),tuple(view.get('_partner_tasks',())))
    if key not in cache:
        groups,known=assignment_groups(root,view)
        primary=alternative_task_value(groups,root['partner_remaining'],view['coffee'],**known)
        coherent_groups,_=assignment_groups(root,view,strict=False)
        coherent=alternative_task_value(coherent_groups,root['partner_remaining'],view['coffee'],**known)
        ratio=1.
        if view.get('_partner_tasks') and not root['last_round']:
            optional_groups,_=assignment_groups(root,view,include_optional=True)
            joint=alternative_task_value(optional_groups,root['partner_remaining'],view['coffee'],**known)
            ratio=min(1.,joint/max(primary,1.))
        cache[key]=(primary,coherent,emergency_control_value(root,view),ratio)
    primary,coherent,emergency,ratio=cache[key]
    secondary=progress_value(root,view)*ratio-capacity_penalty(view)
    if details:
        return primary,coherent,emergency,secondary
    return primary+.01*coherent+.001*emergency+secondary


def plan_briefed_round(view, allowed, *, beam=24,coordination=False,early_ice=False,fuel_capacity=False,partner_gears=False):
    if (type(beam) is not int or not 1<=beam<=128 or len(allowed)!=len(MODULE_ACTIONS)
            or any(type(flag) is not bool for flag in allowed) or type(coordination) is not bool
            or any(type(flag) is not bool for flag in (early_ice,fuel_capacity,partner_gears))):
        raise ValueError('Use a bounded beam and the Boolean schema-3 engine mask.')
    state = view['modules_state']
    if view['reroll'] or state['swap'] or state['pending'] and state['pending']['value'] is None:
        return PlanScores()
    if coordination:
        from .round_responsibility import public_responsibilities
        view={**view,'_public_responsibilities':public_responsibilities(view,public_movement_target(view))}
    if early_ice:view={**view,'_early_ice':True}
    if fuel_capacity:view={**view,'_fuel_capacity':True}
    if partner_gears:view={**view,'_partner_gears':True}
    pending = state['pending']
    root = Plan(view,virtual=pending['value'] if pending else 0,source=pending['source'] if pending else '')
    frontier, completed, fallback, cache = [root], {}, {}, {}
    primary_available = False
    primary_value=0.
    wind_cache={}

    def value_for(node_view, *, exact=False):
        values=None
        if "wind" in state["modules"] and not view["last_round"]:
            key=_wind_pair_key(node_view)
            if key not in wind_cache:wind_cache[key]=wind_pair_values(view,node_view)
            values=wind_cache[key]
        return ability_value(view,node_view,exact=exact,wind_values=values)

    def record(node):
        nonlocal primary_available,primary_value
        primary, coherent, emergency, secondary = final_value(view,node.view,cache,details=True)
        primary_available |= primary>0
        primary_value=max(primary_value,primary)
        commitment = ability_commitment(view,node.first_slot)
        ability = value_for(node.view,exact=True)
        normal = primary+.01*coherent+.001*emergency+secondary+commitment+ability
        # If no complete plan can satisfy the contract, retain the best
        # physical flight and useful work. A missed task must not erase the
        # distinction between a level, slow landing and a stall at full speed.
        rescue = coherent+.1*emergency+progress_value(view,node.view)-.05*capacity_penalty(node.view)+commitment+ability
        completed[node.first] = max(completed.get(node.first,-math.inf),normal)
        fallback[node.first] = max(fallback.get(node.first,-math.inf),rescue)
    for depth in range(6):
        expanded = []
        for node in frontier:
            current = node.view
            if not any(current['own_dice']) and not node.virtual:
                record(node)
                continue
            pool = [(4,node.virtual)] if node.virtual else list(enumerate(current['own_dice']))
            for die, original in pool:
                if not original:
                    continue
                can_flip = (die!=4 and not node.flipped and current['modules_state']['adaptation'][view['role']])
                for flip in (False,True) if can_flip else (False,):
                    start = 7-original if flip else original
                    for face in range(1,7):
                        cost = abs(face-start)
                        if cost>current['coffee'] or die==4 and node.source=='intern' and cost:
                            continue
                        for slot_index,slot in enumerate(MODULE_SLOTS):
                            if not legal_target(node,slot_index,face):
                                continue
                            if die!=4 and slot.target not in ('ruder','triebwerk','training'):
                                missing = sum(current['board'][i] is None for i in (ROLES.index(view['role']),ROLES.index(view['role'])+2))
                                if sum(bool(v) for v in current['own_dice'])<=missing:
                                    continue
                            if die==4:
                                first = IDS[Action('bonus_coffee',delta=face-original)] if cost else IDS[Action('bonus_place',slot=slot_index)]
                            else:
                                first = (IDS[Action('adaptation',die=die)] if flip else
                                         IDS[Action('coffee',die=die,delta=face-original)] if cost else
                                         IDS[Action('place',die=die,slot=slot_index)])
                            if node.first<0 and not allowed[first]:
                                continue
                            child = apply_placement(node,die,slot_index,face,current['coffee']-cost,flip)
                            if child is None:
                                continue
                            child.first = node.first if node.first>=0 else first
                            child.first_slot=node.first_slot if node.first>=0 else slot_index
                            variants=[child]
                            partner_turn=(not child.virtual and (die!=4 or node.source=='intern'
                                          or current['regular_turn']!=current['role']))
                            assumed=partner_ice_completion(child) if partner_turn else None
                            if assumed:
                                variants.append(assumed)
                            for variant in variants:
                                rough = value_for(variant.view) + progress_value(view,variant.view)-capacity_penalty(variant.view)+ability_commitment(view,variant.first_slot)
                                own = ROLES.index(view['role'])
                                if variant.view['board'][own] and variant.view['board'][own+2]:
                                    rough += .02*final_value(view,variant.view,cache)
                                expanded.append((rough,variant))
        if not expanded:
            break
        expanded.sort(key=lambda item:item[0],reverse=True)
        unique = []
        seen = set()
        for _,node in expanded:
            v=node.view
            key=(tuple(v['own_dice']),tuple(None if f is None else (f['value'],f['owner']) for f in v['board']),
                 v['coffee'],tuple(v['gear']),tuple(v['flaps']),tuple(v['brake_progress']),
                 tuple(cell['planes'] for cell in v['track']),tuple(v['modules_state']['intern']),
                 tuple(None if f is None else (f['value'],f['owner']) for f in v['modules_state']['extra_fields']),
                 v['fuel']['remaining'],v['fuel']['occupied'],node.virtual,node.source,node.flipped,node.first,node.first_slot)
            key+=(tuple(v.get('_partner_tasks',())),)
            if key not in seen:
                seen.add(key);unique.append(node)
        leaders={}
        for node in unique:
            slot=MODULE_SLOTS[node.first_slot]
            leaders.setdefault((slot.target,slot.owner),node)
        frontier=list(leaders.values())[:beam]
        selected={id(node) for node in frontier}
        frontier.extend(node for node in unique if id(node) not in selected)
        frontier=frontier[:beam]
    for node in frontier:
        if not any(node.view['own_dice']) and not node.virtual:
            record(node)
    chosen=completed if primary_available else fallback
    return PlanScores({i:value for i,value in chosen.items() if i>=0 and allowed[i]},
                      primary_available=primary_available,primary_value=primary_value)

