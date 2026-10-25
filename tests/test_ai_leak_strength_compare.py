"""Finite-prior comparisons preserve tensors, case identity and real rules."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.agents import ModelAgent
from ai.checkpoints import load_checkpoint, planner_fingerprint, save_checkpoint, weight_fingerprint
from ai.modules import CARDS, ModuleEnv
from ai.module_training_eval import case_key
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai import leak_strength_compare as compare


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / 'ai/experiments/modules-30pct-2026-10-25/matrix.json'


def fixture(folder):
    torch.manual_seed(251056)
    source = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
    candidate = deepcopy(source)
    with torch.no_grad():
        candidate.residual.actor.bias[0] += .25
    config = dict(assistance_version=11, phase_kind='new_public_module_profile_11_leak',
                  planner_sha256=planner_fingerprint(3), phase_sha256=compare.phase_fingerprint(),
                  source_weights_sha256=weight_fingerprint(source), source_phase_steps=500347)
    warm, best = folder / 'warm.pt', folder / 'best.pt'
    save_checkpoint(warm, source, train_config=deepcopy(config), total_steps=0)
    save_checkpoint(best, candidate, train_config=deepcopy(config), total_steps=128)
    return warm, best, source, candidate


class LeakStrengthComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_six_independent_margin_copies_change_only_config_and_offreference_prior(self):
        with tempfile.TemporaryDirectory() as directory:
            warm, best, source, candidate = fixture(Path(directory))
            original_files = warm.read_bytes(), best.read_bytes()
            source_before = weight_fingerprint(source)
            variants, metadata = compare.load_variants(warm, best)
            self.assertEqual(tuple(variants), compare.VARIANTS)
            self.assertEqual(len(variants), 6)
            observation = torch.zeros(489)
            reference = torch.zeros(217, dtype=torch.bool); reference[0] = True
            for origin, original in (('source', source), ('candidate', candidate)):
                baseline = variants[f'{origin}_margin4']
                with torch.no_grad():
                    first_logits, first_value = baseline.policy_output(observation, reference)
                for margin in (4, 8, 12):
                    label = f'{origin}_margin{margin}'
                    model = variants[label]
                    self.assertEqual(model.guide_margin, margin)
                    self.assertEqual(model.config['guide_margin'], margin)
                    self.assertEqual(compare.tensor_fingerprint(model), compare.tensor_fingerprint(original))
                    self.assertFalse(metadata[label]['tensor_values_changed_from_loaded_checkpoint'])
                    self.assertEqual(metadata[label]['model_fingerprint_sha256'], weight_fingerprint(model))
                    if margin != 4:
                        self.assertNotEqual(weight_fingerprint(model), weight_fingerprint(original))
                    with torch.no_grad():
                        logits, value = model.policy_output(observation, reference)
                    self.assertTrue(torch.equal(value, first_value))
                    self.assertTrue(torch.equal(logits[reference], first_logits[reference]))
                    self.assertTrue(torch.allclose(logits[~reference],
                                                   first_logits[~reference] - (margin - 4), atol=1e-6, rtol=0.))
            untouched = compare.tensor_fingerprint(variants['candidate_margin4'])
            with torch.no_grad():
                variants['candidate_margin8'].residual.actor.bias[1] += 1.
            self.assertEqual(compare.tensor_fingerprint(variants['candidate_margin4']), untouched)
            self.assertEqual(weight_fingerprint(source), source_before)
            self.assertEqual((warm.read_bytes(), best.read_bytes()), original_files)

    def test_stale_phase_lineage_or_changed_frozen_foundation_is_rejected(self):
        mutations = ('phase_sha256', 'planner_sha256', 'source_weights_sha256', 'foundation', 'warm_steps')
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                warm, best, _, _ = fixture(Path(directory))
                path = warm if mutation == 'warm_steps' else best
                model, payload = load_checkpoint(path)
                if mutation == 'foundation':
                    with torch.no_grad():
                        model.source.actor.bias[0] += 1.
                    payload['model_state'] = model.state_dict()
                elif mutation == 'warm_steps':
                    payload['total_steps'] = 1
                else:
                    payload['train_config'][mutation] = 'different'
                torch.save(payload, path)
                with self.assertRaises(ValueError):
                    compare.load_variants(warm, best)

    def test_case_selection_and_disjoint_development_seed_guards(self):
        cases = compare.atlanta_cases(MATRIX)
        self.assertEqual(len(cases), 6)
        self.assertEqual([case_key(case) for case in cases], sorted(case_key(case) for case in cases))
        self.assertEqual({case['abilities'][0] for case in cases}, set(CARDS))
        self.assertTrue(all(case['airport'] == 'LOG_ATL_YELLOW' and case['modules'] == ['leak'] for case in cases))
        compare.validate_seed_budget(14_920_000, 20)
        compare.validate_seed_budget(14_999_400, 100)
        for seed, games in ((15_000_000, 1), (14_999_401, 100), (13_999_999, 1),
                            (14_920_000, 101), (14_920_000, True)):
            with self.subTest(seed=seed, games=games), self.assertRaises(ValueError):
                compare.validate_seed_budget(seed, games)

    def test_both_paired_controls_are_retained_and_unmatched_cases_or_seeds_fail(self):
        patterns = {'source_margin4': (True, False, False, True),
                    'candidate_margin4': (False, True, False, True),
                    'candidate_margin8': (True, True, False, False)}
        rows = {}
        for variant in compare.VARIANTS:
            outcomes = patterns.get(variant, patterns['source_margin4'])
            rows[variant] = dict(airport='LOG_ATL_YELLOW', abilities=['adaptation'], modules=['leak'],
                episodes=[dict(scenario='LOG_ATL_YELLOW', seed=14_920_000+i,
                               status='gewonnen' if won else 'verloren') for i, won in enumerate(outcomes)])
        before = deepcopy(rows)
        result = compare.paired_summaries(rows)
        self.assertEqual(rows, before)
        expected = dict(both_win=1, both_lose=1, candidate_only=1, baseline_only=1)
        self.assertEqual(result['candidate_margin8']['paired_against_source_margin4'], expected)
        self.assertEqual(result['candidate_margin8']['paired_against_candidate_margin4'], expected)
        for variant in compare.VARIANTS:
            self.assertEqual(result[variant]['episodes'], rows[variant]['episodes'])
        missing = deepcopy(rows); missing.pop('source_margin12')
        with self.assertRaises(ValueError):
            compare.paired_summaries(missing)
        mismatched = deepcopy(rows); mismatched['candidate_margin12']['abilities'] = ['control']
        with self.assertRaises(ValueError):
            compare.paired_summaries(mismatched)
        mismatched = deepcopy(rows); mismatched['candidate_margin12']['episodes'][0]['seed'] += 100
        with self.assertRaises(ValueError):
            compare.paired_summaries(mismatched)

    def test_cli_preflight_honors_stop_resources_and_existing_outputs_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, stop = root / 'report.json', root / 'STOP_AI_TRAINING'
            common = ['--output', str(output), '--matrix', str(MATRIX)]
            with patch.object(compare, 'STOP_FILE', stop), \
                    patch.object(compare, 'load_variants', side_effect=AssertionError('No model may load')), \
                    redirect_stderr(io.StringIO()):
                for extra in (['--workers', '9'], ['--cpu-duty-cycle', '.8'], ['--seed', '15000000']):
                    with self.subTest(args=extra), self.assertRaises(SystemExit) as raised:
                        compare.main(common + extra)
                    self.assertEqual(raised.exception.code, 2)
                stop.write_text('user stop')
                with self.assertRaisesRegex(ValueError, 'Persistent'):
                    compare.check_stop()
                with self.assertRaises(SystemExit) as raised:
                    compare.main(common)
                self.assertEqual(raised.exception.code, 2)
                output.write_text('existing evidence')
                with self.assertRaises(SystemExit) as raised:
                    compare.main(common)
                self.assertEqual(raised.exception.code, 2)
                self.assertEqual(output.read_text(), 'existing evidence')

    def test_atomic_initial_report_cannot_replace_another_comparison(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            compare._write(output, {'complete': False}, initial=True)
            with self.assertRaises(FileExistsError):
                compare._write(output, {'overwrite': True}, initial=True)
            self.assertEqual(json.loads(output.read_text()), {'complete': False})
            self.assertFalse(list(Path(directory).glob('*.partial')))
            compare._write(output, {'complete': True})
            self.assertEqual(json.loads(output.read_text()), {'complete': True})

    def test_one_native_case_uses_unchanged_public_masks_and_frozen_variant_tensors(self):
        with tempfile.TemporaryDirectory() as directory:
            warm, best, _, _ = fixture(Path(directory))
            variants, _ = compare.load_variants(warm, best)
            case = compare.atlanta_cases(MATRIX)[0]
            env = ModuleEnv(case['airport'], abilities=case['abilities'], assistance_version=11)
            _, info = env.reset(seed='train:leak-strength-mask-unit:251056')
            before = deepcopy(env.view()), deepcopy(info), env.rng.getstate()
            for model in variants.values():
                chosen = ModelAgent(model).select(env.view(), info['action_mask'],
                                                 reference_mask=info['reference_action_mask'])
                self.assertTrue(info['action_mask'][chosen])
                self.assertEqual((env.view(), env.info(), env.rng.getstate()), before)
            model = variants['candidate_margin8']
            tensors = compare.tensor_fingerprint(model)
            # Separate unit-test development seed, outside the fresh main cohort.
            result = compare.compare_case(model, case, 14_955_000, 1, duty=.7)
            self.assertEqual(result['case_key'], case_key(case))
            self.assertEqual(result['games'], 1)
            self.assertEqual(len(result['episodes']), 1)
            self.assertEqual(result['clock_model'], 'engine_wall_clock')
            self.assertFalse(result['release_evidence'])
            self.assertEqual(result['assistance_version'], 11)
            self.assertEqual(result['reference_departures'], sum(row['reference_departures'] for row in result['episodes']))
            self.assertEqual(compare.tensor_fingerprint(model), tensors)


if __name__ == '__main__':
    unittest.main()
