"""Leak transfer protects weak card cases and the real guided rollout path."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.checkpoints import weight_fingerprint, save_checkpoint
from ai.intern_strength_compare import tensor_fingerprint
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
                   ('--workers', '9'), ('--eval-seed', '15000000'),
                   ('--assistance-version', '13'), ('--guide-margin', '0'),
                   ('--guide-margin', 'nan')]
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

    def test_new_phase_margin_changes_probabilities_but_preserves_exact_source_tensors(self):
        torch.manual_seed(251058)
        source = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'crew2-original.pt'
            save_checkpoint(checkpoint, source, train_config={'assistance_version': 9}, total_steps=500347)
            original_bytes = checkpoint.read_bytes()
            old, _, old_lineage = train_leak.initialize_phase(checkpoint)
            new, payload, lineage = train_leak.initialize_phase(checkpoint,
                assistance_version=12, guide_margin=12.)
            observation = torch.zeros(489)
            allowed = torch.zeros(217, dtype=torch.bool); allowed[:2] = True
            reference = torch.zeros(217, dtype=torch.bool); reference[0] = True
            with torch.no_grad():
                original_policy, _ = source.distribution(observation, allowed, reference_mask=reference)
                old_policy, _ = old.distribution(observation, allowed, reference_mask=reference)
                new_policy, _ = new.distribution(observation, allowed, reference_mask=reference)
            self.assertTrue(torch.equal(original_policy.probs, old_policy.probs))
            self.assertGreater(float(old_policy.probs[1]), float(new_policy.probs[1]))
            self.assertEqual(weight_fingerprint(old), weight_fingerprint(source))
            self.assertNotEqual(weight_fingerprint(new), weight_fingerprint(source))
            self.assertEqual(tensor_fingerprint(new), tensor_fingerprint(source))
            self.assertEqual(weight_fingerprint(new.source), weight_fingerprint(source.source))
            self.assertEqual(lineage['source_checkpoint_weights_sha256'], weight_fingerprint(source))
            self.assertEqual(lineage['source_weights_sha256'], weight_fingerprint(source))
            self.assertEqual(lineage['initial_weights_sha256'], weight_fingerprint(new))
            self.assertEqual(lineage['source_tensor_sha256'], lineage['initial_tensor_sha256'])
            self.assertEqual(lineage['source_phase_steps'], 500347)
            self.assertEqual(payload['total_steps'], 500347)
            self.assertEqual(lineage['phase_kind'], 'new_public_module_profile_12_leak_cards')
            self.assertEqual(old_lineage['phase_kind'], 'new_public_module_profile_11_leak')
            self.assertTrue(lineage['guide_margin_overridden'])
            self.assertFalse(old_lineage['guide_margin_overridden'])
            self.assertEqual(source.guide_margin, 4.)
            self.assertEqual(checkpoint.read_bytes(), original_bytes)

    def test_cli_records_explicit_profile12_lineage_and_constructs_fresh_adam(self):
        torch.manual_seed(251058)
        source = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            checkpoint, run = folder / 'original.pt', folder / 'fresh-phase'
            save_checkpoint(checkpoint, source, train_config={'assistance_version': 9, 'planner_sha256': 'original'},
                            total_steps=500347, optimizer_state={'not_a_resumable_optimizer': True})
            original_adam, optimizers = torch.optim.Adam, []

            def fresh_adam(*args, **kwargs):
                optimizer = original_adam(*args, **kwargs)
                optimizers.append(optimizer)
                return optimizer

            class StopBeforeWorkers(RuntimeError):
                pass

            arguments = ['ai.train_leak', '--source', str(checkpoint), '--run-dir', str(run),
                         '--matrix', str(ROOT / 'ai/experiments/modules-30pct-2026-10-25/matrix.json'),
                         '--device', 'cpu', '--assistance-version', '12', '--guide-margin', '12',
                         '--workers', '1', '--steps', '1', '--seconds', '1', '--eval-games-per-case', '1']
            with patch('sys.argv', arguments), patch.object(train_leak.torch.optim, 'Adam', side_effect=fresh_adam), \
                    patch.object(train_leak, 'ProcessPoolExecutor', side_effect=StopBeforeWorkers):
                with self.assertRaises(StopBeforeWorkers):
                    train_leak.main()
            config = json.loads((run / 'config.json').read_text())
            self.assertEqual(config['assistance_version'], 12)
            self.assertEqual(config['guide_margin'], 12.)
            self.assertEqual(config['planning_cpu_duty_cycle'], .7)
            self.assertEqual(config['phase_kind'], 'new_public_module_profile_12_leak_cards')
            self.assertEqual(config['source_phase_steps'], 500347)
            self.assertEqual(config['source_weights_sha256'], weight_fingerprint(source))
            self.assertNotEqual(config['initial_weights_sha256'], config['source_weights_sha256'])
            self.assertEqual(config['initial_tensor_sha256'], config['source_tensor_sha256'])
            self.assertEqual(config['phase_sha256'], train_leak.phase_fingerprint())
            self.assertEqual(len(optimizers), 1)
            self.assertFalse(optimizers[0].state)
            self.assertEqual(optimizers[0].param_groups[0]['lr'], 5e-5)

    def test_real_profile12_margin12_rollout_has_exact_log_probs_and_frozen_foundation(self):
        torch.manual_seed(251058)
        source = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'original.pt'
            save_checkpoint(checkpoint, source, train_config={'assistance_version': 9}, total_steps=500347)
            model, _, _ = train_leak.initialize_phase(checkpoint, assistance_version=12, guide_margin=12.)
        frozen = weight_fingerprint(model.source)
        detail = weight_fingerprint(model.residual)
        options = dict(airport='LOG_ATL_YELLOW', abilities=['adaptation'], assistance_version=12,
                       max_steps=64, round_reward=0., sync_weight=.05, sync_tolerance=1., task_weight=.02)
        train_leak._initialize(model.config, options, 1.)
        batch, records = train_leak._collect((deepcopy(model.state_dict()), 8, 251058, 0, 0))
        self.assertTrue(all(row['abilities'] == ['adaptation'] and row['modules'] == ['leak'] for row in records))
        with torch.no_grad():
            probabilities, _, _ = model.evaluate_actions(batch['observations'], batch['masks'], batch['actions'],
                uniform_mix=.03, reference_mask=batch['reference_masks'])
        self.assertTrue(torch.allclose(probabilities, batch['log_probs'], atol=2e-6, rtol=0.))
        optimizer = torch.optim.Adam((parameter for parameter in model.parameters() if parameter.requires_grad),
                                     lr=5e-5, eps=1e-5)
        ppo_update(model, optimizer, batch, epochs=1, minibatch_size=64, uniform_mix=.03)
        self.assertEqual(weight_fingerprint(model.source), frozen)
        self.assertNotEqual(weight_fingerprint(model.residual), detail)
        case = {'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': ['adaptation']}
        with patch.object(train_leak, 'run_public_case', return_value={'case_key': case_key(case)}) as evaluate:
            train_leak._evaluate((deepcopy(model.state_dict()), case, 1, 14_960_020))
        self.assertEqual(evaluate.call_args.kwargs['assistance_version'], 12)


if __name__ == '__main__':
    unittest.main()
