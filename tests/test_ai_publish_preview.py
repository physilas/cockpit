"""Explicit preview visibility never confers approval or replaces old crews."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.checkpoints import load_checkpoint, planner_fingerprint, save_checkpoint, weight_fingerprint
from ai.export_browser import export_models
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.module_training_eval import case_key
from ai.modules import CARDS
from ai.publish import main, publish, publish_preview


def fixture(root, *, profile=10, supported_modules=('intern',)):
    model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217,
                                     hidden_size=8, hidden_layers=1, guide_margin=8.)
    checkpoint = root/'runs'/'preview-source'/'best.pt'
    config = {'airport': 'LOG_ATL_GREEN', 'assistance_version': profile,
              'supported_modules': list(supported_modules), 'max_steps': 256,
              'display_name': 'Prior approved source', 'recommended': True,
              'supported_airports': ['MUC'], 'quality': {'approved': True},
              'publication_status': 'requires_independent_route_qualification',
              'source_checkpoint': str(root/'runs'/'prior'/'best.pt'),
              'external_metadata': str(root.parent/'some-private-folder'/'original.pt')}
    save_checkpoint(checkpoint, model, train_config=config, total_steps=120000,
                    module_training_steps=120000)
    report = {'complete': True, 'release_evidence': False, 'evaluation_kind': 'development',
              'weights_sha256': weight_fingerprint(model), 'assistance_version': profile,
              'planner_sha256': planner_fingerprint(3),
              'routes': {'LOG_ATL_GREEN': {'games': 40, 'wins': 0, 'win_rate': 0.},
                         'LOG_LHR_YELLOW': {'games': 40, 'wins': 1, 'win_rate': .025}}}
    evaluation = root/'development.json'
    evaluation.write_text(json.dumps(report))
    return checkpoint, evaluation, report


def card_fixture(root):
    checkpoint, evaluation, report = fixture(root, profile=11, supported_modules=('leak',))
    model, payload = load_checkpoint(checkpoint)
    payload['train_config'].update(supported_cards=list(CARDS), ability_count=1)
    save_checkpoint(checkpoint, model, train_config=payload['train_config'], total_steps=120000,
                    module_training_steps=120000)
    report.pop('routes')
    report['cases'] = {}
    for ordinal, card in enumerate(sorted(CARDS)):
        case = {'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': [card]}
        wins = ordinal % 2
        report['cases'][case_key(case)] = {**case, 'games': 40, 'wins': wins, 'win_rate': wins/40}
    evaluation.write_text(json.dumps(report))
    return checkpoint, evaluation, report


class PublishPreviewTests(unittest.TestCase):
    def setUp(self):
        torch.set_num_threads(1)
        torch.manual_seed(251052)

    def test_explicit_weak_preview_keeps_quality_false_and_preserves_existing_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old_path = root/'ai'/'releases'/'crew1-test'/'best.pt'
            save_checkpoint(old_path, ActorCritic(hidden_size=8, hidden_layers=1),
                train_config={'airport': 'MUC', 'supported_airports': ['MUC'],
                              'quality': {'approved': True}, 'recommended': True, 'display_name': 'Crew 1'},
                total_steps=10)
            previous = export_models(root/'ai'/'releases', root/'frontend'/'web', checkpoints=[old_path])
            old_model = deepcopy(previous['models'][0])
            checkpoint, evaluation, report = fixture(root)
            original_bytes = hashlib.sha256(checkpoint.read_bytes()).digest()
            path, catalog = publish_preview(checkpoint, evaluation, 'intern-preview-test', 'Intern Preview', root=root)
            self.assertEqual(len(catalog['models']), 2)
            old_export = next(model for model in catalog['models'] if model['id'] == old_model['id'])
            self.assertEqual(old_export, old_model)
            preview = next(model for model in catalog['models'] if model['id'].startswith('intern-preview-test/'))
            self.assertFalse(preview['quality']['approved'])
            self.assertFalse(preview['recommended'])
            self.assertTrue(preview['preview']['enabled'])
            self.assertTrue(preview['preview']['user_requested'])
            self.assertEqual(preview['preview']['evaluation_kind'], 'development')
            self.assertEqual(preview['supported_airports'], ['LOG_ATL_GREEN', 'LOG_LHR_YELLOW'])
            self.assertEqual(preview['preview']['route_results'], report['routes'])
            released, payload = load_checkpoint(path)
            original, _ = load_checkpoint(checkpoint)
            self.assertEqual(weight_fingerprint(released), weight_fingerprint(original))
            self.assertEqual(payload['train_config']['publication_status'], 'experimental_preview')
            self.assertFalse(payload['train_config']['quality']['approved'])
            self.assertEqual(payload['train_config']['source_checkpoint'], 'runs/prior/best.pt')
            self.assertEqual(payload['train_config']['external_metadata'], 'external/original.pt')
            self.assertEqual(hashlib.sha256(checkpoint.read_bytes()).digest(), original_bytes)
            self.assertFalse(catalog['skipped'])

    def test_preview_rejects_unfinished_or_mismatched_development_evidence(self):
        mutations = (
            lambda report: report.__setitem__('complete', False),
            lambda report: report.pop('complete'),
            lambda report: report.__setitem__('release_evidence', True),
            lambda report: report.pop('release_evidence'),
            lambda report: report.__setitem__('weights_sha256', 'wrong'),
            lambda report: report.__setitem__('assistance_version', 9),
            lambda report: report.__setitem__('planner_sha256', 'obsolete'),
            lambda report: report.__setitem__('routes', {}),
            lambda report: report['routes']['LOG_ATL_GREEN'].__setitem__('games', 0),
            lambda report: report['routes']['LOG_ATL_GREEN'].__setitem__('games', True),
            lambda report: report['routes']['LOG_ATL_GREEN'].__setitem__('wins', -1),
            lambda report: report['routes']['LOG_ATL_GREEN'].__setitem__('win_rate', .5),
            lambda report: report['routes']['LOG_ATL_GREEN'].__setitem__('win_rate', False),
            lambda report: report['routes'].__setitem__('LOG_ATL_GREEN', []),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, report = fixture(root)
                mutate(report); evaluation.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'rejected-preview', 'Preview', root=root)
                self.assertFalse((root/'ai'/'releases'/'rejected-preview').exists())

    def test_unknown_reference_incompatible_or_research_only_profiles_are_rejected(self):
        for profile in (0, 9, 999, True):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, _ = fixture(root, profile=profile)
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'bad-profile', 'Preview', root=root)
        for flag in ('research_all_modules', 'research_open_risk', 'research_capacity_guard'):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, _ = fixture(root)
                model, payload = load_checkpoint(checkpoint)
                payload['train_config'][flag] = True
                save_checkpoint(checkpoint, model, train_config=payload['train_config'], total_steps=0)
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'wrapper-preview', 'Preview', root=root)

    def test_unimplemented_cards_or_unclaimed_modules_are_rejected(self):
        for route in ('LOG_PRG_GREEN', 'LOG_GIG_YELLOW', 'LOG_OSL_GREEN'):
            with self.subTest(route=route), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, report = fixture(root)
                report['routes'] = {route: {'games': 40, 'wins': 1, 'win_rate': .025}}
                evaluation.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'unsupported-preview', 'Preview', root=root)

    def test_existing_release_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint, evaluation, _ = fixture(root)
            existing = root/'ai'/'releases'/'crew2-existing'
            existing.mkdir(parents=True)
            sentinel = existing/'best.pt'; sentinel.write_bytes(b'preserve existing release')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                publish_preview(checkpoint, evaluation, 'crew2-existing', 'Preview', root=root)
            self.assertEqual(sentinel.read_bytes(), b'preserve existing release')
            self.assertFalse((existing/'development.json').exists())

    def test_weak_report_cannot_use_qualification_path_and_cli_requires_preview_flag(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint, evaluation, _ = fixture(root)
            with self.assertRaises(ValueError):
                publish(checkpoint, evaluation, 'not-qualified', 'Preview', root=root, require_all=False)
            self.assertFalse((root/'ai'/'releases'/'not-qualified').exists())
        arguments = ['ai.publish', '--checkpoint', 'source.pt', '--evaluation', 'report.json',
                     '--release-id', 'requested-preview', '--name', 'Preview']
        for explicit in (False, True):
            with patch('sys.argv', arguments+(['--experimental-preview'] if explicit else [])), \
                    patch('ai.publish.publish', return_value=(Path('qualified.pt'), {})) as normal, \
                    patch('ai.publish.publish_preview', return_value=(Path('preview.pt'), {})) as preview:
                main()
                self.assertEqual(preview.call_count, int(explicit))
                self.assertEqual(normal.call_count, int(not explicit))

    def test_explicit_profile11_card_preview_lists_only_tested_cases_including_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint, evaluation, report = card_fixture(root)
            # A preview may expose a tested subset. Other cards on the same
            # route must not become selectable merely via supported_airports.
            kept = sorted(report['cases'])[:2]
            report['cases'] = {key: report['cases'][key] for key in kept}
            evaluation.write_text(json.dumps(report))
            source_bytes = checkpoint.read_bytes()
            path, catalog = publish_preview(checkpoint, evaluation, 'leak-card-preview', 'Crew Cards Test', root=root)
            entry = catalog['models'][0]
            self.assertFalse(entry['quality']['approved'])
            self.assertFalse(entry['recommended'])
            self.assertEqual(entry['assistance_version'], 11)
            self.assertEqual(entry['supported_airports'], ['LOG_ATL_YELLOW'])
            self.assertTrue(entry['preview']['enabled'])
            self.assertTrue(entry['preview']['user_requested'])
            self.assertNotIn('route_results', entry['preview'])
            self.assertEqual(entry['preview']['supported_cases'],
                             [{'airport': 'LOG_ATL_YELLOW', 'abilities': report['cases'][key]['abilities']}
                              for key in kept])
            self.assertEqual(entry['preview']['case_results'],
                             {key: {field: report['cases'][key][field] for field in ('games', 'wins', 'win_rate')}
                              for key in kept})
            self.assertEqual(min(row['win_rate'] for row in entry['preview']['case_results'].values()), 0.)
            original, _ = load_checkpoint(checkpoint)
            saved, payload = load_checkpoint(path)
            self.assertEqual(weight_fingerprint(saved), weight_fingerprint(original))
            self.assertEqual(payload['train_config']['preview'], entry['preview'])
            self.assertEqual(checkpoint.read_bytes(), source_bytes)
            self.assertFalse(catalog['skipped'])
            with self.assertRaisesRegex(ValueError, 'already exists'):
                publish_preview(checkpoint, evaluation, 'leak-card-preview', 'Different name', root=root)

    def test_card_case_identity_legality_and_counts_cannot_be_pooled_or_guessed(self):
        def mutate_first(report, field, value):
            report['cases'][next(iter(report['cases']))][field] = value

        def rename_first(report):
            key = next(iter(report['cases']))
            report['cases']['another-key'] = report['cases'].pop(key)

        mutations = [
            lambda report: report.__setitem__('cases', {}),
            lambda report: report.__setitem__('routes', {'LOG_ATL_GREEN': {'games': 1, 'wins': 0, 'win_rate': 0.}}),
            rename_first,
            lambda report: mutate_first(report, 'case_key', 'LOG_ATL_YELLOW|wrong'),
            lambda report: mutate_first(report, 'airport', 'LOG_PRG_GREEN'),
            lambda report: mutate_first(report, 'abilities', []),
            lambda report: mutate_first(report, 'abilities', ['adaptation', 'control']),
            lambda report: mutate_first(report, 'abilities', ['unsupported-card']),
            lambda report: mutate_first(report, 'modules', ['kerosene']),
            lambda report: mutate_first(report, 'games', 0),
            lambda report: mutate_first(report, 'games', True),
            lambda report: mutate_first(report, 'wins', 41),
            lambda report: mutate_first(report, 'wins', False),
            lambda report: mutate_first(report, 'win_rate', .8),
        ]
        for ordinal, mutate in enumerate(mutations):
            with self.subTest(ordinal=ordinal), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, report = card_fixture(root)
                mutate(report); evaluation.write_text(json.dumps(report))
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'rejected-cards', 'Cards Test', root=root)
                self.assertFalse((root/'ai'/'releases'/'rejected-cards').exists())

    def test_card_preview_requires_declared_registered_cards_modules_and_count(self):
        mutations = [
            lambda config: config.pop('supported_cards'),
            lambda config: config.__setitem__('supported_cards', []),
            lambda config: config.__setitem__('supported_cards', ['invented-card']),
            lambda config: config.__setitem__('supported_cards', [*CARDS, CARDS[0]]),
            lambda config: config.__setitem__('supported_modules', ['intern']),
            lambda config: config.__setitem__('supported_modules', ['leak', 'invented-module']),
            lambda config: config.__setitem__('ability_count', 2),
        ]
        for ordinal, mutate in enumerate(mutations):
            with self.subTest(ordinal=ordinal), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                checkpoint, evaluation, _ = card_fixture(root)
                model, payload = load_checkpoint(checkpoint)
                mutate(payload['train_config'])
                save_checkpoint(checkpoint, model, train_config=payload['train_config'], total_steps=120000)
                with self.assertRaises(ValueError):
                    publish_preview(checkpoint, evaluation, 'unclaimed-cards', 'Cards Test', root=root)
                self.assertFalse((root/'ai'/'releases'/'unclaimed-cards').exists())

    def test_duplicate_json_keys_are_rejected_before_a_release_is_created(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            checkpoint, evaluation, report = card_fixture(root)
            serialized = json.dumps(report)
            evaluation.write_text('{"cases": {},' + serialized[1:])
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                publish_preview(checkpoint, evaluation, 'duplicate-report', 'Cards Test', root=root)
            self.assertFalse((root/'ai'/'releases'/'duplicate-report').exists())


if __name__ == '__main__': unittest.main()
