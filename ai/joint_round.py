"""Exact static dice assignments for hypothetical future hands.

Both controls and additional tasks consume distinct dice. Coffee is a single
shared budget, and an explicitly supplied black die belongs to only one role.
The fair-hand prior contains no engine state or RNG. This is a building block
for a search teacher, not a game win probability: sequencing, new coffee,
rerolls, card triggers and future traffic still require a game-level planner.
"""
from functools import lru_cache
from itertools import combinations_with_replacement, product
from math import factorial, inf, prod


def _fair_hands():
    return tuple((h, factorial(4) // prod(factorial(h.count(v)) for v in set(h)))
                 for h in combinations_with_replacement(range(1, 7), 4))


HANDS = _fair_hands()
PAIRS = tuple((r, t) for r in range(1, 7) for t in range(1, 7))


def _tasks(requirements):
    result = tuple(sorted(tuple(sorted(set(values))) for values in requirements))
    if any(not values or any(type(v) is not int or not 1 <= v <= 6 for v in values) for values in result):
        raise ValueError('Every task needs permitted integer faces in 1..6.')
    return result


def _hand(values):
    values = tuple(values)
    if len(values) > 4 or any(type(v) is not int or not 1 <= v <= 6 for v in values):
        raise ValueError('A regular hypothetical hand has at most four integer faces in 1..6.')
    return tuple(sorted(values))


@lru_cache(maxsize=16384)
def _task_cost(hand, requirements):
    if len(requirements) > len(hand):
        return inf
    if not requirements:
        return 0
    return min((min(abs(face - target) for target in requirements[0])
                + _task_cost(hand[:i] + hand[i + 1:], requirements[1:])
                for i, face in enumerate(hand)), default=inf)


@lru_cache(maxsize=16384)
def _options(hand, requirements):
    """Minimum task coffee for each reserved, unadjusted rudder/thrust pair."""
    costs = [inf] * 36
    if len(requirements) + 2 > len(hand):
        return tuple(costs)
    for i, rudder in enumerate(hand):
        for j, thrust in enumerate(hand):
            if i == j:
                continue
            rest = tuple(v for k, v in enumerate(hand) if k not in (i, j))
            pair = (rudder - 1) * 6 + thrust - 1
            costs[pair] = min(costs[pair], _task_cost(rest, requirements))
    return tuple(costs)


@lru_cache(maxsize=512)
def _control_costs(delta, low, high):
    # Rudder and thrust adjustments use different reserved dice. Projection
    # onto the permitted difference/sum intervals gives their exact L1 cost.
    return tuple(tuple(abs(c - a - delta) + max(0, low - b - d, b + d - high)
                       for c, d in PAIRS) for a, b in PAIRS)


def _constraints(delta, low, high):
    if any(type(v) is not int for v in (delta, low, high)):
        raise ValueError('Control constraints must be integer face sums/differences.')
    return max(2, low), min(12, high)


def _allocations(pilot_tasks, copilot_tasks, shared_tasks, shared_face):
    extras = (((), ()),) if shared_face is None else (((shared_face,), ()), ((), (shared_face,)))
    for owners in product((0, 1), repeat=len(shared_tasks)):
        p = tuple(sorted(pilot_tasks + tuple(t for t, r in zip(shared_tasks, owners) if r == 0)))
        c = tuple(sorted(copilot_tasks + tuple(t for t, r in zip(shared_tasks, owners) if r == 1)))
        for p_extra, c_extra in extras:
            yield p, c, p_extra, c_extra


def minimum_coffee(pilot, copilot, delta, low, high, pilot_tasks=(), copilot_tasks=(), *,
                   shared_face=None, shared_tasks=()):
    """Minimum static budget for supplied hypothetical hands; inf if impossible.

    delta is copilot rudder minus pilot rudder. Optional task face sets are
    role-specific. A supplied shared die may be assigned to either role once.
    """
    pilot, copilot = _hand(pilot), _hand(copilot)
    p_tasks, c_tasks, shared_tasks = _tasks(pilot_tasks), _tasks(copilot_tasks), _tasks(shared_tasks)
    low, high = _constraints(delta, low, high)
    if shared_face is not None:
        _hand((shared_face,))
    if abs(delta) > 5 or low > high or len(p_tasks) + len(c_tasks) + len(shared_tasks) + 4 > len(pilot) + len(copilot) + int(shared_face is not None):
        return inf
    control = _control_costs(delta, low, high)
    best = inf
    for p_req, c_req, p_extra, c_extra in _allocations(p_tasks, c_tasks, shared_tasks, shared_face):
        p = _options(tuple(sorted(pilot + p_extra)), p_req)
        c = _options(tuple(sorted(copilot + c_extra)), c_req)
        for i, p_cost in enumerate(p):
            if p_cost >= best:
                continue
            for j, c_cost in enumerate(c):
                best = min(best, p_cost + c_cost + control[i][j])
                if best == 0:
                    return 0
    return best


@lru_cache(maxsize=1024)
def _compatible_hands(delta, low, high, coffee, requirements, extra):
    """Bitsets of copilot hands compatible with each pilot pair and budget."""
    by_budget = [[0] * 36 for _ in range(coffee + 1)]
    for index, (hand, _) in enumerate(HANDS):
        for pair, cost in enumerate(_options(tuple(sorted(hand + extra)), requirements)):
            if cost <= coffee:
                for budget in range(int(cost), coffee + 1):
                    by_budget[budget][pair] |= 1 << index
    control = _control_costs(delta, low, high)
    result = []
    for budget in range(coffee + 1):
        masks = []
        for costs in control:
            allowed = 0
            for pair, cost in enumerate(costs):
                if cost <= budget:
                    allowed |= by_budget[budget - cost][pair]
            masks.append(allowed)
        result.append(tuple(masks))
    return tuple(result)


@lru_cache(maxsize=4096)
def _weight(bits):
    total = 0
    while bits:
        first = bits & -bits
        total += HANDS[first.bit_length() - 1][1]
        bits ^= first
    return total


@lru_cache(maxsize=4096)
def _prior(delta, low, high, coffee, pilot_tasks, copilot_tasks, shared_face, shared_tasks):
    masks = [0] * len(HANDS)
    for p_req, c_req, p_extra, c_extra in _allocations(pilot_tasks, copilot_tasks, shared_tasks, shared_face):
        compatible = _compatible_hands(delta, low, high, coffee, c_req, c_extra)
        for index, (hand, _) in enumerate(HANDS):
            for pair, cost in enumerate(_options(tuple(sorted(hand + p_extra)), p_req)):
                if cost <= coffee:
                    masks[index] |= compatible[coffee - int(cost)][pair]
    return sum(weight * _weight(bits) for (_, weight), bits in zip(HANDS, masks)) / 6 ** 8


def assignment_prior(delta, low, high, coffee, pilot_tasks=(), copilot_tasks=(), *, shared_face=None, shared_tasks=()):
    """Exact probability of this static assignment under two fair four-die hands.

    Shared-die ownership is chosen per hypothetical pair of hands and successful
    hands are unioned before counting; never add two ownership probabilities.
    Passing shared_face asserts availability, not merely possession of a card.
    """
    low, high = _constraints(delta, low, high)
    p, c, shared_tasks = _tasks(pilot_tasks), _tasks(copilot_tasks), _tasks(shared_tasks)
    if type(coffee) is not int or not 0 <= coffee <= 3:
        raise ValueError('The shared stored coffee budget must be in 0..3.')
    if shared_face is not None:
        _hand((shared_face,))
    if abs(delta) > 5 or low > high or len(p) + len(c) + len(shared_tasks) > 4 + int(shared_face is not None):
        return 0.
    return _prior(delta, low, high, coffee, p, c, shared_face, shared_tasks)
