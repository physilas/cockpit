import json
from pathlib import Path
import tempfile
import unittest

import torch

from ai.checkpoints import load_checkpoint,planner_fingerprint,save_checkpoint
from ai.publish import publish,publish_preview
from ai.strategy_fingerprint import public_strategy_fingerprint
from tests.test_ai_publish_preview import card_fixture


class StrategyPublishTests(unittest.TestCase):
    def test_new_case_previews_use_their_own_fingerprint_and_never_inherit_approval(self):
        torch.set_num_threads(1)
        old=planner_fingerprint(3)
        self.assertNotEqual(public_strategy_fingerprint(13),public_strategy_fingerprint(14))
        for profile in (13,14):
            with tempfile.TemporaryDirectory() as folder:
                root=Path(folder);checkpoint,evaluation,report=card_fixture(root)
                model,payload=load_checkpoint(checkpoint)
                payload['train_config']['assistance_version']=profile
                save_checkpoint(checkpoint,model,train_config=payload['train_config'],total_steps=0)
                report.update(assistance_version=profile,planner_sha256=old)
                evaluation.write_text(json.dumps(report))
                with self.assertRaisesRegex(ValueError,'case-based'):
                    publish(checkpoint,evaluation,'wrong-qualification','Wrong',root=root)
                with self.assertRaises(ValueError):publish_preview(checkpoint,evaluation,'stale','Stale',root=root)
                report['planner_sha256']=public_strategy_fingerprint(profile)
                evaluation.write_text(json.dumps(report))
                released,catalog=publish_preview(checkpoint,evaluation,'new-public','New Public',root=root)
                row=catalog['models'][0]
                self.assertEqual(profile,row['assistance_version'])
                self.assertFalse(row['quality']['approved'])
                self.assertEqual(6,len(row['preview']['supported_cases']))
        self.assertEqual(old,planner_fingerprint(3))
