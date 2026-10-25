"""Exact control expectation under a declared hypothetical fair-hand model.

The caller supplies scores for36 possible partner rudder/thrust pairs. Unknown
remaining dice are IID fair in this MODEL, not read from the actual partner.
Published pair members consume no remaining die. Two unpublished controls
must use different dice; all adjustments share one supplied coffee budget.
Public action selection can bias the real remaining hand, so this is not a
calibrated posterior or a win probability. No engine instance or RNG is used.
"""
from functools import lru_cache
from itertools import combinations_with_replacement, permutations, product
from math import factorial, isfinite, prod


IMPOSSIBLE = -20_000.
_REACHABILITY = {}


@lru_cache(maxsize=5)
def fair_hands(count):
    if type(count) is not int or not 0 <= count <= 4:
        raise ValueError('Use0..4 hypothetical remaining regular dice.')
    return tuple((hand, factorial(count) // prod(factorial(hand.count(face)) for face in set(hand)))
                 for hand in combinations_with_replacement(range(1, 7), count))


def _reachability(count, missing, cooperate=None):
    """For each target, bitsets of fair hands reachable at coffee<=0..3."""
    key = count, missing
    if key in _REACHABILITY:
        return _REACHABILITY[key]
    targets = tuple(product(range(1, 7), repeat=missing))
    masks = [[0] * len(targets) for _ in range(4)]
    if count >= missing:
        for number, (hand, _) in enumerate(fair_hands(count)):
            if cooperate is not None: cooperate()
            assignments = tuple(permutations(hand, missing))
            for index, target in enumerate(targets):
                cost = min(sum(abs(face - goal) for face, goal in zip(values, target)) for values in assignments)
                for budget in range(cost, 4):
                    masks[budget][index] |= 1 << number
    result = targets, tuple(tuple(row) for row in masks)
    _REACHABILITY[key] = result
    return result


@lru_cache(maxsize=8192)
def _weight(count, bits):
    hands = fair_hands(count)
    result = 0
    while bits:
        bit = bits & -bits
        result += hands[bit.bit_length() - 1][1]
        bits ^= bit
    return result


def fair_control_value(pair_scores, remaining, coffee, *, rudder=None, thrust=None,
                       coffee_value=1.5, cooperate=None):
    """E[max pair score + retained coffee value] over independent FAIR hands.

    One own plan is fixed BEFORE the expectation. The hidden hypothetical
    partner may choose its best compatible pair within that hand. Maxima are
    unioned per hand before probability weighting; no double counting across
    assignments, coffee allocations or duplicated equal-face dice.
    """
    if (len(pair_scores) != 36 or any(type(score) not in (int, float) or not isfinite(score) for score in pair_scores)
            or type(remaining) is not int or not 0 <= remaining <= 4
            or type(coffee) is not int or not 0 <= coffee <= 3
            or type(coffee_value) not in (int, float) or not isfinite(coffee_value) or coffee_value < 0):
        raise ValueError('Use36 finite pair scores,0..4 dice,0..3 coffee and nonnegative coffee value.')
    if any(face is not None and (type(face) is not int or not 1 <= face <= 6) for face in (rudder, thrust)):
        raise ValueError('Published controls must be known integer faces1..6 or None.')
    missing = int(rudder is None) + int(thrust is None)
    if remaining < missing:
        return IMPOSSIBLE
    if not missing:
        return pair_scores[(rudder - 1) * 6 + thrust - 1] + coffee_value * coffee
    targets, masks = _reachability(remaining, missing, cooperate)
    by_quality = {}
    for index, target in enumerate(targets):
        r = target[0] if rudder is None else rudder
        t = target[-1] if thrust is None else thrust
        score = pair_scores[(r - 1) * 6 + t - 1]
        for cost in range(coffee + 1):
            bits = masks[cost][index]
            if bits:
                quality = score + coffee_value * (coffee - cost)
                by_quality[quality] = by_quality.get(quality, 0) | bits
    covered, total = 0, 0.
    for quality in sorted(by_quality, reverse=True):
        if cooperate is not None: cooperate()
        new = by_quality[quality] & ~covered
        if new:
            total += quality * _weight(remaining, new)
            covered |= new
    all_hands = (1 << len(fair_hands(remaining))) - 1
    # Every hypothetical hand with enough dice can at least play its original
    # control faces at zero coffee. A missing hand is an implementation error.
    if covered != all_hands:
        raise RuntimeError('Incomplete fair-hand assignment coverage.')
    return total / 6 ** remaining
