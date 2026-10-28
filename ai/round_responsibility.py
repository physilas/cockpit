"""Public task prescriptions, independent of either player's private faces.

These are coordination heuristics, not a solution of the common-information
dynamic program. They allocate scarce radio slots, suggest sustainable fuel
payments and schedule intern training before the final round.
"""
from math import ceil

from .actions import ROLES
from .modules import MODULE_SLOTS


def public_responsibilities(view,movement):
    if type(movement) is not int or not 0<=movement<=2:
        raise ValueError('A public movement target in 0..2 is required.')
    state=view['modules_state'];modules=set(state['modules'])
    future=0 if view['last_round'] else max(0,int(view['height']//1000))
    own=view['role'];other=ROLES[1-ROLES.index(own)]
    counts={own:sum(bool(v) for v in view['own_dice']),other:view['partner_remaining']}
    pending=state['pending']
    if pending and pending['source']=='intern':counts[pending['role']]+=1
    controls={r:sum(view['board'][i] is None for i in (j,j+2)) for j,r in enumerate(ROLES)}
    spare={r:max(0,counts[r]-controls[r]) for r in ROLES}
    slots={r:sum(slot.target=='funk' and slot.owner==r and view['board'][i] is None
                 for i,slot in enumerate(MODULE_SLOTS[:20])) for r in ROLES}
    capacity={r:min(spare[r],slots[r]) for r in ROLES}
    owned={'pilot':view['gear'].count(False),'kopilot':view['flaps'].count(False)}
    if 'ice' in modules:
        owned['pilot']+=4-state['ice_progress']
        owned['kopilot']+=4-state['ice_progress']
    else:
        owned['pilot']+=int(not any(view['brake_progress']))
    radios={r:[] for r in ROLES}
    cells=sorted(view['track'],key=lambda c:-c['distance'])
    for cell in cells:
        face=view['distance']-cell['distance']+1
        if (not 1<=face<=6 or cell['distance']<view['distance']-max(0,movement-1)):
            continue
        for _ in range(cell['planes']):
            candidates=[r for r in ROLES if capacity[r]>0]
            if not candidates:break
            # Preserve capacity for owned upgrades; ties use the pilot's
            # single radio before the copilot's two flexible radio slots.
            chosen=max(candidates,key=lambda r:(spare[r]-len(radios[r])-owned[r]/(future+1),r=='pilot'))
            radios[chosen].append(face);capacity[chosen]-=1
    fuel_role=None
    payment_target=None
    if 'kerosene' in modules and 'leak' not in modules and not view['fuel']['occupied']:
        candidates=[r for r in ROLES if spare[r]>len(radios[r])]
        if candidates:
            fuel_role=max(candidates,key=lambda r:(spare[r]-len(radios[r])-owned[r]/(future+1),r=='kopilot'))
            payment_target=min(6,max(1,(view['fuel']['remaining']-1)//(future+1)))
    trained=sum(state['extra_fields'][i] is not None for i in (0,1))
    quota=max(0,ceil((len(state['intern'])+trained)/(future+1))-trained)
    eligible=[r for i,r in enumerate(ROLES) if state['extra_fields'][i] is None and counts[r]>0]
    # The round's alternating first role is publicly recoverable from height.
    preferred='pilot' if future%2==0 else 'kopilot'
    eligible.sort(key=lambda r:r!=preferred)
    training=eligible[:quota]
    return dict(radios=radios,fuel_role=fuel_role,payment_target=payment_target,
                training_roles=training,future_rounds=future,
                private_faces_used=False,approximate=True)
