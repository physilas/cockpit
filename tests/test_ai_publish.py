import json
from pathlib import Path
import tempfile
import unittest

from ai.checkpoints import save_checkpoint, load_checkpoint, weight_fingerprint, planner_fingerprint
from ai.nn_model import ActorCritic
from ai.publish import publish


class PublishTests(unittest.TestCase):
    def test_matching_held_out_qualification_is_required_and_preserves_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = ActorCritic(hidden_size=8)
            checkpoint = root/'candidate.pt'
            save_checkpoint(checkpoint, model, train_config={'airport':'MUC','assistance_version':1,
                'partner_checkpoints':[str(root/'reference.pt')]}, total_steps=10)
            report = {'weights_sha256':weight_fingerprint(model),'assistance_version':1,
                      'planner_sha256':planner_fingerprint(),
                      'minimum_win_rate':.2,'qualified_routes':['MUC'],
                      'routes':{'MUC':{'self':{'games':500,'win_ci_low':.7}}}}
            evaluation = root/'evaluation.json'
            evaluation.write_text(json.dumps({**report,'weights_sha256':'wrong'}))
            with self.assertRaises(ValueError):
                publish(checkpoint,evaluation,'crew-test','Test',root=root,require_all=False)
            self.assertFalse((root/'ai/releases/crew-test').exists())
            evaluation.write_text(json.dumps(report))
            with self.assertRaises(ValueError):
                publish(checkpoint,evaluation,'crew-test','Test',root=root)
            path,catalog = publish(checkpoint,evaluation,'crew-test','Test',root=root,require_all=False)
            saved,payload = load_checkpoint(path)
            self.assertEqual(weight_fingerprint(saved),weight_fingerprint(model))
            self.assertTrue(payload['train_config']['quality']['approved'])
            self.assertEqual(payload['train_config']['partner_checkpoints'],['reference.pt'])
            self.assertEqual(catalog['models'][0]['supported_airports'],['MUC'])


if __name__ == '__main__':
    unittest.main()
