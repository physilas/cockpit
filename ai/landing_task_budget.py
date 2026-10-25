"""Optimistic public COUNT bound across the remaining Wind/Ice rounds.

Not an assignment/win proof: faces, ordering, future traffic and coffee costs
are ignored. A future synchronization opportunity causes abstention, never die
credit just for card possession. An actually issued black die counts once.
This passive diagnostic does not change masks, references, rewards or actions.
"""
import math

from .actions import ROLES
from .modules import MODULE_SLOTS


def task_budget(view):
    x=view['modules_state'];modules=set(x['modules'])
    if not modules or modules-{'wind','ice'}:
        return dict(supported=False,possible=None,reason='unsupported_modules')
    if x['pending'] and x['pending']['source']!='synchronisation':
        return dict(supported=False,possible=None,reason='unsupported_pending_token')
    future=0 if view['last_round'] else max(0,int(view['height']//1000))
    other=ROLES[1-ROLES.index(view['role'])]
    regular={view['role']:sum(bool(v) for v in view['own_dice']),other:view['partner_remaining']}
    available={r:regular[r]+4*future for r in ROLES}
    controls={r:sum(view['board'][i] is None for i in (j,j+2))+2*future for j,r in enumerate(ROLES)}
    pilot_need=sum(not done for done in view['gear']);copilot_need=sum(not done for done in view['flaps'])
    shared_ice=0
    if 'ice' in modules:
        fields=x['extra_fields'][2:];first=x['ice_progress']*2
        pilot_need+=sum(fields[i] is None for i in range(first,8,2))
        shared_ice=sum(fields[i] is None for i in range(first+1,8,2))
        brake_upgrades=0
    else:
        # Before the final round, permit the most favorable future wind. In
        # the final round a successful level rudder leaves the current ring
        # position unchanged. Published thrusts cannot be reduced later.
        wind=x['wind_value'] if view['last_round'] else -3
        minimum_speed=sum(view['board'][i]['value'] if view['board'][i] else 1 for i in (2,3))+wind if view['last_round'] else 2+wind
        brake_upgrades=max(0,math.ceil(max(0,minimum_speed)/2)-sum(view['brake_progress']))
        pilot_need+=brake_upgrades
    planes=sum(cell['planes'] for cell in view['track'])
    radios={r:sum(slot.target=='funk' and slot.owner==r and view['board'][i] is None
                  for i,slot in enumerate(MODULE_SLOTS[:20]))+(1 if r=='pilot' else 2)*future for r in ROLES}
    pending=x['pending']
    issued=int(bool(pending and pending['source']=='synchronisation'))
    uncertain=('synchronisation' in x['cards'] and (future>0 or not x['sync_triggered']) and not issued)
    # Even after this round's issued bonus, later rounds could trigger another.
    uncertain=uncertain or 'synchronisation' in x['cards'] and future>0
    details=dict(supported=True,future_rounds=future,regular_remaining=regular,
        available_by_role=available,issued_shared_bonus=issued,uncertain_future_bonus=bool(uncertain),
        controls_by_role=controls,pilot_owned_tasks=pilot_need,copilot_owned_tasks=copilot_need,
        shared_ice_tasks=shared_ice,radio_tasks=planes,radio_slots_by_role=radios,
        minimum_brake_upgrades=brake_upgrades,
        minimum_total_need=sum(controls.values())+pilot_need+copilot_need+shared_ice+planes,
        available_total=sum(available.values())+issued)
    if uncertain:return dict(**details,possible=None,reason='unissued_future_sync_abstention')
    possible=False
    for bonus_owner in ((None,) if not issued else ROLES):
        for pilot_ice in range(shared_ice+1):
            for pilot_radio in range(planes+1):
                copilot_radio=planes-pilot_radio
                if pilot_radio>radios['pilot'] or copilot_radio>radios['kopilot']:continue
                p=controls['pilot']+pilot_need+pilot_ice+pilot_radio
                c=controls['kopilot']+copilot_need+shared_ice-pilot_ice+copilot_radio
                if p<=available['pilot']+int(bonus_owner=='pilot') and c<=available['kopilot']+int(bonus_owner=='kopilot'):
                    possible=True;break
            if possible:break
        if possible:break
    return dict(**details,possible=possible,reason='count_bound_passes' if possible else 'necessary_count_bound_fails')
