"""Analytic fair-control expectation checked against counts and ordered dice."""
from itertools import permutations, product
import random
import unittest

from ai.public_hand_prior import fair_control_value, fair_hands, IMPOSSIBLE


class PublicHandPriorTests(unittest.TestCase):
    def test_multiset_weights_equal_all_ordered_fair_rolls(self):
        for count in range(5):
            self.assertEqual(sum(weight for _, weight in fair_hands(count)), 6 ** count)
        self.assertEqual(len(fair_hands(4)), 126)

    def test_two_equal_controls_need_two_different_hypothetical_dice(self):
        scores = tuple(float(r == t == 1) for r in range(1, 7) for t in range(1, 7))
        self.assertEqual(fair_control_value(scores, 1, 0, coffee_value=0), IMPOSSIBLE)
        self.assertAlmostEqual(fair_control_value(scores, 2, 0, coffee_value=0), 1 / 36)
        self.assertAlmostEqual(fair_control_value(scores, 3, 0, coffee_value=0), 16 / 216)
        self.assertAlmostEqual(fair_control_value(scores, 1, 0, rudder=1, coffee_value=0), 1 / 6)
        self.assertEqual(fair_control_value(scores, 0, 3, rudder=1, coffee_value=0), IMPOSSIBLE)

    def test_adjustments_share_one_coffee_budget_and_union_each_hand_once(self):
        scores = tuple(float(r == t == 1) for r in range(1, 7) for t in range(1, 7))
        self.assertAlmostEqual(fair_control_value(scores, 2, 1, coffee_value=0), 3 / 36)
        self.assertAlmostEqual(fair_control_value(scores, 2, 2, coffee_value=0), 6 / 36)
        any_one = tuple(float(r == 1 or t == 1) for r in range(1, 7) for t in range(1, 7))
        self.assertAlmostEqual(fair_control_value(any_one, 2, 0, coffee_value=0), 11 / 36)

    def test_arbitrary_score_max_matches_independent_ordered_roll_enumeration(self):
        scores = tuple(float(9 * (r == t) - abs(r - 3) - t) for r in range(1, 7) for t in range(1, 7))
        before, rng = tuple(scores), random.getstate()
        total = 0.
        for hand in product(range(1, 7), repeat=2):
            best = -float('inf')
            for first, second in permutations(range(2), 2):
                for r, t in product(range(1, 7), repeat=2):
                    cost = abs(hand[first] - r) + abs(hand[second] - t)
                    if cost <= 1:
                        best = max(best, scores[(r - 1) * 6 + t - 1] + 1.5 * (1 - cost))
            total += best
        self.assertAlmostEqual(fair_control_value(scores, 2, 1), total / 36)
        self.assertEqual(scores, before)
        self.assertEqual(random.getstate(), rng)

    def test_published_controls_cost_no_hypothetical_die_and_are_immutable(self):
        scores = tuple(float(r * 7 + t) for r in range(1, 7) for t in range(1, 7))
        self.assertEqual(fair_control_value(scores, 0, 2, rudder=2, thrust=3), 20.)
        self.assertEqual(fair_control_value(scores, 4, 2, rudder=2, thrust=3), 20.)
        self.assertAlmostEqual(fair_control_value(scores, 1, 0, rudder=2), 17.5)

    def test_own_plan_is_fixed_before_unknown_hand_expectation(self):
        a = tuple(float(r == 1) for r in range(1, 7) for t in range(1, 7))
        b = tuple(float(r == 2) for r in range(1, 7) for t in range(1, 7))
        fixed = max(fair_control_value(row, 1, 0, thrust=1, coffee_value=0) for row in (a, b))
        cheating = fair_control_value(tuple(max(x, y) for x, y in zip(a, b)), 1, 0, thrust=1, coffee_value=0)
        self.assertAlmostEqual(fixed, 1 / 6)
        self.assertAlmostEqual(cheating, 2 / 6)

    def test_invalid_or_nonfinite_inputs_are_rejected(self):
        for scores, count, coffee, kwargs in (([0.] * 35, 2, 0, {}), ([float('nan')] * 36, 2, 0, {}),
                ([0.] * 36, 5, 0, {}), ([0.] * 36, 2, 4, {}),
                ([0.] * 36, True, 0, {}), ([0.] * 36, 2, 0, {'rudder': True}),
                ([0.] * 36, 2, 0, {'coffee_value': -1})):
            with self.subTest(count=count, coffee=coffee, kwargs=kwargs), self.assertRaises(ValueError):
                fair_control_value(scores, count, coffee, **kwargs)


if __name__ == '__main__':
    unittest.main()
