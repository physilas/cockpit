import unittest

import torch

from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.evaluate import evaluate
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.open_risk_compare import compare_games, validate_seed_budget
from ai.search_evaluate import evaluate_open_risk


class OpenRiskComparisonTests(unittest.TestCase):
    def test_counter_instrumentation_preserves_both_control_and_open_policy(self):
        torch.set_num_threads(1);torch.manual_seed(251040)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1)
        sha = weight_fingerprint(model)
        for opened in (False, True):
            records = compare_games(model, 'LOG_HND_GREEN', 251040, 1, opened=opened, duty=1., beam=16)
            expected = (evaluate_open_risk(ModelAgent(model), 'LOG_HND_GREEN', 251040, 1, 1., 16)
                        if opened else evaluate(ModelAgent(model), airport='LOG_HND_GREEN', seed=251040,
                                                games=1, assistance_version=9, round_reward=0.))['episodes']
            self.assertEqual([(r['status'],r['reason'],r['steps']) for r in records],
                             [(r['status'],r['reason'],r['steps']) for r in expected])
            self.assertLessEqual(records[0]['proposal_actions'], records[0]['steps'])
            if not opened:self.assertEqual(records[0]['proposal_actions'], 0)
        self.assertEqual(weight_fingerprint(model), sha)

    def test_qualification_partition_is_not_consumed_as_development(self):
        validate_seed_budget(14700000, 200, ['OSL', 'HND', 'LHR', 'YUL'])
        with self.assertRaises(ValueError):validate_seed_budget(15000000, 200, ['OSL'])
        with self.assertRaises(ValueError):validate_seed_budget(14999900, 200, ['OSL'])
        with self.assertRaises(ValueError):validate_seed_budget(14700000, 0, ['OSL'])


if __name__ == '__main__':
    unittest.main()
