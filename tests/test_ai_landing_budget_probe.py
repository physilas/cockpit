"""Passive probe makes no update and never marks interrupted evidence complete."""
from contextlib import redirect_stderr,redirect_stdout
import io
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai import landing_budget_probe as probe
from ai.agents import ModelAgent
from ai.checkpoints import weight_fingerprint
from tests.test_ai_wind_ice_compare import model_fixture,ice_case


class LandingBudgetProbeTests(unittest.TestCase):
    def test_actual_probe_retains_model_rng_and_records_only_training_namespaces(self):
        model=model_fixture();before=weight_fingerprint(model),random.getstate(),torch.get_rng_state().clone()
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'out.json'
            with patch.object(probe.legacy,'load_model',return_value=(model,{})),patch.object(probe.legacy,'cases',return_value=[ice_case()]),\
                    patch('ai.throttle.CpuBudget.pause'),redirect_stdout(io.StringIO()):
                probe.main(['--output',str(output)])
            report=json.loads(output.read_text())
        self.assertTrue(report['complete']);self.assertEqual(len(report['episodes']),2)
        self.assertTrue(all(r['seed'].startswith('train:landing-budget-probe:251070:') for r in report['episodes']))
        self.assertEqual(report['ppo_updates'],0);self.assertEqual(report['new_training_decisions'],0)
        self.assertEqual(report['workers'],1);self.assertEqual(report['cpu_duty_cycle'],.7)
        self.assertGreater(report['sampled_training_decisions'],0)
        self.assertEqual(before[0],weight_fingerprint(model));self.assertEqual(before[1],random.getstate())
        self.assertTrue(torch.equal(before[2],torch.get_rng_state()))

    def test_failure_leaves_incomplete_and_preserves_original_exception(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'out.json'
            with patch.object(probe.legacy,'load_model',return_value=(model_fixture(),{})),patch.object(probe.legacy,'cases',return_value=[ice_case()]),\
                    patch.object(ModelAgent,'select',side_effect=RuntimeError('controlled failure')):
                with self.assertRaisesRegex(RuntimeError,'controlled failure'):probe.main(['--output',str(output)])
            report=json.loads(output.read_text());self.assertFalse(report['complete'])
            self.assertEqual(report['ppo_updates'],0)

    def test_stop_and_existing_output_prevent_start(self):
        with tempfile.TemporaryDirectory() as folder:
            output,stop=Path(folder)/'out.json',Path(folder)/'STOP'
            with patch.object(probe.legacy,'STOP_FILE',stop),patch.object(probe.legacy,'load_model',side_effect=AssertionError('No load')),redirect_stderr(io.StringIO()):
                stop.touch()
                with self.assertRaises(SystemExit):probe.main(['--output',str(output)])
                stop.unlink();output.write_text('existing evidence')
                with self.assertRaises(SystemExit):probe.main(['--output',str(output)])
                self.assertEqual(output.read_text(),'existing evidence')


if __name__=='__main__':unittest.main()
