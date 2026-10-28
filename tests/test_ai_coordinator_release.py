"""Audit Koordinator's portable tensors, frozen comparison and preserved crews."""
import gzip
import hashlib
import json
from pathlib import Path
import unittest

from ai.ability_fingerprint import ability_fingerprint
from ai.ability_publish import compare_totals
from ai.checkpoints import load_checkpoint,weight_fingerprint
from ai.module_training_eval import case_key
from ai.preview_matrix_eval import catalogue_cases
from ai.strategy_fingerprint import public_strategy_fingerprint

ROOT=Path(__file__).resolve().parents[1]
RELEASE=ROOT/'ai/releases/crew6-abilities-2026-10-28-v1'


@unittest.skipUnless(RELEASE.is_dir(),'Koordinator is not yet published')
class CoordinatorReleaseTests(unittest.TestCase):
    def test_previous_crews_and_all_case_metadata_are_preserved(self):
        catalog=json.loads((ROOT/'frontend/web/js/ai-models.js').read_text().split(' = ',1)[1].strip().rstrip(';'))
        byid={m['id']:m for m in catalog['models']}
        for old in json.loads((RELEASE/'previous-crews.json').read_text()):
            self.assertEqual(old,byid[old['id']])
        entry=byid[RELEASE.name+'/best.pt']
        self.assertEqual(6,entry['crew_number']);self.assertFalse(entry['ui_hidden'])
        self.assertEqual(15,entry['assistance_version']);self.assertEqual(256,entry['max_steps'])
        self.assertFalse(entry['quality']['approved']);self.assertFalse(entry['preview']['positive_only'])
        expected={case_key(c) for c in catalogue_cases()}
        self.assertEqual(expected,set(entry['preview']['case_results']))
        self.assertEqual(expected,{case_key(c) for c in entry['preview']['supported_cases']})
        self.assertEqual(byid['crew5-planner-2026-10-28-v1/best.pt']['url'],entry['url'])

    def test_frozen_input_source_and_unchanged_weights_are_bound(self):
        manifest=json.loads((RELEASE/'confirmation-protocol.json').read_text())
        model,payload=load_checkpoint(RELEASE/'best.pt')
        self.assertEqual(manifest['weights_sha256'],weight_fingerprint(model))
        self.assertEqual(manifest['weights_sha256'],payload['train_config']['source_weights_sha256'])
        self.assertFalse(payload['train_config']['new_tensor_training'])
        self.assertEqual(manifest['checkpoint_file_sha256'],hashlib.sha256(gzip.decompress((RELEASE/'confirmation-input.pt.gz').read_bytes())).hexdigest())
        self.assertEqual(manifest['planner_sha256'],ability_fingerprint())
        self.assertEqual(manifest['baseline_strategy_sha256'],public_strategy_fingerprint(13))
        self.assertEqual(manifest['evaluation_sha256'],hashlib.sha256((ROOT/'ai/ability_compare.py').read_bytes()).hexdigest())
        self.assertEqual(manifest['publication_validator_sha256'],hashlib.sha256((ROOT/'ai/ability_publish.py').read_bytes()).hexdigest())

    def test_confirmation_retains_zeroes_and_declares_actual_and_reused_games(self):
        manifest=json.loads((RELEASE/'confirmation-protocol.json').read_text())
        report=json.loads((RELEASE/'comparison.json').read_text())
        self.assertTrue(report['complete']);self.assertTrue(report['release_evidence'])
        self.assertFalse(report['qualification_granted']);self.assertEqual(manifest,report['config'])
        self.assertEqual(0,report['reused_previous_baseline_games'])
        counts={method:sum(r['games'] for r in report['results'].values() if r['execution_method']==method)
                for method in ('played','identical_policy_reuse')}
        self.assertEqual(counts['played'],report['actual_played_games'])
        self.assertEqual(counts['identical_policy_reuse'],report['reused_identical_policy_games'])
        self.assertEqual(2*len(catalogue_cases())*manifest['games'],report['represented_policy_games'])
        for case in catalogue_cases():
            for mode in ('baseline','candidate'):
                row=report['results'][case_key(case)+'/'+mode]
                self.assertEqual(manifest['games'],row['games'])
                self.assertEqual([f"{manifest['cohort']}:{case_key(case)}:{i}" for i in range(manifest['games'])],[e['seed'] for e in row['episodes']])
        totals=compare_totals(report);a,b=totals['baseline'],totals['candidate']
        self.assertGreaterEqual(b['wins']-a['wins'],5)
        self.assertGreaterEqual(b['ability_wins']-a['ability_wins'],5)
        self.assertGreater(b['equal_route_win_rate'],a['equal_route_win_rate'])
        self.assertEqual(0,b['avoidable_immediate_losses']);self.assertEqual(0,b['truncations'])
