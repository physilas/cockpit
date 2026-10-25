"""Profile-10 integration: legal soft advice, legacy parity and public tokens."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from backend import bridge
from ai.browser_bridge import decision
from ai.module_guidance import module_guidance
from ai.modules import ModuleEnv, MODULE_ACTIONS


MATRIX = json.loads((Path(__file__).resolve().parents[1] /
                    'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())


def assert_masks(test, raw, allowed, reference):
    test.assertEqual(len(raw), len(MODULE_ACTIONS))
    test.assertEqual(len(allowed), len(raw))
    test.assertEqual(len(reference), len(raw))
    test.assertTrue(all(type(value) is bool for value in allowed+reference))
    test.assertFalse(any(allowed_value and not legal for allowed_value, legal in zip(allowed, raw)))
    test.assertFalse(any(advice and not allowed_value for advice, allowed_value in zip(reference, allowed)))
    if any(raw):
        test.assertTrue(any(allowed))
        test.assertTrue(any(reference))


class ModuleGuidanceIntegrationTests(unittest.TestCase):
    def test_base_and_fuel_profiles_10_and_9_match_exactly_across_turns(self):
        for airport in ('MUC', 'LOG_LHR_GREEN', 'LOG_OSL_GREEN'):
            for seed in ('profile10-legacy-1', 'profile10-legacy-2'):
                legacy = ModuleEnv(airport, assistance_version=9, clock=lambda: 0)
                guided = ModuleEnv(airport, assistance_version=10, clock=lambda: 0)
                legacy.reset(seed=seed); guided.reset(seed=seed)
                for _ in range(12):
                    first, second = legacy.info(), guided.info()
                    self.assertEqual(legacy.observation(), guided.observation())
                    self.assertEqual(first['action_mask'], second['action_mask'])
                    self.assertEqual(first['reference_action_mask'], second['reference_action_mask'])
                    self.assertEqual(legacy.done, guided.done)
                    if legacy.done:
                        break
                    action = next(index for index, valid in enumerate(first['reference_action_mask']) if valid)
                    expected, actual = legacy.step(action), guided.step(action)
                    self.assertEqual(expected, actual)

    def test_legacy_pending_reroll_masks_remain_exact(self):
        for airport in ('MUC', 'LOG_OSL_GREEN'):
            pair = [ModuleEnv(airport, assistance_version=profile, clock=lambda: 0) for profile in (9, 10)]
            for env in pair:
                env.reset(seed='profile10-reroll')
                env.game.neuwurf_plaettchen = 1
                env.reroll = {'initiator': env.current_role,
                              'selections': {'pilot': None, 'kopilot': None}}
            for _ in range(2):
                first, second = (env.info() for env in pair)
                self.assertEqual(first['action_mask'], second['action_mask'])
                self.assertEqual(first['reference_action_mask'], second['reference_action_mask'])
                action = next(index for index, valid in enumerate(first['action_mask']) if valid)
                self.assertEqual(pair[0].step(action), pair[1].step(action))
            self.assertIsNone(pair[0].reroll)
            self.assertIsNone(pair[1].reroll)

    def test_all_186_initial_cases_have_legal_nonempty_public_advice(self):
        for case in MATRIX['cases']:
            with self.subTest(airport=case['airport'], abilities=case['abilities']):
                env = ModuleEnv(case['airport'], abilities=case['abilities'], clock=lambda: 0)
                env.reset(seed='profile10-all-cases')
                view, raw = env.view(), env.action_mask()
                before_view, before_mask = deepcopy(view), list(raw)
                rng_state = random.getstate()
                allowed, reference = module_guidance(view, raw)
                assert_masks(self, raw, allowed, reference)
                self.assertEqual(before_view, view)
                self.assertEqual(before_mask, raw)
                self.assertEqual(rng_state, random.getstate())
                env.assistance_version = 10
                info = env.info()
                self.assertEqual(info['action_mask'], allowed)
                self.assertEqual(info['reference_action_mask'], reference)
                observation = env.observation()
                for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
                    if die.ist_verfuegbar():
                        die.augenzahl = 7-die.augenzahl
                self.assertEqual(observation, env.observation())
                self.assertEqual(env.view(), before_view)
                self.assertEqual(env.info()['action_mask'], allowed)
                self.assertEqual(env.info()['reference_action_mask'], reference)

    def assert_browser_parity(self, env):
        previous = bridge._spiel
        try:
            bridge._spiel = env.game
            rng_state = random.getstate()
            actual = decision(env.current_role, json.dumps(env.reroll), env.steps, env.max_steps, 10, 3)
            info = env.info()
            self.assertEqual(actual['observation'], env.observation())
            self.assertEqual(actual['action_mask'], info['action_mask'])
            self.assertEqual(actual['reference_action_mask'], info['reference_action_mask'])
            self.assertEqual(actual['role'], env.current_role)
            self.assertNotIn('own_dice', actual['public_state'])
            self.assertNotIn('pilot_wuerfel', actual['public_state'])
            self.assertNotIn('kopilot_wuerfel', actual['public_state'])
            self.assertEqual(rng_state, random.getstate())
        finally:
            bridge._spiel = previous

    def test_pending_intern_transition_and_native_browser_profile_10_parity(self):
        for airport in ('LOG_ATL_GREEN', 'LOG_LHR_YELLOW'):
            for role in ('pilot', 'kopilot'):
                env = ModuleEnv(airport, assistance_version=10, clock=lambda: 0)
                env.reset(seed='profile10-pending-intern')
                env.game.am_zug = role
                token = env.game.zusatz.praktikant[0 if role == 'pilot' else -1]
                env.game._wuerfel_liste(role)[0].augenzahl = token % 6+1
                self.assert_browser_parity(env)
                info = env.info()
                training = next(index for index, action in enumerate(MODULE_ACTIONS)
                                if info['action_mask'][index] and action.kind == 'place'
                                and action.slot in (21, 22))
                before = len(env.game.zusatz.praktikant)
                env.step(training)
                pending = env.view()['modules_state']['pending']
                self.assertEqual(pending, {'role': role, 'source': 'intern', 'value': token})
                self.assertEqual(env.current_role, role)
                self.assertEqual(len(env.game.zusatz.praktikant), before-1)
                info = env.info()
                self.assertTrue(all(action.kind == 'bonus_place'
                                    for action, selected in zip(MODULE_ACTIONS, info['reference_action_mask']) if selected))
                raw = ModuleEnv(); raw.game = env.game
                assert_masks(self, raw.action_mask(), info['action_mask'], info['reference_action_mask'])
                self.assert_browser_parity(env)
                action = next(index for index, advised in enumerate(info['reference_action_mask']) if advised)
                env.step(action)
                self.assertIsNone(env.view()['modules_state']['pending'])
                self.assertEqual(env.current_role, env.other_role(role))
                self.assertEqual(len(env.game.zusatz.praktikant), before-1)
                self.assert_browser_parity(env)

    def test_compatible_kerosene_cards_keep_legal_alternatives_outside_reference(self):
        case = next(case for case in MATRIX['cases'] if case['airport'] == 'LOG_PRG_GREEN'
                    and set(case['abilities']) == {'adaptation', 'control'})
        env = ModuleEnv(case['airport'], abilities=case['abilities'], assistance_version=10, clock=lambda: 0)
        _, info = env.reset(seed='profile10-soft-cards')
        outside = [index for index, (allowed, advised) in enumerate(zip(info['action_mask'], info['reference_action_mask']))
                   if allowed and not advised]
        self.assertTrue(outside)
        self.assertTrue(any(MODULE_ACTIONS[index].kind == 'adaptation' for index in outside))
        # The network can assign finite probability to those engine-legal
        # departures; the reference remains a soft prior, not a new hard mask.
        import torch
        from ai.nn_model import ActorCritic, GuidedResidualActorCritic
        torch.set_num_threads(1)
        policy = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                           hidden_size=8, hidden_layers=1)
        with torch.no_grad():
            distribution, _ = policy.distribution(torch.tensor(env.observation()), info['action_mask'],
                                                  reference_mask=info['reference_action_mask'])
        self.assertTrue(all(float(distribution.probs[index]) > 0 for index in outside))
        self.assert_browser_parity(env)

    def test_malformed_masks_fail_and_terminal_masks_stay_empty(self):
        env = ModuleEnv('LOG_ATL_GREEN', clock=lambda: 0)
        env.reset(seed='profile10-validation')
        view = env.view()
        with self.assertRaises(ValueError): module_guidance(view, [True])
        with self.assertRaises(ValueError): module_guidance(view, [1]*len(MODULE_ACTIONS))
        blank = [False]*len(MODULE_ACTIONS)
        self.assertEqual(module_guidance(view, blank), (blank, blank))


if __name__ == '__main__':
    unittest.main()
