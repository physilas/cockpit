import json
import unittest

from backend import bridge
from ai.modules import ModuleEnv
from ai.strategy_bridge import strategy_decision
from ai.strategy_environment import StrategyEnv


class StrategyEnvironmentTests(unittest.TestCase):
    def test_both_profiles_match_browser_inputs_across_real_transitions(self):
        for profile,policy in ((13,'contract'),(14,'coherent')):
            env=StrategyEnv('LOG_KEF_YELLOW',abilities=['adaptation'],assistance_version=profile)
            _,info=env.reset(seed='train:strategy-env:parity')
            for _ in range(12):
                bridge._spiel=env.game
                actual=strategy_decision(reroll_json=json.dumps(env.reroll),steps=env.steps,policy=policy)
                self.assertEqual(env.observation(),actual['observation'])
                self.assertEqual(info['action_mask'],actual['action_mask'])
                self.assertEqual(info['reference_action_mask'],actual['reference_action_mask'])
                if profile==13:self.assertEqual(info['public_plan'],actual['public_plan'])
                self.assertTrue(any(info['reference_action_mask']))
                action=next(i for i,ok in enumerate(info['reference_action_mask']) if ok)
                _,_,done,truncated,info=env.step(action)
                if done or truncated:break

    def test_legacy_constructor_still_rejects_new_profiles(self):
        with self.assertRaises(ValueError):ModuleEnv(assistance_version=13)
        with self.assertRaises(ValueError):StrategyEnv(assistance_version=15)
