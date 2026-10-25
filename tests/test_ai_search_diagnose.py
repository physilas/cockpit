from copy import deepcopy
import random
import unittest

from ai import search_teacher
from ai.environment import CrewEnv
from ai.search_diagnose import capture_plan, public_context, select_seeds


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

    def test_selects_all_requested_loss_types_without_requiring_teacher_failures(self):
        rows = {1: {'status': 'gewonnen', 'reason': ''},
                2: {'status': 'verloren', 'reason': 'kollision'},
                3: {'status': 'verloren', 'reason': 'ruder_verbotene_stellung'},
                4: {'status': 'verloren', 'reason': 'flugzeuge_uebrig,nicht_waagerecht'}}
        self.assertEqual(select_seeds({'model': rows}, selection='model-losses',
                         reasons=['kollision', 'ruder_verbotene_stellung']), [2, 3])
        self.assertEqual(select_seeds({'model': rows}, selection='model-losses',
                         reasons=['nicht_waagerecht']), [4])
        self.assertEqual(select_seeds({'model': rows}, selection='model-losses', seeds=[3, 4], limit=1), [3])
        with self.assertRaises(ValueError):select_seeds({'model': rows})
        teacher = {**rows, 1: {'status': 'verloren', 'reason': 'trudeln'}}
        self.assertEqual(select_seeds({'model': rows, 'joint-finish': teacher}), [1])


if __name__ == '__main__':
    unittest.main()
