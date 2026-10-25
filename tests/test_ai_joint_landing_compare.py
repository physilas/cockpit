"""Separate reference keeps prior/control paths, privacy and evidence intact."""
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

from ai import joint_landing_compare as compare
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.joint_landing_environment import JointLandingEnv
from ai.modules import ModuleEnv
from ai.wind_ice_prior_environment import PriorWindIceEnv
from tests.test_ai_joint_landing import ice_fixture
from tests.test_ai_wind_ice_compare import model_fixture,ice_case


class JointLandingComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_early_round_fallback_and_final_inputs_masks_rng_are_unchanged(self):
        source=PriorWindIceEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        research=JointLandingEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        source.reset(seed='train:joint-landing-inputs:251069');research.reset(seed='train:joint-landing-inputs:251069')
        self.assertEqual(source.view(),research.view())
        self.assertEqual(source.observation(),research.observation())
        self.assertEqual(source.info()['reference_action_mask'],research.info()['reference_action_mask'])
        self.assertEqual(source.rng.getstate(),research.rng.getstate())
        self.assertFalse(research.info()['joint_landing']['eligible'])
        fixed=ice_fixture().game
        native=ModuleEnv(assistance_version=12);native.game=deepcopy(fixed)
        source.game=deepcopy(fixed);research.game=deepcopy(fixed)
        self.assertEqual(native.view(),research.view())
        self.assertEqual(native.observation(),research.observation())
        self.assertEqual(native.action_mask(),research.action_mask())
        self.assertEqual(source.info()['reference_action_mask'],research.info()['prior_reference_action_mask'])
        self.assertTrue(research.info()['joint_landing']['positive_candidates'])
        self.assertNotEqual(research.info()['reference_action_mask'],source.info()['reference_action_mask'])
        self.assertIsNone(research.clock)
        with patch('ai.joint_landing_environment.joint_landing_plans',side_effect=AssertionError('Use cache')):
            research.info()

    def test_instrumented_prior_arm_is_exactly_unchanged_and_weights_rng_survive(self):
        model=model_fixture();model.train()
        initial=weight_fingerprint(model),random.getstate(),torch.get_rng_state().clone()
        with patch('ai.throttle.CpuBudget.pause'):
            before=compare.prior.run_arm(model,ice_case(),'prior',14_989_300,1)
            after=compare.run_arm(model,ice_case(),'prior',14_989_300,1)
        self.assertEqual(before,after)
        self.assertEqual(initial[0],weight_fingerprint(model));self.assertTrue(model.training)
        self.assertEqual(initial[1],random.getstate());self.assertTrue(torch.equal(initial[2],torch.get_rng_state()))

    def test_real_engine_episode_and_instrumented_inputs_match_uninstrumented_research(self):
        model=model_fixture();fixed=ice_fixture().game
        class Fixture(JointLandingEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        # Capture all ModelAgent queries: instrumentation adds native/prior
        # probes. Played decisions are independently observed at actual step.
        from ai.public_case_eval import run_public_case
        before=weight_fingerprint(model)
        with patch('ai.throttle.CpuBudget.pause'),patch('ai.public_case_eval.ModuleEnv',Fixture):
            expected=run_public_case(model,ice_case(),1,14_989_310,assistance_version=12)
        with patch('ai.throttle.CpuBudget.pause'),patch.object(compare,'JointLandingEnv',Fixture):
            actual=compare.run_arm(model,ice_case(),'joint',14_989_310,1)
        for key in ('wins','truncated','decisions','reference_departures'):
            self.assertEqual(actual['summary'][key],expected[key])
        for key in ('status','reason','round','steps'):
            self.assertEqual(actual['summary']['episodes'][0][key],expected['episodes'][0][key])
        self.assertGreater(actual['joint_landing_counts']['positive_decisions'],0)
        self.assertEqual(before,weight_fingerprint(model))

    def test_pacing_and_poisoned_unknown_partner_faces_do_not_change_reference(self):
        env=JointLandingEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        env.game=ice_fixture().game
        view=env.view();info=env.info();rng=env.rng.getstate()
        for die in env.game.kopilot_wuerfel:die.augenzahl=6
        self.assertEqual(env.view(),view)
        with patch('ai.joint_landing_advice.CpuBudget.pause'):
            env._joint_cache=None;env.planning_cpu_duty_cycle=.7
            self.assertEqual(env.info()['reference_action_mask'],info['reference_action_mask'])
        self.assertEqual(env.rng.getstate(),rng)

    def test_resources_stop_existing_output_and_reserved_seeds_are_guarded(self):
        for arm,seed,games,duty in (('other',14_989_300,1,.7),('joint',15_000_000,1,.7),
                ('joint',14_989_300,21,.7),('joint',14_989_300,1,.8)):
            with self.assertRaises(ValueError):compare.run_arm(model_fixture(),ice_case(),arm,seed,games,duty)
        with tempfile.TemporaryDirectory() as folder:
            stop,output=Path(folder)/'STOP',Path(folder)/'out.json'
            with patch.object(compare,'STOP_FILE',stop),patch.object(compare.legacy,'load_model',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                for args in (['--workers','9'],['--cpu-duty-cycle','.8']):
                    with self.assertRaises(SystemExit):compare.main(['--output',str(output)]+args)
                stop.touch()
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                stop.unlink();output.write_text('evidence')
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'evidence')

    def test_worker_failure_does_not_complete_report_or_invent_training(self):
        class FailedPool:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def map(self,*args):raise RuntimeError('controlled failure')
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'out.json'
            with patch.object(compare,'STOP_FILE',Path(folder)/'STOP'),patch.object(compare.legacy,'load_model',return_value=(None,{})),\
                    patch.object(compare,'comparison_fingerprint',return_value='code-sha'),patch.object(compare,'ProcessPoolExecutor',FailedPool):
                with self.assertRaisesRegex(RuntimeError,'controlled failure'):compare.main(['--output',str(output)])
            report=json.loads(output.read_text());self.assertFalse(report['complete'])
            self.assertFalse(report['qualification_used']);self.assertEqual(report['ppo_updates'],0)
            self.assertEqual(report['new_training_decisions'],0)


if __name__=='__main__':unittest.main()
