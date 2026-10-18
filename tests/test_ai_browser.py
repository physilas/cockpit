import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from backend import bridge
from ai.browser_bridge import decision
from ai.environment import CrewEnv
from ai.observation import OBSERVATION_SIZE

try:
    import torch
except ImportError:
    torch = None


class BrowserDecisionTests(unittest.TestCase):
    def test_exact_training_inputs_and_hidden_partner_boundary(self):
        bridge.neues_spiel("MUC")
        env = CrewEnv()
        env.game = bridge._spiel
        actual = decision()
        self.assertEqual(actual["observation"], env.observation())
        self.assertEqual(actual["action_mask"], env.action_mask())
        for die in bridge._spiel._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl = 7 - die.augenzahl
        self.assertEqual(actual, decision())
        self.assertNotIn("own_dice", actual["public_state"])
        self.assertEqual(len(actual["observation"]), OBSERVATION_SIZE)

    def test_reroll_and_information_role_are_enforced(self):
        bridge.neues_spiel("MUC")
        pending = {"initiator": "pilot", "selections": {"pilot": [0], "kopilot": None}}
        actual = decision("kopilot", json.dumps(pending))
        self.assertEqual(actual["role"], "kopilot")
        self.assertTrue(any(actual["action_mask"]))
        with self.assertRaises(ValueError):
            decision("pilot", json.dumps(pending))
        bridge.neues_spiel("LOG_HND_RED", '["control"]')
        with self.assertRaises(ValueError):
            decision()


@unittest.skipUnless(torch is not None and shutil.which("node"), "torch and node required")
class BrowserModelTests(unittest.TestCase):
    def test_exported_logits_and_choices_match_pytorch_for_architectures(self):
        from ai.actions import ACTION_COUNT
        from ai.checkpoints import save_checkpoint
        from ai.export_browser import export_models
        from ai.nn_model import ActorCritic
        torch.set_num_threads(1)
        root = Path(__file__).resolve().parents[1]
        for depth in (2, 3):
            with self.subTest(depth=depth), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                torch.manual_seed(14)
                model = ActorCritic(hidden_size=32, hidden_layers=depth)
                save_checkpoint(folder / "runs/a/latest.pt", model,
                                train_config={"airport": "MUC", "max_steps": 256}, total_steps=123)
                catalog = export_models(folder / "runs", folder / "web")
                model_data = json.loads((folder / "web" / catalog["models"][0]["url"]).read_text())
                observations = torch.randn(20, OBSERVATION_SIZE)
                masks = torch.rand(20, ACTION_COUNT) > .3
                with torch.no_grad():
                    expected = model(observations)[0]
                    choices = model.act(observations, masks, deterministic=True)[0]
                fixture = {"catalog": catalog, "model": model_data,
                           "observations": observations.tolist(), "masks": masks.tolist()}
                code = """
const fs=require('node:fs');global.window={};
eval(fs.readFileSync(process.argv[1],'utf8'));
const f=JSON.parse(fs.readFileSync(0,'utf8')),p=window.CockpitPolicy.create(f.model,f.catalog);
process.stdout.write(JSON.stringify(f.observations.map((o,i)=>({logits:p.logits(o),choice:p.select({observation:o,action_mask:f.masks[i]})}))));
"""
                result = subprocess.run(["node", "-e", code, str(root / "frontend/web/js/ai-policy.js")],
                                        input=json.dumps(fixture), text=True, capture_output=True, check=True)
                actual = json.loads(result.stdout)
                self.assertTrue(torch.allclose(expected, torch.tensor([r["logits"] for r in actual]), atol=1e-6))
                self.assertEqual(choices.tolist(), [r["choice"] for r in actual])
