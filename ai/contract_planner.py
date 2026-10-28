"""Whole-own-hand planning under a shared public round objective.

Distinct own dice, one coffee budget, public module physics, and a declared
IID partner-hand assignment model. Partner radio/fuel tasks consume distinct
hypothetical dice too. Plans are receding-horizon proposals: only the first
engine-legal action is executed. Unknown future bonuses are not credited.
"""
from dataclasses import dataclass
from itertools import combinations,product
import math

from .actions import Action, ROLES
from .assignment_belief import alternative_task_value
from .module_physics import predict_rudder, predict_thrust, WIND_RING
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .public_hand_prior import fair_control_value


IDS = {action: index for index, action in enumerate(MODULE_ACTIONS)}
GEAR = ((1,2),(3,4),(5,6))
FLAPS = ((1,2),(2,3),(4,5),(5,6))


@dataclass
class Plan:
    view: dict
    first: int = -1
    virtual: int = 0
    source: str = ''
    flipped: bool = False
    first_slot: int = -1


class PlanScores(dict):
    """First-action ranks and the objective actually used in this state."""
    def __init__(self, values=(), *, primary_available=False,primary_value=0.):
        super().__init__(values)
        self.primary_available = primary_available
        self.primary_value=primary_value
        self.mode = 'round_contract' if primary_available else 'physical_fallback'


def field_at(view, slot_index):
    if slot_index < 20:
        return view['board'][slot_index]
    if slot_index == 20:
        return {'value':1} if view['fuel']['occupied'] else None
    return view['modules_state']['extra_fields'][slot_index-21]


def legal_target(plan, slot_index, face):
    view, state = plan.view, plan.view['modules_state']
    slot = MODULE_SLOTS[slot_index]
    if field_at(view, slot_index) is not None:
        return False
    if slot.owner is not None and slot.owner != view['role'] and plan.source != 'synchronisation':
        return False
    if slot.target == 'fahrwerk':
        return face in GEAR[slot.index]
    if slot.target == 'landeklappe':
        first = next((i for i, done in enumerate(view['flaps']) if not done), 4)
        return (view['flaps'][slot.index] or slot.index == first) and face in FLAPS[slot.index]
    if slot.target == 'bremse':
        first = next((i for i, done in enumerate(view['brake_progress']) if not done), 3)
        return ('ice' not in state['modules'] and (view['brake_progress'][slot.index] or slot.index == first)
                and face == (2,4,6)[slot.index])
    if slot.target == 'eisbremse':
        return 'ice' in state['modules'] and slot.index//2 == state['ice_progress'] and face == 2+slot.index//2
    if slot.target == 'kerosin':
        return 'kerosene' in state['modules'] and 'leak' not in state['modules']
    if slot.target == 'training':
        return (not plan.virtual and 'intern' in state['modules'] and state['intern']
                and state['intern'][0 if view['role']=='pilot' else -1] != face)
    if slot.target == 'konzentration' and plan.source == 'intern':
        return False
    return slot.target in ('ruder','triebwerk','funk','konzentration')


def apply_placement(plan, die, slot_index, face, coffee, flip):
    before = plan.view
    slot = MODULE_SLOTS[slot_index]
    role = slot.owner or ('pilot' if die==4 and plan.source=='synchronisation' else before['role'])
    view = {**before, 'own_dice': list(before['own_dice']), 'board': list(before['board']),
            'modules_state': {**before['modules_state'], 'extra_fields': list(before['modules_state']['extra_fields'])},
            'fuel': dict(before['fuel']), 'coffee': coffee}
    state = view['modules_state']
    virtual, source = plan.virtual, plan.source
    if die == 4:
        virtual, source = 0, ''
    else:
        view['own_dice'][die] = 0
    placed = {'value': face, 'owner': role}
    if slot_index < 20:
        view['board'][slot_index] = placed
    elif slot_index > 20:
        state['extra_fields'][slot_index-21] = placed
    if slot.target == 'fahrwerk' and not before['gear'][slot.index]:
        view['gear'] = list(before['gear']); view['gear'][slot.index] = True
        view['aero_blue'] += 1
    elif slot.target == 'landeklappe' and not before['flaps'][slot.index]:
        view['flaps'] = list(before['flaps']); view['flaps'][slot.index] = True
        view['aero_orange'] += 1
    elif slot.target == 'bremse' and not before['brake_progress'][slot.index]:
        view['brake_progress'] = list(before['brake_progress']); view['brake_progress'][slot.index] = True
        view['brakes'] += 2
    elif slot.target == 'konzentration':
        view['coffee'] = min(3, coffee+1)
    elif slot.target == 'funk':
        distance = before['distance']-face+1
        view['track'] = [dict(cell) for cell in before['track']]
        for cell in view['track']:
            if cell['distance'] == distance and cell['planes']:
                cell['planes'] -= 1
    elif slot.target == 'kerosin':
        view['fuel'].update(occupied=True, remaining=before['fuel']['remaining']-face)
        if view['fuel']['remaining'] <= 0:
            return None
    elif slot.target == 'training':
        state['intern'] = list(state['intern'])
        virtual = state['intern'].pop(0 if before['role']=='pilot' else -1)
        source = 'intern'
        # A token must have an actual legal destination after training.
        check = Plan(view, virtual=virtual, source=source)
        if not any(legal_target(check, i, virtual) for i in range(len(MODULE_SLOTS))):
            return None
    elif slot.target == 'eisbremse':
        pair = slot.index//2
        if all(state['extra_fields'][2+pair*2+i] is not None for i in (0,1)):
            state['ice_progress'] += 1
            view['brakes'] += 1
    if slot.target == 'ruder' and all(view['board'][i] is not None for i in (0,1)):
        rudder = predict_rudder({**before,'coffee':coffee}, **{f'{role}_value':face})
        if rudder['stalled']:
            return None
        view['attitude'] = rudder['attitude']
        if rudder['wind_position'] is not None:
            state['wind_position'] = rudder['wind_position']
        view['coffee'] = min(3, view['coffee']+rudder['coffee_gain'])
    if slot.target == 'triebwerk' and 'leak' in state['modules'] and all(view['board'][i] is not None for i in (2,3)):
        view['fuel']['remaining'] -= abs(view['board'][2]['value']-view['board'][3]['value'])+1
        view['_leak_paid'] = True
        if view['fuel']['remaining'] <= 0:
            return None
    view['_virtual_available'] = int(bool(virtual))
    view['_flipped'] = bool(before.get('_flipped') or flip)
    return Plan(view, plan.first, virtual, source, plan.flipped or flip, plan.first_slot)


def progress_value(root, view):
    state, original = view['modules_state'], root['modules_state']
    responsibilities=root.get('_public_responsibilities')
    gain = 26*(sum(view['gear'])-sum(root['gear'])) + 30*(sum(view['flaps'])-sum(root['flaps']))
    own_index=ROLES.index(view['role'])
    gain+=35*sum(root['board'][i] is None and view['board'][i] is not None for i in (own_index,own_index+2))
    gain+=20*sum(root['board'][i] is None and view['board'][i] is not None for i in (1-own_index,3-own_index))
    gain += 20*(sum(view['brake_progress'])-sum(root['brake_progress']))
    # A completed ice pair consumes TWO dice, unlike one gear/flap upgrade.
    gain += (64 if root.get('_early_ice') else 32)*(state['ice_progress']-original['ice_progress'])
    gain += (40 if responsibilities else 16)*(len(original['intern'])-len(state['intern']))
    if responsibilities and root['role'] in responsibilities['training_roles']:
        index=ROLES.index(root['role'])
        gain+=20*int(original['extra_fields'][index] is None and state['extra_fields'][index] is not None)
    own=view['role'];other=ROLES[1-ROLES.index(own)]
    spare={own:sum(bool(v) for v in view['own_dice'])+view.get('_virtual_available',0)
                    -sum(view['board'][i] is None for i in (ROLES.index(own),ROLES.index(own)+2)),
           other:view['partner_remaining']-sum(view['board'][i] is None for i in (ROLES.index(other),ROLES.index(other)+2))}
    for pair in range(state['ice_progress'],4):
        top,bottom=state['extra_fields'][2+2*pair:4+2*pair]
        if bool(top)==bool(bottom):
            continue
        possible=spare['pilot']>0 if top is None else max(0,spare['pilot'])+max(0,spare['kopilot'])>0
        if possible:
            gain+=8*sum(a is None and b is not None for a,b in zip(
                original['extra_fields'][2+2*pair:4+2*pair],state['extra_fields'][2+2*pair:4+2*pair]))
    for before, after in zip(root['track'], view['track']):
        removed = before['planes']-after['planes']
        delta = root['distance']-before['distance']
        gain += removed*(65 if delta==0 else 45 if delta==1 else 22)
    gain += 8*(view['coffee']-root['coffee'])
    gain -= 6*int(view.get('_flipped', False))
    if view['fuel']['occupied'] and not root['fuel']['occupied']:
        gain += (10 if responsibilities else 4)*(6-(root['fuel']['remaining']-view['fuel']['remaining']))
    return gain


def partner_ice_completion(node):
    """Explicit hypothesis for the partner turn between two own placements.

    The required face is recorded for joint hand/coffee accounting. This is
    never applied to the real game or returned as an executable sequence.
    """
    view=node.view;state=view['modules_state']
    pair=state['ice_progress']
    if 'ice' not in state['modules'] or pair>=4:
        return None
    top,bottom=state['extra_fields'][2+2*pair:4+2*pair]
    if bool(top)==bool(bottom):
        return None
    other=ROLES[1-ROLES.index(view['role'])]
    if top is None and other!='pilot':
        return None
    tasks=tuple(view.get('_partner_tasks',()))
    other_index=ROLES.index(other)
    controls=sum(view['board'][i] is None for i in (other_index,other_index+2))
    if len(tasks)+controls>=view['partner_remaining']:
        return None
    changed={**view,'modules_state':{**state,'extra_fields':list(state['extra_fields'])},
             '_partner_tasks':tasks+((2+pair,),),'brakes':view['brakes']+1}
    row=0 if top is None else 1
    changed['modules_state']['extra_fields'][2+2*pair+row]={'value':2+pair,'owner':other}
    changed['modules_state']['ice_progress']+=1
    return Plan(changed,node.first,node.virtual,node.source,node.flipped,node.first_slot)


def commitment_value(root,slot_index):
    if slot_index<0:
        return 0.
    slot=MODULE_SLOTS[slot_index]
    if slot.target not in ('ruder','triebwerk'):
        return 0.
    if 'wind' in root['modules_state']['modules'] and not all(root['board'][i] for i in (0,1)):
        return 24. if slot.target=='ruder' else -8.
    if slot.target=='ruder':
        other=1 if slot.owner=='pilot' else 0
        return 20. if root['board'][other] is None else 8.
    # The copilot publishes thrust before the pilot commits while landing
    # gear can still move the lower aerodynamic marker. The pilot then fits
    # its known gear plan to that public value, avoiding two private promises.
    if slot.owner=='kopilot' and root['board'][2] is None:
        return 24.
    if slot.owner=='pilot' and root['board'][3] is None and not all(root['gear']):
        return -8.
    return 16. if root['board'][3 if slot.owner=='pilot' else 2] is None else 8.


def capacity_penalty(view):
    state = view['modules_state']
    future = 0 if view['last_round'] else max(0, int(view['height']//1000))
    need = {'pilot': view['gear'].count(False), 'kopilot': view['flaps'].count(False)}
    if 'ice' in state['modules']:
        progress = state['ice_progress']
        # An unfinished half-pair is cleared at round end. Do not count its
        # occupied upper/lower field as a persistent future brake upgrade.
        need['pilot'] += 4-progress
        shared = 4-progress
    else:
        need['pilot'] += int(not any(view['brake_progress']))
        shared = 0
    if view.get('_fuel_capacity'):
        from .fuel_capacity import necessary_fuel_fields
        shared+=necessary_fuel_fields(view)['minimum_payments']
    own, other = view['role'], ROLES[1-ROLES.index(view['role'])]
    own_controls = sum(view['board'][i] is None for i in (ROLES.index(own),ROLES.index(own)+2))
    partner_controls = sum(view['board'][i] is None for i in (ROLES.index(other),ROLES.index(other)+2))
    capacity = {own: 2*future+sum(bool(v) for v in view['own_dice'])+view.get('_virtual_available',0)-own_controls,
                other: 2*future+view['partner_remaining']-len(view.get('_partner_tasks',()))-partner_controls}
    deficit = sum(max(0,need[r]-capacity[r]) for r in ROLES)
    spare = sum(max(0,capacity[r]-need[r]) for r in ROLES)
    deficit += max(0,shared+sum(p['planes'] for p in view['track'])-spare)
    training_now = sum(view['modules_state']['extra_fields'][i] is None and
                       (sum(bool(v) for v in view['own_dice'])>0 if r==own else view['partner_remaining']>0)
                       for i,r in enumerate(ROLES))
    deficit += max(0,len(state['intern'])-2*future-training_now)
    return 1200*deficit


def public_movement_target(view):
    """Same round contract for both roles; never depends on private faces.

    Stop to clear a queue that cannot fit into the public remaining radio
    capacity. Otherwise keep pace with altitude; leave high-spawn cells faster
    when the crossed public traffic can still fit into this round's radios.
    """
    if view['last_round'] or view['holding'] or view['distance']==0:
        return 0
    own=view['role'];other=ROLES[1-ROLES.index(own)]
    counts={own:sum(bool(v) for v in view['own_dice']),other:view['partner_remaining']}
    pending=view['modules_state']['pending']
    if pending and pending['source']=='intern':
        counts[pending['role']]+=1
    radios=0
    for i,role in enumerate(ROLES):
        missing=sum(view['board'][j] is None for j in (i,i+2))
        slots=sum(slot.target=='funk' and slot.owner==role and view['board'][j] is None
                  for j,slot in enumerate(MODULE_SLOTS[:20]))
        radios+=min(max(0,counts[role]-missing),slots)
    if pending and pending['source']=='synchronisation':
        free=sum(slot.target=='funk' and view['board'][i] is None for i,slot in enumerate(MODULE_SLOTS[:20]))
        radios=min(free,radios+1)
    cells={cell['distance']:cell for cell in view['track']}
    here=cells[view['distance']]
    if here['planes']>radios:
        return 0
    target=min(2,math.ceil(view['distance']/max(1,view['height']//1000)))
    if (view['distance']>=2 and here['traffic']>=2
            and here['planes']+cells[view['distance']-1]['planes']<=radios):
        target=2
    if target==2:
        crossing=(here,cells[view['distance']-1])
        if (sum(c['planes'] for c in crossing)>radios
                or max(c['min'] for c in crossing)>min(c['max'] for c in crossing)):
            target=1
    modules=view['modules_state']['modules']
    wind=0
    if 'wind' in modules:
        state=view['modules_state']
        wind=(state['wind_value'] if all(view['board'][i] is not None for i in (0,1)) else
              max(WIND_RING[(state['wind_position']+attitude)%len(WIND_RING)] for attitude in range(-2,3)))
    maximum_speed=sum(view['board'][i]['value'] if view['board'][i] else 6 for i in (2,3))+wind
    maximum_movement=int(maximum_speed>=view['aero_blue'])+int(maximum_speed>=view['aero_orange'])
    target=min(target,maximum_movement)
    return target


def landing_count_possible(view):
    """Optimistic public win bound; False is an impossibility proof.

    Ignore faces, ordering and coffee costs. An unissued synchronization die
    causes abstention, rather than counting a bonus that may never arrive.
    """
    state=view['modules_state'];modules=set(state['modules'])
    if any(c['planes'] and c['distance']>view['distance'] for c in view['track']):
        return False
    if not view['last_round']:
        maximum_speed=15 if 'wind' in modules else 12
        maximum_move=int(maximum_speed>=view['aero_blue'])+int(maximum_speed>=view['aero_orange'])
        return view['holding'] or view['distance']<=maximum_move*max(0,int(view['height']//1000))
    if all(view['board'][i] is not None for i in (0,1)) and view['attitude']!=0:
        return False
    minimum_speed=sum(view['board'][i]['value'] if view['board'][i] else 1 for i in (2,3))
    minimum_speed+=state['wind_value'] if 'wind' in modules else 0
    if minimum_speed>(5 if 'ice' in modules else 6):
        return False
    pending=state['pending']
    black=int(bool(pending and pending['source']=='synchronisation'))
    if 'synchronisation' in state['cards'] and not state['sync_triggered'] and not black:
        return True
    own=view['role'];other=ROLES[1-ROLES.index(own)]
    available={own:sum(bool(v) for v in view['own_dice']),other:view['partner_remaining']}
    if pending and pending['source']=='intern':
        available[pending['role']]+=1
    controls={r:sum(view['board'][i] is None for i in (j,j+2)) for j,r in enumerate(ROLES)}
    pilot_need=view['gear'].count(False)
    copilot_need=view['flaps'].count(False)
    shared=0
    if 'ice' in modules:
        first=state['ice_progress']*2
        fields=state['extra_fields'][2:]
        pilot_need+=sum(fields[i] is None for i in range(first,8,2))
        shared+=sum(fields[i] is None for i in range(first+1,8,2))
    else:
        pilot_need+=max(0,math.ceil(max(0,minimum_speed)/2)-sum(view['brake_progress']))
    if 'kerosene' in modules and 'leak' not in modules and not view['fuel']['occupied'] and view['fuel']['remaining']<=6:
        shared+=1
    # Each training consumes a regular die and replaces it with its token,
    # leaving the useful-dice count unchanged. No free training token credit.
    train_slots=sum(state['extra_fields'][i] is None and available[r]>0 for i,r in enumerate(ROLES))
    if len(state['intern'])>train_slots:
        return False
    planes=sum(c['planes'] for c in view['track'])
    radios={r:sum(slot.target=='funk' and slot.owner==r and view['board'][i] is None
                  for i,slot in enumerate(MODULE_SLOTS[:20])) for r in ROLES}
    for bonus_role in (ROLES if black else (None,)):
        for pilot_shared in range(shared+1):
            for pilot_radio in range(planes+1):
                if pilot_radio>radios['pilot'] or planes-pilot_radio>radios['kopilot']:
                    continue
                p=controls['pilot']+pilot_need+pilot_shared+pilot_radio
                c=controls['kopilot']+copilot_need+shared-pilot_shared+planes-pilot_radio
                if p<=available['pilot']+int(bonus_role=='pilot') and c<=available['kopilot']+int(bonus_role=='kopilot'):
                    return True
    return False


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


def emergency_control_value(root,view):
    own=ROLES.index(root['role']);other=1-own
    r,t=view['board'][own],view['board'][own+2]
    if r is None or t is None:
        return -30000.
    partner_r,partner_t=view['board'][other],view['board'][other+2]
    values=[]
    for pr in range(1,7):
        for pt in range(1,7):
            if partner_r and partner_r['value']!=pr or partner_t and partner_t['value']!=pt:
                values.append(-30000.);continue
            rudder=predict_rudder(root,**{f'{root["role"]}_value':r['value'],f'{ROLES[other]}_value':pr})
            physics={**view,'board':list(root['board']),'track':[dict(c,planes=0) for c in view['track']]}
            if view.get('_leak_paid'):
                physics['board'][2:4]=view['board'][2:4]
            motion=predict_thrust(physics,**{f'{root["role"]}_value':t['value'],f'{ROLES[other]}_value':pt},rudder=rudder)
            penalty=10000*rudder['stalled']+10000*bool(motion['fuel'].get('reason'))
            penalty+=500*abs(rudder['attitude']) if root['last_round'] else 3*abs(rudder['attitude'])
            if root['last_round']:
                penalty+=400*max(0,motion['speed']-motion['braking']['maximum_integer_speed'])
            elif motion['motion_reason']:
                penalty+=3000
            values.append(-float(penalty))
    return fair_control_value(tuple(values),root['partner_remaining'],view['coffee'],
        rudder=partner_r['value'] if partner_r else None,
        thrust=partner_t['value'] if partner_t else None,coffee_value=5.)


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


def plan_round(view, allowed, *, beam=24,coordination=False,early_ice=False,fuel_capacity=False,partner_gears=False):
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

    def record(node):
        nonlocal primary_available,primary_value
        primary, coherent, emergency, secondary = final_value(view,node.view,cache,details=True)
        primary_available |= primary>0
        primary_value=max(primary_value,primary)
        commitment = commitment_value(view,node.first_slot)
        normal = primary+.01*coherent+.001*emergency+secondary+commitment
        # If no complete plan can satisfy the contract, retain the best
        # physical flight and useful work. A missed task must not erase the
        # distinction between a level, slow landing and a stall at full speed.
        rescue = coherent+.1*emergency+progress_value(view,node.view)-.05*capacity_penalty(node.view)+commitment
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
                                rough = progress_value(view,variant.view)-capacity_penalty(variant.view)+commitment_value(view,variant.first_slot)
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


class ContractAgent:
    def __init__(self, airport, blueprint, *, beam=24,coordination=False,prospective_rerolls=False,early_ice=False,fuel_capacity=False,partner_gears=False):
        from .safety_guard import ShieldedBlueprint
        self.airport,self.blueprint,self.beam=airport,ShieldedBlueprint(airport,blueprint),beam
        if any(type(flag) is not bool for flag in (coordination,prospective_rerolls,early_ice,fuel_capacity,partner_gears)):
            raise ValueError('Use explicit Boolean strategy options.')
        self.coordination,self.prospective_rerolls=coordination,prospective_rerolls
        self.early_ice=early_ice
        self.fuel_capacity=fuel_capacity
        self.partner_gears=partner_gears
        self.last_report={}

    def select(self,view,mask):
        from .coherent_safety import coherent_safe_actions
        from .module_capacity import reserve_controls
        safe,safety=coherent_safe_actions(self.airport,view,mask)
        safe=reserve_controls(view,safe)
        ranks=plan_round(view,safe,beam=self.beam,coordination=self.coordination,early_ice=self.early_ice,
                         fuel_capacity=self.fuel_capacity,partner_gears=self.partner_gears)
        baseline,_=self.blueprint.rank(view,safe)
        chosen=baseline
        if ranks:
            best=max(ranks,key=ranks.get)
            if ranks.get(baseline,-math.inf)<ranks[best]-1.:
                chosen=best
            reroll=IDS[Action('reroll_start')]
            if (not ranks.primary_available and safe[reroll] and not view['reroll']
                    and not view['modules_state']['pending'] and not safety['unavoidable_closing_loss']
                    and landing_count_possible(view)):
                chosen=reroll
        elif not view['reroll'] and not view['modules_state']['pending'] and safe[IDS[Action('reroll_start')]]:
            chosen=IDS[Action('reroll_start')]
        reroll_values={}
        if self.prospective_rerolls and not safety['unavoidable_closing_loss']:
            from .reroll_advice import reroll_selection,worthwhile_landing_reroll
            options=dict(coordination=self.coordination,early_ice=self.early_ice,fuel_capacity=self.fuel_capacity,
                         partner_gears=self.partner_gears)
            if view['reroll']:
                selected,reroll_values=reroll_selection(view,safe,beam=min(12,self.beam),options=options)
                if selected is not None:chosen=selected
            else:
                worthwhile,reroll_values=worthwhile_landing_reroll(view,safe,beam=min(12,self.beam),options=options)
                if worthwhile:chosen=IDS[Action('reroll_start')]
        self.last_report=dict(baseline=baseline,chosen=chosen,ranks=ranks,
                              planning_mode=ranks.mode,
                              coordination=self.coordination,prospective_rerolls=self.prospective_rerolls,
                              early_ice=self.early_ice,
                              fuel_capacity=self.fuel_capacity,
                              partner_gears=self.partner_gears,
                              reroll_values=reroll_values,
                              objective='public_static_round_assignment',approximate=True)
        return chosen
