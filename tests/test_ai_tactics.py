from copy import deepcopy
import unittest

from ai.actions import ACTIONS, ACTION_IDS, Action, SLOTS
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
        for profile in (1,2,3):
            for role in ('pilot','kopilot'):
                env = CrewEnv(assistance_version=profile)
                env.reset(seed=5100000)
                env.game.am_zug = role
                before = deepcopy((env.view(), env.action_mask()))
                for die in env.game._wuerfel_liste(env.other_role(role)):
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

    def test_final_round_preserves_shared_radio_capacity(self):
        env = CrewEnv('MUC_T3')
        env.reset(seed=7)
        view = env.view()
        view.update(height=0, last_round=True, gear=[True]*3, flaps=[True]*4, brakes=6)
        view['track'][0]['planes'] = 3
        for cell in view['track'][1:]:
            cell['planes'] = 0
        view['own_dice'][3] = 0
        view['board'][17] = {'owner': 'pilot', 'value': 3}
        filler = ACTION_IDS[Action('place', die=2, slot=18)]
        rudder = ACTION_IDS[Action('place', die=1, slot=0)]
        mask = [False]*len(ACTIONS)
        mask[filler] = mask[rudder] = True
        filtered = capacity_mask(view, mask, include_traffic=True)
        self.assertFalse(filtered[filler])
        self.assertTrue(filtered[rudder])

    def test_known_curve_is_respected_when_movement_is_required(self):
        env = CrewEnv(assistance_version=3)
        env.reset(seed=7)
        g, c = env.game, env.game.cockpit
        g.am_zug = 'kopilot'
        g.landung.hoehe, g.landung.entfernung = 1000, 1
        index = g.landung.get_laenge() - 2
        g.landung._kurven_min[index], g.landung._kurven_max[index] = -2, -1
        c.fahrwerk_ausgefahren[:] = [True]*3
        c.landeklappen_ausgefahren[:] = [True]*4
        c.bremsen_aktiviert[:] = [True]*3
        c.aerodynamik_blau, c.aerodynamik_orange = 7.5, 12.5
        g.pilot_wuerfel[0].augenzahl = 4
        c.ruder_pilot.platziere(g.pilot_wuerfel[0])
        g.pilot_wuerfel[1].augenzahl = 6
        c.schub_pilot.platziere(g.pilot_wuerfel[1])
        for d, value in zip(g.kopilot_wuerfel, (3,5,6,2)):
            d.augenzahl = value
        slot = next(i for i,s in enumerate(SLOTS) if s.target == 'ruder' and s.owner == 'kopilot')
        mask = env.action_mask()
        self.assertTrue(mask[ACTION_IDS[Action('place', die=0, slot=slot)]])
        self.assertFalse(mask[ACTION_IDS[Action('place', die=1, slot=slot)]])

    def test_mixed_route_resets_are_reproducible(self):
        a = CrewEnv(curriculum_airports=('TRAIN_SHORT','TRAIN_LONG','MUC_T2'))
        b = CrewEnv(curriculum_airports=('TRAIN_SHORT','TRAIN_LONG','MUC_T2'))
        codes = set()
        for seed in range(12):
            self.assertEqual(a.reset(seed=seed), b.reset(seed=seed))
            codes.add(a.game.landung.get_code())
        self.assertEqual(codes, {'TRAIN_SHORT','TRAIN_LONG','MUC_T2'})


if __name__ == '__main__':
    unittest.main()
