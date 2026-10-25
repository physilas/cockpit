"""New masks keep old controls exact and separate causal timing diagnostics."""
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

from ai import task_deadline_compare as compare
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.public_case_eval import run_public_case
from ai.task_deadline_environment import TaskDeadlineEnv
from ai.joint_landing_environment import JointLandingEnv
from ai.wind_ice_prior_environment import PriorWindIceEnv
from tests.test_ai_task_deadline import deadline_fixture
from tests.test_ai_joint_landing import radio_fixture
from tests.test_ai_wind_ice_compare import model_fixture,ice_case
from tests.test_ai_wind_ice_counterexamples import _action,ice_final_pair_fixture


class TaskDeadlineComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_prior_and_joint_controls_keep_exact_played_inputs_outputs_rng_and_weights(self):
        model=model_fixture();model.train()
        initial=weight_fingerprint(model),random.getstate(),torch.get_rng_state().clone()
        select=ModelAgent.select
        for arm,klass,seed in (('prior',PriorWindIceEnv,14_989_400),('joint',JointLandingEnv,14_989_410)):
            sequence=[]
            def capture(agent,view,mask,*,reference_mask=None):
                action=select(agent,view,mask,reference_mask=reference_mask)
                sequence.append((deepcopy(view),list(mask),list(reference_mask),action));return action
            with patch.object(ModelAgent,'select',capture),patch('ai.throttle.CpuBudget.pause'):
                with patch('ai.public_case_eval.ModuleEnv',klass):
                    expected=run_public_case(model,ice_case(),1,seed,assistance_version=12)
                expected_sequence=deepcopy(sequence);sequence.clear()
                actual=compare.run_arm(model,ice_case(),arm,seed,1)
            self.assertEqual(actual['summary'],expected);self.assertEqual(sequence,expected_sequence)
        self.assertEqual(initial[0],weight_fingerprint(model));self.assertEqual(initial[1],random.getstate())
        self.assertTrue(torch.equal(initial[2],torch.get_rng_state()));self.assertTrue(model.training)

    def test_actual_new_mask_episodes_record_narrowing_with_legal_references(self):
        fixed=deadline_fixture().game
        class Fixture(TaskDeadlineEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        model=model_fixture();initial=weight_fingerprint(model)
        with patch.object(compare,'TaskDeadlineEnv',Fixture),patch('ai.throttle.CpuBudget.pause'):
            result=compare.run_arm(model,ice_case(),'deadline',14_989_420,1)
        self.assertGreater(result['counts']['narrowed_mask_states'],0)
        self.assertGreater(result['counts']['removed_placement_options'],0)
        self.assertEqual(result['summary']['episodes'][0]['seed'],14_989_420)
        self.assertEqual(weight_fingerprint(model),initial)

    def test_prevented_counterfactual_choice_and_same_round_capacity_loss_are_measured(self):
        # This actual radio exercise has exactly four copilot obligations;
        # concentration spends a required regular die without doing any task.
        fixed=radio_fixture().game
        class JointFixture(JointLandingEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        class GuardFixture(TaskDeadlineEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        case=next(r for r in compare.legacy.cases() if r['airport']=='LOG_GIG_YELLOW' and r['abilities']==['adaptation'])
        bad=_action(0,'konzentration',index=0)
        def scripted(agent,view,mask,*,reference_mask=None):
            return bad if mask[bad] else next(i for i,v in enumerate(reference_mask) if v)
        with patch.object(ModelAgent,'select',scripted),patch.object(compare,'JointLandingEnv',JointFixture),\
                patch.object(compare,'TaskDeadlineEnv',GuardFixture),patch('ai.throttle.CpuBudget.pause'):
            baseline=compare.run_arm(model_fixture(),case,'joint',14_989_430,1)
            guarded=compare.run_arm(model_fixture(),case,'deadline',14_989_430,1)
        self.assertGreater(baseline['counts'].get('same_round_count_losses',0),0)
        self.assertGreater(guarded['counts']['prevented_old_placement_choices'],0)
        self.assertEqual(guarded['counts'].get('same_round_count_losses',0),0)

    def test_half_ice_loss_at_round_boundary_is_not_counted_as_same_round_failure(self):
        fixed=ice_final_pair_fixture().game
        fixed.landung.hoehe=1000;fixed.letzte_runde=False;fixed.warteschleife=True
        fixed.cockpit.fahrwerk_ausgefahren[:]=[False,False,True]
        fixed.cockpit.landeklappen_ausgefahren[-1]=False
        class Fixture(TaskDeadlineEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        bad=_action(3,'konzentration',index=2)
        def scripted(agent,view,mask,*,reference_mask=None):
            return bad if mask[bad] else next(i for i,v in enumerate(reference_mask) if v)
        with patch.object(ModelAgent,'select',scripted),patch.object(compare,'TaskDeadlineEnv',Fixture),patch('ai.throttle.CpuBudget.pause'):
            result=compare.run_arm(model_fixture(),ice_case(),'deadline',14_989_440,1)
        self.assertGreater(result['counts'].get('round_boundary_count_losses',0),0)
        transitions=[r for r in result['measurements'][0]['changes'] if r['kind']=='capacity_transition']
        self.assertTrue(transitions);self.assertFalse(transitions[0]['same_round'])

    def test_resource_seeds_stop_and_existing_report_guards(self):
        for arm,seed,games,duty in (('other',14_989_400,1,.7),('deadline',15_000_000,1,.7),
                ('deadline',14_989_400,21,.7),('deadline',14_989_400,1,.8)):
            with self.assertRaises(ValueError):compare.run_arm(model_fixture(),ice_case(),arm,seed,games,duty)
        with tempfile.TemporaryDirectory() as folder:
            output,stop=Path(folder)/'out.json',Path(folder)/'STOP'
            with patch.object(compare,'STOP_FILE',stop),patch.object(compare.legacy,'load_model',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                for args in (['--workers','9'],['--cpu-duty-cycle','.8']):
                    with self.assertRaises(SystemExit):compare.main(['--output',str(output)]+args)
                stop.touch()
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                stop.unlink();output.write_text('evidence')
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'evidence')

    def test_failure_never_marks_evidence_complete_or_adds_training(self):
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
            self.assertFalse(report['release_evidence']);self.assertEqual(report['ppo_updates'],0)
            self.assertEqual(report['new_training_decisions'],0)


if __name__=='__main__':unittest.main()
