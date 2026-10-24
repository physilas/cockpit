import unittest
from unittest.mock import patch

from ai.agents import HeuristicAgent
from ai.compare import paired_summary
from ai.evaluate import evaluate


class ComparisonTests(unittest.TestCase):
    def test_shared_seeds_across_routes_and_roles_are_one_cluster(self):
        baseline,candidate={},{}
        for airport in ('MUC','LOG_YUL_GREEN'):
            for role in ('pilot','kopilot'):
                for seed in (10,11):
                    key=airport,'heuristic',role,seed
                    baseline[key]={'status':'verloren'}
                    candidate[key]={'status':'gewonnen' if seed==10 else 'verloren'}
        result=paired_summary(baseline,candidate)
        self.assertEqual(result['seed_clusters'],2)
        self.assertEqual(result['paired_games'],8)
        self.assertEqual(result['win_rate_delta'],.5)
        self.assertLess(result['delta_ci_low'],0)

    def test_policy_rng_is_reset_for_each_game_not_only_the_batch(self):
        with patch('torch.manual_seed') as seed:
            evaluate(HeuristicAgent(),games=2,seed=5100010,policy_seed=90,round_reward=0)
            self.assertEqual([call.args[0] for call in seed.call_args_list],[90,91])
