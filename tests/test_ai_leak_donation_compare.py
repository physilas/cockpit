"""Paired donation research keeps the native control, tensors and raw rules."""
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

from ai import leak_donation_compare as compare
from ai.actions import Action
from ai.agents import ModelAgent
from ai.checkpoints import load_checkpoint, planner_fingerprint, save_checkpoint, weight_fingerprint
from ai.leak_donation_environment import DonationEnv
from ai.modules import MODULE_ACTIONS, ModuleEnv
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.public_case_eval import run_public_case
from tests.test_ai_leak_donation_advice import donation_env


def model_fixture():
    torch.manual_seed(251062)
    return GuidedResidualActorCritic(ActorCritic(489,217,8,1),489,217,8,1,guide_margin=12.)


def checkpoint_fixture(path):
    model=model_fixture()
    config=dict(assistance_version=12,phase_kind='new_public_module_profile_12_leak_cards',
                planner_sha256=planner_fingerprint(3),phase_sha256=compare.phase_fingerprint(),
                initial_weights_sha256=weight_fingerprint(model))
    save_checkpoint(path,model,train_config=config,total_steps=0)
    return model


def synthetic_output(seed,statuses):
    episodes=[];instrumentation=[]
    for ordinal,status in enumerate(statuses):
        episodes.append(dict(seed=seed+ordinal,scenario=compare.CASE['airport'],case_key=compare.CASE_KEY,
            airport=compare.CASE['airport'],abilities=['working-together'],modules=['leak'],
            status=status,reason='' if status=='gewonnen' else 'trudeln',round=1,steps=2,
            **{'return':1. if status=='gewonnen' else -1.},outcome_return=0.,round_return=0.,
            sync_return=0.,tasks_return=0.,tasks_undone=1,distance_remaining=7,sync_error=1.,
            airport_reached=0,landing_round_started=0,reference_departures=0,decisions=2))
        instrumentation.append(dict(seed=seed+ordinal,scenario=compare.CASE['airport'],
            **{key:{'swap_start':0} for key in compare.COUNTERS},swap_events=[]))
    return {'summary':{'episodes':episodes},'instrumentation':instrumentation}


class LeakDonationComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):torch.set_num_threads(1)

    def test_native_arm_is_exact_public_case_control_including_policy_inputs_and_rng(self):
        model=model_fixture();model.train()
        before=weight_fingerprint(model),random.getstate(),torch.get_rng_state().clone()
        original=ModelAgent.select;selected=[]
        def capture(agent,view,mask,*,reference_mask=None):
            self.assertNotIn('partner_dice',view)
            result=original(agent,view,mask,reference_mask=reference_mask)
            selected.append((deepcopy(view),list(mask),list(reference_mask),result))
            return result
        # A separate technical-test seed leaves the preregistered50-game
        # donation cohort completely unused before the actual experiment.
        with patch.object(ModelAgent,'select',capture),patch('ai.throttle.CpuBudget.pause'):
            baseline=run_public_case(model,compare.CASE,1,14_982_000,assistance_version=12)
            sequence=deepcopy(selected);selected.clear()
            actual=compare.run_arm(model,'native',14_982_000,1)
        self.assertEqual(actual['summary'],baseline)
        self.assertEqual(selected,sequence)
        self.assertEqual(weight_fingerprint(model),before[0]);self.assertEqual(random.getstate(),before[1])
        self.assertTrue(torch.equal(torch.get_rng_state(),before[2]));self.assertTrue(model.training)
        info=actual['instrumentation'][0]
        self.assertFalse(any(info['additional_swap_reference_decisions'].values()))
        self.assertFalse(any(info['additional_swap_chosen_actions'].values()))

    def test_real_research_swap_is_counted_against_same_state_native_reference(self):
        fixed=donation_env().game
        class NativeFixture(ModuleEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        class DonationFixture(DonationEnv):
            def reset(self,**kwargs):
                super().reset(**kwargs);self.game=deepcopy(fixed)
                return self.observation(),self.info()
        native=NativeFixture(**{'airport':'LOG_ATL_YELLOW','abilities':['working-together'],'assistance_version':12})
        donation=DonationFixture(**{'airport':'LOG_ATL_YELLOW','abilities':['working-together'],'assistance_version':12})
        native.reset(seed='train:donation-comparison-unit');donation.reset(seed='train:donation-comparison-unit')
        first,second=native.info(),donation.info()
        self.assertEqual(first['action_mask'],second['action_mask'])
        self.assertEqual(first['reference_action_mask'],second['source_reference_action_mask'])
        start=MODULE_ACTIONS.index(Action('swap_start'))
        self.assertFalse(first['reference_action_mask'][start]);self.assertTrue(second['reference_action_mask'][start])
        model=model_fixture();before=weight_fingerprint(model)
        with patch.object(compare,'DonationEnv',DonationFixture),patch('ai.throttle.CpuBudget.pause'):
            actual=compare.run_arm(model,'donation',14_982_010,1)
        info=actual['instrumentation'][0]
        self.assertGreater(info['additional_swap_reference_decisions']['swap_start'],0)
        self.assertGreater(info['additional_swap_chosen_actions']['swap_start'],0)
        self.assertTrue(any(event['kind']=='swap_start' and event['additional_to_native_reference'] for event in info['swap_events']))
        self.assertEqual(weight_fingerprint(model),before)
        self.assertTrue(all('own_dice' not in event and 'partner_dice' not in event for event in info['swap_events']))

    def test_warm_model_configuration_lineage_and_file_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'warm.pt';checkpoint_fixture(path);before=path.read_bytes()
            model,metadata=compare.load_warm(path)
            self.assertEqual(metadata['weights_sha256'],weight_fingerprint(model))
            self.assertEqual(metadata['guide_margin'],12.);self.assertEqual(metadata['phase_steps'],0)
            self.assertEqual(path.read_bytes(),before)
            for mutation in ('total_steps','planner_sha256','phase_sha256','initial_weights_sha256','assistance_version'):
                path.write_bytes(before);_,payload=load_checkpoint(path)
                if mutation=='total_steps':payload[mutation]=1
                else:payload['train_config'][mutation]='changed'
                torch.save(payload,path)
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):compare.load_warm(path)

    def test_chunk_and_pair_identity_keep_each_full_episode(self):
        seed=14_982_020
        native_outputs=[synthetic_output(seed,['gewonnen','verloren']),synthetic_output(seed+2,['verloren','gewonnen'])]
        donation_outputs=[synthetic_output(seed,['verloren','gewonnen']),synthetic_output(seed+2,['verloren','gewonnen'])]
        arms={'native':compare.combine_chunks(native_outputs,seed,4),'donation':compare.combine_chunks(donation_outputs,seed,4)}
        self.assertEqual(len(arms['native']['summary']['episodes']),4)
        paired=compare.paired_details(arms)
        self.assertEqual(paired['outcomes'],dict(both_win=1,both_lose=1,candidate_only=1,baseline_only=1))
        self.assertEqual([row['seed'] for row in paired['episodes']],list(range(seed,seed+4)))
        broken=deepcopy(donation_outputs);broken[0]['summary']['episodes'][0]['seed']+=100
        with self.assertRaises(ValueError):compare.combine_chunks(broken,seed,4)
        broken=deepcopy(arms);broken['donation']['summary']['episodes'][0]['case_key']='LOG_ATL_YELLOW|control'
        with self.assertRaises(ValueError):compare.paired_details(broken)
        with self.assertRaises(ValueError):compare.paired_details({'donation':arms['donation']})

    def test_bad_arm_seeds_duty_and_nonmatching_margin_never_start_game(self):
        model=model_fixture()
        with patch('ai.public_case_eval.ModuleEnv',side_effect=AssertionError('No game may start')):
            for arm,seed,games in (('unknown',14_982_000,1),('native',15_000_000,1),('native',13_999_999,1),('native',14_982_000,51)):
                with self.subTest(arm=arm,seed=seed,games=games),self.assertRaises(ValueError):compare.run_arm(model,arm,seed,games)
            with self.assertRaises(ValueError):compare.run_arm(model,'native',14_982_000,1,cpu_duty_cycle=.8)
        other=model_fixture();other.guide_margin=4.;other.config['guide_margin']=4.
        with self.assertRaises(ValueError):compare.run_arm(other,'native',14_982_000,1)

    def test_cli_preregistered_cohort_resources_stop_and_existing_output_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'report.json';stop=root/'STOP'
            with patch.object(compare,'STOP_FILE',stop),patch.object(compare,'load_warm',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                for args in (['--workers','9'],['--cpu-duty-cycle','.8'],['--seed','15000000'],['--seed','14983000'],['--games','49']):
                    with self.subTest(args=args),self.assertRaises(SystemExit):compare.main(['--output',str(output)]+args)
                stop.touch()
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                stop.unlink();output.write_text('existing evidence')
                with self.assertRaises(SystemExit):compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'existing evidence')

    def test_failed_worker_keeps_atomic_complete_false_without_replacing_existing_evidence(self):
        class FailedPool:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def map(self,*args):raise RuntimeError('donation worker fixture failure')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'report.json'
            with patch.object(compare,'STOP_FILE',root/'STOP'),patch.object(compare,'load_warm',return_value=(None,{})), \
                    patch.object(compare,'comparison_fingerprint',return_value='code-sha'),patch.object(compare,'ProcessPoolExecutor',FailedPool):
                with self.assertRaisesRegex(RuntimeError,'donation worker fixture failure'):compare.main(['--output',str(output)])
            report=json.loads(output.read_text())
            self.assertFalse(report['complete']);self.assertFalse(report['release_evidence'])
            self.assertEqual(report['ppo_updates'],0);self.assertEqual(report['error_type'],'RuntimeError')
            self.assertEqual(report['base_seed'],14_984_000);self.assertEqual(report['games_per_arm'],50)
            self.assertFalse(list(root.glob('*.partial')))


if __name__=='__main__':unittest.main()
