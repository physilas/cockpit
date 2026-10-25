"""Experimental public continuation heuristic with joint task/control assignments.

Supports base game and kerosene, without cards. Fair future hands, preparation,
radios, shared fuel and coffee compete for the same eight dice. Traffic spawns
and the choice of plans before hypothetical hands are revealed remain
approximations. This is not a calibrated win probability.
"""
from functools import lru_cache
from itertools import combinations
from math import ceil, exp

from .actions import SLOTS
from .joint_round import assignment_prior


def make_joint_forecast(view, *, cooperate=None):
    modules = view.get('modules_state', {})
    if set(modules.get('modules', [])) - {'kerosene'} or modules.get('cards'):
        raise ValueError('This experimental forecast supports base/kerosene without cards.')
    cells = tuple((c['distance'], c['min'], c['max'], c['traffic']) for c in view['track'])
    blue0 = view['aero_blue'] - sum(view['gear'])
    orange0 = view['aero_orange'] - sum(view['flaps'])
    fuel = view.get('fuel', {})
    fuel_present = bool(fuel.get('present'))
    height = int(view['height'] // 1000)
    partner = 'kopilot' if view['role'] == 'pilot' else 'pilot'
    missing = sum(s.owner == partner and s.target in ('ruder', 'triebwerk') and view['board'][i] is None
                  for i, s in enumerate(SLOTS))
    radios = sum(s.owner == partner and s.target == 'funk' and view['board'][i] is None
                 for i, s in enumerate(SLOTS))
    partner_clearance = max(0, min(radios, view['partner_remaining'] - missing))

    def fuel_choices(remaining, rounds):
        # Reserve at least one for each later round, and one to stay alive.
        return range(1, min(6, remaining - rounds) + 1) if fuel_present else (0,)

    def chance(delta, low, high, coffee, p, c, consumption):
        shared = ((consumption,),) if fuel_present else ()
        spare = 4 - len(p) - len(c) - int(fuel_present)
        if spare < 0:
            return ()
        coins = coffee + min(3, spare)
        # A fixed spend bound gives a guaranteed lower bound on coffee left.
        # Unused dice can first make coffee; availability remains capped at 3.
        def probabilities():
            for spent in range(min(3, coins) + 1):
                if cooperate is not None:cooperate()
                yield assignment_prior(delta, low, high, spent, p, c, shared_tasks=shared), min(3, coins - spent)
        return probabilities()

    @lru_cache(maxsize=256)
    def pilot_options(gear, brakes):
        options = []
        missing = [i for i in range(3) if not gear & (1 << i)]
        for count in range(min(2, len(missing)) + 1):
            for chosen in combinations(missing, count):
                new_gear = gear | sum(1 << i for i in chosen)
                p = tuple(((1, 2), (3, 4), (5, 6))[i] for i in chosen)
                for extra in range(min(2 - count, 3 - brakes) + 1):
                    tasks = p + tuple(((2, 4, 6)[i],) for i in range(brakes, brakes + extra))
                    options.append((new_gear, brakes + extra, tasks))
        return tuple(options)

    def radio_allocations(faces, p, c):
        # Pilot has one radio; copilot has two. Mission tasks consume the same
        # two optional slots per role. Different radio faces are not exchangeable.
        allocations = set()
        if len(faces) <= min(2, 2 - len(c)):
            allocations.add((p, c + tuple((face,) for face in faces)))
        if len(p) < 2 and len(faces) - 1 <= min(2, 2 - len(c)):
            for index, face in enumerate(faces):
                allocations.add((p + ((face,),), c + tuple((f,) for i, f in enumerate(faces) if i != index)))
        return tuple(allocations)

    def clear(traffic, distance, count):
        changed, faces = list(traffic), []
        for i in sorted(range(len(cells)), key=lambda i: cells[i][0], reverse=True):
            face = distance - cells[i][0] + 1
            if 1 <= face <= 6:
                take = min(changed[i], count - len(faces))
                changed[i] -= take
                faces.extend([face] * take)
                if len(faces) == count:
                    break
        return tuple(changed), tuple(faces)

    @lru_cache(maxsize=4096)
    def landing(attitude, gear, flaps, brakes, coffee, traffic, remaining_fuel):
        if cooperate is not None:cooperate()
        if any(n and cells[i][0] != 0 for i, n in enumerate(traffic)):
            return 0.
        p_gear = tuple(((1, 2), (3, 4), (5, 6))[i] for i in range(3) if not gear & (1 << i))
        c = tuple(((1, 2), (2, 3), (4, 5), (5, 6))[i] for i in range(flaps.bit_count(), 4))
        if len(p_gear) > 2 or len(c) > 2:
            return 0.
        best = 0.
        for extra in range(int(not brakes), min(2 - len(p_gear), 3 - brakes) + 1):
            p = p_gear + tuple(((2, 4, 6)[i],) for i in range(brakes, brakes + extra))
            for p_tasks, c_tasks in radio_allocations((1,) * sum(traffic), p, c):
                for consumption in fuel_choices(remaining_fuel, 1):
                    for probability, _ in chance(-attitude, 2, 2 * (brakes + extra), coffee, p_tasks, c_tasks, consumption):
                        best = max(best, probability)
        return best

    @lru_cache(maxsize=8192)
    def future(distance, attitude, gear, flaps, brakes, coffee, traffic, remaining_fuel, h):
        if cooperate is not None:cooperate()
        if distance < 0 or distance > 2 * h or any(n and cells[i][0] > distance for i, n in enumerate(traffic)):
            return 0.
        if h == 0:
            return landing(attitude, gear, flaps, brakes, coffee, traffic, remaining_fuel) if distance == 0 else 0.
        best = 0.
        for g, b, p in pilot_options(gear, brakes):
            if 3 - g.bit_count() + int(not b) > 2 * h:
                continue
            for flap_count in range(min(2, 4 - flaps.bit_count()) + 1):
                f = flaps | sum(1 << i for i in range(flaps.bit_count(), flaps.bit_count() + flap_count))
                if 4 - f.bit_count() > 2 * h:
                    continue
                c = tuple(((1, 2), (2, 3), (4, 5), (5, 6))[i]
                          for i in range(flaps.bit_count(), flaps.bit_count() + flap_count))
                maximum = min(sum(traffic), min(1, 2 - len(p)) + min(2, 2 - len(c)),
                              4 - len(p) - len(c) - int(fuel_present))
                blue, orange = ceil(blue0 + g.bit_count()), ceil(orange0 + f.bit_count())
                for move in range(min(2, distance) + 1):
                    crossed = [i for i, cell in enumerate(cells) if distance - move < cell[0] <= distance]
                    needed = sum(traffic[i] for i in crossed)
                    if needed > maximum:
                        continue
                    low, high = (2, 12) if distance == 0 else ((2, blue - 1), (blue, orange - 1), (orange, 12))[move]
                    for count in sorted({needed, min(maximum, needed + 1)}):
                        remaining, faces = clear(traffic, distance, count)
                        if len(faces) != count or any(remaining[i] for i in crossed):
                            continue
                        for p_tasks, c_tasks in radio_allocations(faces, p, c):
                            for consumption in fuel_choices(remaining_fuel, h + 1):
                                for target in range(-2, 3):
                                    if any(not cells[i][1] <= target <= cells[i][2] for i in crossed):
                                        continue
                                    for probability, next_coffee in chance(target - attitude, low, high, coffee,
                                                                           p_tasks, c_tasks, consumption):
                                        if probability <= best:
                                            continue
                                        tail = future(distance - move, target, g, f, b, next_coffee, remaining,
                                                      remaining_fuel - consumption, h - 1)
                                        stars = next((cell[3] for cell in cells if cell[0] == distance), 0)
                                        best = max(best, probability * tail * exp(-.08 * stars))
        return best

    @lru_cache(maxsize=1024)
    def after_round(move, attitude, gear, flaps, brakes, coffee, traffic, *, fuel_cost=0):
        distance = view['distance'] - move
        passed = [i for i, cell in enumerate(cells) if distance < cell[0] <= view['distance']]
        if sum(traffic[i] for i in passed) > partner_clearance:
            return 0.
        traffic = tuple(0 if i in passed else n for i, n in enumerate(traffic))
        # A not-yet-paid partner fuel value remains optimistic at one. Its hand
        # is never inspected; known hypothetical own consumption is used exactly.
        consumption = (fuel_cost or 1) if fuel_present and not fuel.get('occupied') else 0
        return future(distance, attitude, gear, flaps, brakes.bit_count(), coffee, traffic,
                      fuel.get('remaining', 0) - consumption, height - 1)

    return after_round
