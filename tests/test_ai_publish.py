import json
from pathlib import Path
import tempfile
import unittest

from ai.checkpoints import save_checkpoint, load_checkpoint, weight_fingerprint, planner_fingerprint
from ai.nn_model import ActorCritic
from ai.publish import publish


class PublishTests(unittest.TestCase):
    def test_module_release_uses_new_user_floor_and_rejects_unmatched_research_masks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = ActorCritic(489, 217, hidden_size=8)
            checkpoint, evaluation = root/'candidate.pt', root/'evaluation.json'
            config = dict(airport='LOG_OSL_GREEN', assistance_version=9,
                          supported_modules=['kerosene'])
            report = dict(complete=True, weights_sha256=weight_fingerprint(model),
                assistance_version=9, planner_sha256=planner_fingerprint(3),
                minimum_win_rate=.3, qualified_routes=['LOG_OSL_GREEN'],
                routes={'LOG_OSL_GREEN': {'self': dict(games=500, win_ci_low=.36, win_rate=.4)}})
            evaluation.write_text(json.dumps(report))
            for flag in ('research_all_modules', 'research_open_risk'):
                save_checkpoint(checkpoint, model, train_config={**config, flag: True},
                                total_steps=10, module_training_steps=10)
                with self.assertRaisesRegex(ValueError, 'matching browser'):
                    publish(checkpoint,evaluation,'module-test','Test',root=root,require_all=False)
            save_checkpoint(checkpoint, model, train_config=config, total_steps=10,
                            module_training_steps=0)
            with self.assertRaisesRegex(ValueError, 'actual module training'):
                publish(checkpoint,evaluation,'module-test','Test',root=root,require_all=False)
            save_checkpoint(checkpoint, model, train_config=config, total_steps=10,
                            module_training_steps=10)
            evaluation.write_text(json.dumps({**report, 'minimum_win_rate': .29}))
            with self.assertRaisesRegex(ValueError, 'at least 30%'):
                publish(checkpoint,evaluation,'module-test','Test',root=root,require_all=False)
            evaluation.write_text(json.dumps(report))
            path, catalog = publish(checkpoint,evaluation,'module-test','Test',root=root,require_all=False)
            saved, payload = load_checkpoint(path)
            self.assertEqual(weight_fingerprint(saved),weight_fingerprint(model))
            self.assertEqual(payload['train_config']['quality']['minimum_win_rate'], .3)
            self.assertEqual(catalog['models'][0]['supported_airports'], ['LOG_OSL_GREEN'])

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
            evaluation.write_text(json.dumps({**report, 'complete': False}))
            with self.assertRaisesRegex(ValueError, 'still running'):
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
