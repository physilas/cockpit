"""Passive known-cohort tracing must preserve public-case play exactly."""
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

from ai import leak_failure_probe as probe
from ai.actions import Action
from ai.agents import ModelAgent
from ai.checkpoints import load_checkpoint, planner_fingerprint, save_checkpoint, weight_fingerprint
from ai.modules import CARDS, MODULE_ACTIONS
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.public_case_eval import run_public_case


CASE = {'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': ['adaptation']}


def tiny_model():
    torch.manual_seed(251061)
    return GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1, guide_margin=12.)


def checkpoints(folder):
    warm = tiny_model()
    candidate = deepcopy(warm)
    with torch.no_grad():
        candidate.residual.actor.bias[0] += .125
    config = dict(assistance_version=12, phase_kind='new_public_module_profile_12_leak_cards',
        planner_sha256=planner_fingerprint(3), phase_sha256=probe.phase_fingerprint(),
        initial_weights_sha256=weight_fingerprint(warm), source_weights_sha256='original-prephase-source',
        eval_seed=probe.BASE_SEED, eval_seed_stride=100, eval_games_per_case=20,
        curriculum_cases=[{'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': [card]}
                          for card in sorted(CARDS)])
    source_path, candidate_path = folder/'warm.pt', folder/'latest.pt'
    save_checkpoint(source_path, warm, train_config=deepcopy(config), total_steps=0)
    save_checkpoint(candidate_path, candidate, train_config=deepcopy(config), total_steps=128)
    return source_path, candidate_path


class LeakFailureProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_native_public_evaluator_actions_summary_rng_and_weights_are_identical(self):
        model = tiny_model()
        model.train()
        before = weight_fingerprint(model), random.getstate(), torch.get_rng_state().clone()
        selected = []
        original = ModelAgent.select

        def record(agent, view, mask, *, reference_mask=None):
            self.assertNotIn('partner_dice', view)
            action = original(agent, view, mask, reference_mask=reference_mask)
            selected.append((deepcopy(view), list(mask), list(reference_mask), action))
            return action

        # Pacing is not part of the physical ATL rules. Disable sleeps only in
        # this tiny technical test, identically for both control and trace.
        with patch.object(ModelAgent, 'select', record), patch('ai.throttle.CpuBudget.pause'):
            expected = run_public_case(model, CASE, 1, probe.BASE_SEED, assistance_version=12)
            control_actions = deepcopy(selected)
            selected.clear()
            actual = probe.run_probe_case(model, CASE, 1, probe.BASE_SEED)
        self.assertEqual(actual['summary'], expected)
        self.assertEqual(selected, control_actions)
        self.assertTrue(model.training)
        self.assertEqual(weight_fingerprint(model), before[0])
        self.assertEqual(random.getstate(), before[1])
        self.assertTrue(torch.equal(torch.get_rng_state(), before[2]))
        trace = actual['traces'][0]
        self.assertEqual(trace['seed'], probe.BASE_SEED)
        self.assertEqual(trace['status'], expected['episodes'][0]['status'])
        self.assertLessEqual(len(trace['last_events']), 3)
        self.assertEqual(len(trace['last_events']), 0 if trace['status']=='gewonnen' else min(3,len(control_actions)))
        for event in trace['last_events']:
            self.assertIn(event['action']['id'], event['legal_action_ids'])
            self.assertTrue(set(event['reference_action_ids']) <= set(event['legal_action_ids']))
            self.assertEqual(len(event['own_hand']), 4)
            for field in ('public_before', 'public_after'):
                for private in ('own_dice', 'partner_dice', 'pilot_wuerfel', 'kopilot_wuerfel', 'rng'):
                    self.assertNotIn(private, event[field])
        self.assertFalse(actual['summary']['release_evidence'])

    def test_public_snapshot_allowlist_and_nested_copies_cannot_serialize_private_extras(self):
        view = {'role': 'pilot', 'board': [{'owner': 'kopilot', 'value': 4}],
                'own_dice': [1,2,3,4], 'partner_dice': ['PRIVATE'], 'rng': 'FUTURE',
                'engine': 'PRIVATE_ENGINE', 'track': [{'distance': 2, 'planes': 1}]}
        before = deepcopy(view)
        result = probe.public_view(view)
        self.assertEqual(result, {'role': 'pilot', 'board': [{'owner': 'kopilot', 'value': 4}],
                                  'track': [{'distance': 2, 'planes': 1}]})
        result['board'][0]['value'] = 1
        self.assertEqual(view, before)

    def test_only_the_old_six_disjoint_validation_cohorts_are_allowed(self):
        for ordinal, card in enumerate(sorted(CARDS)):
            case = {**CASE, 'abilities': [card]}
            first = probe.BASE_SEED + 100*ordinal
            probe.validate_case_seed(case, first, 20)
            probe.validate_case_seed(case, first+19, 1)
            for seed, games in ((first-1,1),(first+20,1),(first,21),(15_000_000,1),(first,True)):
                with self.subTest(card=card,seed=seed,games=games), self.assertRaises(ValueError):
                    probe.validate_case_seed(case, seed, games)
        with self.assertRaises(ValueError):
            probe.validate_case_seed({**CASE,'abilities':['control','adaptation']},probe.BASE_SEED,1)
        with patch('ai.public_case_eval.ModuleEnv',side_effect=AssertionError('No game may start')):
            with self.assertRaises(ValueError):
                probe.run_probe_case(tiny_model(),CASE,1,14_940_000)

    def test_groups_keep_loss_round_height_and_active_or_passive_card_usage(self):
        def trace(seed,status,reason,chosen,triggered):
            return dict(seed=seed,status=status,reason=reason,round=2,height=5000,
                        card_offered_decisions={'adaptation':3},card_reference_offered_decisions={'adaptation':1},
                        card_selected_actions=chosen,card_pair_or_sync_triggers=triggered,last_events=[])
        rows = [trace(1,'verloren','trudeln',{},{}),
                trace(2,'verloren','trudeln',{'adaptation':1},{}),
                trace(3,'verloren','kerosin_leer',{}, {'mastery':1}),
                trace(4,'gewonnen','',{'adaptation':1},{})]
        before = deepcopy(rows)
        result = probe.group_traces(rows)
        self.assertEqual(rows,before)
        self.assertEqual(result['losses_by_reason'],{'trudeln':2,'kerosin_leer':1})
        self.assertEqual(result['losses_by_round'],{'2':3})
        self.assertEqual(result['losses_by_height'],{'5000':3})
        self.assertEqual(len(result['loss_groups']),3)
        self.assertEqual(result['card_selected_actions'],{'adaptation':2})
        self.assertEqual(result['card_pair_or_sync_triggers'],{'mastery':1})

    def test_finished_model_lineage_and_sources_are_checked_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            warm, latest = checkpoints(Path(directory))
            before = warm.read_bytes(), latest.read_bytes()
            models, metadata = probe.load_models(warm,latest)
            self.assertEqual(metadata['source']['phase_steps'],0)
            self.assertEqual(metadata['candidate']['phase_steps'],128)
            self.assertEqual(metadata['source']['initial_weights_sha256'],weight_fingerprint(models['source']))
            self.assertEqual((warm.read_bytes(),latest.read_bytes()),before)
            for mutation in ('planner_sha256','phase_sha256','initial_weights_sha256','eval_seed','eval_games_per_case','foundation'):
                latest.write_bytes(before[1])
                model,payload=load_checkpoint(latest)
                if mutation=='foundation':
                    with torch.no_grad(): model.source.actor.bias[0]+=.1
                    payload['model_state']=model.state_dict()
                else: payload['train_config'][mutation]='changed'
                torch.save(payload,latest)
                with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                    probe.load_models(warm,latest)

    def test_old_validation_is_unique_complete_and_difference_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'validation.jsonl'
            cases={'LOG_ATL_YELLOW|'+card:dict(games=20,wins=0,win_rate=0.,decisions=100,
                reference_departures=0,loss_reasons={'trudeln':20}) for card in CARDS}
            rows=[dict(steps=steps,cases=cases,release_evidence=False) for steps in (0,128)]
            data='\n'.join(json.dumps(row) for row in rows)+'\n';file.write_text(data)
            metadata={'source':{'phase_steps':0},'candidate':{'phase_steps':128}}
            validation,_=probe.load_validation(file,metadata)
            self.assertEqual(validation['source'],cases)
            expected=cases['LOG_ATL_YELLOW|adaptation']
            self.assertEqual(probe.validation_match(expected,deepcopy(expected)),{})
            changed={**expected,'wins':1,'win_rate':.05}
            self.assertEqual(set(probe.validation_match(changed,expected)),{'wins','win_rate'})
            file.write_text(data+json.dumps(rows[0])+'\n')
            with self.assertRaises(ValueError):probe.load_validation(file,metadata)

    def test_cli_stop_resources_seed_and_existing_output_fail_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'report.json';stop=root/'STOP_AI_TRAINING'
            with patch.object(probe,'STOP_FILE',stop),patch.object(probe,'load_models',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                for args in (['--workers','9'],['--cpu-duty-cycle','.8'],['--seed','15000000'],['--seed','14940000'],['--games','21']):
                    with self.subTest(args=args),self.assertRaises(SystemExit):probe.main(['--output',str(output)]+args)
                stop.touch()
                with self.assertRaises(SystemExit):probe.main(['--output',str(output)])
                stop.unlink();output.write_text('preserved evidence')
                with self.assertRaises(SystemExit):probe.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'preserved evidence')

    def test_worker_failure_leaves_atomic_incomplete_report(self):
        class FailedPool:
            def __init__(self,*args,**kwargs):pass
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def map(self,*args):raise RuntimeError('fixture worker failure')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);output=root/'report.json'
            with patch.object(probe,'STOP_FILE',root/'STOP'), \
                    patch.object(probe,'atlanta_cases',return_value=[CASE]), \
                    patch.object(probe,'load_models',return_value=({},{})), \
                    patch.object(probe,'load_validation',return_value=({},'validation-sha')), \
                    patch.object(probe,'ProcessPoolExecutor',FailedPool), \
                    patch.object(probe,'probe_fingerprint',return_value='probe-sha'):
                with self.assertRaisesRegex(RuntimeError,'fixture worker failure'):
                    probe.main(['--output',str(output)])
            result=json.loads(output.read_text())
            self.assertFalse(result['complete'])
            self.assertFalse(result['fresh_evidence'])
            self.assertTrue(result['repeated_development_validation'])
            self.assertEqual(result['error_type'],'RuntimeError')
            self.assertFalse(list(root.glob('*.partial')))


if __name__=='__main__':
    unittest.main()
