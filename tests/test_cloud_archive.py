import hashlib
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, call
from urllib.error import HTTPError

from cloud.archive_to_github import GitHubArchive, archive_batches, validate_record


def record():
    payload = json.loads((Path(__file__).resolve().parents[1] / 'ai/data/demonstrations/'
                         '2026-10-18-MUC-605a503f-d565-4450-b62e-a05031efc5fb.json').read_bytes())
    raw = json.dumps(payload, ensure_ascii=False)
    s = payload['session']
    return {'participant_hash': 'a' * 64, 'session_id': s['id'], 'revision': s['data_revision'],
            'mode': s['mode'], 'status': s['status'], 'event_count': len(s['events']),
            'received_at': payload['received_at'], 'payload': raw,
            'sha256': hashlib.sha256(raw.encode()).hexdigest()}


class ArchiveTests(TestCase):
    def test_exact_payload_and_no_installation_hash_in_archive_path(self):
        row = record()
        path, raw = validate_record(row)
        self.assertEqual(raw, row['payload'].encode())
        self.assertIn(row['sha256'], path)
        self.assertNotIn(row['participant_hash'], path)
        self.assertNotIn('participant_hash', json.loads(raw))

    def test_invalid_digest_metadata_and_paths_stop_before_publish(self):
        for changes in ({'sha256': '0' * 64}, {'revision': 1}, {'session_id': '../../bad'},
                        {'status': 'active'}, {'event_count': 999}):
            with self.subTest(changes=changes):
                cloud = Mock(return_value={'records': [{**record(), **changes}]})
                github = Mock()
                with self.assertRaises(ValueError):
                    archive_batches(github, cloud)
                github.publish_and_verify.assert_not_called()
                cloud.assert_called_once_with('export', {})

    def test_failed_push_or_verification_never_acknowledges_deletion(self):
        for failure in (ConnectionError('push failed'), ValueError('remote checksum mismatch')):
            github = Mock()
            github.publish_and_verify.side_effect = failure
            cloud = Mock(return_value={'records': [record()]})
            with self.assertRaises(type(failure)):
                archive_batches(github, cloud)
            cloud.assert_called_once_with('export', {})

    def test_publish_and_verify_precede_acknowledgement(self):
        row = record()
        sequence = Mock()
        github = Mock()
        github.publish_and_verify.return_value = 'published-commit'
        cloud = Mock(side_effect=[{'records': [row]}, {'results': [{
            'session_id': row['session_id'], 'revision': row['revision'], 'status': 'deleted'}]}, {'records': []}])
        sequence.attach_mock(cloud, 'cloud')
        sequence.attach_mock(github.publish_and_verify, 'publish')
        self.assertEqual(archive_batches(github, cloud, output=lambda _: None), 1)
        self.assertEqual([c[0] for c in sequence.mock_calls], ['cloud', 'publish', 'cloud', 'cloud'])
        self.assertEqual(sequence.mock_calls[2], call.cloud('ack', {'records': [{
            k: row[k] for k in ('participant_hash', 'session_id', 'revision', 'sha256')}]}))

    def test_existing_archive_is_verified_without_another_commit(self):
        path, raw = validate_record(record())
        github = GitHubArchive('physilas/cockpit', 'test-token')
        github.api = Mock(return_value={'object': {'sha': 'published-head'}})
        github.read = Mock(return_value=raw)
        self.assertEqual(github.publish_and_verify({path: raw}), 'published-head')
        self.assertEqual(github.read.call_args_list, [call(path, 'published-head'), call(path, 'published-head')])
        self.assertTrue(all('method' not in c.kwargs for c in github.api.call_args_list))

    def test_new_commit_is_published_without_force_and_read_back_from_branch(self):
        path, raw = validate_record(record())
        github = GitHubArchive('physilas/cockpit', 'test-token')
        github.read = Mock(side_effect=[HTTPError('test', 404, 'missing', None, None), raw])
        github.api = Mock(side_effect=[{'object': {'sha': 'old'}}, {'sha': 'blob'},
            {'tree': {'sha': 'old-tree'}}, {'sha': 'new-tree'}, {'sha': 'new-commit'},
            {}, {'object': {'sha': 'published-head'}}])
        self.assertEqual(github.publish_and_verify({path: raw}), 'published-head')
        self.assertIn(call('/git/refs/heads/main', method='PATCH', data={'sha': 'new-commit', 'force': False}),
                      github.api.call_args_list)
        self.assertEqual(github.read.call_args_list[-1], call(path, 'published-head'))

    def test_remote_corruption_stops_the_archive(self):
        path, raw = validate_record(record())
        github = GitHubArchive('physilas/cockpit', 'test-token')
        github.api = Mock(return_value={'object': {'sha': 'head'}})
        github.read = Mock(side_effect=[raw, b'corrupt'])
        with self.assertRaises(ValueError):
            github.publish_and_verify({path: raw})

    def test_concurrent_commit_retries_from_new_head(self):
        path, raw = validate_record(record())
        github = GitHubArchive('physilas/cockpit', 'test-token')
        github.read = Mock(side_effect=[HTTPError('test', 404, 'missing', None, None), raw, raw])
        github.api = Mock(side_effect=[{'object': {'sha': 'old'}}, {'sha': 'blob'},
            {'tree': {'sha': 'old-tree'}}, {'sha': 'new-tree'}, {'sha': 'orphan'},
            HTTPError('test', 422, 'not fast forward', None, None),
            {'object': {'sha': 'concurrent-head'}}, {'object': {'sha': 'concurrent-head'}}])
        self.assertEqual(github.publish_and_verify({path: raw}), 'concurrent-head')

    def test_acknowledgement_for_wrong_session_is_rejected(self):
        github = Mock()
        cloud = Mock(side_effect=[{'records': [record()]}, {'results': [{
            'session_id': 'wrong', 'revision': 70, 'status': 'deleted'}]}])
        with self.assertRaises(ValueError):
            archive_batches(github, cloud)

    def test_monthly_keepalive_uses_a_deterministic_non_training_file(self):
        github = GitHubArchive('physilas/cockpit', 'test-token')
        github.publish_and_verify = Mock()
        github.keep_schedule_active()
        first = github.publish_and_verify.call_args
        github.keep_schedule_active()
        self.assertEqual(first, github.publish_and_verify.call_args)
        path = next(iter(first.args[0]))
        self.assertTrue(path.startswith('.github/archive-keepalive/'))
        self.assertTrue(path.endswith('.txt'))
