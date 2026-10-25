from pathlib import Path
import tempfile
import unittest

import torch

from ai.agents import ModelAgent
from ai.checkpoints import save_checkpoint, weight_fingerprint
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.parallel import ParallelGames
from ai.search_evaluate import evaluate_open_risk
from ai.train import ppo_update
from ai.train_fuel import initialize_research_phase


class OpenRiskTrainingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def model(self):
        torch.manual_seed(251038)
        return GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)

    def test_new_phase_preserves_weights_and_old_provenance_without_resuming_optimizer(self):
        model = self.model()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.pt'
            save_checkpoint(path, model, total_steps=123, module_training_steps=17,
                            train_config={'planner_sha256': 'previous-research-code'})
            original = path.read_bytes()
            copied, payload = initialize_research_phase(path, 'cpu')
            self.assertEqual(weight_fingerprint(model), weight_fingerprint(copied))
            self.assertEqual(payload['total_steps'], 123)
            self.assertEqual(payload['train_config']['planner_sha256'], 'previous-research-code')
            self.assertTrue(all(not p.requires_grad for p in copied.source.parameters()))
            self.assertTrue(all(p.requires_grad for p in copied.residual.parameters()))
            self.assertEqual(path.read_bytes(), original)
            save_checkpoint(path, ActorCritic(489, 217, 8, 1))
            with self.assertRaises(ValueError):initialize_research_phase(path, 'cpu')

    def test_parallel_open_rollouts_keep_guidance_and_train_only_the_existing_detail_branch(self):
        model = self.model()
        frozen = weight_fingerprint(model.source)
        detail = {k:v.clone() for k,v in model.residual.state_dict().items()}
        options = dict(airport='LOG_HND_GREEN', round_reward=0., max_steps=128,
                       assistance_version=9, research_open_risk=True)
        pool = ParallelGames(1, model.config, options, cpu_duty_cycle=1.)
        try:
            batch, records = pool.collect(model, 8, seed=251038, update=0, gamma=.995,
                        gae_lambda=.95, uniform_mix=0., discount_unit='placement')
            self.assertEqual(batch['reference_masks'].shape, batch['masks'].shape)
            self.assertTrue(bool(batch['masks'].gather(1,batch['actions'][:,None]).all()))
            self.assertTrue(all(isinstance(r['seed'], str) and r['seed'].startswith('train:') for r in records))
            with torch.no_grad():
                logp, _, _ = model.evaluate_actions(batch['observations'], batch['masks'], batch['actions'],
                                                    reference_mask=batch['reference_masks'])
            self.assertLess(float((logp - batch['log_probs']).abs().max()), 1e-5)
            optimizer = torch.optim.Adam(model.parameters(), lr=5e-5)
            ppo_update(model, optimizer, batch, epochs=1, minibatch_size=64)
            self.assertEqual(weight_fingerprint(model.source), frozen)
            self.assertTrue(any(not torch.equal(v,model.residual.state_dict()[k]) for k,v in detail.items()))
            result = pool.evaluate(model, games=2, seed=14580000)
            direct = evaluate_open_risk(ModelAgent(model), 'LOG_HND_GREEN', 14580000, 2, 1., 64, max_steps=128)
            self.assertEqual([(r['seed'],r['status'],r['reason']) for r in result['episodes']],
                             [(r['seed'],r['status'],r['reason']) for r in direct['episodes']])
        finally:
            pool.close()


if __name__ == '__main__':
    unittest.main()
