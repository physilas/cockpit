"""Confirm a selected configuration with independent fresh training seeds."""
import argparse
from contextlib import redirect_stdout
import json
from pathlib import Path

from .optimize import Tee, open_study, source_fingerprint, write_json
from .scoring import evaluation_score
from ..train import train


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-dir", type=Path, required=True)
    parser.add_argument("--trial", type=int, default=None, help="Default: best COMPLETE trial; use this to confirm the baseline too.")
    parser.add_argument("--seeds", type=int, nargs="+", default=[101, 102, 103])
    args = parser.parse_args()
    study = open_study(args.study_dir)
    trial = study.best_trial if args.trial is None else next((t for t in study.trials if t.number == args.trial), None)
    if trial is None or trial.state.name != "COMPLETE":
        parser.error("Bitte einen vollständig abgeschlossenen Versuch wählen.")
    config = study.user_attrs["experiment"]
    if config["source_sha256"] != source_fingerprint(config["training"]["airport"]):
        parser.error("Der Trainingscode hat sich seit der Studie geändert. Eine neue Studie anlegen.")
    if len(set(args.seeds)) != len(args.seeds) or config["training"]["seed"] in args.seeds:
        parser.error("Unterschiedliche neue Seeds verwenden; den Such-Seed nicht wiederholen.")
    directory = args.study_dir.resolve() / "confirmation" / f"trial-{trial.number:04d}"
    directory.mkdir(parents=True, exist_ok=True)
    import sys
    for seed in args.seeds:
        run_dir = directory / f"seed-{seed}"
        checkpoint = run_dir / "latest.pt"
        # Same full budget and validation games; only the training seed changes.
        training = {**config["training"], **trial.user_attrs["train_parameters"], "seed": seed}
        run_dir.mkdir(parents=True, exist_ok=True)
        manifest = run_dir / "confirmation-config.json"
        if manifest.exists() and json.loads(manifest.read_text(encoding="utf-8")) != training:
            parser.error(f"Andere Konfiguration in {run_dir}.")
        write_json(manifest, training)

        def report(row, result):
            score = evaluation_score(result, initial_distance=config["initial_distance"], initial_tasks=config["initial_tasks"])
            write_json(run_dir / "validation.json", {**result, **score, "total_steps": row["total_steps"], "seed": seed})

        options = argparse.Namespace(**training, run_dir=run_dir, resume=checkpoint if checkpoint.exists() else None)
        print(f"Bestätigung von Trial {trial.number}, Trainings-Seed {seed} → {run_dir}", flush=True)
        try:
            with (run_dir / "training.log").open("a", encoding="utf-8") as handle, redirect_stdout(Tee(sys.stdout, handle)):
                train(options, on_validation=report)
        except KeyboardInterrupt:
            print("Unterbrochen. Derselbe Befehl setzt die Bestätigung am letzten gespeicherten Update fort.", flush=True)
            return
    summaries = []
    for path in sorted(directory.glob("seed-*/validation.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        if result["total_steps"] >= config["training"]["steps"]:
            summaries.append({k: v for k, v in result.items() if k != "episodes"})
    write_json(directory / "summary.json", {"trial": trial.number, "training_seeds": summaries,
               "note": "Independent training runs on the same validation games. Use separate test seeds only after selection."})


if __name__ == "__main__":
    main()
