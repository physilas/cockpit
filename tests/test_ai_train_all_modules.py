"""A real worker rollout and PPO update across the new module boundary."""
from copy import deepcopy
import unittest

import torch

from ai.checkpoints import weight_fingerprint
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.train import ppo_update
from ai import train_all_modules


class AllModulesTrainingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_worker_masks_and_terminal_targets_survive_real_ppo_update(self):
        torch.manual_seed(251046)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1),
                                         489, 217, 8, 1)
        initial = deepcopy(model.state_dict())
        frozen_before = weight_fingerprint(model.source)
        detail_before = weight_fingerprint(model.residual)
        # This explicit card/module case exercises the raw-module fallback
        # rather than the existing base-game planner. One decision exhausts
        # the research budget, providing a known terminal PPO target.
        options = dict(airport='LOG_PRG_GREEN',
                       abilities=['adaptation', 'working-together'],
                       assistance_version=9, max_steps=1,
                       round_reward=0., sync_weight=0., task_weight=0.)
        train_all_modules._initialize(model.config, options, 1.)
        batch, records = train_all_modules._collect((initial, 8, 251046, 0, 0))
        self.assertEqual(len(batch['actions']), 8)
        self.assertEqual(len(records), 8)
        self.assertTrue(torch.equal(batch['masks'], batch['reference_masks']))
        self.assertTrue(all(record['reason'] == 'training_decision_budget' for record in records))
        self.assertTrue(all(record['training_budget_failure'] for record in records))
        self.assertTrue(all(record['outcome_return'] == -1. for record in records))
        self.assertTrue(all(record['modules'] == ['kerosene'] for record in records))
        self.assertTrue(all(record['abilities'] == ['adaptation', 'working-together'] for record in records))
        self.assertTrue(torch.equal(batch['returns'], -torch.ones(8)))
        # Before changing weights, re-evaluation must reproduce the worker's
        # sampled probabilities, including the all-module reference masks.
        with torch.no_grad():
            actual, _, _ = model.evaluate_actions(batch['observations'], batch['masks'],
                                                   batch['actions'], uniform_mix=.03,
                                                   reference_mask=batch['reference_masks'])
        self.assertTrue(torch.allclose(actual, batch['log_probs'], atol=1e-6, rtol=0.))
        optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad),
                                     lr=5e-5, eps=1e-5)
        metrics = ppo_update(model, optimizer, batch, epochs=1, minibatch_size=8,
                             uniform_mix=.03)
        self.assertTrue(torch.isfinite(torch.tensor(metrics['value_loss'])))
        self.assertEqual(weight_fingerprint(model.source), frozen_before)
        self.assertNotEqual(weight_fingerprint(model.residual), detail_before)
        self.assertTrue(all(parameter.grad is None for parameter in model.source.parameters()))
        # The caller supplied detached checkpoint state, not mutable worker
        # parameter references; both work and PPO must leave it unchanged.
        for key, value in initial.items():
            if key.startswith('source.'):
                self.assertTrue(torch.equal(value, model.state_dict()[key]))


if __name__ == '__main__':
    unittest.main()
