from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from ai.demonstrations import coefficient, load_demonstrations

FIXTURE = (Path(__file__).resolve().parents[1] / "ai/data/demonstrations/"
           "2026-10-18-MUC-605a503f-d565-4450-b62e-a05031efc5fb.json")


class ImportTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text())

    def write(self, root, data, name="sample.json"):
        path = Path(root) / name
        path.write_text(json.dumps(data))
        return path

    def test_actual_win_yields_sixty_valid_role_limited_decisions(self):
        data = load_demonstrations([FIXTURE], "MUC")
        self.assertEqual((data.manifest["sessions"], len(data.actions)), (1, 60))
        self.assertEqual(data.manifest["roles"], {"pilot": 30, "kopilot": 30})
        self.assertEqual(data.manifest["excluded"], {"voided": 1, "non_decision": 7, "incompatible": 0, "non_human": 0})
        self.assertTrue(all(mask[action] for mask, action in zip(data.masks, data.actions)))

    def test_duplicate_single_and_browser_exports_do_not_multiply_the_game(self):
        original = load_demonstrations([FIXTURE], "MUC")
        exported = {**self.data, "format": "flyteam-learning-data", "sessions": [self.data["session"]]}
        del exported["session"]
        with tempfile.TemporaryDirectory() as root:
            self.write(root, self.data)
            self.write(root, exported, "browser.json")
            actual = load_demonstrations([root, FIXTURE], "MUC")
        self.assertEqual(actual.manifest["sha256"], original.manifest["sha256"])
        self.assertEqual(len(actual.actions), 60)

    def test_latest_losing_revision_supersedes_the_old_win(self):
        losing = deepcopy(self.data)
        losing["session"].update(data_revision=71, status="verloren")
        with tempfile.TemporaryDirectory() as root:
            self.write(root, self.data)
            self.write(root, losing, "new.json")
            with self.assertRaisesRegex(ValueError, "Keine gewonnenen"):
                load_demonstrations([root], "MUC")

    def test_conflicting_same_revision_is_rejected(self):
        changed = deepcopy(self.data)
        changed["session"]["events"][0]["decision"]["observation"][8] += 0.1
        with tempfile.TemporaryDirectory() as root:
            self.write(root, self.data)
            self.write(root, changed, "conflict.json")
            with self.assertRaisesRegex(ValueError, "Widersprüchliche"):
                load_demonstrations([root], "MUC")

    def test_bad_schema_mask_observation_and_action_are_rejected(self):
        cases = []
        bad = deepcopy(self.data); bad["schema"]["features"].reverse(); cases.append(bad)
        bad = deepcopy(self.data); bad["action_mask_version"] += 1; cases.append(bad)
        bad = deepcopy(self.data); bad["session"]["events"][0]["decision"]["observation"][0] = float("nan"); cases.append(bad)
        bad = deepcopy(self.data); bad["session"]["events"][0]["decision"]["observation"][0] = True; cases.append(bad)
        bad = deepcopy(self.data)
        first = bad["session"]["events"][0]; first["decision"]["action_mask"][first["action_id"]] = False
        cases.append(bad)
        bad = deepcopy(self.data); bad["session"]["events"][0]["action"]["die"] = 99; cases.append(bad)
        bad = deepcopy(self.data); bad["session"]["consent"]["version"] = "unknown"; cases.append(bad)
        for index, data in enumerate(cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as root:
                path = self.write(root, data)
                with self.assertRaises(ValueError):
                    load_demonstrations([path], "MUC")

    def test_other_routes_feedback_nonconsented_and_nonhuman_actions_are_excluded(self):
        with self.assertRaises(ValueError):
            load_demonstrations([FIXTURE], "TEST")
        for field, value in (("mode", "feedback"), ("consent", None), ("status", "aborted")):
            data = deepcopy(self.data); data["session"][field] = value
            with self.subTest(field=field), tempfile.TemporaryDirectory() as root:
                with self.assertRaises(ValueError):
                    load_demonstrations([self.write(root, data)], "MUC")
        self.data["session"]["events"][0]["actor"] = "ai"
        self.data["session"]["events"][1]["training_compatible"] = False
        with tempfile.TemporaryDirectory() as root:
            data = load_demonstrations([self.write(root, self.data)], "MUC")
        self.assertEqual(len(data.actions), 58)
        self.assertEqual((data.manifest["excluded"]["non_human"], data.manifest["excluded"]["incompatible"]), (1, 1))

    def test_decay_is_relative_to_activation_and_can_be_disabled(self):
        self.assertEqual(coefficient(0.01, 20_000_000, 20_000_000, 100_000), 0.01)
        self.assertAlmostEqual(coefficient(0.01, 20_050_000, 20_000_000, 100_000), 0.005)
        self.assertEqual(coefficient(0.01, 20_100_001, 20_000_000, 100_000), 0)
        self.assertEqual(coefficient(0.01, 100_000, 0, 0), 0.01)


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optional torch dependency missing")
class LearningTests(unittest.TestCase):
    def setUp(self):
        import torch
        torch.set_num_threads(1)
        torch.manual_seed(19)

    def rollout(self, model):
        from ai.environment import CrewEnv
        from ai.train import collect_rollout
        return collect_rollout(model, CrewEnv(), 64, seed=42, episodes_done=0,
                               gamma=0.995, gae_lambda=0.95)[0]

    def test_zero_coefficient_is_bit_identical_to_standard_ppo_including_rng(self):
        import torch
        from ai.nn_model import ActorCritic
        from ai.train import ppo_update
        first = ActorCritic(hidden_size=16)
        second = deepcopy(first)
        batch = self.rollout(first)
        demo = load_demonstrations([FIXTURE], "MUC").tensors()
        torch.manual_seed(88)
        a = ppo_update(first, torch.optim.Adam(first.parameters()), batch, epochs=2, minibatch_size=32)
        rng = torch.get_rng_state()
        torch.manual_seed(88)
        b = ppo_update(second, torch.optim.Adam(second.parameters()), batch, epochs=2, minibatch_size=32,
                       demonstrations=demo, demo_coef=0)
        self.assertEqual(a, b)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        self.assertTrue(all(torch.equal(v, second.state_dict()[k]) for k, v in first.state_dict().items()))

    def test_auxiliary_gradient_improves_demo_likelihood_without_a_critic_target(self):
        import torch
        from ai.nn_model import ActorCritic
        from ai.train import ppo_update
        model = ActorCritic(hidden_size=16)
        batch = self.rollout(model)
        batch["advantages"].zero_()
        demo = load_demonstrations([FIXTURE], "MUC").tensors()
        def nll():
            with torch.no_grad():
                return -model.evaluate_actions(demo["observations"], demo["masks"], demo["actions"])[0].mean().item()
        before = nll()
        critic = deepcopy(model.critic.state_dict())
        stats = ppo_update(model, torch.optim.SGD(model.parameters(), lr=0.05), batch,
                           epochs=1, minibatch_size=len(batch["actions"]), value_coef=0, entropy_coef=0,
                           demonstrations=demo, demo_coef=0.1)
        self.assertGreater(stats["demo_loss"], 0)
        self.assertLess(nll(), before)
        self.assertTrue(all(torch.equal(value, model.critic.state_dict()[key]) for key, value in critic.items()))

    def test_demo_sampling_uses_its_own_rng(self):
        import torch
        from ai.nn_model import ActorCritic
        from ai.train import ppo_update
        model = ActorCritic(hidden_size=16)
        copy = deepcopy(model)
        batch = self.rollout(model)
        demo = load_demonstrations([FIXTURE], "MUC").tensors()
        generator = torch.Generator().manual_seed(2)
        before = generator.get_state()
        torch.manual_seed(33)
        ppo_update(model, torch.optim.Adam(model.parameters()), batch, epochs=1, minibatch_size=32, target_kl=0)
        rng = torch.get_rng_state()
        torch.manual_seed(33)
        ppo_update(copy, torch.optim.Adam(copy.parameters()), batch, epochs=1, minibatch_size=32, target_kl=0,
                   demonstrations=demo, demo_coef=0.01, demo_batch_size=8, demo_generator=generator)
        self.assertTrue(torch.equal(rng, torch.get_rng_state()))
        self.assertFalse(torch.equal(before, generator.get_state()))

    def options(self, folder, extra=()):
        from ai.train import parser
        return parser().parse_args(["--run-dir", str(folder), "--steps", "192", "--rollout-steps", "64",
            "--epochs", "1", "--minibatch-size", "32", "--eval-every", "1", "--eval-games", "1",
            "--hidden-size", "16", *extra])

    def test_split_resume_matches_uninterrupted_demo_training_and_preserves_decay(self):
        import torch
        from ai.checkpoints import load_checkpoint
        from ai.train import train
        class StopAfterSavedUpdate(Exception):
            pass
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()):
            root = Path(root)
            extra = ["--demo-data", str(FIXTURE), "--demo-batch-size", "8", "--demo-decay-steps", "256"]
            train(self.options(root / "full", extra))
            def stop(row, result):
                raise StopAfterSavedUpdate()
            with self.assertRaises(StopAfterSavedUpdate):
                train(self.options(root / "split", extra), on_validation=stop)
            train(self.options(root / "split", ["--resume", str(root / "split/latest.pt")]))
            full, a = load_checkpoint(root / "full/latest.pt")
            split, b = load_checkpoint(root / "split/latest.pt")
            self.assertTrue(all(torch.equal(value, split.state_dict()[key]) for key, value in full.state_dict().items()))
            self.assertTrue(torch.equal(a["demo_rng_state"], b["demo_rng_state"]))
            self.assertTrue(torch.equal(a["torch_rng_state"], b["torch_rng_state"]))
            self.assertEqual(a["train_config"]["demo_start_step"], b["train_config"]["demo_start_step"])
            self.assertFalse(b["train_config"]["demo_changed_on_resume"])

    def test_changing_demo_weight_or_data_needs_a_new_run_directory(self):
        from ai.train import train
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            root = Path(root)
            source = root / "data.json"
            original = json.loads(FIXTURE.read_text())
            source.write_text(json.dumps(original))
            run = root / "run"
            train(self.options(run, ["--demo-data", str(source)]))
            checkpoint = run / "latest.pt"
            digest = hashlib.sha256(checkpoint.read_bytes()).digest()
            with self.assertRaises(SystemExit):
                train(self.options(run, ["--resume", str(checkpoint), "--demo-coef", "0.02"]))
            original["session"]["events"][0]["decision"]["observation"][8] += 0.1
            source.write_text(json.dumps(original))
            with self.assertRaises(SystemExit):
                train(self.options(run, ["--resume", str(checkpoint)]))
            self.assertEqual(hashlib.sha256(checkpoint.read_bytes()).digest(), digest)

    def test_enabling_from_normal_run_defaults_to_small_weight_and_disabling_needs_no_data(self):
        from ai.checkpoints import load_checkpoint
        from ai.train import train
        with tempfile.TemporaryDirectory() as root, redirect_stdout(io.StringIO()):
            root = Path(root)
            train(self.options(root / "off"))
            _, base = load_checkpoint(root / "off/latest.pt")
            source = root / "data.json"
            source.write_bytes(FIXTURE.read_bytes())
            train(self.options(root / "on", ["--resume", str(root / "off/latest.pt"),
                "--steps", str(base["total_steps"] + 64), "--demo-data", str(source)]))
            _, active = load_checkpoint(root / "on/latest.pt")
            self.assertEqual(active["train_config"]["demo_coef"], 0.01)
            self.assertEqual(active["train_config"]["demo_start_step"], base["total_steps"])
            source.unlink()
            train(self.options(root / "disabled", ["--resume", str(root / "on/latest.pt"),
                "--steps", str(active["total_steps"] + 64), "--demo-coef", "0"]))
            _, off = load_checkpoint(root / "disabled/latest.pt")
            self.assertIsNone(off["train_config"]["demo_manifest"])
            self.assertEqual(off["train_config"]["demo_data"], [])


if __name__ == "__main__":
    unittest.main()
