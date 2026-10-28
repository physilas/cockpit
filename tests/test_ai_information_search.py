import unittest

from ai.information_search import InformationSearchAgent
from ai.modules import ModuleEnv


class RecordingBlueprint:
    def __init__(self):
        self.roles = set()

    def rank(self, view, mask):
        self.roles.add(view['role'])
        assert 'partner_dice' not in view and 'rng' not in view
        legal = [i for i, ok in enumerate(mask) if ok]
        return legal[0], legal

    def select(self, view, mask):
        return self.rank(view, mask)[0]


class InformationSearchTests(unittest.TestCase):
    def test_single_role_tree_and_fixed_filtered_partner(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000130)
        blueprint = RecordingBlueprint()
        agent = InformationSearchAgent('MUC', blueprint, simulations=12, width=2,
                                        max_seconds=10., minimum_visits=2)
        before = env.view()
        action = agent.select(before, env.action_mask())
        self.assertTrue(env.action_mask()[action])
        self.assertEqual(before, env.view())
        self.assertEqual(12, agent.last_report['simulations'])
        self.assertEqual({'pilot', 'kopilot'}, blueprint.roles)
        self.assertTrue(all('"role":"pilot"' in key for key in agent.tree))

    def test_no_budget_falls_back_without_partial_tree_claim(self):
        env = ModuleEnv('MUC')
        env.reset(seed=14000131)
        agent = InformationSearchAgent('MUC', RecordingBlueprint(), max_seconds=.000001)
        action = agent.select(env.view(), env.action_mask())
        self.assertEqual(agent.last_report['baseline'], action)
        self.assertEqual(0, agent.last_report['simulations'])
