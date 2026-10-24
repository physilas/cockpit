from copy import deepcopy
import unittest

from ai.actions import ACTIONS
from ai.environment import CrewEnv
from ai.tactics import capacity, capacity_mask
from ai.train import compute_gae


class LandingPlanningTests(unittest.TestCase):
    def test_tight_capacity_reserves_optional_slots_and_allows_extra_die(self):
        env = CrewEnv()
        env.reset(seed=7)
        env.game.am_zug = 'kopilot'
        env.game.landung.hoehe = 0
        env.game.letzte_runde = True
        env.game.cockpit.landeklappen_ausgefahren[:2] = [True, True]
        view, mask = env.view(), env.action_mask()
        self.assertEqual(capacity(view)['slack'], 0)
        filtered = capacity_mask(view, mask)
        for i, allowed in enumerate(filtered):
            if allowed and ACTIONS[i].kind == 'place':
                from ai.actions import SLOTS
                self.assertIn(SLOTS[ACTIONS[i].slot].target, ('ruder', 'triebwerk', 'landeklappe'))
        self.assertEqual(capacity(view, extra_placements=1)['slack'], 1)

    def test_assistance_keeps_partner_faces_hidden_and_legacy_mask_separate(self):
        env = CrewEnv(assistance_version=1)
        env.reset(seed=5100000)
        before = deepcopy((env.view(), env.action_mask()))
        for die in env.game.kopilot_wuerfel:
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual(before, (env.view(), env.action_mask()))
        self.assertTrue(any(before[1]))
        for i, allowed in enumerate(before[1]):
            if allowed:
                self.assertNotEqual(ACTIONS[i].kind, 'reroll_start')

    def test_cards_disable_unsupported_capacity_assumptions(self):
        env = CrewEnv(assistance_version=1)
        env.reset(seed=7)
        env.game.zusatz.karten = ['anticipation']
        with self.assertRaises(ValueError):
            env.action_mask()

    def test_helpers_do_not_discount_a_future_loss(self):
        advantages, _ = compute_gae([0, -1], [0, 0], gamma=.5, gae_lambda=1,
                                    discounts=[1, .5], traces=[1, 1])
        self.assertEqual(advantages, [-1, -1])


if __name__ == '__main__':
    unittest.main()
