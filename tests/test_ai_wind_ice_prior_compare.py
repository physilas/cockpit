"""New three-arm protocol preserves the old controls, episodes and RNG."""
from contextlib import redirect_stderr
from copy import deepcopy
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai import wind_ice_prior_compare as compare
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.wind_ice_prior_environment import PriorWindIceEnv
from tests.test_ai_wind_ice_compare import model_fixture, ice_case
from tests.test_ai_wind_ice_counterexamples import ice_final_pair_fixture


class WindIcePriorComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): torch.set_num_threads(1)

    def test_existing_microplan_control_is_exact_including_inputs_policy_and_rng(self):
        model = model_fixture()
        before = weight_fingerprint(model), random.getstate(), torch.get_rng_state().clone()
        select, sequence = ModelAgent.select, []
        def capture(agent, view, mask, *, reference_mask=None):
            action = select(agent, view, mask, reference_mask=reference_mask)
            sequence.append((deepcopy(view), list(mask), list(reference_mask), action))
            return action
        with patch.object(ModelAgent, 'select', capture), patch('ai.throttle.CpuBudget.pause'):
            control = compare.legacy.run_arm(model, ice_case(), 'microplans', 14_989_100, 1)
            expected = deepcopy(sequence); sequence.clear()
            actual = compare.run_arm(model, ice_case(), 'microplans', 14_989_100, 1)
        self.assertEqual(actual, control)
        self.assertEqual(sequence, expected)
        self.assertEqual(weight_fingerprint(model), before[0])
        self.assertEqual(random.getstate(), before[1])
        self.assertTrue(torch.equal(torch.get_rng_state(), before[2]))

    def test_new_prior_uses_actual_engine_and_same_state_native_comparison(self):
        fixed = ice_final_pair_fixture().game
        class Fixture(PriorWindIceEnv):
            def reset(self, **kwargs):
                super().reset(**kwargs)
                self.game = deepcopy(fixed)
                return self.observation(), self.info()
        model = model_fixture()
        before = weight_fingerprint(model), torch.get_rng_state().clone(), random.getstate()
        with patch.object(compare, 'PriorWindIceEnv', Fixture), patch('ai.throttle.CpuBudget.pause'):
            result = compare.run_arm(model, ice_case(), 'prior', 14_989_110, 1)
        self.assertEqual(result['summary']['wins'], 1)
        self.assertGreater(result['counts']['changed_reference_decisions'], 0)
        self.assertEqual(result['counts']['reference_departures'], 0)
        self.assertEqual(weight_fingerprint(model), before[0])
        self.assertTrue(torch.equal(torch.get_rng_state(), before[1]))
        self.assertEqual(random.getstate(), before[2])

    def test_preregistered_cases_and_development_cohorts_are_disjoint(self):
        self.assertEqual(compare.ARMS, ('native', 'microplans', 'prior'))
        cases = compare.legacy.cases()
        self.assertEqual(len(cases), 12)
        seeds = [compare.BASE_SEED + compare.STRIDE * index for index in range(len(cases))]
        self.assertEqual(seeds[0], 14_987_000)
        self.assertEqual(seeds[-1] + compare.GAMES - 1, 14_988_119)
        self.assertEqual(compare.GAMES, 20)
        self.assertLess(seeds[-1] + compare.GAMES, 15_000_000)
        with self.assertRaises(ValueError): compare.run_arm(model_fixture(), ice_case(), 'unknown', 14_989_100, 1)

    def test_resource_stop_and_existing_report_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output, stop = root/'report.json', root/'STOP'
            with patch.object(compare.legacy, 'STOP_FILE', stop), patch.object(compare.legacy, 'load_model', side_effect=AssertionError('No load')), redirect_stderr(io.StringIO()):
                for args in (['--workers','9'], ['--workers','0'], ['--cpu-duty-cycle','.8']):
                    with self.assertRaises(SystemExit): compare.main(['--output',str(output)] + args)
                stop.touch()
                with self.assertRaises(SystemExit): compare.main(['--output',str(output)])
                stop.unlink(); output.write_text('old evidence')
                with self.assertRaises(SystemExit): compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(), 'old evidence')

    def test_failed_worker_persists_explicit_new_phase_without_training(self):
        class FailedPool:
            def __init__(self,*args,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def map(self,*args): raise RuntimeError('prior worker fixture failure')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root/'report.json'
            with patch.object(compare.legacy, 'STOP_FILE', root/'STOP'), patch.object(compare.legacy, 'load_model', return_value=(None, {})), \
                    patch.object(compare, 'comparison_fingerprint', return_value='new-code-sha'), patch.object(compare, 'ProcessPoolExecutor', FailedPool):
                with self.assertRaisesRegex(RuntimeError, 'worker fixture failure'): compare.main(['--output', str(output)])
            report = json.loads(output.read_text())
            self.assertFalse(report['complete'])
            self.assertEqual(report['phase'], 'public_joint_partner_fair_hand_prior')
            self.assertEqual(report['ppo_updates'], 0)
            self.assertEqual(report['new_training_decisions'], 0)
            self.assertFalse(report['qualification_used'])


if __name__ == '__main__':
    unittest.main()
