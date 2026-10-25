"""Explicit public evaluation uses native rules, clocks, masks, and case IDs."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

import torch

from ai.actions import Action
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.public_case_eval import run_public_case


ATL = {'airport': 'LOG_ATL_GREEN', 'modules': ['intern'], 'abilities': []}


class PublicCaseEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def model(self):
        torch.manual_seed(251054)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1),
                                         489, 217, 8, 1)
        # Deliberately prefer an initially legal nonreference reroll, so the
        # instrumentation is checked against a real departure, not only zero.
        with torch.no_grad():
            model.residual.actor.bias[MODULE_ACTIONS.index(Action('reroll_start'))] = 8.
        return model

    def test_real_atl_episode_preserves_model_rng_and_counts_actual_departures(self):
        model = self.model()
        model.train()
        before_weights = weight_fingerprint(model)
        before_torch, before_random = torch.get_rng_state().clone(), random.getstate()
        original_select = ModelAgent.select
        observed = []
        created = []

        class RecordingModuleEnv(ModuleEnv):
            def __init__(self, *args, **kwargs):
                created.append((args, deepcopy(kwargs)))
                super().__init__(*args, **kwargs)

        def checked_select(agent, view, mask, *, reference_mask=None):
            self.assertIsNotNone(reference_mask)
            self.assertEqual(len(mask), 217)
            self.assertTrue(any(reference_mask))
            self.assertTrue(all(not advised or mask[i] for i, advised in enumerate(reference_mask)))
            self.assertNotIn('partner_dice', view)
            action = original_select(agent, view, mask, reference_mask=reference_mask)
            self.assertTrue(mask[action])
            observed.append(int(not reference_mask[action]))
            return action

        with patch('ai.public_case_eval.ModuleEnv', RecordingModuleEnv), \
                patch.object(ModelAgent, 'select', checked_select):
            result = run_public_case(model, ATL, 1, 14_960_000,
                                     cpu_duty_cycle=.7, assistance_version=10)
        self.assertEqual(result['games'], 1)
        self.assertEqual(len(result['episodes']), 1)
        self.assertEqual(result['clock_model'], 'engine_wall_clock')
        self.assertTrue(result['complete'])
        self.assertFalse(result['release_evidence'])
        self.assertFalse(result['qualification_used'])
        self.assertGreater(sum(observed), 0)
        self.assertEqual(result['reference_departures'], sum(observed))
        self.assertEqual(result['decisions'], len(observed))
        self.assertEqual(result['reference_departure_rate'], sum(observed) / len(observed))
        episode = result['episodes'][0]
        self.assertEqual(episode['scenario'], ATL['airport'])
        self.assertEqual(episode['airport'], ATL['airport'])
        self.assertEqual(episode['abilities'], [])
        self.assertEqual(episode['modules'], ['intern'])
        self.assertEqual(episode['seed'], 14_960_000)
        self.assertEqual(episode['steps'], result['decisions'])
        self.assertNotIn('training_budget_failure', episode)
        self.assertEqual(episode['reference_departures'], sum(observed))
        self.assertEqual(created[0][0], (ATL['airport'],))
        self.assertNotIn('clock', created[0][1])
        self.assertNotIn('curriculum_cases', created[0][1])
        self.assertNotIn('curriculum_airports', created[0][1])
        self.assertEqual(created[0][1]['abilities'], [])
        self.assertTrue(model.training)
        self.assertEqual(weight_fingerprint(model), before_weights)
        self.assertTrue(torch.equal(torch.get_rng_state(), before_torch))
        self.assertEqual(random.getstate(), before_random)

    def test_seed_guard_rejects_qualification_before_constructing_an_engine(self):
        model = self.model()
        with patch('ai.public_case_eval.ModuleEnv', side_effect=AssertionError('No game may start')):
            for seed, games in ((15_000_000, 1), (13_999_999, 1), (14_999_999, 2)):
                with self.subTest(seed=seed, games=games), self.assertRaises(ValueError):
                    run_public_case(model, ATL, games, seed, assistance_version=10)

    def test_missing_required_card_and_wrong_modules_are_rejected_before_game(self):
        model = self.model()
        bad_cases = [
            {'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': []},
            {'airport': 'LOG_ATL_GREEN', 'modules': ['kerosene'], 'abilities': []},
            {'airport': 'LOG_ATL_GREEN', 'modules': ['intern'], 'abilities': ['adaptation']},
        ]
        with patch('ai.public_case_eval.ModuleEnv', side_effect=AssertionError('No game may start')):
            for case in bad_cases:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    run_public_case(model, case, 1, 14_960_010, assistance_version=10)

    def test_resource_and_profile_bounds_are_explicit(self):
        model = self.model()
        with patch('ai.public_case_eval.ModuleEnv', side_effect=AssertionError('No game may start')):
            for duty in (.8, 0., float('nan')):
                with self.subTest(duty=duty), self.assertRaises(ValueError):
                    run_public_case(model, ATL, 1, 14_960_010,
                                    cpu_duty_cycle=duty, assistance_version=10)
            with self.assertRaises(ValueError):
                run_public_case(model, ATL, 1, 14_960_010, assistance_version=9)
            with self.assertRaises(ValueError):
                run_public_case(ActorCritic(489, 217, 8, 1), ATL, 1,
                                14_960_010, assistance_version=10)


if __name__ == '__main__':
    unittest.main()
