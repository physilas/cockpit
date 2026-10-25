"""Paired research uses the real source policy/mask and untouched weights."""
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

from ai import wind_ice_compare as compare
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.public_case_eval import run_public_case
from ai.wind_ice_environment import WindIceEnv
from tests.test_ai_wind_ice_counterexamples import ice_final_pair_fixture


def model_fixture():
    torch.manual_seed(251065)
    return GuidedResidualActorCritic(ActorCritic(489, 217, 8, 1), 489, 217, 8, 1, guide_margin=12.)


def ice_case():
    return next(row for row in compare.cases() if row['airport'] == 'LOG_KEF_YELLOW' and row['abilities'] == ['adaptation'])


class WindIceComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): torch.set_num_threads(1)

    def test_native_instrumentation_keeps_exact_inputs_actions_rng_and_game(self):
        model = model_fixture(); model.train()
        before = weight_fingerprint(model), random.getstate(), torch.get_rng_state().clone()
        select, sequence = ModelAgent.select, []
        def capture(agent, view, mask, *, reference_mask=None):
            result = select(agent, view, mask, reference_mask=reference_mask)
            sequence.append((deepcopy(view), list(mask), list(reference_mask), result))
            return result
        with patch.object(ModelAgent, 'select', capture), patch('ai.throttle.CpuBudget.pause'):
            control = run_public_case(model, ice_case(), 1, 14_989_000, assistance_version=12)
            expected = deepcopy(sequence); sequence.clear()
            actual = compare.run_arm(model, ice_case(), 'native', 14_989_000, 1)
        self.assertEqual(actual['summary'], control)
        self.assertEqual(sequence, expected)
        self.assertEqual(actual['counts']['changed_reference_decisions'], 0)
        self.assertEqual(weight_fingerprint(model), before[0])
        self.assertEqual(random.getstate(), before[1])
        self.assertTrue(torch.equal(torch.get_rng_state(), before[2]))
        self.assertTrue(model.training)

    def test_research_actual_engine_win_and_same_state_preference_measurement(self):
        fixed = ice_final_pair_fixture().game
        class Fixture(WindIceEnv):
            def reset(self, **kwargs):
                super().reset(**kwargs)
                self.game = deepcopy(fixed)
                return self.observation(), self.info()
        model = model_fixture()
        before = weight_fingerprint(model), torch.get_rng_state().clone(), random.getstate()
        with patch.object(compare, 'WindIceEnv', Fixture), patch('ai.throttle.CpuBudget.pause'):
            result = compare.run_arm(model, ice_case(), 'microplans', 14_989_010, 1)
        self.assertEqual(result['summary']['wins'], 1)
        self.assertGreater(result['counts']['changed_reference_decisions'], 0)
        self.assertEqual(result['counts']['reference_departures'], 0)
        self.assertEqual(result['measurements'][0]['seed'], 14_989_010)
        self.assertTrue(all('own_dice' not in row and 'partner_dice' not in row for row in result['measurements'][0]['changes']))
        self.assertEqual(weight_fingerprint(model), before[0])
        self.assertTrue(torch.equal(torch.get_rng_state(), before[1]))
        self.assertEqual(random.getstate(), before[2])

    def test_pairing_preserves_each_card_seed_and_rejects_cross_card_join(self):
        def output(statuses):
            return {'summary': {'episodes': [dict(seed=14_989_020+i, scenario='LOG_KEF_YELLOW',
                case_key='LOG_KEF_YELLOW|adaptation', status=status, reason='') for i, status in enumerate(statuses)]}}
        before, after = output(['gewonnen', 'verloren']), output(['verloren', 'gewonnen'])
        pairs = compare.paired_details(before, after)
        self.assertEqual(pairs['outcomes'], dict(both_win=0, both_lose=0, baseline_only=1, candidate_only=1))
        self.assertEqual(len(pairs['episodes']), 2)
        after['summary']['episodes'][0]['case_key'] = 'LOG_KEF_YELLOW|control'
        with self.assertRaises(ValueError): compare.paired_details(before, after)

    def test_resources_reserved_seeds_stop_and_existing_reports_are_guarded(self):
        model = model_fixture()
        for arm, seed, games, duty in (('unknown',14_989_000,1,.7), ('native',15_000_000,1,.7),
                ('native',14_989_000,21,.7), ('native',14_989_000,1,.8)):
            with self.subTest(arm=arm, seed=seed, games=games, duty=duty), self.assertRaises(ValueError):
                compare.run_arm(model, ice_case(), arm, seed, games, duty)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); stop, output = root/'STOP', root/'out.json'
            with patch.object(compare, 'STOP_FILE', stop), patch.object(compare, 'load_model', side_effect=AssertionError('No load')), redirect_stderr(io.StringIO()):
                for args in (['--workers','9'], ['--cpu-duty-cycle','.8']):
                    with self.assertRaises(SystemExit): compare.main(['--output',str(output)] + args)
                stop.touch()
                with self.assertRaises(SystemExit): compare.main(['--output',str(output)])
                stop.unlink(); output.write_text('existing evidence')
                with self.assertRaises(SystemExit): compare.main(['--output',str(output)])
                self.assertEqual(output.read_text(), 'existing evidence')

    def test_worker_failure_keeps_complete_false_and_records_no_training(self):
        class FailedPool:
            def __init__(self,*args,**kwargs): pass
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def map(self,*args): raise RuntimeError('wind-ice worker fixture failure')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); output = root/'report.json'
            with patch.object(compare, 'STOP_FILE', root/'STOP'), patch.object(compare, 'load_model', return_value=(None, {})), \
                    patch.object(compare, 'comparison_fingerprint', return_value='code-sha'), patch.object(compare, 'ProcessPoolExecutor', FailedPool):
                with self.assertRaisesRegex(RuntimeError, 'worker fixture failure'): compare.main(['--output', str(output)])
            report = json.loads(output.read_text())
            self.assertFalse(report['complete'])
            self.assertFalse(report['release_evidence'])
            self.assertEqual(report['ppo_updates'], 0)
            self.assertEqual(report['new_training_decisions'], 0)
            self.assertEqual(len(report['cases']), 12)


if __name__ == '__main__':
    unittest.main()
