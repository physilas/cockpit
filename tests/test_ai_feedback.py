"""Offline thumbs preserve consent, revisions, neutral defaults and schemas."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ai.feedback import load_feedback


ROOT = Path(__file__).resolve().parents[1]
ARCHIVES = ROOT / 'ai/data/archives'
HISTORICAL_EXPORTS = tuple(ARCHIVES / path for path in (
    '2026-10-24/feedback/c12eb23d-13f0-4e84-82ba-4d31f7090f11/'
    'r98-a636302ace2dfbf83eda22ac8c9f93c9ba3d115e69877249f1cfd515f5cd1c43.json',
    '2026-10-18/feedback/ae12b052-5713-4bbe-985b-e2eca828eb01/'
    'r102-82868df61cba7cdf6936f7a045823f3b65c2b0378ce4adc453abdb76566a4411.json',
    '2026-10-18/feedback/814d2b6f-872c-40d8-a72e-69f6ee047ea8/'
    'r22-6126ee6dc7f4d019d37fb1f86a75b0c26e984c71df69c104880805a2243f0400.json',
))
FIXTURE = HISTORICAL_EXPORTS[0]


class FeedbackImportTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())
        event = next(event for event in self.data['session']['events']
                     if event.get('feedback', {}).get('value') and not event['voided'])
        self.data['session']['events'] = [event]
        event['feedback']['value'] = 1

    @staticmethod
    def write(folder, data, name='feedback.json'):
        path = Path(folder) / name
        path.write_text(json.dumps(data))
        return path

    def load(self, data=None, **options):
        with tempfile.TemporaryDirectory() as folder:
            return load_feedback([self.write(folder, self.data if data is None else data)],
                                 schema_version=1, **options)

    def test_actual_archive_accepts_rated_ai_moves_in_lost_games(self):
        dataset = load_feedback(HISTORICAL_EXPORTS, schema_version=1)
        self.assertEqual(dataset.manifest['decisions'], 16)
        self.assertEqual(dataset.manifest['sessions'], 3)
        self.assertEqual(dataset.manifest['ratings'], {'-1': 7, '1': 9})
        self.assertEqual(dataset.manifest['legacy_scale_normalized'], 9)
        self.assertEqual(set(dataset.ratings), {-1, 1})
        self.assertTrue(all(mask[action] for mask, action in zip(dataset.masks, dataset.actions)))
        self.assertFalse(dataset.manifest['model_updates_applied'])
        self.assertFalse(dataset.manifest['critic_targets'])
        self.assertIsNone(dataset.reference_masks)
        self.assertEqual(len(dataset.manifest['rated_models']), 3)
        self.assertEqual(sum(row['decisions'] for row in dataset.manifest['rated_models']), 16)
        self.assertTrue(all(row['id'] and row['fingerprint'] for row in dataset.manifest['rated_models']))

    def test_neutral_pending_voided_human_implicit_and_nonconsented_are_ignored(self):
        original = self.data['session']['events'][0]
        events = []
        for index, change in enumerate(('neutral', 'pending', 'voided', 'human', 'implicit', 'incompatible')):
            event = deepcopy(original); event['id'] = index
            if change == 'neutral': event['feedback']['value'] = 0
            if change == 'pending': event['feedback']['committed'] = False
            if change == 'voided': event['voided'] = True
            if change == 'human': event['actor'] = 'human'
            if change == 'implicit': event['feedback']['explicit'] = False
            if change == 'incompatible': event['training_compatible'] = False
            events.append(event)
        accepted = deepcopy(original); accepted['id'] = 20
        self.data['session']['events'] = events + [accepted]
        dataset = self.load()
        self.assertEqual(len(dataset.actions), 1)
        self.assertEqual(dataset.manifest['excluded']['neutral'], 1)
        self.assertEqual(dataset.manifest['excluded']['uncommitted_or_implicit'], 2)
        self.data['session']['consent'] = None
        with self.assertRaisesRegex(ValueError, 'No explicit'):
            self.load()

    def test_latest_neutral_or_revoked_revision_removes_old_labels(self):
        with tempfile.TemporaryDirectory() as folder:
            older = self.write(folder, self.data)
            changed = deepcopy(self.data)
            changed['session']['data_revision'] += 1
            changed['session']['events'][0]['feedback']['value'] = 0
            newer = self.write(folder, changed, 'newer.json')
            with self.assertRaisesRegex(ValueError, 'No explicit'):
                load_feedback([older, newer], schema_version=1)
            changed['session']['events'][0]['feedback']['value'] = 1
            changed['session']['consent'] = None
            newer.write_text(json.dumps(changed))
            with self.assertRaisesRegex(ValueError, 'No explicit'):
                load_feedback([older, newer], schema_version=1)

    def test_export_dedup_and_conflicting_same_revision(self):
        expected = self.load()
        batch = deepcopy(self.data)
        batch['format'] = 'flyteam-learning-data'
        batch['sessions'] = [batch.pop('session')]
        with tempfile.TemporaryDirectory() as folder:
            self.write(folder, self.data)
            duplicate = self.write(folder, batch, 'browser.json')
            actual = load_feedback([folder], schema_version=1)
            self.assertEqual(actual.manifest['sha256'], expected.manifest['sha256'])
            self.assertEqual(len(actual.actions), 1)
            batch['sessions'][0]['events'][0]['feedback']['value'] = -1
            duplicate.write_text(json.dumps(batch))
            with self.assertRaisesRegex(ValueError, 'Conflicting'):
                load_feedback([folder], schema_version=1)

    def test_malformed_rated_rows_fail_closed(self):
        def event(data): return data['session']['events'][0]
        changes = [
            lambda data: event(data)['feedback'].__setitem__('value', True),
            lambda data: event(data)['feedback'].__setitem__('value', 3),
            lambda data: event(data).__setitem__('voided', None),
            lambda data: event(data)['decision']['observation'].__setitem__(3, float('nan')),
            lambda data: event(data)['decision']['observation'].__setitem__(3, True),
            lambda data: event(data)['decision']['action_mask'].__setitem__(event(data)['action_id'], False),
            lambda data: event(data)['action'].__setitem__('die', 99),
            lambda data: data['session']['consent'].__setitem__('accepted_at', '2026-10-25T12:00:00'),
            lambda data: data['schema']['features'].reverse(),
        ]
        for index, change in enumerate(changes):
            with self.subTest(index=index):
                changed = deepcopy(self.data); change(changed)
                with self.assertRaises(ValueError): self.load(changed)

    @staticmethod
    def schema3_export():
        from ai.modules import ModuleEnv, module_schema
        env = ModuleEnv('LOG_YUL_GREEN', assistance_version=9)
        observation, info = env.reset(seed='feedback-fixture')
        action_id = next(index for index, allowed in enumerate(info['action_mask']) if allowed)
        action = env.actions[action_id]
        move = {**action.to_dict(), 'role': env.current_role}
        if action.kind == 'place':
            slot = env.slots[action.slot]
            move.update(target=slot.target, index=slot.index, radio_index=slot.radio_index)
        return {'format': 'flyteam-learning-session', 'version': 1,
                'schema': module_schema(), 'action_mask_version': 2,
                'session': {'id': 'schema3-fixture', 'data_revision': 1, 'mode': 'feedback',
                    'schema': module_schema(), 'schema_version': 3, 'action_mask_version': 2,
                    'human_role': env.other_role(env.current_role),
                    'scenario': {'engine_code': 'LOG_YUL_GREEN'}, 'status': 'verloren',
                    'consent': {'version': '2026-10-18', 'accepted_at': '2026-10-25T12:00:00Z'},
                    'events': [{'id': 0, 'actor': 'ai', 'voided': False, 'training_compatible': True,
                        'action_id': action_id, 'action': move,
                        'decision': {'role': env.current_role, 'observation': observation,
                            'action_mask': info['action_mask'],
                            'reference_action_mask': info['reference_action_mask']},
                        'feedback': {'value': -1, 'explicit': True, 'committed': True}}]}}

    def test_schema3_batch_uses_session_schema_and_saved_reference(self):
        data = self.schema3_export()
        data['format'] = 'flyteam-learning-data'
        data['sessions'] = [data.pop('session')]
        data['schema'] = self.data['schema']
        with tempfile.TemporaryDirectory() as folder:
            dataset = load_feedback([self.write(folder, data)], schema_version=3)
        self.assertEqual(len(dataset.observations[0]), 489)
        self.assertEqual(len(dataset.masks[0]), 217)
        self.assertEqual(dataset.ratings, (-1,))
        self.assertEqual(dataset.reference_masks[0],
                         tuple(data['sessions'][0]['events'][0]['decision']['reference_action_mask']))
        self.assertTrue(dataset.manifest['requires_saved_reference_masks'])

    def test_schema3_missing_or_invalid_reference_is_not_fabricated(self):
        original = self.schema3_export()
        for invalid in (None, [False] * 217, [True] * 217):
            with self.subTest(invalid=invalid is None), tempfile.TemporaryDirectory() as folder:
                data = deepcopy(original)
                data['session']['events'][0]['decision']['reference_action_mask'] = invalid
                with self.assertRaisesRegex(ValueError, 'reference mask'):
                    load_feedback([self.write(folder, data)], schema_version=3)
        with self.assertRaisesRegex(ValueError, 'schema 3'):
            load_feedback([FIXTURE], schema_version=3)

    def test_tensors_are_auxiliary_only_and_importer_is_torch_free(self):
        result = subprocess.run([sys.executable, '-c',
            "import sys; import ai.feedback; assert 'torch' not in sys.modules"],
            cwd=ROOT, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        dataset = self.load()
        tensors = dataset.tensors()
        self.assertEqual(set(tensors), {'observations', 'masks', 'actions', 'ratings'})
        self.assertEqual(tensors['ratings'].tolist(), [1.])
        self.assertFalse(any(value.requires_grad for value in tensors.values()))


if __name__ == '__main__':
    unittest.main()
