import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import torch

from ai.checkpoints import planner_fingerprint, save_checkpoint
from ai.nn_model import ActorCritic, GuidedResidualActorCritic
from ai.route_eval import main


class InlinePool:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def map(self, function, tasks):
        return map(function, tasks)


class RouteQualificationTests(unittest.TestCase):
    def test_module_model_records_its_actual_planner_and_finishes_report(self):
        torch.set_num_threads(1)
        model = GuidedResidualActorCritic(ActorCritic(489, 217, hidden_size=8),
                                         489, 217, hidden_size=8)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checkpoint, output = root / 'candidate.pt', root / 'evaluation.json'
            save_checkpoint(checkpoint, model, train_config={'assistance_version': 9})
            argv = ['ai.route_eval', '--checkpoint', str(checkpoint), '--airports', 'MUC',
                    '--games', '1', '--partner-games', '1', '--workers', '1',
                    '--cpu-duty-cycle', '.7', '--output', str(output)]
            with patch('sys.argv', argv), patch('ai.route_eval.ProcessPoolExecutor', InlinePool), contextlib.redirect_stdout(io.StringIO()):
                main()
            report = json.loads(output.read_text())
            self.assertTrue(report['complete'])
            self.assertEqual(report['schema_version'], 3)
            self.assertEqual(report['planner_sha256'], planner_fingerprint(3))
            self.assertNotEqual(report['planner_sha256'], planner_fingerprint(1))
            self.assertEqual(report['routes']['MUC']['self']['games'], 1)
            self.assertEqual(report['routes']['MUC']['heuristic_partner']['games'], 2)
            self.assertEqual(report['cpu_duty_cycle'], .7)


if __name__ == '__main__':
    unittest.main()
