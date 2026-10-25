"""Research-only all-module masks, finite episodes, and logical time."""
import json
from pathlib import Path
import unittest

import torch

from ai.actions import Action
from ai.all_modules_environment import AllModulesEnv
from ai.modules import ModuleEnv, MODULE_ACTIONS, shared_capacity
from ai.train import collect_rollout


ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())['cases']


def choose(env, kind, **fields):
    return next(index for index, action in enumerate(MODULE_ACTIONS)
                if action.kind == kind and all(getattr(action, key) == value for key, value in fields.items())
                and env.action_mask()[index])


def case_with(card=None, module=None):
    return next(case for case in CASES
                if (card is None or card in case['abilities'])
                and (module is None or module in case['modules']))


def make(case, **kwargs):
    env = AllModulesEnv(case['airport'], abilities=case['abilities'], **kwargs)
    env.reset(seed='train:all-module-env-test:251044')
    return env


class NoBootstrapModel(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(()))
        self.config = {'kind': 'test'}

    def act(self, observation, mask, **kwargs):
        return torch.tensor(next(i for i, valid in enumerate(mask) if valid)), torch.tensor(0.), torch.tensor(0.)

    def forward(self, observation):
        raise AssertionError('A terminal training-budget failure must not bootstrap')


class AllModulesEnvironmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_all_186_cases_have_private_engine_legal_guidance(self):
        self.assertEqual(len(CASES), 186)
        for case in CASES:
            with self.subTest(airport=case['airport'], cards=case['abilities']):
                env = make(case)
                raw = ModuleEnv(case['airport'], abilities=case['abilities'], clock=lambda: 0.)
                raw.reset(seed='train:all-module-env-test:251044')
                info = env.info()
                self.assertTrue(any(info['action_mask']))
                self.assertTrue(any(info['reference_action_mask']))
                self.assertEqual(info['raw_action_mask'], raw.action_mask())
                self.assertTrue(all(not flag or info['action_mask'][index]
                                    for index, flag in enumerate(info['reference_action_mask'])))
                self.assertTrue(all(not flag or info['raw_action_mask'][index]
                                    for index, flag in enumerate(info['action_mask'])))
                before = env.observation(), env.view(), env.info()
                for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
                    if die.ist_verfuegbar():
                        die.augenzahl = 7 - die.augenzahl
                self.assertEqual(before, (env.observation(), env.view(), env.info()))

    def test_plain_profiles_and_reference_masks_remain_exact(self):
        for airport in ('MUC', 'LOG_HND_GREEN', 'LOG_OSL_GREEN'):
            with self.subTest(airport=airport):
                env = AllModulesEnv(airport)
                old = ModuleEnv(airport, assistance_version=9)
                env.reset(seed=251044);old.reset(seed=251044)
                for _ in range(5):
                    self.assertEqual(env.view(), old.view())
                    self.assertEqual(env.observation(), old.observation())
                    self.assertEqual(env.action_mask(), old.action_mask())
                    self.assertEqual(env.info()['reference_action_mask'], old.info()['reference_action_mask'])
                    if env.done:
                        break
                    selected = next(i for i, valid in enumerate(env.action_mask()) if valid)
                    env.step(selected);old.step(selected)

    def test_swap_cancel_cycle_is_closed_but_both_legal_choices_complete(self):
        env = make(case_with(card='working-together'))
        env.step(choose(env, 'swap_start'))
        info = env.info()
        cancel = MODULE_ACTIONS.index(Action('swap_cancel'))
        self.assertTrue(info['raw_action_mask'][cancel])
        self.assertFalse(info['action_mask'][cancel])
        self.assertFalse(info['reference_action_mask'][cancel])
        initiator = env.current_role
        env.step(choose(env, 'swap_choose', die=0))
        self.assertEqual(env.current_role, env.other_role(initiator))
        self.assertFalse(env.action_mask()[cancel])
        env.step(choose(env, 'swap_choose', die=0))
        self.assertIsNone(env.game.zusatz.kooperation)
        self.assertTrue(env.game.zusatz.kooperation_genutzt)
        self.assertFalse(any(valid and action.kind == 'swap_start'
                             for valid, action in zip(env.action_mask(), MODULE_ACTIONS)))

    def test_training_budget_is_terminal_and_settles_outcome_and_tasks(self):
        env = make(case_with(card='working-together'), max_steps=1,
                   round_reward=0., sync_weight=0., task_weight=.02)
        game = env.game
        expected_tasks = -.02 * sum(env.unfinished_tasks().values())
        _, reward, terminated, truncated, info = env.step(choose(env, 'swap_start'))
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertTrue(env.done)
        self.assertTrue(env.blocked)
        self.assertEqual(game.status, 'laeuft')
        self.assertEqual(game.verlust_grund, None)
        self.assertEqual(info['status'], 'verloren')
        self.assertEqual(info['reason'], 'training_decision_budget')
        self.assertTrue(info['training_budget_failure'])
        self.assertEqual(info['reward_components']['outcome'], -1.)
        self.assertAlmostEqual(info['reward_components']['tasks'], expected_tasks)
        self.assertAlmostEqual(reward, -1. + expected_tasks)
        self.assertAlmostEqual(sum(info['reward_totals'].values()), reward)
        record = env.episode_record('train:budget', 'both', reward)
        self.assertTrue(record['training_budget_failure'])
        self.assertEqual(record['abilities'], sorted(game.zusatz.karten))
        self.assertEqual(record['modules'], sorted(game.cockpit.module))

    def test_collector_does_not_bootstrap_budget_failures(self):
        env = AllModulesEnv('MUC', max_steps=1, task_weight=0., round_reward=0.)
        batch, records = collect_rollout(NoBootstrapModel(), env, 1, seed=251044,
                                        episodes_done=0, gamma=.995, gae_lambda=.95)
        self.assertEqual(records[0]['reason'], 'training_decision_budget')
        self.assertEqual(records[0]['outcome_return'], -1.)
        self.assertEqual(float(batch['returns'][0]), -1.)

    def test_logical_realtime_clock_resets_and_expires_deterministically(self):
        case = case_with(module='realtime')
        first = make(case, step_seconds=60.)
        second = make(case, step_seconds=60.)
        self.assertEqual(first.view()['modules_state']['time_remaining'], 60)
        action = next(i for i, valid in enumerate(first.action_mask()) if valid)
        result = first.step(action)
        self.assertEqual(result, second.step(action))
        self.assertTrue(result[2])
        self.assertFalse(result[3])
        self.assertNotEqual(result[4]['reason'], 'training_decision_budget')
        self.assertEqual(first.logical_time, 60.)
        first.reset(seed='train:clock-reset')
        self.assertEqual(first.logical_time, 0.)
        self.assertEqual(first.view()['modules_state']['time_remaining'], 60)
        with self.assertRaises(ValueError):
            AllModulesEnv(clock=lambda: 0.)
        with self.assertRaises(ValueError):
            AllModulesEnv(step_seconds=0.)

    def test_issued_synchronisation_die_counts_once_through_pending_stages(self):
        env = make(case_with(card='synchronisation'))
        env.game.pilot_wuerfel[0].augenzahl = 1
        env.step(choose(env, 'place', die=0, slot=7))
        self.assertEqual(shared_capacity(env.view())['shared_bonus'], 0)
        env.game.kopilot_wuerfel[0].augenzahl = 1
        env.step(choose(env, 'place', die=0, slot=10))
        self.assertEqual(shared_capacity(env.view())['shared_bonus'], 1)
        self.assertEqual(shared_capacity(env.view())['total'], 7)
        self.assertTrue(env.info()['reference_action_mask'][choose(env, 'bonus_roll')])
        env.step(choose(env, 'bonus_roll'))
        self.assertEqual(shared_capacity(env.view())['shared_bonus'], 1)
        self.assertEqual(shared_capacity(env.view())['total'], 7)
        self.assertTrue(any(env.info()['reference_action_mask']))
        env.step(choose(env, 'bonus_place'))
        self.assertEqual(shared_capacity(env.view())['shared_bonus'], 0)

    def test_intern_token_remains_available_and_engine_legal(self):
        env = make(case_with(module='intern'))
        value = env.game.zusatz.praktikant[0]
        env.game.pilot_wuerfel[0].augenzahl = 1 if value != 1 else 2
        env.step(choose(env, 'place', die=0, slot=21))
        self.assertEqual(env.view()['modules_state']['pending']['source'], 'intern')
        self.assertEqual(shared_capacity(env.view())['shared_bonus'], 0)
        self.assertEqual(shared_capacity(env.view())['total'], 8)
        self.assertTrue(any(env.info()['reference_action_mask']))
        env.step(choose(env, 'bonus_place'))
        self.assertIsNone(env.view()['modules_state']['pending'])


if __name__ == '__main__':
    unittest.main()
