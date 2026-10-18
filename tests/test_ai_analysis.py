"""Concatenated logs and their notebook plots, including reset counters."""
import ast
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from ai.analysis_data import load_runs


ROOT = Path(__file__).resolve().parents[1]


class AnalysisFixtures:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_run(self, name, counters, **config):
        directory = self.root / "runs" / name
        directory.mkdir(parents=True)
        (directory / "config.json").write_text(json.dumps(config))
        metrics = []
        episodes = []
        for update, steps in counters:
            metrics.append(dict(update=update, total_steps=steps, policy_loss=update,
                                value_loss=2, entropy=1, eval_win_rate=0,
                                train_mean_round=2, eval_mean_round=3,
                                train_mean_tasks_undone=12, eval_mean_tasks_undone=10,
                                train_mean_distance_remaining=4, eval_mean_distance_remaining=3,
                                eval_landing_round_rate=0.1))
            episodes.append(dict(phase="eval", update=update, total_steps=steps, seed="same-seed",
                                 ai_role="both", status="verloren", reason="trudeln", round=3,
                                 steps=25, **{"return": -1}, distance_remaining=3))
        for filename, rows in [("metrics.csv", metrics), ("episodes.csv", episodes)]:
            with (directory / filename).open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        return directory


class AnalysisDataTests(AnalysisFixtures, unittest.TestCase):
    def test_cumulative_resume_counters_are_not_added_twice(self):
        # The first run's config has been rewritten by an in-place resume.
        self.write_run("a", [(1, 10), (2, 20)], resumed_from_steps=10)
        self.write_run("b", [(3, 30), (4, 40)], resumed_from_steps=20)
        runs = load_runs(self.root, ["a", "b"])
        self.assertEqual([r.start_step for r in runs], [0, 20])
        self.assertEqual([row["plot_steps"] for r in runs for row in r.metrics], [10, 20, 30, 40])
        single = load_runs(self.root, "b")[0]
        self.assertEqual((single.start_step, single.end_step), (20, 40))

    def test_reset_counters_and_repeated_episode_ids_stay_separate(self):
        self.write_run("a", [(1, 10), (2, 20)])
        directory = self.write_run("b", [(1, 10), (2, 20)])
        # Repeated CSV writes should still be deduplicated within one run.
        with (directory / "episodes.csv").open("a") as handle:
            handle.write((directory / "episodes.csv").read_text().splitlines()[-1] + "\n")
        runs = load_runs(self.root, ["a", "b"])
        self.assertEqual([row["plot_steps"] for r in runs for row in r.metrics], [10, 20, 30, 40])
        self.assertEqual([len(r.episodes) for r in runs], [2, 2])
        self.assertEqual(runs[1].metrics[0]["total_steps"], "10")
        self.assertEqual(runs[1].episodes[0]["plot_steps"], 30)
        self.assertEqual(runs[1].episodes[0]["run_name"], "b")

    def test_partially_written_and_uncommitted_updates_are_excluded(self):
        directory = self.write_run("live", [(1, 10), (2, 20)])
        with (directory / "metrics.csv").open("a") as handle:
            handle.write("3,30,")
        with (directory / "episodes.csv").open("a") as handle:
            handle.write("eval,3,30,next,both,verloren,trudeln,3,25,-1,3\n")
            handle.write("eval,2,999,wrong-step,both,verloren,trudeln,3,25,-1,3\n")
            handle.write("eval,4,40,partial")
        run = load_runs(self.root, ["live"])[0]
        self.assertEqual(len(run.metrics), 2)
        self.assertEqual(len(run.episodes), 2)

    def test_missing_or_ambiguous_selection_fails_with_run_context(self):
        self.write_run("a", [(1, 10)])
        for selection in ([], ["a", "a"]):
            with self.assertRaisesRegex(ValueError, "RUN_NAMES"):
                load_runs(self.root, selection)
        with self.assertRaisesRegex(RuntimeError, "missing"):
            load_runs(self.root, ["a", "missing"])

    def test_incompatible_airports_and_nonmonotonic_logs_are_rejected(self):
        self.write_run("a", [(1, 10)], airport="MUC")
        self.write_run("b", [(1, 10)], airport="LHR")
        self.write_run("backwards", [(2, 20), (1, 10)])
        with self.assertRaisesRegex(ValueError, "Strecke"):
            load_runs(self.root, ["a", "b"])
        with self.assertRaisesRegex(ValueError, "backwards"):
            load_runs(self.root, ["backwards"])


@unittest.skipUnless(importlib.util.find_spec("matplotlib") and importlib.util.find_spec("numpy"),
                     "Notebook plotting packages are optional")
class AnalysisNotebookTests(AnalysisFixtures, unittest.TestCase):
    def test_all_notebook_plots_respect_run_boundaries_and_latest_validation(self):
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from unittest.mock import patch

        self.addCleanup(plt.close, "all")
        self.write_run("a", [(1, 10), (2, 20)], value_coef=0.5)
        self.write_run("b", [(1, 10), (2, 20)], value_coef=0.25)
        self.write_run("c", [(1, 50)], resumed_from_steps=40, value_coef=0.75)
        report = dict(win_ci_low=0, win_ci_high=0.2, wins=0, games=20, mean_round=3, win_rate=0)
        for name in ("a", "c"):
            directory = self.root / "runs" / name / "evaluations"
            directory.mkdir()
            (directory / "self.json").write_text(json.dumps(report))

        notebook = json.loads((ROOT / "ai/analysis.ipynb").read_text())
        namespace = {}
        with patch.object(plt, "show"):
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                tree = ast.parse("".join(cell["source"]))
                for node in tree.body:
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                        if node.targets[0].id == "ROOT":
                            node.value = ast.parse(f"Path({str(self.root)!r})", mode="eval").body
                        elif node.targets[0].id == "RUN_NAMES":
                            node.value = ast.parse('["a", "b", "c"]', mode="eval").body
                exec(compile(ast.fix_missing_locations(tree), "analysis.ipynb", "exec"), namespace)

        self.assertEqual(namespace["latest_validation_row"]["run_name"], "c")
        self.assertEqual(len(namespace["eval_episodes"]), 1)
        self.assertEqual(namespace["eval_episodes"][0]["run_name"], "c")
        self.assertEqual([name for name, _ in namespace["reports"]], ["a / self", "c / self"])
        self.assertAlmostEqual(namespace["runs"][0].metrics[0]["total_loss"], 1.99)
        self.assertAlmostEqual(namespace["runs"][1].metrics[0]["total_loss"], 1.49)
        self.assertAlmostEqual(namespace["runs"][2].metrics[0]["total_loss"], 2.49)

        figures = [plt.figure(i) for i in plt.get_fignums()]
        self.assertEqual(len(figures), 5)
        for fig_index, fig in enumerate(figures):
            for ax_index, ax in enumerate(fig.axes):
                boundaries = [line for line in ax.lines if line.get_linestyle() == "--"
                              and line.get_color() == "#94a3b8"]
                is_time_axis = fig_index in (0, 2) or (fig_index == 1 and ax_index < 5)
                self.assertEqual([line.get_xdata()[0] for line in boundaries],
                                 [20, 40] if is_time_axis else [])
        policy_lines = figures[0].axes[0].lines
        smoothed = [line for line in policy_lines if line.get_alpha() != 0.2
                    and line.get_linestyle() != "--"]
        self.assertEqual([list(line.get_ydata()) for line in smoothed], [[1, 1.5], [1, 1.5], [1]])


if __name__ == "__main__":
    unittest.main()
