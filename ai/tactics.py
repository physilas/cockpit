"""Small public-information round planner and conservative landing capacity.

This module is torch-free and also runs in Pyodide. It never receives a game,
the partner's hand, or a random generator. The optional assistance profile is
separate from the historical legal-action mask, so old checkpoints and human
demonstrations retain their meaning.
"""
from math import ceil, factorial, prod
from functools import lru_cache
from itertools import combinations_with_replacement, product
import json

from .actions import ACTIONS, ACTION_IDS, Action, SLOTS, ROLES

ASSISTANCE_VERSION = 10
_SLOT = {(s.target, s.owner, s.index, s.radio_index): i for i, s in enumerate(SLOTS)}


def capacity(view, role=None, *, extra_placements=0):
    """Optimistic placement budget; extra dice must be assigned only once.

    The caller must account for ability rules before enabling this for cards.
    Current callers explicitly reject all modules and abilities. Faces, traffic
    and flight controls can make a state harder, never easier, than this bound.
    """
    role = role or view['role']
    free = sum(bool(d) for d in view['own_dice']) if role == view['role'] else view['partner_remaining']
    required = sum(s.owner == role and s.target in ('ruder', 'triebwerk') and view['board'][i] is None
                   for i, s in enumerate(SLOTS))
    future = 0 if view['last_round'] else max(0, int(view['height'] // 1000))
    needed = (sum(not x for x in view['gear']) + int(view['brakes'] < 2)
              if role == 'pilot' else sum(not x for x in view['flaps']))
    available = free - required + 2 * future + extra_placements
    return {'available': available, 'needed': needed, 'slack': available - needed}


def _traffic_budget(view):
    future = 0 if view['last_round'] else max(0, int(view['height'] // 1000))
    slack, radios = 0, 0
    for role in ROLES:
        budget = capacity(view, role)
        slack += budget['slack']
        free_radios = sum(s.target == 'funk' and s.owner == role and view['board'][i] is None
                          for i, s in enumerate(SLOTS))
        max_radios = free_radios + (1 if role == 'pilot' else 2) * future
        radios += max(0, min(budget['slack'], max_radios))
    traffic = sum(c['planes'] for c in view['track'])
    return slack - traffic, radios - traffic


def capacity_mask(view, mask, *, include_traffic=False):
    """Remove only moves that cross from feasible to provably insufficient.

    Already impossible states retain their ordinary actions, including rescue
    resources: an empty policy distribution is never manufactured here.
    """
    result = list(mask)
    budget = capacity(view)
    if budget['slack'] != 0 and not include_traffic:
        return result
    for i, valid in enumerate(mask):
        if not valid or ACTIONS[i].kind != 'place':
            continue
        s = SLOTS[ACTIONS[i].slot]
        useful = (s.target in ('ruder', 'triebwerk')
                  or s.target == 'fahrwerk' and not view['gear'][s.index]
                  or s.target == 'landeklappe' and not view['flaps'][s.index]
                  or s.target == 'bremse' and view['brakes'] < 2 and not view['brake_progress'][s.index])
        if budget['slack'] == 0 and not useful:
            result[i] = False
    if include_traffic and min(_traffic_budget(view)) >= 0 and budget['slack'] >= 0:
        for i, valid in enumerate(result):
            action = ACTIONS[i]
            if not valid or action.kind != 'place':
                continue
            s = SLOTS[action.slot]
            changed = {**view, 'own_dice': list(view['own_dice']), 'board': list(view['board']),
                       'gear': list(view['gear']), 'flaps': list(view['flaps']),
                       'track': [dict(c) for c in view['track']]}
            face = changed['own_dice'][action.die]
            changed['own_dice'][action.die] = 0
            changed['board'][action.slot] = {'value': face, 'owner': view['role']}
            if s.target == 'fahrwerk':
                changed['gear'][s.index] = True
            elif s.target == 'landeklappe':
                changed['flaps'][s.index] = True
            elif s.target == 'bremse' and not view['brake_progress'][s.index]:
                changed['brakes'] += 2
            elif s.target == 'funk':
                for cell in changed['track']:
                    if cell['distance'] == view['distance'] - face + 1 and cell['planes']:
                        cell['planes'] -= 1
                        break
            if min(_traffic_budget(changed)) < 0:
                result[i] = False
    return result if any(result) else list(mask)


def _bits(values):
    return sum(1 << i for i, value in enumerate(values) if value)


def joint_control_probability(rudder_faces, thrust_faces, dice, coffee=0):
    """Exact chance of two distinct iid dice satisfying two face sets.

    This is a public-information prior, not an inference about a hidden hand.
    In particular, one die in the intersection cannot fill both controls.
    """
    if dice < 2:
        return 0.0
    a, b = set(rudder_faces), set(thrust_faces)
    if coffee:
        return _joint_with_coffee(tuple(sorted(a)),tuple(sorted(b)),dice,coffee)
    union, intersection = len(a | b), len(a & b)
    both = 1 - (1-len(a)/6)**dice - (1-len(b)/6)**dice + (1-union/6)**dice
    single = dice * intersection / 6 * (1-union/6)**(dice-1)
    return max(0.0, min(1.0, both-single))


@lru_cache(maxsize=4096)
def _joint_with_coffee(a,b,dice,coffee):
    if not a or not b:
        return 0.0
    costs_a={n:min(abs(n-target) for target in a) for n in range(1,7)}
    costs_b={n:min(abs(n-target) for target in b) for n in range(1,7)}
    wins=0
    for hand in combinations_with_replacement(range(1,7),dice):
        if any(costs_a[x]+costs_b[y]<=coffee for i,x in enumerate(hand) for j,y in enumerate(hand) if i!=j):
            wins+=factorial(dice)//prod(factorial(hand.count(n)) for n in set(hand))
    return wins/6**dice


def expected_best_face(scores, dice):
    """Expected best score in iid fair dice, including all bad outcomes."""
    return _expected_best_face(tuple(scores),max(1,dice))


@lru_cache(maxsize=2048)
def _expected_best_face(scores, dice):
    dice = max(1, dice)
    levels = sorted(set(scores))
    result = levels[0]
    for before, level in zip(levels, levels[1:]):
        below = sum(value < level for value in scores) / len(scores)
        result += (level-before) * (1-below**dice)
    return result


def plan_actions(view, mask, *, beam=24, version=1):
    """Rank the first macro action of complete plans for the visible own hand.

    Coffee followed by placement is evaluated as one operation; only its first
    ordinary action is returned. Unseen partner dice are represented by an
    optimistic distribution over faces, not sampled or read from the engine.
    """
    fuel = view.get('fuel', {})
    slots, actions = SLOTS, ACTIONS
    if fuel.get('present'):
        from .fuel import FUEL_SLOTS, FUEL_ACTIONS
        slots, actions = FUEL_SLOTS, FUEL_ACTIONS
    action_ids = {a: i for i, a in enumerate(actions)}
    forecast=None
    if view.get('_horizon') and not view['reroll'] and 0<view['height']<=2000:
        from .horizon import make_forecast
        forecast=make_forecast(view)
    role = view['role']
    partner = ROLES[1 - ROLES.index(role)]
    own_r = _SLOT['ruder', role, None, 0]
    own_t = _SLOT['triebwerk', role, None, 0]
    partner_r = view['board'][_SLOT['ruder', partner, None, 0]]
    partner_t = view['board'][_SLOT['triebwerk', partner, None, 0]]
    original_r = view['board'][own_r]
    original_t = view['board'][own_t]
    occupied = sum(1 << i for i, value in enumerate(view['board']) if value)
    gear0, flaps0 = _bits(view['gear']), _bits(view['flaps'])
    # state: dice, occupied slots, own rudder/thrust, progress, coffee, traffic.
    traffic0 = tuple(c['planes'] for c in view['track'])
    start = (tuple(view['own_dice']), occupied, original_r['value'] if original_r else 0,
             original_t['value'] if original_t else 0, gear0, flaps0,
             _bits(view['brake_progress']), view['coffee'], traffic0, 0)
    rounds = max(1, int(view['height'] // 1000))
    future = 0 if view['last_round'] else int(view['height'] // 1000)
    partner_required = sum(s.owner == partner and s.target in ('ruder', 'triebwerk') and view['board'][i] is None
                           for i, s in enumerate(slots))
    partner_radios = sum(s.owner == partner and s.target == 'funk' and view['board'][i] is None
                        for i, s in enumerate(slots))
    partner_clearance = max(0, min(partner_radios, view['partner_remaining'] - partner_required))
    partner_budget = capacity(view,partner)
    if version >= 4:
        partner_clearance=min(partner_clearance,max(0,partner_budget['slack']))
    curve_soon = any(c['distance'] in (view['distance'], view['distance'] - 1)
                     and not c['min'] <= 0 <= c['max'] for c in view['track'])
    control_priority = 0 if version >= 3 and curve_soon and not partner_r and not view['last_round'] else (2.5 if version >= 3 else 1.0)
    if version == 4 and curve_soon and not partner_r and not view['last_round']:
        control_priority=-3

    @lru_cache(maxsize=4096)
    def score(state, complete=False, projected=False, attitude_target=None):
        dice, used, rudder, thrust, gear, flaps, brakes, coffee, traffic, fuel_cost = state
        value = 13 * gear.bit_count() + 14 * flaps.bit_count()
        value += sum(w for i, w in enumerate((18, 16, 10)) if brakes & (1 << i))
        value += 2.0 * coffee
        if version >= 3:
            value += sum((80 if cell['distance'] == view['distance'] else
                          40 if cell['distance'] == view['distance'] - 1 else 18) * (before - after)
                         for cell, before, after in zip(view['track'], traffic0, traffic))
        else:
            value += 18 * (sum(traffic0) - sum(traffic))
        if fuel.get('present') and not fuel['occupied']:
            # A shared field is paid once. An unseen partner can still take it
            # only when public spare capacity remains; never inspect its hand.
            partner_can_pay = view['partner_remaining'] > partner_required
            consumption = fuel_cost or (3 if partner_can_pay else 6)
            after = fuel['remaining'] - consumption
            # Leftover fuel has value only when needed in the remaining
            # rounds. In the landing round sufficient fuel is simply enough.
            if view.get('_fuel_profile') in (5,6,7,8,9):
                value += 9 * (6 - consumption)
            else:
                value -= 12 * max(0, 2.5 * future + 1 - after)
            value -= 1000 * max(0, future + 1 - after)
        required = int(not rudder) + int(not thrust)
        need = ((3 - gear.bit_count()) + int(not brakes) if role == 'pilot' else 4 - flaps.bit_count())
        spare = sum(bool(d) for d in dice) - required + 2 * future
        value -= 1000 * max(0, need - spare)
        if version >= 4:
            # Check the WHOLE hypothetical plan, not only its first placement.
            # Otherwise the search can promise later optional moves which
            # would spend the dice needed to clear public traffic.
            own_slack=spare-need
            own_radios=sum(s.target=='funk' and s.owner==role and not used & (1<<i)
                           for i,s in enumerate(slots))+(1 if role=='pilot' else 2)*future
            partner_radio_budget=partner_radios+(1 if partner=='pilot' else 2)*future
            radio_budget=max(0,min(own_slack,own_radios))+max(0,min(partner_budget['slack'],partner_radio_budget))
            shortfall=max(0,sum(traffic)-own_slack-partner_budget['slack'],sum(traffic)-radio_budget)
            value-=1000*shortfall
        wanted = min(2, ceil((view['distance'] + int(version >= 2 and rounds > 1)) / rounds))
        low, high = -2, 2
        if version >= 3 and not view['last_round'] and not view['holding']:
            # Prepare the next bend even if the currently intended speed is
            # one: an unseen partner can still supply a larger thrust die.
            lookahead = max(wanted, min(2, view['distance']))
            cells = [c for c in view['track'] if view['distance'] - lookahead < c['distance'] <= view['distance']]
            if cells:
                low, high = max(c['min'] for c in cells), min(c['max'] for c in cells)
                if low > high:
                    wanted = 1
                    cell = next(c for c in view['track'] if c['distance'] == view['distance'])
                    low, high = cell['min'], cell['max']
        desired_attitude = (0 if view['last_round'] else max(low, min(high, 0))) if attitude_target is None else attitude_target
        attitude = desired_attitude if version >= 3 else view['attitude']
        rudder_faces = set(range(1, 7))
        if rudder:
            if original_r and (partner_r or version < 3):
                attitude = view['attitude']
            elif partner_r:
                attitude = view['attitude'] + (partner_r['value'] - rudder if role == 'pilot' else rudder - partner_r['value'])
            else:
                target = rudder - view['attitude'] if role == 'pilot' else rudder + view['attitude']
                if version >= 3:
                    target += desired_attitude if role == 'pilot' else -desired_attitude
                value -= 2 * abs(target - 3.5) + 150 * max(0, 1 - target, target - 6)
                if version == 4:
                    def resulting_attitude(other):
                        return view['attitude'] + (other-rudder if role == 'pilot' else rudder-other)
                    rudder_faces = {n for n in range(1, 7) if
                        (resulting_attitude(n) == 0 if view['last_round'] else
                         low <= resulting_attitude(n) <= high and abs(resulting_attitude(n)) < 3)}
                    reachable={n for n in range(1,7) if any(abs(n-target)<=coffee for target in rudder_faces)}
                    chance = 1-(1-len(reachable)/6)**max(1, view['partner_remaining'])
                    value -= (140 if view['last_round'] else 70) * (1-chance)
                attitude = desired_attitude if version >= 3 else 0
            if version >= 3 and not view['last_round']:
                value -= 60 * max(0, low - attitude, attitude - high) + 2 * abs(attitude - desired_attitude)
            else:
                value -= (1000 if view['last_round'] else 12) * abs(attitude)
            if abs(attitude) >= 3:
                value -= 2000
        if thrust:
            blue = view['aero_blue'] + gear.bit_count() - gear0.bit_count()
            orange = view['aero_orange'] + flaps.bit_count() - flaps0.bit_count()
            brake = 2 * brakes.bit_count()

            def speed_score(other):
                speed = thrust + other
                if view['last_round']:
                    return -1000 * max(0, speed - brake)
                if view['holding']:
                    return 0
                move = int(speed >= blue) + int(speed >= orange)
                if move > view['distance']:
                    return -1500
                if rounds == 1 and move != view['distance']:
                    return -1200
                remaining = view['distance'] - move
                future_max = (int(12 >= blue) + int(12 >= orange)) if version >= 2 else 2
                target = wanted
                collision = any(count and view['distance'] - move < cell['distance'] <= view['distance']
                                for cell, count in zip(view['track'], traffic))
                pending_planes = sum(count for cell, count in zip(view['track'], traffic)
                                     if view['distance'] - move < cell['distance'] <= view['distance'])
                collision_cost = 2000 if collision else 0
                if version >= 3:
                    # The partner may still use PUBLIC spare radio slots. This
                    # is an optimistic capacity estimate, never their hand.
                    # Keeping a risk cost prevents both roles delegating every
                    # radio task to one another while spending dice on upgrades.
                    collision_cost = 2000 * max(0, pending_planes - partner_clearance) + 30 * pending_planes
                bad_curve = any(not c['min'] <= attitude <= c['max']
                                for c in view['track'] if view['distance'] - move < c['distance'] <= view['distance'])
                destination = next((c for c in view['track'] if c['distance'] == remaining), None)
                spawn_cost = 2 * destination['traffic'] if version >= 3 and destination and rounds > 1 else 0
                continuation=(40*forecast(move,attitude,gear,flaps,brakes,coffee,traffic)
                              if projected and forecast else 0)
                return (continuation-30 * abs(move - target) - spawn_cost
                        - 500 * max(0, remaining - future_max * (rounds - 1))
                        - (collision_cost if version >= 2 else 0)
                        - (2000 if version >= 3 and bad_curve else 0))

            if partner_t:
                value += speed_score(partner_t['value'])
            else:
                scores = [speed_score(n) for n in range(1, 7)]
                best = max(scores)
                good = sum(s >= best - 1 for s in scores)
                # Four unknown dice can usually supply one of the useful faces.
                miss = (1 - good / 6) ** max(1, view['partner_remaining'])
                if version == 4:
                    # Unseen faces are a prior, not an observed catastrophe.
                    # Cap the risk term: a partner may still use shared coffee
                    # or choose another useful task before publishing controls.
                    adjusted=[max(scores[actual-1]-.5*abs(actual-face) for actual in range(1,7)
                                  if abs(actual-face)<=coffee) for face in range(1,7)]
                    value += expected_best_face([max(s,best-80) for s in adjusted], view['partner_remaining'])
                    if rudder and not partner_r:
                        thrust_faces = {n for n, s in enumerate(scores, 1) if s >= best-1}
                        chance = joint_control_probability(rudder_faces, thrust_faces, view['partner_remaining'],coffee)
                        value -= 80 * (1-chance)
                else:
                    value += best - (60 if view['last_round'] else 18) * miss
        # Missing controls are permitted only while building the plan.
        if complete and required:
            value -= 3000 * required
        return value

    # Keep several possible first actions, even when their final states agree.
    nodes = [(start, None, ())]
    depth = sum(bool(d) for d in start[0])
    for _ in range(depth):
        expanded = {}
        for state, first, sequence in nodes:
            dice, used, rudder, thrust, gear, flaps, brakes, coffee, traffic, fuel_cost = state
            remaining = sum(bool(d) for d in dice)
            missing = int(not rudder) + int(not thrust)
            for die, face in enumerate(dice):
                if not face:
                    continue
                for index, slot in enumerate(slots):
                    if used & (1 << index) or slot.owner is not None and slot.owner != role:
                        continue
                    target = slot.target
                    if remaining <= missing and target not in ('ruder', 'triebwerk'):
                        continue
                    if target == 'landeklappe' and not flaps & (1 << slot.index):
                        if slot.index != flaps.bit_count():
                            continue
                    if target == 'bremse' and not brakes & (1 << slot.index):
                        if slot.index != brakes.bit_count():
                            continue
                    if target == 'fahrwerk':
                        faces = ((1, 2), (3, 4), (5, 6))[slot.index]
                    elif target == 'landeklappe':
                        faces = ((1, 2), (2, 3), (4, 5), (5, 6))[slot.index]
                    elif target == 'bremse':
                        faces = ((2,), (4,), (6,))[slot.index]
                    elif target in ('ruder', 'triebwerk', 'funk', 'kerosin'):
                        faces = range(max(1, face - coffee), min(6, face + coffee) + 1)
                    else:
                        faces = (face,)
                    for actual in faces:
                        if fuel.get('present') and view.get('_fuel_profile') in (7,8,9) and not fuel['occupied'] and not fuel_cost:
                            maximum = fuel['remaining'] - future - 1
                            if target == 'kerosin' and actual > maximum:
                                continue
                            mandatory = target in ('ruder','triebwerk')
                            if target != 'kerosin' and maximum < 6 and view['partner_remaining'] <= partner_required and remaining - 1 - (missing - int(mandatory)) < 1:
                                continue
                        cost = abs(actual - face)
                        if cost > coffee:
                            continue
                        placement = action_ids[Action('place', die=die, slot=index)]
                        action = action_ids[Action('coffee', die=die, delta=actual - face)] if cost else placement
                        if first is None and not mask[action]:
                            continue
                        next_dice = list(dice)
                        next_dice[die] = 0
                        next_traffic = traffic
                        if target == 'funk':
                            distance = view['distance'] - actual + 1
                            cell = next((i for i, c in enumerate(view['track']) if c['distance'] == distance), None)
                            if cell is not None and traffic[cell]:
                                next_traffic = traffic[:cell] + (traffic[cell] - 1,) + traffic[cell + 1:]
                        next_state = (tuple(next_dice), used | (1 << index), actual if target == 'ruder' else rudder,
                                      actual if target == 'triebwerk' else thrust,
                                      gear | (1 << slot.index) if target == 'fahrwerk' else gear,
                                      flaps | (1 << slot.index) if target == 'landeklappe' else flaps,
                                      brakes | (1 << slot.index) if target == 'bremse' else brakes,
                                      min(3, coffee - cost + int(target == 'konzentration')), next_traffic,
                                      actual if target == 'kerosin' else fuel_cost)
                        head = action if first is None else first
                        key = (next_state, head)
                        if key not in expanded:
                            expanded[key] = (next_state, head, sequence + ((die, index, actual, cost),))
        if not expanded:
            break
        def rank(node):
            priority = 0
            if version >= 3 and node[2]:
                priority = control_priority if slots[node[2][0][1]].target == 'ruder' else 0
                die, index, actual, _cost = node[2][0]
                if slots[index].target == 'funk' and actual == 1 and any(
                        c['distance'] == view['distance'] and c['planes'] for c in view['track']):
                    priority = 20
            return score(node[0], _ == depth - 1) + priority
        nodes = sorted(expanded.values(), key=rank, reverse=True)[:beam]
    if forecast:
        # Keep several persistent preparation alternatives, sharing their
        # continuation model across action orders and current control faces.
        groups=[]
        for node in sorted(nodes,key=lambda n:score(n[0],True),reverse=True):
            key=node[0][4:]
            if key not in groups:
                groups.append(key)
            if len(groups)==4:
                break
        nodes=[n for n in nodes if n[0][4:] in groups]
    ranked, sequences = {}, {}
    for state, first, sequence in nodes:
        if first is None:
            continue
        quality = (max(score(state,True,True,target) for target in range(-2,3))
                   if forecast else score(state,True))
        first_slot = slots[sequence[0][1]]
        # Publish a control early so a partner can respond before spending dice.
        quality += control_priority if first_slot.target == 'ruder' else 0.2 if first_slot.target == 'triebwerk' else 0
        if version >= 3 and first_slot.target == 'funk' and sequence[0][2] == 1 and any(
                c['distance'] == view['distance'] and c['planes'] for c in view['track']):
            quality += 20
        if quality > ranked.get(first, float('-inf')):
            ranked[first], sequences[first] = quality, sequence
    return ranked, sequences


def assisted_mask(view, mask, *, version=1):
    return list(_cached_mask(json.dumps(view, sort_keys=True, separators=(',', ':')), tuple(mask), version))


# Balanced probes, deliberately independent of the engine and its future RNG.
# Single-die rerolls and hands with at most two dice are enumerated exactly.
_REROLL_PROBES=((1,2,6,3),(2,5,4,1),(3,1,2,6),(4,6,5,2),(5,3,1,4),(6,4,3,5),
                (4,1,2,5),(1,3,6,4),(6,6,3,1),(2,4,1,6),(5,2,5,3),(3,5,4,2))


def _future_action_mask(view,coffee=False):
    from .public_rules import legal_placement_in_view
    result=[]
    for action in ACTIONS:
        valid=action.kind=='place' and legal_placement_in_view(view,action)
        if coffee and action.kind=='coffee':
            face=view['own_dice'][action.die]
            valid=bool(face) and abs(action.delta)<=view['coffee'] and 1<=face+action.delta<=6
        result.append(valid)
    return capacity_mask(view,result,include_traffic=True)


@lru_cache(maxsize=5)
def _weighted_rolls(count):
    """Every unordered iid outcome, with its number of ordered realizations."""
    return tuple((faces,factorial(count)//prod(factorial(faces.count(n)) for n in set(faces)))
                 for faces in combinations_with_replacement(range(1,7),count))


def _choose_reroll(view,eligible,current_quality,*,exact=False):
    none=next((i for i in eligible if not ACTIONS[i].subset),None)
    if none is not None and current_quality>=-100:
        return none
    available_indices=[i for i,d in enumerate(view['own_dice']) if d]
    available=len(available_indices)
    quality_cache={}
    def quality(dice):
        # Base-game dice have no identity-dependent effects. Canonicalizing
        # only available positions shares at most C(9,4)=126 leaf searches
        # across every possible four-die reroll subset.
        key=tuple(sorted(dice[i] for i in available_indices)) if exact else tuple(dice)
        if key not in quality_cache:
            if exact:
                dice=list(dice)
                for i,face in zip(available_indices,key):
                    dice[i]=face
            changed={**view,'own_dice':dice,'reroll':None}
            ranked,_=plan_actions(changed,_future_action_mask(changed,coffee=True),
                                  version=3,beam=24 if available<=2 else 8)
            quality_cache[key]=max(ranked.values(),default=-10000)
        return quality_cache[key]
    scores={}
    for action_id in eligible:
        indices=[j for j in range(4) if ACTIONS[action_id].subset & (1<<j)]
        if not indices:
            qualities=[(current_quality,1)]
        else:
            rolls=(_weighted_rolls(len(indices)) if exact else
                   ((faces,1) for faces in (product(range(1,7),repeat=len(indices)) if available<=2 or len(indices)==1
                   else (tuple(row[j] for j in indices) for row in _REROLL_PROBES))))
            qualities=[]
            for faces,weight in rolls:
                dice=list(view['own_dice'])
                for index,face in zip(indices,faces):
                    dice[index]=face
                # An optimistic own-hand rescue test, rather than a prediction
                # of the partner's private dice or their eventual decisions.
                qualities.append((quality(dice),weight))
        total=sum(weight for _,weight in qualities)
        scores[action_id]=(sum(weight for q,weight in qualities if q>=-100)/total,
            sum(max(-3000,min(500,q))*weight for q,weight in qualities)/total,-len(indices))
    return max(eligible,key=lambda i:(*scores[i],-i))


@lru_cache(maxsize=512)
def _cached_mask(serialized_view, mask, version):
    return tuple(_assisted_mask(json.loads(serialized_view), mask, version))


def _assisted_mask(view, mask, version, *, placement_margin=None):
    """Conservative capacity plus a practical own-hand planning shortlist.

    This profile is deliberately a hybrid player, not a claim that all pruned
    actions are rule-illegal. The neural policy ranks the remaining alternatives.
    """
    if version==10:
        return _assisted_mask({**view,'_horizon':True},mask,3)
    if version in (6,7,8,9):
        if version in (7,8,9):
            view={**view,'_smart_reroll':True}
        if version==9:
            view={**view,'_exact_reroll':True}
        return _assisted_mask(view,mask,4 if version not in (8,9) and view['role']=='pilot' else 3)
    base = capacity_mask(view, mask, include_traffic=version >= 3)
    planning_mask = list(base)
    for i, action in enumerate(ACTIONS):
        if action.kind in ('reroll_start', 'reroll_select'):
            planning_mask[i] = False
    # During reroll selection use normal placements for hypothetical own plans.
    if view['reroll']:
        if view.get('_smart_reroll'):
            planning_mask=_future_action_mask(view,coffee=True)
        else:
            from .public_rules import legal_placement_in_view
            planning_mask = [a.kind == 'place' and legal_placement_in_view(view, a) for a in ACTIONS]
            planning_mask = capacity_mask(view, planning_mask, include_traffic=version >= 3)
    ranked, sequences = plan_actions(view, planning_mask, version=version, beam=64 if version >= 3 else 24)
    best = max(ranked.values(), default=-10000)
    rescue_score = best
    if version >= 4 and best < -100:
        # A reroll must be justified by our visible hand, rather than solely
        # by hypothetical bad faces in the partner's unseen hand.
        optimistic, _ = plan_actions(view, planning_mask, version=3, beam=64)
        rescue_score = max(optimistic.values(),default=-10000)
    result = [False] * len(mask)
    if view['reroll']:
        if rescue_score < -100:
            wanted = sum(1 << i for i, d in enumerate(view['own_dice']) if d)
        else:
            wanted = 0
        eligible = [i for i, a in enumerate(ACTIONS) if base[i] and a.kind == 'reroll_select']
        if eligible:
            selected = (_choose_reroll(view,eligible,rescue_score,exact=view.get('_exact_reroll',False)) if view.get('_smart_reroll') else
                        min(eligible, key=lambda i: (ACTIONS[i].subset ^ wanted).bit_count()))
            result[selected] = True
    else:
        for i, quality in ranked.items():
            margin = 3 if version == 4 and ACTIONS[i].kind == 'place' else 1.5
            if placement_margin is not None and ACTIONS[i].kind == 'place':
                margin = placement_margin
            if base[i] and quality >= best - margin:
                result[i] = True
        reroll = ACTION_IDS[Action('reroll_start')]
        if base[reroll] and rescue_score < -100:
            result = [False] * len(mask)
            result[reroll] = True
    return result if any(result) else base
