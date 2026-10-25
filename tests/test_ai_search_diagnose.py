from copy import deepcopy
import random
import unittest

from ai import search_teacher
from ai.environment import CrewEnv
from ai.search_diagnose import capture_plan, public_context


class SearchDiagnosisTests(unittest.TestCase):
    def test_instrumentation_preserves_plans_view_and_rng(self):
        env = CrewEnv('LOG_HND_GREEN');env.reset(seed=251035)
        view, mask = env.view(), env.action_mask()
        before, state = deepcopy(view), random.getstate()
        expected = search_teacher.plan_actions(view, mask, beam=8, version=3)
        with capture_plan() as captured:
            actual = search_teacher.plan_actions(view, mask, beam=8, version=3)
        self.assertEqual(actual, expected)
        self.assertEqual(captured['ranks'], expected[0])
        self.assertEqual(captured['sequences'], expected[1])
        self.assertEqual(view, before)
        self.assertEqual(random.getstate(), state)

    def test_diagnostic_context_keeps_only_public_fields_and_own_die_count(self):
        env = CrewEnv();env.reset(seed=251035)
        view = env.view()
        view['unregistered_private_field'] = [1, 2, 3, 4]
        result = public_context(view)
        self.assertEqual(result['own_remaining'], 4)
        self.assertNotIn('own_dice', result)
        self.assertNotIn('unregistered_private_field', result)


if __name__ == '__main__':
    unittest.main()
