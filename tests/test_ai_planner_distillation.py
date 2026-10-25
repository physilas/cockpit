import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import torch

from ai.distill_planner import distillation_loss, make_student, teacher_rows
from ai.checkpoints import save_checkpoint
from ai.export_browser import export_models
from ai.nn_model import ActorCritic, ResidualActorCritic


class PlannerDistillationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_policy_bootstrap_preserves_teacher_and_value(self):
        source = ResidualActorCritic(ActorCritic(hidden_size=16), 489, 217)
        model = make_student(source)
        observation = torch.randn(5, 489)
        source_state = {k: v.clone() for k, v in source.state_dict().items()}
        logits, value = source(observation)
        actual, actual_value = model(observation)
        torch.testing.assert_close(actual, logits)
        torch.testing.assert_close(actual_value, value)
        masks = torch.ones(5, 217, dtype=torch.bool)
        targets = torch.zeros(5, 217)
        targets[:, 0] = 1.
        before = float(distillation_loss(actual.detach(), masks, targets))
        optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=.01)
        for _ in range(5):
            loss = distillation_loss(model(observation)[0], masks, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        self.assertLess(float(distillation_loss(model(observation)[0].detach(), masks, targets)), before)
        torch.testing.assert_close(model(observation)[1], value)
        for key, tensor in source.state_dict().items():
            self.assertTrue(torch.equal(tensor, source_state[key]))

    def test_teacher_uses_separate_namespaces_and_retains_its_support(self):
        source = ActorCritic(489, 217, hidden_size=16)
        data, report = teacher_rows(source, 'LOG_OSL_GREEN', ['planner-teacher:test:train:0'], duty=1.)
        again, repeated = teacher_rows(source, 'LOG_OSL_GREEN', ['planner-teacher:test:train:0'], duty=1.)
        self.assertEqual(report, repeated)
        self.assertEqual(data['observations'].shape[1], 489)
        self.assertEqual(report['decisions'], len(data['targets']))
        self.assertFalse(bool((data['teacher_masks'] & ~data['masks']).any()))
        self.assertFalse(bool((data['targets'][~data['teacher_masks']] != 0).any()))
        torch.testing.assert_close(data['targets'].sum(-1), torch.ones(len(data['targets'])))
        for key in data: self.assertTrue(torch.equal(data[key], again[key]))

    def test_dagger_labels_student_visited_states_with_the_fixed_teacher(self):
        teacher = ActorCritic(489, 217, hidden_size=16)
        student = ActorCritic(489, 217, hidden_size=16)
        data, report = teacher_rows(teacher, 'LOG_OSL_GREEN', ['planner-teacher:test:dagger:0'],
                                    duty=1., student=student, student_fraction=1.)
        self.assertEqual(report['student_decisions'], report['decisions'])
        with torch.inference_mode():
            teacher_logits = teacher(data['observations'])[0]
            expected = teacher_logits.masked_fill(~data['teacher_masks'], torch.finfo(teacher_logits.dtype).min).softmax(-1)
        torch.testing.assert_close(data['targets'], expected)
        self.assertFalse(bool((data['teacher_masks'] & ~data['masks']).any()))

    @unittest.skipUnless(shutil.which('node'), 'node required')
    def test_nested_frozen_teacher_exports_to_browser(self):
        model = make_student(ResidualActorCritic(ActorCritic(hidden_size=16), 489, 217, hidden_size=24))
        torch.nn.init.normal_(model.residual.actor.weight, std=.05)
        inputs = torch.randn(3, 489)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            save_checkpoint(root / 'runs/student/best.pt', model)
            catalog = export_models(root / 'runs', root / 'web')
            entry = catalog['models'][0]
            fixture = {'model': json.loads((root / 'web' / entry['url']).read_text()),
                       'catalog': {'schema': entry['schema']}, 'inputs': inputs.tolist()}
            script = """const fs=require('node:fs');global.window={};eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.inputs.map(o=>p.logits(o))));"""
            result = subprocess.run(['node', '-e', script, str(Path(__file__).resolve().parents[1] / 'frontend/web/js/ai-policy.js')],
                                    input=json.dumps(fixture), text=True, capture_output=True, check=True)
            torch.testing.assert_close(model(inputs)[0], torch.tensor(json.loads(result.stdout)), atol=2e-6, rtol=1e-6)


if __name__ == '__main__':
    unittest.main()
