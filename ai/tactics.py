"""Small public-information round planner and conservative landing capacity.

This module is torch-free and also runs in Pyodide. It never receives a game,
the partner's hand, or a random generator. The optional assistance profile is
separate from the historical legal-action mask, so old checkpoints and human
demonstrations retain their meaning.
"""
from math import ceil
from functools import lru_cache
import json

from .actions import ACTIONS, ACTION_IDS, Action, SLOTS, ROLES

ASSISTANCE_VERSION = 1
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


def capacity_mask(view, mask):
    """Remove only moves that cross from feasible to provably insufficient.

    Already impossible states retain their ordinary actions, including rescue
    resources: an empty policy distribution is never manufactured here.
    """
    result = list(mask)
    budget = capacity(view)
    if budget['slack'] != 0:
        return result
    for i, valid in enumerate(mask):
        if not valid or ACTIONS[i].kind != 'place':
            continue
        s = SLOTS[ACTIONS[i].slot]
        useful = (s.target in ('ruder', 'triebwerk')
                  or s.target == 'fahrwerk' and not view['gear'][s.index]
                  or s.target == 'landeklappe' and not view['flaps'][s.index]
                  or s.target == 'bremse' and view['brakes'] < 2 and not view['brake_progress'][s.index])
        if not useful:
            result[i] = False
    return result if any(result) else list(mask)


def _bits(values):
    return sum(1 << i for i, value in enumerate(values) if value)


def plan_actions(view, mask, *, beam=24):
    """Rank the first macro action of complete plans for the visible own hand.

    Coffee followed by placement is evaluated as one operation; only its first
    ordinary action is returned. Unseen partner dice are represented by an
    optimistic distribution over faces, not sampled or read from the engine.
    """
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
             _bits(view['brake_progress']), view['coffee'], traffic0)
    rounds = max(1, int(view['height'] // 1000))
    future = 0 if view['last_round'] else int(view['height'] // 1000)

    def score(state, complete=False):
        dice, used, rudder, thrust, gear, flaps, brakes, coffee, traffic = state
        value = 13 * gear.bit_count() + 14 * flaps.bit_count()
        value += sum(w for i, w in enumerate((18, 16, 10)) if brakes & (1 << i))
        value += 2.0 * coffee + 18 * (sum(traffic0) - sum(traffic))
        required = int(not rudder) + int(not thrust)
        need = ((3 - gear.bit_count()) + int(not brakes) if role == 'pilot' else 4 - flaps.bit_count())
        spare = sum(bool(d) for d in dice) - required + 2 * future
        value -= 1000 * max(0, need - spare)
        if rudder:
            if original_r:
                attitude = view['attitude']
            elif partner_r:
                attitude = view['attitude'] + (partner_r['value'] - rudder if role == 'pilot' else rudder - partner_r['value'])
            else:
                target = rudder - view['attitude'] if role == 'pilot' else rudder + view['attitude']
                value -= 2 * abs(target - 3.5) + 150 * max(0, 1 - target, target - 6)
                attitude = 0
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
                return (-30 * abs(move - min(2, ceil(view['distance'] / rounds)))
                        - 500 * max(0, remaining - 2 * (rounds - 1)))

            if partner_t:
                value += speed_score(partner_t['value'])
            else:
                scores = [speed_score(n) for n in range(1, 7)]
                best = max(scores)
                good = sum(s >= best - 1 for s in scores)
                # Four unknown dice can usually supply one of the useful faces.
                miss = (1 - good / 6) ** max(1, view['partner_remaining'])
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
            dice, used, rudder, thrust, gear, flaps, brakes, coffee, traffic = state
            remaining = sum(bool(d) for d in dice)
            missing = int(not rudder) + int(not thrust)
            for die, face in enumerate(dice):
                if not face:
                    continue
                for index, slot in enumerate(SLOTS):
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
                    elif target in ('ruder', 'triebwerk', 'funk'):
                        faces = range(max(1, face - coffee), min(6, face + coffee) + 1)
                    else:
                        faces = (face,)
                    for actual in faces:
                        cost = abs(actual - face)
                        if cost > coffee:
                            continue
                        placement = ACTION_IDS[Action('place', die=die, slot=index)]
                        action = ACTION_IDS[Action('coffee', die=die, delta=actual - face)] if cost else placement
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
                                      min(3, coffee - cost + int(target == 'konzentration')), next_traffic)
                        head = action if first is None else first
                        key = (next_state, head)
                        if key not in expanded:
                            expanded[key] = (next_state, head, sequence + ((die, index, actual, cost),))
        if not expanded:
            break
        nodes = sorted(expanded.values(), key=lambda n: score(n[0], _ == depth - 1), reverse=True)[:beam]
    ranked, sequences = {}, {}
    for state, first, sequence in nodes:
        if first is None:
            continue
        quality = score(state, True)
        first_slot = SLOTS[sequence[0][1]]
        # Publish a control early so a partner can respond before spending dice.
        quality += 1.0 if first_slot.target == 'ruder' else 0.2 if first_slot.target == 'triebwerk' else 0
        if quality > ranked.get(first, float('-inf')):
            ranked[first], sequences[first] = quality, sequence
    return ranked, sequences


def assisted_mask(view, mask):
    return list(_cached_mask(json.dumps(view, sort_keys=True, separators=(',', ':')), tuple(mask)))


@lru_cache(maxsize=512)
def _cached_mask(serialized_view, mask):
    return tuple(_assisted_mask(json.loads(serialized_view), mask))


def _assisted_mask(view, mask):
    """Conservative capacity plus a practical own-hand planning shortlist.

    This profile is deliberately a hybrid player, not a claim that all pruned
    actions are rule-illegal. The neural policy ranks the remaining alternatives.
    """
    base = capacity_mask(view, mask)
    planning_mask = list(base)
    for i, action in enumerate(ACTIONS):
        if action.kind in ('reroll_start', 'reroll_select'):
            planning_mask[i] = False
    # During reroll selection use normal placements for hypothetical own plans.
    if view['reroll']:
        from .public_rules import legal_placement_in_view
        planning_mask = [a.kind == 'place' and legal_placement_in_view(view, a) for a in ACTIONS]
        planning_mask = capacity_mask(view, planning_mask)
    ranked, sequences = plan_actions(view, planning_mask)
    best = max(ranked.values(), default=-10000)
    result = [False] * len(mask)
    if view['reroll']:
        if best < -100:
            wanted = sum(1 << i for i, d in enumerate(view['own_dice']) if d)
        else:
            wanted = 0
        eligible = [i for i, a in enumerate(ACTIONS) if base[i] and a.kind == 'reroll_select']
        if eligible:
            selected = min(eligible, key=lambda i: (ACTIONS[i].subset ^ wanted).bit_count())
            result[selected] = True
    else:
        for i, quality in ranked.items():
            if base[i] and quality >= best - 1.5:
                result[i] = True
        reroll = ACTION_IDS[Action('reroll_start')]
        if base[reroll] and best < -100:
            result = [False] * len(mask)
            result[reroll] = True
    return result if any(result) else base
