"""Profile 15: value synchronization opportunities and future wind geometry.

Only own dice and public state are inputs. Bonuses that have not been rolled
are utility estimates, never invented dice in a physics or feasibility proof.
The wind dynamic program is optimistic about future dice, upgrades and radio
work; its bounded value is a preference, not a guaranteed landing probability.
Legacy profile 13 and its recorded evidence remain byte-for-byte unchanged.
"""
from functools import lru_cache
from itertools import product
import math

from .actions import Action, ROLES
from .assignment_belief import alternative_task_value
from .contract_planner import (
    IDS, GEAR, FLAPS, Plan, PlanScores, legal_target, apply_placement,
    progress_value, capacity_penalty, commitment_value, partner_ice_completion,
    final_value, assignment_groups, public_movement_target,
)
from .module_physics import WIND_RING, predict_rudder
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .joint_landing_prior import _reach
from .joint_round import _tasks
from .public_hand_prior import _weight


SYNC_BONUS_VALUE = 110.
SYNC_FUTURE_PAIR_VALUE = 45.
WIND_HORIZON_VALUE = 400.


def weighted_task_value(groups, remaining, coffee, *, rudder=None, thrust=None):
    """Expected best nonnegative utility of jointly assignable public tasks.

    An alternative is (36 physical outcomes, tasks, 36 utilities). Union hand
    bitsets in descending utility order, charging every hypothetical die and
    sharing the coffee budget. Overlapping alternatives are counted only once.
    """
    missing = int(rudder is None) + int(thrust is None)
    buckets = {}
    for pairs, tasks, values in groups:
        tasks = _tasks(tasks)
        if missing + len(tasks) > remaining:
            continue
        targets, masks = _reach(remaining, missing, tasks, None)
        for index, target in enumerate(targets):
            r = target[0] if rudder is None else rudder
            t = target[-1] if thrust is None else thrust
            pair = (r-1)*6+t-1
            value = values[pair]
            if not pairs[pair] or value <= 0:
                continue
            bits = 0
            for cost in range(coffee+1):
                bits |= masks[cost][index]
            buckets[value] = buckets.get(value, 0) | bits
    covered = 0
    total = 0.
    for value in sorted(buckets, reverse=True):
        bits = buckets[value] & ~covered
        total += value * _weight(remaining, bits)
        covered |= bits
    return total / 6**remaining


def _occupied(view, indices):
    return any(view['board'][i] is not None for i in indices)


def _matching_options(view, indices, progress, faces):
    missing = [i for i in indices if view['board'][i] is None]
    if indices[0] == 10:  # flaps must advance in order
        first = next((i for i, done in enumerate(progress) if not done), len(progress))
        fresh = [first] if first < len(progress) and first+indices[0] in missing else []
    else:
        fresh = [i-indices[0] for i in missing if not progress[i-indices[0]]]
    reusable = [i-indices[0] for i in missing if progress[i-indices[0]]]
    return [(tuple(sorted({face for i in choices for face in faces[i]})), refill)
            for choices, refill in ((fresh, False), (reusable, True)) if choices]


def bonus_opportunity_value(view):
    """Expected useful destination of the non-uniform traffic die.

    Optimistic single-die utility, not an inserted resource or a probability
    of winning. A full coffee pool or a green switch earns no artificial gain.
    """
    total = 0.
    for rolled in (2,3,3,4,4,5):
        best = 0.
        node = Plan(view,virtual=rolled,source='synchronisation')
        for face in range(1,7):
            cost = abs(face-rolled)
            if cost > view['coffee']:
                continue
            for index, slot in enumerate(MODULE_SLOTS):
                if not legal_target(node,index,face):
                    continue
                utility = 0.
                if slot.target in ('ruder','triebwerk'):
                    utility = 35.
                elif slot.target == 'fahrwerk' and not view['gear'][slot.index]:
                    utility = 26.
                elif slot.target == 'landeklappe' and not view['flaps'][slot.index]:
                    utility = 30.
                elif slot.target == 'bremse' and not view['brake_progress'][slot.index]:
                    utility = 20.
                elif slot.target == 'konzentration' and view['coffee']-cost < 3:
                    utility = 8.
                elif slot.target == 'funk':
                    distance = view['distance']-face+1
                    if any(c['distance']==distance and c['planes'] for c in view['track']):
                        utility = 65. if face==1 else 45. if face==2 else 22.
                elif slot.target == 'eisbremse':
                    pair = slot.index//2
                    fields = view['modules_state']['extra_fields'][2+pair*2:4+pair*2]
                    utility = 32. if any(fields) else 8.
                elif slot.target == 'kerosin':
                    utility = max(0., 4.*(6-face))
                best = max(best, utility-12.*cost)
        total += best
    return min(SYNC_BONUS_VALUE, 2.*total/6)


def synchronisation_value(root, view, *, exact=False):
    state = root['modules_state']
    if 'synchronisation' not in state['cards']:
        return 0.
    future = 0 if root['last_round'] else max(0, int(root['height']//1000))
    reserve = min(view['gear'].count(False), view['flaps'].count(False), future)
    value = SYNC_FUTURE_PAIR_VALUE * reserve
    # Filling two already-green switches to obtain one die is a net loss.
    refills = sum(root['board'][i] is None and view['board'][i] is not None and root[key][i-offset]
                  for key, offset, indices in (('gear', 7, range(7,10)), ('flaps', 10, range(10,14)))
                  for i in indices)
    value -= 120. * refills
    if state['sync_triggered']:
        return value
    gear, flaps = _occupied(view, range(7,10)), _occupied(view, range(10,14))
    own = ROLES.index(root['role'])
    if not (gear if own == 0 else flaps) and not (gear and flaps):
        return value
    bonus_value = bonus_opportunity_value(view) if exact else SYNC_BONUS_VALUE
    if gear and flaps:
        return value + bonus_value
    # The other player must still have a distinct die left after controls.
    other = 1-own
    known = {'rudder': view['board'][other]['value'] if view['board'][other] else None,
             'thrust': view['board'][other+2]['value'] if view['board'][other+2] else None}
    spare = root['partner_remaining'] - sum(v is None for v in known.values()) - len(view.get('_partner_tasks', ()))
    if spare < 1:
        return value
    options = (_matching_options(view, range(10,14), view['flaps'], FLAPS) if own == 0
               else _matching_options(view, range(7,10), view['gear'], GEAR))
    if exact:
        groups, known = assignment_groups(root, view)
        best = 0.
        for faces, refill in options:
            constrained = [(pairs, tasks + (faces,), [max(0.,bonus_value-120.*refill)]*36)
                           for pairs, tasks in groups]
            best = max(best, weighted_task_value(constrained, root['partner_remaining'], view['coffee'], **known))
        return value + best
    chance = max((max(0.,bonus_value-120.*refill) * (1-(1-len(faces)/6)**spare)
                  for faces, refill in options), default=0.)
    return value + chance


@lru_cache(maxsize=2048)
def _landing_wind_value(position, bank, progress, ice):
    wind = WIND_RING[position]
    total = 0.
    for a, b in product(range(1,7), repeat=2):
        speed = a+b+wind
        need = max(0, speed-1) if ice else math.ceil(max(0, speed)/2)
        maximum = 4 if ice else 3
        if need <= maximum:
            total += 1 - .08*(2 if ice else 1)*max(0, need-progress)
    return total/36 - .02*abs(bank)


@lru_cache(maxsize=20000)
def _wind_horizon(position, bank, distance, rounds, blue, orange, max_blue, max_orange, curves, progress, ice):
    if distance > 2*max(0,rounds-1):
        return 0.
    if rounds <= 1:
        return max(0., _landing_wind_value(position, bank, progress, ice)) if distance == 0 else 0.
    best = 0.
    for attitude in range(-2,3):
        pos = (position+attitude) % len(WIND_RING)
        wind = WIND_RING[pos]
        possible = (2+wind < max_blue, 12+wind >= blue and 2+wind < max_orange, 12+wind >= orange)
        for move in range(min(2,distance)+1):
            if not possible[move] or any(not curves[d][0] <= attitude <= curves[d][1]
                                         for d in range(distance-move+1,distance+1)):
                continue
            future = _wind_horizon(pos, attitude, distance-move, rounds-1, blue, orange,
                                   max_blue, max_orange, curves, progress, ice)
            best = max(best, future - .02*abs(attitude-bank) - .003*abs(attitude))
    return best


def wind_pair_values(root, view):
    if 'wind' not in root['modules_state']['modules'] or root['last_round']:
        return (0.,)*36
    own = ROLES.index(root['role']); other = 1-own
    if not view['board'][own] or not view['board'][own+2]:
        return (0.,)*36
    # Remaining future rounds include the final (stationary) landing round.
    rounds = max(1, int(root['height']//1000))
    target = public_movement_target(root)
    curves = tuple((cell['min'],cell['max']) for cell in sorted(root['track'],key=lambda c:c['distance']))
    progress = view['modules_state']['ice_progress'] if 'ice' in root['modules_state']['modules'] else sum(view['brake_progress'])
    values = []
    for pr, pt in product(range(1,7),repeat=2):
        if any(view['board'][i] and view['board'][i]['value'] != face for i,face in ((other,pr),(other+2,pt))):
            values.append(0.); continue
        rudder = predict_rudder(root, **{f'{root["role"]}_value':view['board'][own]['value'], f'{ROLES[other]}_value':pr})
        if rudder['stalled']:
            values.append(0.); continue
        value = _wind_horizon(rudder['wind_position'],rudder['attitude'],max(0,root['distance']-target),rounds,
            view['aero_blue'], view['aero_orange'],view['aero_blue']+view['gear'].count(False),
            view['aero_orange']+view['flaps'].count(False),curves,progress,'ice' in root['modules_state']['modules'])
        values.append(WIND_HORIZON_VALUE*value)
    return tuple(values)


def ability_commitment(root, slot_index):
    value = commitment_value(root,slot_index)
    state = root['modules_state']
    if slot_index < 0 or 'synchronisation' not in state['cards'] or state['sync_triggered']:
        return value
    slot = MODULE_SLOTS[slot_index]
    own = ROLES.index(root['role'])
    target = 'fahrwerk' if own==0 else 'landeklappe'
    progress = root['gear'] if own==0 else root['flaps']
    own_slots = range(7,10) if own==0 else range(10,14)
    other_slots = range(10,14) if own==0 else range(7,10)
    if slot.target != target or progress[slot.index] or _occupied(root,own_slots):
        return value
    if _occupied(root,other_slots):
        return value+45.  # Expose the bonus before the partner commits more dice.
    other=1-own
    spare=root['partner_remaining']-sum(root['board'][i] is None for i in (other,other+2))
    if spare<1:return value
    options=(_matching_options(root,range(10,14),root['flaps'],FLAPS) if own==0 else
             _matching_options(root,range(7,10),root['gear'],GEAR))
    chance=max((1-(1-len(faces)/6)**spare for faces,refill in options if not refill),default=0.)
    return value+40.*chance


def deadline_value(root, view):
    """Soft risk penalty for postponing several upgrades into too few rounds.

    One reliable upgrade per future round is a scheduling preference, never
    a hard capacity claim: two upgrades and bonus dice remain fully legal.
    """
    future=0 if root['last_round'] else max(0,int(root['height']//1000))
    own=ROLES.index(root['role']);other=1-own
    other_spare=root['partner_remaining']-sum(view['board'][i] is None for i in (other,other+2))-len(view.get('_partner_tasks',()))
    capacity={own:future,other:future+int(other_spare>0)}
    needs={0:view['gear'].count(False),1:view['flaps'].count(False)}
    return -600.*sum(max(0,needs[role]-capacity[role])**2 for role in (0,1))


def ability_value(root, view, *, exact=False):
    value = synchronisation_value(root, view, exact=exact) + deadline_value(root,view)
    if 'wind' in root['modules_state']['modules'] and not root['last_round']:
        values = wind_pair_values(root, view)
        if exact:
            groups, known = assignment_groups(root, view)
            value += weighted_task_value([(pairs,tasks,values) for pairs,tasks in groups],
                                         root['partner_remaining'],view['coffee'],**known)
        else:
            value += max(values,default=0.)
    return value


def plan_ability_round(view, allowed, *, beam=24,coordination=False,early_ice=False,fuel_capacity=False,partner_gears=False):
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
        commitment = ability_commitment(view,node.first_slot)
        ability = ability_value(view,node.view,exact=True)
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
                                rough = ability_value(view,variant.view) + progress_value(view,variant.view)-capacity_penalty(variant.view)+ability_commitment(view,variant.first_slot)
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

