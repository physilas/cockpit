"""Light checks of the explicit profile-10 intern PPO phase."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.modules import ModuleEnv
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.train import collect_rollout, ppo_update
from ai.train_intern import ROUTES, main, selection_score


class InternTrainingTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(251050)

    def test_selection_prioritizes_the_weaker_route_before_any_mean(self):
        def summary(first, second, pooled):
            return {'by_route': {ROUTES[0]: {'win_rate': first}, ROUTES[1]: {'win_rate': second}},
                    'win_rate': pooled}
        initial = selection_score(summary(.3, .9, .99))
        balanced = selection_score(summary(.4, .4, .01))
        self.assertGreater(balanced, initial)
        self.assertGreater(selection_score(summary(.4, .6, 0)), balanced)
        self.assertEqual(initial[0], .3)

    def test_real_profile_10_rollouts_and_ppo_keep_frozen_foundation_exact(self):
        policy = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                           hidden_size=8, hidden_layers=1)
        initial_source = deepcopy(policy.source.state_dict())
        initial_actor = deepcopy(policy.residual.actor.state_dict())
        optimizer = torch.optim.Adam((parameter for parameter in policy.parameters() if parameter.requires_grad),
                                     lr=5e-5, eps=1e-5)
        for route in ROUTES:
            env = ModuleEnv(route, abilities=[], assistance_version=10, round_reward=0.,
                            sync_weight=.05, task_weight=.02, max_steps=256)
            batch, records = collect_rollout(policy, env, 1,
                seed=f'intern-unit-test:{route}', episodes_done=0,
                gamma=.995, gae_lambda=.95, uniform_mix=.03,
                discount_unit='placement')
            self.assertTrue(records)
            self.assertTrue(all(record['scenario'] == route for record in records))
            self.assertTrue(all(str(record['seed']).startswith('train:intern-unit-test:') for record in records))
            self.assertEqual(sum(record['steps'] for record in records), len(batch['actions']))
            self.assertIn('reference_masks', batch)
            self.assertTrue(bool(batch['reference_masks'].any(dim=1).all()))
            self.assertFalse(bool((batch['reference_masks'] & ~batch['masks']).any()))
            with torch.no_grad():
                recomputed = policy.evaluate_actions(batch['observations'], batch['masks'], batch['actions'],
                    uniform_mix=.03, reference_mask=batch['reference_masks'])[0]
            self.assertTrue(torch.allclose(recomputed, batch['log_probs'], atol=2e-6, rtol=2e-6))
            stats = ppo_update(policy, optimizer, batch, epochs=1, minibatch_size=len(batch['actions']),
                clip=.2, value_coef=.5, entropy_coef=.01, uniform_mix=.03)
            self.assertTrue(all(torch.isfinite(parameter).all() for parameter in policy.parameters()))
            self.assertTrue(all(torch.equal(value, initial_source[name])
                                for name, value in policy.source.state_dict().items()))
            self.assertTrue(all(not parameter.requires_grad for parameter in policy.source.parameters()))
        self.assertTrue(any(not torch.equal(value, initial_actor[name])
                            for name, value in policy.residual.actor.state_dict().items()))

    def test_cli_rejects_resource_or_qualification_seed_misuse_before_loading_source(self):
        invalid_options = (('--workers', '9'), ('--cpu-duty-cycle', '.8'),
                           ('--seconds', '901'), ('--steps', '0'),
                           ('--eval-seed', '15000000'), ('--eval-seed', '15200000'))
        with tempfile.TemporaryDirectory() as folder:
            run = str(Path(folder) / 'unused-run')
            for options in invalid_options:
                with self.subTest(options=options), redirect_stderr(io.StringIO()), \
                        patch('sys.argv', ['ai.train_intern', '--run-dir', run, *options]), \
                        patch('ai.train_intern.load_checkpoint') as loader:
                    with self.assertRaises(SystemExit): main()
                    loader.assert_not_called()
                    self.assertFalse(Path(run).exists())


if __name__ == '__main__':
    unittest.main()
