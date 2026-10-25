"""Small checks of the finite-guide development comparison, with no heavy job."""
from copy import deepcopy
from pathlib import Path
import random
import tempfile
import unittest

import torch

from ai.agents import ModelAgent
from ai.checkpoints import planner_fingerprint, save_checkpoint, weight_fingerprint
from ai.evaluate import evaluate
from ai.intern_strength_compare import compare_games, load_variants, tensor_fingerprint, validate_seed_budget, with_margin
from ai.nn_model import ActorCritic, GuidedResidualActorCritic, build_model


def tiny_model():
    return GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                     hidden_size=8, hidden_layers=1)


class InternStrengthComparisonTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(251051)

    def test_margin_changes_configuration_but_never_tensors_or_original_model(self):
        original = tiny_model()
        source_config = deepcopy(original.config)
        source_sha, tensors = weight_fingerprint(original), tensor_fingerprint(original)
        observation = torch.zeros(489)
        observation[0] = 1
        mask = torch.zeros(217, dtype=torch.bool); mask[:2] = True
        reference = torch.zeros(217, dtype=torch.bool); reference[0] = True
        probabilities = []
        for margin in (4, 8, 12):
            variant = with_margin(original, margin)
            self.assertEqual(variant.guide_margin, float(margin))
            self.assertEqual(variant.config['guide_margin'], float(margin))
            self.assertEqual(tensor_fingerprint(variant), tensors)
            self.assertEqual(weight_fingerprint(variant) == source_sha, margin == 4)
            rebuilt = build_model(variant.config)
            rebuilt.load_state_dict(variant.state_dict())
            self.assertEqual(weight_fingerprint(rebuilt), weight_fingerprint(variant))
            with torch.no_grad():
                distribution, _ = variant.distribution(observation, mask, reference_mask=reference)
            probabilities.append(float(distribution.probs[1]))
        self.assertGreater(probabilities[0], probabilities[1])
        self.assertGreater(probabilities[1], probabilities[2])
        self.assertGreater(probabilities[2], 0.)
        self.assertEqual(original.config, source_config)
        self.assertEqual(original.guide_margin, 4.)
        self.assertEqual(weight_fingerprint(original), source_sha)

    def test_warm_control_and_three_preselected_candidate_variants_have_auditable_lineage(self):
        warm = tiny_model()
        candidate = deepcopy(warm)
        with torch.no_grad(): candidate.residual.actor.bias[0] += .01
        config = {'assistance_version': 10, 'phase_kind': 'new_public_module_profile_10',
                  'planner_sha256': planner_fingerprint(3), 'source_phase_steps': 500347,
                  'source_weights_sha256': weight_fingerprint(warm)}
        with tempfile.TemporaryDirectory() as folder:
            source_path, candidate_path = Path(folder)/'warm.pt', Path(folder)/'best.pt'
            save_checkpoint(source_path, warm, train_config=config, total_steps=0)
            save_checkpoint(candidate_path, candidate, train_config=config, total_steps=128)
            models, metadata = load_variants(source_path, candidate_path)
            self.assertEqual(set(models), {'source_margin4', 'candidate_margin4', 'candidate_margin8', 'candidate_margin12'})
            candidate_labels = [label for label in models if label.startswith('candidate_')]
            self.assertEqual(len({metadata[label]['tensor_sha256'] for label in candidate_labels}), 1)
            self.assertEqual(len({metadata[label]['model_fingerprint_sha256'] for label in candidate_labels}), 3)
            self.assertEqual(len({row['frozen_source_model_sha256'] for row in metadata.values()}), 1)
            self.assertTrue(all(not row['tensor_values_changed_from_loaded_checkpoint'] for row in metadata.values()))
            self.assertFalse(metadata['source_margin4']['tensor_values_changed_from_warm'])
            self.assertTrue(metadata['candidate_margin8']['configuration_changed'])
            invalid = {**config, 'source_weights_sha256': 'wrong-lineage'}
            save_checkpoint(candidate_path, candidate, train_config=invalid, total_steps=128)
            with self.assertRaisesRegex(ValueError, 'lineage'):
                load_variants(source_path, candidate_path)

    def test_departure_instrumentation_preserves_actual_engine_play_and_rng(self):
        model = tiny_model()
        before = weight_fingerprint(model)
        rng = random.getstate()
        for route, seed in (('LOG_ATL_GREEN', 14_980_000), ('LOG_LHR_YELLOW', 14_990_000)):
            rows = compare_games(model, route, seed, 1)
            baseline = evaluate(ModelAgent(model), airport=route, seed=seed, games=1,
                assistance_version=10, abilities=[], round_reward=0., sync_weight=0.,
                task_weight=0., max_steps=256, cpu_duty_cycle=.7)['episodes']
            self.assertGreaterEqual(rows[0]['reference_departures'], 0)
            self.assertLessEqual(rows[0]['reference_departures'], rows[0]['steps'])
            stripped = [{key: value for key, value in row.items() if key != 'reference_departures'} for row in rows]
            self.assertEqual(stripped, baseline)
        self.assertEqual(weight_fingerprint(model), before)
        self.assertEqual(random.getstate(), rng)

    def test_unsupported_margins_models_routes_and_reserved_seeds_fail_closed(self):
        source = tiny_model()
        for margin in (0, 7, 16, float('nan'), True):
            with self.assertRaises(ValueError): with_margin(source, margin)
        with self.assertRaises(ValueError): with_margin(ActorCritic(489, 217, 8, 1), 4)
        with self.assertRaises(ValueError): compare_games(source, 'LOG_OSL_GREEN', 14_980_000, 1)
        validate_seed_budget(14_980_000, 40)
        for seed in (13_999_999, 14_999_999, 15_000_000, 15_200_000):
            with self.assertRaises(ValueError): validate_seed_budget(seed, 40)
        for games in (0, 1001, True):
            with self.assertRaises(ValueError): validate_seed_budget(14_980_000, games)


if __name__ == '__main__':
    unittest.main()
