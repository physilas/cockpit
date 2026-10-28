import unittest

from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.safe_environment import SafeResearchEnv
from ai.safety_guard import safe_actions


class SafeEnvironmentTests(unittest.TestCase):
    def test_reference_always_inside_wide_safe_engine_mask(self):
        env = SafeResearchEnv('LOG_GIG_YELLOW', abilities=['adaptation'])
        _, info = env.reset(seed='train:safe-env:test')
        for _ in range(8):
            if env.done:
                break
            raw = ModuleEnv('LOG_GIG_YELLOW', abilities=['adaptation'])
            raw.game, raw.reroll, raw.steps = env.game, env.reroll, env.steps
            mask = raw.action_mask()
            safe, meta = safe_actions('LOG_GIG_YELLOW', env.view(), mask)
            allowed, reference = info['action_mask'], info['reference_action_mask']
            self.assertTrue(any(reference))
            self.assertTrue(all(not flag or safe[i] for i, flag in enumerate(allowed)))
            self.assertTrue(all(not flag or allowed[i] for i, flag in enumerate(reference)))
            choices = [i for i, ok in enumerate(allowed) if ok and MODULE_ACTIONS[i].kind in ('place', 'bonus_place')]
            action = choices[0] if choices else next(i for i, ok in enumerate(allowed) if ok)
            _, _, _, _, info = env.step(action)
        for role in ('pilot', 'kopilot'):
            row = env.episode_record('train:safe-env:test', role, 0.)
            self.assertEqual(row['steps'] + row['partner_decisions'], row['engine_decisions'])

    def test_training_helper_loop_budget_cannot_bootstrap_out_of_failure(self):
        env = SafeResearchEnv('MUC', max_steps=1)
        _, info = env.reset(seed='train:safe-env:budget')
        native = env.game.status
        action = next(i for i, ok in enumerate(info['action_mask']) if ok and MODULE_ACTIONS[i].kind == 'reroll_start')
        _, reward, terminated, truncated, info = env.step(action)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual('training_decision_budget', info['reason'])
        self.assertEqual(-1., reward)
        self.assertEqual(native, env.game.status)

    def test_partner_and_learner_both_keep_the_public_shield(self):
        env = SafeResearchEnv('MUC')
        env.assisted_roles = ('pilot',)
        self.assertEqual(('pilot', 'kopilot'), env.assisted_roles)
