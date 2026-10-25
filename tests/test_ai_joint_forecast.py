from copy import deepcopy
import random
import unittest
from unittest.mock import patch

import torch

from ai.agents import ModelAgent
from ai.actions import ACTION_IDS, Action
from ai.environment import CrewEnv
from ai.fuel import FuelEnv
from ai.joint_forecast import make_joint_forecast
from ai.modules import ModuleEnv
from ai.nn_model import ActorCritic
from ai.search_evaluate import paired_outcomes
from ai.search_teacher import SearchTeacher
from ai.tactics import plan_actions


class JointForecastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def view(self, fuel=False):
        env = FuelEnv('LOG_OSL_GREEN') if fuel else CrewEnv()
        env.reset(seed=251034)
        view = env.view()
        view.update(height=1000, distance=0, last_round=False, holding=True,
                    gear=[True] * 3, flaps=[True] * 4, brakes=6, brake_progress=[True] * 3,
                    aero_blue=7.5, aero_orange=12.5, coffee=0)
        for c in view['track']:
            c.update(planes=0, traffic=0, min=-2, max=2)
        if fuel:
            view['fuel'].update(remaining=4, occupied=False)
        return view

    def test_fuel_competes_with_landing_tasks_in_same_eight_dice(self):
        plain, fueled = self.view(), self.view(True)
        for view in (plain, fueled):
            traffic = tuple(c['planes'] for c in view['track'])
            value = make_joint_forecast(view)(0, 0, 6, 3, 0, 3, traffic)
            # One gear, first brake and two flaps consume all four optional
            # placements. A ninth placement for fuel is impossible.
            self.assertEqual(value == 0, 'fuel' in view)

    def test_known_own_fuel_cost_preserves_real_remaining_reserve(self):
        view = self.view(True)
        forecast = make_joint_forecast(view)
        traffic = tuple(c['planes'] for c in view['track'])
        self.assertGreater(forecast(0, 0, 7, 15, 7, 0, traffic, fuel_cost=2), 0)
        self.assertEqual(forecast(0, 0, 7, 15, 7, 0, traffic, fuel_cost=3), 0)

    def test_two_round_forecast_rejects_unreachable_speed(self):
        view = self.view()
        view.update(height=2000, distance=2, holding=False)
        traffic = tuple(c['planes'] for c in view['track'])
        forecast = make_joint_forecast(view)
        self.assertEqual(forecast(0, 0, 7, 15, 7, 0, traffic), 0.)
        self.assertGreater(forecast(1, 0, 7, 15, 7, 0, traffic), 0.)

    def test_future_search_can_cooperate_without_changing_its_value(self):
        view = self.view();view.update(height=2000, distance=1, holding=False)
        traffic = tuple(c['planes'] for c in view['track'])
        calls = []
        args = (0, 0, 7, 15, 7, 0, traffic)
        expected = make_joint_forecast(view)(*args)
        actual = make_joint_forecast(view, cooperate=lambda: calls.append(1))(*args)
        self.assertEqual(actual, expected)
        self.assertGreater(len(calls), 1)

    def test_forecast_uses_public_view_without_rng_or_hidden_partner_faces(self):
        env = ModuleEnv('LOG_HND_GREEN');env.reset(seed=251034)
        env.game.landung.hoehe = 1000
        view, rng_state, global_state = env.view(), env.rng.getstate(), random.getstate()
        before = deepcopy(view)
        traffic = tuple(c['planes'] for c in view['track'])
        forecast = make_joint_forecast(view)
        value = forecast(max(0, view['distance']), 0, 7, 15, 7, 0, traffic)
        for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual(env.view(), before)
        self.assertEqual(make_joint_forecast(env.view())(max(0, view['distance']), 0, 7, 15, 7, 0, traffic), value)
        self.assertEqual(env.rng.getstate(), rng_state)
        self.assertEqual(random.getstate(), global_state)
        self.assertEqual(view, before)

    def test_optional_forecast_hook_does_not_change_early_or_default_plans(self):
        env = CrewEnv('LOG_HND_GREEN');env.reset(seed=251034)
        view, mask = env.view(), env.action_mask()
        def forbidden(_):
            raise AssertionError('Late-round search must not run in early rounds.')
        self.assertEqual(plan_actions(view, mask, version=3, beam=8),
                         plan_actions(view, mask, version=3, beam=8, forecast_factory=forbidden))

    def test_cards_are_not_silently_treated_as_free_future_black_dice(self):
        view = self.view()
        view['modules_state'] = {'modules': [], 'cards': ['synchronisation']}
        with self.assertRaises(ValueError):
            make_joint_forecast(view)

    def test_search_teacher_preserves_early_policy_and_late_decision_privacy(self):
        torch.manual_seed(251034)
        model = ActorCritic(489, 217, 8, 1)
        teacher = SearchTeacher(model, beam=16)
        env = ModuleEnv('LOG_OSL_GREEN', assistance_version=9);env.reset(seed=251034)
        view, mask = env.view(), env.action_mask()
        self.assertEqual(teacher.select(view, mask), ModelAgent(model).select(view, mask))
        self.assertEqual(teacher.considered, 0)
        env.game.landung.hoehe = 1000
        env.game.landung.entfernung = 1
        view, mask = env.view(), env.action_mask()
        before, rng_state = deepcopy(view), env.rng.getstate()
        first = teacher.select(view, mask)
        self.assertTrue(mask[first])
        for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual(teacher.select(env.view(), env.action_mask()), first)
        self.assertEqual(env.rng.getstate(), rng_state)
        self.assertEqual(view, before)

    def test_paired_reports_preserve_discordant_outcomes_and_reject_duplicate_seeds(self):
        before = [{'scenario': 'a', 'seed': 1, 'status': 'gewonnen'},
                  {'scenario': 'a', 'seed': 2, 'status': 'verloren'}]
        after = [{'scenario': 'a', 'seed': 1, 'status': 'verloren'},
                 {'scenario': 'a', 'seed': 2, 'status': 'gewonnen'}]
        self.assertEqual(paired_outcomes(before, after),
                         {'both_win': 0, 'both_lose': 0, 'candidate_only': 1, 'baseline_only': 1})
        with self.assertRaises(ValueError):
            paired_outcomes(before, after[:1])
        with self.assertRaises(ValueError):
            paired_outcomes(before * 2, after * 2)

    def test_explicit_finish_experiment_replans_last_die_without_changing_old_modes(self):
        model = ActorCritic(489, 217, 8, 1)
        view = self.view()
        view['own_dice'] = [1, 0, 0, 0]
        view['board'][:4] = [{'value': 3, 'owner': 'pilot'}, {'value': 3, 'owner': 'kopilot'},
                             None, {'value': 1, 'owner': 'kopilot'}]
        place = ACTION_IDS[Action('place', die=0, slot=2)]
        reroll = ACTION_IDS[Action('reroll_start')]
        mask = [False] * 217
        mask[place] = mask[reroll] = True
        before, rng = deepcopy(view), random.getstate()
        with patch.object(ModelAgent, 'select', return_value=reroll):
            self.assertEqual(SearchTeacher(model, mode='joint').select(view, mask), reroll)
            self.assertEqual(SearchTeacher(model, mode='legacy').select(view, mask), reroll)
            self.assertEqual(SearchTeacher(model, mode='joint-finish').select(view, mask), place)
            # No successful alternative plan means the learned reroll survives.
            mask[place] = False
            self.assertEqual(SearchTeacher(model, mode='joint-finish').select(view, mask), reroll)
        self.assertEqual(view, before)
        self.assertEqual(random.getstate(), rng)


if __name__ == '__main__':
    unittest.main()
