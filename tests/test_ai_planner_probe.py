import math
import unittest

from ai.actions import Action, Slot
from ai.fuel import FuelEnv
from ai.planner_probe import ProbeFuelEnv, ProbeModuleEnv, capacity_only_mask, measure_choice, summarize_choices


class PlannerProbeTests(unittest.TestCase):
    def test_equal_dice_do_not_inflate_strategic_freedom(self):
        actions = (Action('place', die=0, slot=0), Action('place', die=1, slot=0),
                   Action('place', die=2, slot=1))
        slots = (Slot('ruder', 'pilot'), Slot('triebwerk', 'pilot'))
        totals = measure_choice({'own_dice': [2, 2, 5, 0]}, [True] * 3,
                                [True, True, False], [0., 0., math.log(2)], actions, slots)
        result = summarize_choices(totals)
        self.assertEqual(result['semantic_forced'], 1.)
        self.assertEqual(result['planner_forced'], 0.)
        self.assertEqual(result['preferred_action_excluded'], 1.)
        self.assertAlmostEqual(result['kept_policy_mass'], .5)
        self.assertEqual(result['semantic_entropy'], 0.)
        self.assertEqual(result['kept_actions'], 2.)

    def test_probe_is_passive_and_partner_hand_cannot_affect_it(self):
        ordinary = FuelEnv('LOG_OSL_GREEN', assistance_version=7)
        probe = ProbeFuelEnv('LOG_OSL_GREEN', assistance_version=7)
        ordinary.reset(seed=19)
        probe.reset(seed=19)
        for _ in range(5):
            self.assertEqual(ordinary.action_mask(), probe.action_mask())
            self.assertEqual(ordinary.observation(), probe.observation())
            self.assertEqual(ordinary.rng.getstate(), probe.rng.getstate())
            mask = probe.action_mask()
            raw = list(probe.unassisted_mask)
            logits = [0.] * len(mask)
            before = measure_choice(probe.view(), raw, mask, logits, probe.actions, probe.slots)
            partner = probe.other_role(probe.current_role)
            dice = probe.game._wuerfel_liste(partner)
            original = [die.augenzahl for die in dice]
            for die in dice:
                if die.ist_verfuegbar(): die.augenzahl = 7 - die.augenzahl
            changed = probe.action_mask()
            self.assertEqual(mask, changed)
            self.assertEqual(raw, probe.unassisted_mask)
            self.assertEqual(before, measure_choice(probe.view(), probe.unassisted_mask, changed,
                                                   logits, probe.actions, probe.slots))
            for die, face in zip(dice, original): die.augenzahl = face
            action = next(i for i, allowed in enumerate(mask) if allowed)
            ordinary.step(action)
            probe.step(action)
            if probe.done: break

    def test_illegal_planner_expansion_is_rejected(self):
        with self.assertRaises(ValueError):
            measure_choice({}, [False], [True], [0.], (), ())

    def test_raw_fuel_mask_does_not_invent_a_field_on_base_routes(self):
        env = ProbeFuelEnv('MUC', assistance_version=7)
        env.reset(seed=23)
        self.assertFalse(any(env.unassisted_mask[121:125]))

    def test_capacity_comparison_contains_the_actual_assisted_choices(self):
        for airport in ('LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN'):
            env = ProbeModuleEnv(airport, assistance_version=7)
            env.reset(seed=23)
            while not env.done:
                mask = env.action_mask()
                budget = capacity_only_mask(env.view(), env.unassisted_mask, 7)
                measure_choice(env.view(), env.unassisted_mask, mask, [0.] * len(mask), env.actions, env.slots, budget)
                env.step(next(i for i, allowed in enumerate(mask) if allowed))

    def test_wider_research_profile_adds_only_budget_safe_placements(self):
        added = 0
        for airport in ('LOG_OSL_GREEN', 'LOG_HND_GREEN', 'MUC'):
            for seed in range(5):
                env = ProbeModuleEnv(airport, assistance_version=7)
                env.reset(seed=seed)
                for _ in range(8):
                    narrow = env.action_mask()
                    env.assistance_version = 9
                    wide = env.action_mask()
                    budget = capacity_only_mask(env.view(), env.unassisted_mask, 9)
                    self.assertTrue(all(not allowed or wide[i] for i, allowed in enumerate(narrow)))
                    self.assertTrue(all(not allowed or budget[i] for i, allowed in enumerate(wide)))
                    for i, action in enumerate(env.actions):
                        if action.kind != 'place': self.assertEqual(narrow[i], wide[i])
                    added += sum(b and not a for a, b in zip(narrow, wide))
                    env.assistance_version = 7
                    env.step(next(i for i, allowed in enumerate(narrow) if allowed))
                    if env.done: break
        self.assertGreater(added, 0)


if __name__ == '__main__':
    unittest.main()
