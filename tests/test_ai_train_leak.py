"""Leak transfer protects weak card cases and the real guided rollout path."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
from pathlib import Path
import unittest
from unittest.mock import patch

import torch

from ai.checkpoints import weight_fingerprint
from ai.module_training_eval import case_key, load_cases
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.train import ppo_update
from ai import train_leak


ROOT = Path(__file__).resolve().parents[1]


class LeakTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_worst_card_case_beats_a_high_average_with_one_failed_case(self):
        average_champion = {str(i): {'win_rate': rate}
                            for i, rate in enumerate((.1, 1., 1., 1., 1., 1.))}
        balanced = {str(i): {'win_rate': .2} for i in range(6)}
        self.assertGreater(sum(row['win_rate'] for row in average_champion.values()),
                           sum(row['win_rate'] for row in balanced.values()))
        self.assertGreater(train_leak.selection_score(balanced),
                           train_leak.selection_score(average_champion))
        with self.assertRaises(ValueError):
            train_leak.selection_score({key: value for key, value in balanced.items() if key != '5'})

    def test_cli_rejects_excess_duty_workers_and_reserved_validation_seeds(self):
        invalid = [('--workers', '8', '--cpu-duty-cycle', '.8'),
                   ('--workers', '9'), ('--eval-seed', '15000000')]
        for extra in invalid:
            with self.subTest(args=extra), redirect_stderr(io.StringIO()), \
                    patch('sys.argv', ['ai.train_leak', '--run-dir', '/tmp/leak-cli-no-start', *extra]), \
                    patch.object(train_leak, 'load_checkpoint', side_effect=AssertionError('No model may load')):
                with self.assertRaises(SystemExit) as raised:
                    train_leak.main()
                self.assertEqual(raised.exception.code, 2)

    def test_real_profile11_worker_rollout_matches_log_probs_and_updates_only_detail(self):
        torch.manual_seed(251055)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1),
                                         489, 217, 8, 1)
        state = deepcopy(model.state_dict())
        frozen_before = weight_fingerprint(model.source)
        detail_before = weight_fingerprint(model.residual)
        cases = [case for case in load_cases(ROOT / 'ai/experiments/modules-30pct-2026-10-25/matrix.json')
                 if case['airport'] == 'LOG_ATL_YELLOW']
        keys = {case_key(case) for case in cases}
        options = dict(airport='LOG_ATL_YELLOW', assistance_version=11,
                       max_steps=64, curriculum_cases=cases, round_reward=0.,
                       sync_weight=.05, sync_tolerance=1., task_weight=.02)
        train_leak._initialize(model.config, options, 1.)
        batch, records = train_leak._collect((state, 8, 251055, 0, 0))
        self.assertGreaterEqual(len(batch['actions']), 8)
        self.assertEqual(sum(record['steps'] for record in records), len(batch['actions']))
        self.assertTrue(all(record['modules'] == ['leak'] and len(record['abilities']) == 1 for record in records))
        self.assertTrue(all(case_key({'airport': row['scenario'], 'abilities': row['abilities']}) in keys
                            for row in records))
        self.assertTrue(torch.all(batch['reference_masks'].any(dim=1)))
        self.assertFalse(torch.any(batch['reference_masks'] & ~batch['masks']))
        with torch.no_grad():
            log_probs, _, _ = model.evaluate_actions(batch['observations'], batch['masks'],
                                                       batch['actions'], uniform_mix=.03,
                                                       reference_mask=batch['reference_masks'])
        self.assertTrue(torch.allclose(log_probs, batch['log_probs'], atol=2e-6, rtol=0.))
        optimizer = torch.optim.Adam((parameter for parameter in model.parameters() if parameter.requires_grad),
                                     lr=5e-5, eps=1e-5)
        metrics = ppo_update(model, optimizer, batch, epochs=1, minibatch_size=64, uniform_mix=.03)
        self.assertTrue(torch.isfinite(torch.tensor(metrics['policy_loss'])))
        self.assertEqual(weight_fingerprint(model.source), frozen_before)
        self.assertNotEqual(weight_fingerprint(model.residual), detail_before)
        self.assertTrue(all(parameter.grad is None for parameter in model.source.parameters()))


if __name__ == '__main__':
    unittest.main()
