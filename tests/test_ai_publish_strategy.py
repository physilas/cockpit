import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.checkpoints import load_checkpoint,save_checkpoint,weight_fingerprint
from ai.nn_model import ActorCritic,GuidedResidualActorCritic
from ai.publish_strategy import prepare,finalize


class PublicStrategyPreparationTests(unittest.TestCase):
    def test_preparation_preserves_tensors_but_resets_approval_and_binds_budget(self):
        torch.set_num_threads(1)
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source.pt'
            model=GuidedResidualActorCritic(ActorCritic(489,217,8,1),489,217,hidden_size=8,hidden_layers=1)
            save_checkpoint(source,model,total_steps=23,train_config=dict(assistance_version=12,max_steps=128,
                quality={'approved':True},recommended=True,preview={'enabled':True}))
            before=hashlib.sha256(source.read_bytes()).hexdigest();original=weight_fingerprint(model)
            target=prepare(str(source),root/'candidate',13)
            candidate,payload=load_checkpoint(target);config=payload['train_config']
            self.assertEqual(original,weight_fingerprint(candidate))
            self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertEqual(13,config['assistance_version']);self.assertEqual(256,config['max_steps'])
            self.assertEqual(192,len(config['supported_cases']))
            self.assertNotIn('quality',config);self.assertNotIn('preview',config)
            self.assertFalse(config['recommended']);self.assertFalse(config['new_tensor_training_in_this_preparation'])
            self.assertEqual(0,config['new_environment_decisions_in_this_preparation'])

    def test_incomplete_case_confirmation_cannot_create_a_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest=root/'frozen.json';evidence=root/'evidence.json'
            manifest.write_text(json.dumps(dict(games=20)))
            evidence.write_text(json.dumps(dict(complete=True,release_evidence=False,qualification_used=True,
                qualification_granted=False,frozen_manifest_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest(),cases={})))
            with patch('ai.publish_strategy.check_manifest'),patch('ai.publish_strategy.publish_preview') as publish:
                with self.assertRaises(ValueError):finalize(manifest,evidence,'new','New',5)
                publish.assert_not_called()
