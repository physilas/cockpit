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
        for flag in ('research_all_modules', 'research_open_risk'):
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


if __name__ == '__main__': unittest.main()
