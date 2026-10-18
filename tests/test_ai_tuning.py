"""Capacity/checkpoint compatibility and real, tiny Optuna study integration."""
from contextlib import redirect_stderr, redirect_stdout
import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from ai.tuning.scoring import evaluation_score


class ObjectiveTests(unittest.TestCase):
    def score(self, *records):
        return evaluation_score({"games": len(records), "episodes": records}, initial_distance=6, initial_tasks=17)

    def test_one_win_dominates_all_progress_and_stationary_preparations_give_none(self):
        stationary = {"status": "verloren", "distance_remaining": 6, "tasks_undone": 0}
        near_win = {**stationary, "distance_remaining": 0}
        won = {**near_win, "status": "gewonnen"}
        self.assertEqual(self.score(stationary)["objective"], 0)
        self.assertGreater(self.score(won, stationary)["objective"], self.score(near_win, near_win)["objective"])
        self.assertEqual(self.score(near_win)["wins"], 0)

    def test_progress_requires_both_navigation_and_preparations_and_excludes_truncations(self):
        halfway = {"status": "verloren", "distance_remaining": 3, "tasks_undone": 8.5}
        self.assertAlmostEqual(self.score(halfway)["progress"], 0.25)
        self.assertEqual(self.score({**halfway, "tasks_undone": 17})["progress"], 0)
        self.assertEqual(self.score({**halfway, "status": "truncated"})["progress"], 0)
        self.assertEqual(self.score({**halfway, "distance_remaining": -1, "tasks_undone": -1})["progress"], 1)


@unittest.skipUnless(importlib.util.find_spec("torch"), "Optionale PyTorch-Pakete fehlen")
class ArchitectureTests(unittest.TestCase):
    def test_deeper_checkpoint_roundtrip_and_legacy_two_layer_weights(self):
        import torch
        from ai.checkpoints import load_checkpoint, save_checkpoint
        from ai.nn_model import ActorCritic
        torch.set_num_threads(1)
        x = torch.randn(4, 349)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.pt"
            for depth in (2, 3):
                model = ActorCritic(hidden_size=32, hidden_layers=depth)
                save_checkpoint(path, model)
                if depth == 2:
                    payload = torch.load(path, weights_only=True)
                    payload["model_config"].pop("hidden_layers")
                    torch.save(payload, path)
                loaded, _ = load_checkpoint(path)
                torch.testing.assert_close(loaded(x)[0], model(x)[0], rtol=0, atol=0)
                self.assertEqual(loaded.config["hidden_layers"], depth)
        with self.assertRaises(ValueError):
            ActorCritic(hidden_layers=0)


@unittest.skipUnless(importlib.util.find_spec("torch") and importlib.util.find_spec("optuna"),
                     "Optionale Tuning-Pakete fehlen: pip install -r ai/requirements-tuning.txt")
class StudyTests(unittest.TestCase):
    def options(self, directory, *extra):
        from ai.tuning.optimize import parser
        return parser().parse_args(["--study-dir", str(directory), "--steps", "64", "--eval-steps", "32",
            "--eval-games", "2", "--rollout-steps", "16", "--epochs", "1", "--minibatch-size", "16",
            "--max-steps", "16", *extra])

    def test_real_trials_exports_idempotent_resume_and_config_guard(self):
        from ai.checkpoints import load_checkpoint
        from ai.tuning.optimize import run
        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            study = run(self.options(root, "--steps", "70"))
            complete = [t for t in study.trials if t.state.name == "COMPLETE"]
            self.assertEqual(len(complete), 2)
            self.assertEqual([t.params["architecture"] for t in complete], ["2x128", "2x256"])
            for trial in complete:
                _, payload = load_checkpoint(root / f"trial-{trial.number:04d}" / "latest.pt")
                self.assertGreaterEqual(payload["total_steps"], 70)
                self.assertEqual(payload["train_config"]["task_weight"], 0.01)
                self.assertIn(70, trial.intermediate_values)
            best = json.loads((root / "best.json").read_text())
            self.assertTrue(Path(best["checkpoint"]).exists())
            with (root / "trials.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([int(r["parameters"]) for r in rows if r["state"] == "COMPLETE"], [77050, 186746])
            repeated = run(self.options(root, "--steps", "70"))
            self.assertEqual(sum(t.state.name == "COMPLETE" for t in repeated.trials), 2)
            with self.assertRaises(SystemExit), redirect_stderr(io.StringIO()):
                run(self.options(root, "--steps", "70", "--task-weight", "0.02"))

    def test_pruned_trial_has_committed_checkpoint_and_no_winner(self):
        import optuna
        from ai.checkpoints import load_checkpoint
        from ai.tuning.optimize import experiment_config, export_results, objective

        class AlwaysPrune(optuna.pruners.BasePruner):
            def prune(self, study, trial):
                return True

        with tempfile.TemporaryDirectory() as directory, redirect_stdout(io.StringIO()):
            root = Path(directory)
            study = optuna.create_study(direction="maximize", pruner=AlwaysPrune())
            config = experiment_config(self.options(root))
            study.set_user_attr("experiment", config)
            study.enqueue_trial({"architecture": "2x128"})
            study.optimize(lambda trial: objective(trial, config, root), n_trials=1)
            self.assertEqual(study.trials[0].state.name, "PRUNED")
            _, checkpoint = load_checkpoint(root / "trial-0000/latest.pt")
            self.assertLess(checkpoint["total_steps"], 64)
            self.assertGreaterEqual(checkpoint["total_steps"], 32)
            with (root / "trial-0000/metrics.csv").open() as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(int(rows[-1]["total_steps"]), checkpoint["total_steps"])
            export_results(study, root)
            self.assertFalse((root / "best.json").exists())


if __name__ == "__main__":
    unittest.main()
