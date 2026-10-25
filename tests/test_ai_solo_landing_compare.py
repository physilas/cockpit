"""Frozen controls, genuine proof actions, phase/resource/evidence boundaries."""
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

from ai import solo_landing_compare as compare
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.solo_landing_environment import SoloLandingEnv
from ai.modules import ModuleEnv
from ai.public_case_eval import run_public_case
from ai.wind_ice_prior_environment import PriorWindIceEnv
from ai.wind_ice_prior_compare import run_arm as prior_arm
from tests.test_ai_wind_ice_compare import ice_case,model_fixture
from tests.test_ai_wind_ice_counterexamples import ice_final_pair_fixture


class SoloLandingComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_untouched_native_and_prior_controls_match_actual_previous_runners(self):
        model=model_fixture();model.train()
        initial=weight_fingerprint(model),torch.get_rng_state().clone(),random.getstate()
        select=ModelAgent.select
        for arm,seed in (('native',14_989_200),('prior',14_989_210)):
            sequence=[]
            def capture(agent,view,mask,*,reference_mask=None):
                action=select(agent,view,mask,reference_mask=reference_mask)
                sequence.append((deepcopy(view),list(mask),list(reference_mask),action))
                return action
            with patch('ai.throttle.CpuBudget.pause'):
                legacy_summary=prior_arm(model,ice_case(),arm,seed,1)['summary']
            with patch.object(ModelAgent,'select',capture),patch('ai.throttle.CpuBudget.pause'):
                # The old instrumented runner also queries same-state native
                # preferences for diagnostics; these are not played decisions.
                with patch('ai.public_case_eval.ModuleEnv',ModuleEnv if arm=='native' else PriorWindIceEnv):
                    expected=run_public_case(model,ice_case(),1,seed,assistance_version=12)
                expected_sequence=deepcopy(sequence);sequence.clear()
                actual=compare.run_arm(model,ice_case(),arm,seed,1)
            self.assertEqual(actual['summary'],legacy_summary)
            self.assertEqual(actual['summary'],expected)
            self.assertEqual(sequence,expected_sequence)
        self.assertEqual(weight_fingerprint(model),initial[0])
        self.assertTrue(torch.equal(torch.get_rng_state(),initial[1]))
        self.assertEqual(random.getstate(),initial[2]);self.assertTrue(model.training)

    def test_overlay_preserves_native_inputs_and_executes_an_actual_proven_win(self):
        fixed=ice_final_pair_fixture().game
        class Fixture(SoloLandingEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        with patch.object(compare,'SoloLandingEnv',Fixture),patch('ai.throttle.CpuBudget.pause'):
            result=compare.run_arm(model_fixture(),ice_case(),'terminal',14_989_220,1)
        self.assertEqual(result['summary']['wins'],1)
        self.assertEqual(result['counts']['proven_decisions'],1)
        self.assertEqual(result['counts'].get('search_exhausted',0),0)
        self.assertEqual(len(result['measurements'][0]['changes']),1)
        self.assertEqual(result['summary']['episodes'][0]['seed'],14_989_220)

    def test_fallback_and_cache_preserve_masks_observations_clock_and_rng(self):
        from ai.wind_ice_prior_environment import PriorWindIceEnv
        source=PriorWindIceEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        candidate=SoloLandingEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        seed='train:solo-landing-input-parity:251068'
        source.reset(seed=seed);candidate.reset(seed=seed)
        self.assertEqual(source.view(),candidate.view())
        self.assertEqual(source.observation(),candidate.observation())
        self.assertEqual(source.rng.getstate(),candidate.rng.getstate())
        self.assertIsNone(candidate.clock)
        for key in ('action_mask','reference_action_mask','source_reference_action_mask','microplans_reference_action_mask'):
            self.assertEqual(source.info()[key],candidate.info()[key])
        self.assertEqual(candidate.info()['landing_proof']['actions'],[])
        candidate.game=ice_final_pair_fixture().game
        with patch('ai.solo_landing_environment.prove_landing',wraps=__import__('ai.solo_landing',fromlist=['prove_landing']).prove_landing) as prove:
            first=candidate.info();candidate.info()
            self.assertEqual(prove.call_count,1)
            self.assertTrue(first['landing_proof']['actions'])

    def test_resources_stop_existing_report_and_independent_seeds_are_guarded(self):
        for arm,seed,games,duty in (('other',14_989_200,1,.7),('prior',15_000_000,1,.7),
                ('terminal',14_989_200,21,.7),('terminal',14_989_200,1,.8)):
            with self.assertRaises(ValueError):compare.run_arm(model_fixture(),ice_case(),arm,seed,games,duty)
        with tempfile.TemporaryDirectory() as folder:
            stop,output=Path(folder)/'STOP',Path(folder)/'out.json'
            with patch.object(compare,'STOP_FILE',stop),patch.object(compare.legacy,'load_model',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                for args in (['--workers','9'],['--cpu-duty-cycle','.8']):
                    with self.assertRaises(SystemExit):compare.main(['--output',str(output)]+args)
                stop.touch()
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                stop.unlink();output.write_text('earlier evidence')
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'earlier evidence')

    def test_failure_never_marks_report_complete_or_adds_training(self):
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
            report=json.loads(output.read_text())
            self.assertFalse(report['complete']);self.assertFalse(report['release_evidence'])
            self.assertEqual(report['ppo_updates'],0);self.assertEqual(report['new_training_decisions'],0)


if __name__=='__main__':unittest.main()
