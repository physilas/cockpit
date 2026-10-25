"""Full-catalogue previews preserve native cases, weights and failed evidence."""
from concurrent.futures import Future
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai import preview_matrix_eval as preview
from ai.agents import ModelAgent
from ai.checkpoints import save_checkpoint, weight_fingerprint
from ai.modules import ModuleEnv
from ai.module_training_eval import case_key
from ai.nn_model import ActorCritic, GuidedResidualActorCritic


def make_model():
    torch.manual_seed(251060)
    return GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)


def save_fixture(path, model, **changes):
    config = {'assistance_version': 10, 'supported_modules': ['intern'],
              'supported_cards': [], 'ability_count': 0,
              'phase_kind': 'new_public_module_profile_10',
              'source_phase_steps': 500347,
              'curriculum_airports': ['LOG_ATL_GREEN', 'LOG_LHR_YELLOW'], **changes}
    save_checkpoint(path, model, train_config=config, total_steps=120272)


def result_fixture(case, seed=14_960_000, won=False):
    key = case_key(case)
    identity = {field: deepcopy(case[field]) for field in ('airport', 'abilities', 'modules')}
    record = {**identity, 'case_key': key, 'scenario': case['airport'], 'seed': seed,
              'status': 'gewonnen' if won else 'verloren',
              'decisions': 3, 'reference_departures': 1}
    return {**identity, 'case_key': key, 'case_scope': case['case_scope'],
            'complete': True, 'release_evidence': False, 'qualification_used': False,
            'assistance_version': 10, 'clock_model': 'engine_wall_clock',
            'games': 1, 'wins': int(won), 'win_rate': float(won),
            'decisions': 3, 'reference_departures': 1,
            'reference_departure_rate': 1 / 3, 'episodes': [record]}


class PreviewMatrixEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_complete_official_matrix_plus_exact_six_separate_custom_cases(self):
        cases = preview.catalogue_cases()
        self.assertEqual(len(cases), 192)
        self.assertEqual(len({case_key(row) for row in cases}), 192)
        self.assertEqual(len({row['airport'] for row in cases}), 27)
        self.assertEqual({row['case_scope'] for row in cases[:186]}, {'official_matrix'})
        self.assertEqual({row['case_scope'] for row in cases[186:]}, {'legacy_catalogue'})
        self.assertEqual(tuple(row['airport'] for row in cases[186:]), preview.LEGACY_AIRPORTS)
        self.assertTrue(all(row['abilities'] == [] and row['modules'] == [] for row in cases[186:]))
        preview.validate_seed_budget(14_960_000, 20)
        self.assertEqual(14_960_000 + 191 * preview.SEED_STRIDE + 19, 14_979_119)
        with tempfile.TemporaryDirectory() as directory:
            matrix = json.loads(preview.DEFAULT_MATRIX.read_text())
            matrix['cases'] = matrix['cases'][:-1]
            path = Path(directory) / 'incomplete.json'
            path.write_text(json.dumps(matrix))
            with self.assertRaises(ValueError):
                preview.catalogue_cases(path)

    def test_load_requires_exact_release_tensors_config_and_native_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            reference, copy = Path(directory) / 'original.pt', Path(directory) / 'copy.pt'
            model = make_model()
            save_fixture(reference, model)
            save_fixture(copy, model, display_name='Metadata-only preview copy')
            reference_bytes, copy_bytes = reference.read_bytes(), copy.read_bytes()
            loaded, metadata = preview.load_crew3(copy, reference_checkpoint=reference)
            self.assertEqual(weight_fingerprint(loaded), weight_fingerprint(model))
            self.assertEqual(metadata['tensor_sha256'], preview.tensor_fingerprint(model))
            self.assertEqual(metadata['original_training_claims']['supported_modules'], ['intern'])
            self.assertEqual(metadata['original_training_claims']['supported_cards'], [])
            self.assertFalse(metadata['tensor_values_changed'])
            self.assertFalse(metadata['policy_configuration_changed'])
            self.assertEqual(reference.read_bytes(), reference_bytes)
            self.assertEqual(copy.read_bytes(), copy_bytes)
            changed = deepcopy(model)
            with torch.no_grad():
                changed.residual.actor.bias[0] += 1.
            save_fixture(copy, changed)
            with self.assertRaises(ValueError):
                preview.load_crew3(copy, reference_checkpoint=reference)
            changed = deepcopy(model)
            changed.config['guide_margin'] = changed.guide_margin = 8.
            save_fixture(copy, changed)
            self.assertEqual(preview.tensor_fingerprint(changed), preview.tensor_fingerprint(model))
            with self.assertRaises(ValueError):
                preview.load_crew3(copy, reference_checkpoint=reference)
            for extra in ({'assistance_version': 11}, {'research_all_modules': True}):
                save_fixture(copy, model, **extra)
                with self.subTest(extra=extra), self.assertRaises(ValueError):
                    preview.load_crew3(copy, reference_checkpoint=reference)

    def test_native_custom_episode_keeps_public_masks_rng_weights_and_engine_clock(self):
        model = make_model()
        model.train()
        before_weights = weight_fingerprint(model)
        before_random, before_torch = random.getstate(), torch.get_rng_state().clone()
        created, selections = [], []
        original_select = ModelAgent.select

        class RecordingModuleEnv(ModuleEnv):
            def __init__(self, *args, **kwargs):
                created.append((args, deepcopy(kwargs)))
                super().__init__(*args, **kwargs)

        def checked_select(agent, view, mask, *, reference_mask=None):
            self.assertIsNotNone(reference_mask)
            self.assertTrue(any(reference_mask))
            self.assertTrue(all(not advice or mask[index]
                                for index, advice in enumerate(reference_mask)))
            self.assertNotIn('partner_dice', view)
            action = original_select(agent, view, mask, reference_mask=reference_mask)
            self.assertTrue(mask[action])
            selections.append(int(not reference_mask[action]))
            return action

        case = {'airport': 'MUC', 'modules': [], 'abilities': [], 'case_scope': 'legacy_catalogue'}
        with patch.object(preview, 'ModuleEnv', RecordingModuleEnv), \
                patch.object(preview, 'check_stop'), patch.object(ModelAgent, 'select', checked_select):
            result = preview.run_case(model, case, 1, 14_979_000)
        preview.validate_result(result, case, 1, 14_979_000)
        self.assertEqual(created[0][0], ('MUC',))
        self.assertEqual(created[0][1]['assistance_version'], 10)
        self.assertEqual(created[0][1]['abilities'], [])
        for prohibited in ('clock', 'step_seconds', 'curriculum_cases', 'curriculum_airports'):
            self.assertNotIn(prohibited, created[0][1])
        self.assertEqual(result['reference_departures'], sum(selections))
        self.assertEqual(result['decisions'], len(selections))
        self.assertNotIn('training_budget_failure', result['episodes'][0])
        self.assertEqual(result['clock_model'], 'engine_wall_clock')
        self.assertFalse(result['release_evidence'])
        self.assertTrue(model.training)
        self.assertEqual(weight_fingerprint(model), before_weights)
        self.assertEqual(random.getstate(), before_random)
        self.assertTrue(torch.equal(torch.get_rng_state(), before_torch))

    def test_official_case_delegates_to_native_public_evaluator_without_curriculum(self):
        case = {'airport': 'LOG_ATL_GREEN', 'modules': ['intern'], 'abilities': [],
                'case_scope': 'official_matrix'}
        sentinel = {'clock_model': 'engine_wall_clock'}
        with patch.object(preview, 'run_public_case', return_value=sentinel) as run:
            model = object()
            result = preview.run_case(model, case, 20, 14_960_000, .7)
        run.assert_called_once_with(model, case, 20, 14_960_000,
                                    cpu_duty_cycle=.7, assistance_version=10)
        self.assertEqual(result, {**sentinel, 'case_scope': 'official_matrix'})

    def test_custom_scope_cannot_hide_an_official_route_card_or_module(self):
        model = make_model()
        bad = [
            {'airport': 'LOG_ATL_GREEN', 'modules': [], 'abilities': []},
            {'airport': 'MUC', 'modules': ['intern'], 'abilities': []},
            {'airport': 'MUC', 'modules': [], 'abilities': ['adaptation']},
            {'airport': 'TRAIN_SHORT', 'modules': [], 'abilities': []},
        ]
        with patch.object(preview, 'ModuleEnv', side_effect=AssertionError('No engine may start')):
            for case in bad:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    preview.run_catalogue_case(model, case, 1, 14_960_000)

    def test_result_validation_retains_zero_wins_and_rejects_misidentified_or_invented_evidence(self):
        case = {'airport': 'MUC', 'modules': [], 'abilities': [], 'case_scope': 'legacy_catalogue'}
        row = result_fixture(case)
        preview.validate_result(row, case, 1, 14_960_000)
        rows = {case_key(case): deepcopy(row)}
        self.assertEqual(preview._positive_cases(rows), {})
        self.assertEqual(rows[case_key(case)]['wins'], 0)
        rows['MUC|'] = result_fixture(case, won=True)
        positive = preview._positive_cases(rows)
        self.assertEqual(positive['MUC|']['wins'], 1)
        self.assertNotIn('episodes', positive['MUC|'])
        mutations = [('wins', 1), ('win_rate', .5), ('case_scope', 'official_matrix'),
                     ('release_evidence', True), ('clock_model', 'logical_one_second_per_decision'),
                     ('decisions', 4), ('assistance_version', 11)]
        for key, value in mutations:
            changed = deepcopy(row); changed[key] = value
            with self.subTest(field=key), self.assertRaises(RuntimeError):
                preview.validate_result(changed, case, 1, 14_960_000)
        for key, value in [('seed', 15_000_000), ('modules', ['intern']),
                           ('scenario', 'LOG_ATL_GREEN'), ('training_budget_failure', True)]:
            changed = deepcopy(row); changed['episodes'][0][key] = value
            with self.subTest(episode_field=key), self.assertRaises(RuntimeError):
                preview.validate_result(changed, case, 1, 14_960_000)

    def test_early_cli_bounds_stop_and_existing_output_never_load_or_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            output, stop = Path(directory) / 'report.json', Path(directory) / 'STOP'
            with patch.object(preview, 'STOP_FILE', stop), \
                    patch.object(preview, 'load_crew3', side_effect=AssertionError('No loading')), \
                    patch.object(preview, 'ProcessPoolExecutor', side_effect=AssertionError('No launch')):
                invalid = [('--workers', '9'), ('--cpu-duty-cycle', '.8'),
                           ('--cpu-duty-cycle', 'nan'), ('--games', '101'),
                           ('--seed', '15000000'), ('--seed', '14990000')]
                for arguments in invalid:
                    with self.subTest(arguments=arguments), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        preview.main(['--output', str(output), *arguments])
                    self.assertFalse(output.exists())
                stop.write_text('user requested stop')
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    preview.main(['--output', str(output)])
                self.assertEqual(stop.read_text(), 'user requested stop')
                stop.unlink()
                output.write_text('preserve')
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    preview.main(['--output', str(output)])
                self.assertEqual(output.read_text(), 'preserve')
                output.unlink()
                output.symlink_to(Path(directory) / 'missing.json')
                with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    preview.main(['--output', str(output)])

    def test_atomic_report_never_overwrites_first_publication_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            preview._write(output, {'complete': False}, initial=True)
            with self.assertRaises(FileExistsError):
                preview._write(output, {'complete': True}, initial=True)
            self.assertEqual(json.loads(output.read_text()), {'complete': False})
            preview._write(output, {'complete': False, 'error': 'worker failed'})
            self.assertFalse(json.loads(output.read_text())['complete'])
            self.assertEqual(list(Path(directory).iterdir()), [output])

    def test_worker_failure_preserves_incomplete_report_and_full_expected_scope(self):
        class FailingExecutor:
            def __init__(self, *args, **kwargs):
                pass

            def submit(self, function, task):
                future = Future()
                future.set_exception(RuntimeError('Explicit failed case'))
                return future

            def shutdown(self, **kwargs):
                pass

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'report.json'
            metadata = {'weights_sha256': 'unchanged', 'original_training_claims': {'supported_modules': ['intern']}}
            with patch.object(preview, 'check_stop'), \
                    patch.object(preview, 'load_crew3', return_value=(None, metadata)), \
                    patch.object(preview, 'ProcessPoolExecutor', FailingExecutor):
                with self.assertRaisesRegex(RuntimeError, 'Explicit failed case'):
                    preview.main(['--output', str(output)])
            report = json.loads(output.read_text())
            self.assertFalse(report['complete'])
            self.assertFalse(report['release_evidence'])
            self.assertEqual(report['error_type'], 'RuntimeError')
            self.assertEqual(report['expected_case_count'], 192)
            self.assertEqual(report['expected_games'], 3840)
            self.assertEqual(len(report['case_seeds']), 192)
            self.assertEqual(report['new_training_decisions'], 0)
            self.assertFalse(report['weights_changed'])


if __name__ == '__main__':
    unittest.main()
