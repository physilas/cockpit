"""Audit the published Navigator against its frozen inputs and preserved peers."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from ai.checkpoints import load_checkpoint,weight_fingerprint
from ai.module_training_eval import case_key
from ai.preview_matrix_eval import catalogue_cases
from ai.strategy_fingerprint import public_strategy_fingerprint


ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'ai/releases/crew5-planner-2026-10-28-v1'


@unittest.skipUnless(RELEASE.is_dir(),'Navigator release not yet published')
class NavigatorReleaseTests(unittest.TestCase):
    def test_old_crews_remain_identical_and_every_new_case_is_selectable(self):
        text=(ROOT/'frontend/web/js/ai-models.js').read_text()
        catalog=json.loads(text.split(' = ',1)[1].strip().rstrip(';'))
        byid={m['id']:m for m in catalog['models']}
        previous=json.loads((RELEASE/'previous-crews.json').read_text())
        for identity,model in previous['models'].items():self.assertEqual(model,byid[identity])
        for path,digest in previous['files'].items():
            self.assertEqual(digest,hashlib.sha256((ROOT/path).read_bytes()).hexdigest(),path)
        row=byid[RELEASE.name+'/best.pt']
        self.assertFalse(row['ui_hidden']);self.assertEqual(5,row['crew_number'])
        self.assertEqual(13,row['assistance_version']);self.assertEqual(256,row['max_steps'])
        self.assertTrue(row['preview']['enabled']);self.assertFalse(row['quality']['approved'])
        self.assertFalse(row['preview'].get('positive_only',False))
        expected={case_key(r) for r in catalogue_cases()}
        self.assertEqual(expected,{case_key(r) for r in row['preview']['supported_cases']})
        self.assertEqual(expected,set(row['preview']['case_results']))

    def test_source_tensors_and_exact_frozen_input_are_preserved(self):
        model,payload=load_checkpoint(RELEASE/'best.pt')
        manifest=json.loads((RELEASE/'confirmation-protocol.json').read_text())
        digest=weight_fingerprint(model);config=payload['train_config']
        self.assertEqual(manifest['candidate_weights_sha256'],digest)
        self.assertEqual(config['source_weights_sha256'],digest)
        self.assertFalse(config['new_tensor_training_in_this_preparation'])
        frozen=gzip.decompress((RELEASE/'confirmation-input.pt.gz').read_bytes())
        self.assertEqual(manifest['candidate_file_sha256'],hashlib.sha256(frozen).hexdigest())
        self.assertEqual(manifest['public_strategy_sha256'],public_strategy_fingerprint(13))
        self.assertEqual(manifest['public_strategy_sha256'],config['planner_sha256'])

    def test_complete_confirmation_is_bound_without_granting_quality_approval(self):
        evidence=json.loads((RELEASE/'development.json').read_text())
        protocol=RELEASE/'confirmation-protocol.json';manifest=json.loads(protocol.read_text())
        self.assertTrue(evidence['complete']);self.assertTrue(evidence['qualification_used'])
        self.assertFalse(evidence['release_evidence']);self.assertFalse(evidence['qualification_granted'])
        self.assertEqual(hashlib.sha256(protocol.read_bytes()).hexdigest(),evidence['frozen_manifest_sha256'])
        self.assertEqual({case_key(r) for r in catalogue_cases()},set(evidence['cases']))
        self.assertTrue(all(r['games']==manifest['games'] for r in evidence['cases'].values()))
