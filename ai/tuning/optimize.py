"""Sequential, persistent PPO experiments: python -m ai.tuning.optimize --help."""
import argparse
from contextlib import redirect_stdout
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

try:
    import optuna
except ImportError as error:
    raise SystemExit("Optuna fehlt. Installieren mit: python -m pip install -r ai/requirements-tuning.txt") from error
import torch

from ..actions import ACTION_MASK_VERSION
from ..environment import CrewEnv
from ..nn_model import ActorCritic
from ..train import parser as training_parser, train
from .scoring import OBJECTIVE_VERSION, evaluation_score
from .search_space import ARCHITECTURES, ENTROPY_RANGE, LR_RANGE, initial_trials, sample_parameters

ROOT = Path(__file__).resolve().parents[2]


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def source_fingerprint(airport):
    paths = [*ROOT.glob("backend/*.py"), ROOT / "backend/landungen" / f"{airport}.yaml"]
    paths += [ROOT / "ai" / name for name in ("train.py", "nn_model.py", "environment.py", "actions.py",
              "observation.py", "public_rules.py", "agents.py", "evaluate.py", "checkpoints.py")]
    paths += list((ROOT / "ai/tuning").glob("*.py"))
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--study-dir", type=Path, default=Path("runs/optuna/muc-architecture"))
    result.add_argument("--mode", choices=("architecture", "search"), default="architecture")
    result.add_argument("--trials", type=int, default=2, help="TOTAL attempted trials, including completed/pruned/failed ones; repeat with a larger target to extend.")
    result.add_argument("--steps", type=int, default=3_000_000, help="Same decision budget per trial; whole games may overshoot slightly.")
    result.add_argument("--eval-steps", type=int, default=100_000)
    result.add_argument("--eval-games", type=int, default=100)
    result.add_argument("--eval-seed", type=int, default=1_000_000)
    result.add_argument("--seed", type=int, default=42, help="Same training seed across candidates; confirm winners on new seeds.")
    result.add_argument("--sampler-seed", type=int, default=2026)
    result.add_argument("--airport", default="MUC")
    result.add_argument("--device", default="cpu")
    result.add_argument("--threads", type=int, default=1)
    result.add_argument("--rollout-steps", type=int, default=2048)
    result.add_argument("--epochs", type=int, default=4)
    result.add_argument("--minibatch-size", type=int, default=256)
    result.add_argument("--max-steps", type=int, default=256)
    # Match muc5 by default, rather than silently inheriting future train defaults.
    result.add_argument("--round-reward", type=float, default=0.0)
    result.add_argument("--sync-weight", type=float, default=0.05)
    result.add_argument("--sync-tolerance", type=float, default=1.0)
    result.add_argument("--task-weight", type=float, default=0.01)
    result.add_argument("--uniform-mix", type=float, default=0.03)
    result.add_argument("--pruner", choices=("none", "median"), default="none", help="Opt-in for search mode; architecture comparisons always run the full budget.")
    result.add_argument("--prune-warmup-steps", type=int, default=1_000_000)
    return result


def experiment_config(args):
    base = vars(training_parser().parse_args([])).copy()
    for name in ("airport", "steps", "eval_steps", "eval_games", "eval_seed", "seed", "device", "threads",
                 "rollout_steps", "epochs", "minibatch_size", "max_steps", "round_reward", "sync_weight",
                 "sync_tolerance", "task_weight", "uniform_mix"):
        base[name] = getattr(args, name)
    base.pop("run_dir")
    base.pop("resume")
    if not 0 <= args.uniform_mix <= 1:
        raise ValueError("--uniform-mix muss zwischen 0 und 1 liegen.")
    env = CrewEnv(args.airport, args.round_reward, args.max_steps, sync_weight=args.sync_weight,
                  sync_tolerance=args.sync_tolerance, task_weight=args.task_weight)
    env.reset(seed=args.seed)
    return {"format_version": 1, "objective_version": OBJECTIVE_VERSION, "mode": args.mode,
            "training": base, "architectures": ARCHITECTURES, "lr_range": list(LR_RANGE),
            "entropy_range": list(ENTROPY_RANGE), "action_mask_version": ACTION_MASK_VERSION,
            "initial_distance": env.game.landung.entfernung, "initial_tasks": sum(env.unfinished_tasks().values()),
            "pruner": args.pruner, "prune_warmup_steps": args.prune_warmup_steps,
            "sampler_seed": args.sampler_seed, "source_sha256": source_fingerprint(args.airport),
            "torch_version": str(torch.__version__), "optuna_version": optuna.__version__}


def open_study(directory):
    directory = Path(directory).resolve()
    return optuna.load_study(study_name=directory.name, storage=f"sqlite:///{directory / 'study.sqlite3'}")


def export_results(study, directory):
    fields = ["trial", "state", "objective", "architecture", "lr", "entropy_coef", "wins", "games", "win_rate",
              "progress", "mean_round", "mean_distance_remaining", "mean_tasks_undone", "landing_round_rate",
              "parameters", "elapsed_seconds", "steps_per_second", "run_dir"]
    with (directory / "trials.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for trial in study.trials:
            summary = trial.user_attrs.get("validation", {})
            selected = trial.user_attrs.get("train_parameters", {})
            writer.writerow({"trial": trial.number, "state": trial.state.name, "objective": trial.value,
                             "architecture": trial.params.get("architecture"),
                             "lr": selected.get("lr"), "entropy_coef": selected.get("entropy_coef"),
                             **{key: summary.get(key) for key in fields[6:14]},
                             **{key: trial.user_attrs.get(key) for key in fields[14:]}})
    complete = study.get_trials(states=(optuna.trial.TrialState.COMPLETE,))
    if complete:
        best = study.best_trial
        write_json(directory / "best.json", {"trial": best.number, "objective": best.value,
                   "architecture": best.params["architecture"], "checkpoint": str(Path(best.user_attrs["run_dir"]) / "latest.pt"),
                   "train_config": {**study.user_attrs["experiment"]["training"], **best.user_attrs["train_parameters"]},
                   "validation": best.user_attrs["validation"]})


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, value):
        for stream in self.streams:
            stream.write(value)
        return len(value)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def objective(trial, config, directory):
    parameters = sample_parameters(trial, config["mode"])
    run_dir = directory / f"trial-{trial.number:04d}"
    run_dir.mkdir(parents=True, exist_ok=False)
    trial.set_user_attr("run_dir", str(run_dir))
    trial.set_user_attr("train_parameters", parameters)
    # Constructing a model consumes RNG; train() resets it before initialization.
    torch.set_num_threads(config["training"]["threads"])
    parameter_count = sum(p.numel() for p in ActorCritic(hidden_size=parameters["hidden_size"], hidden_layers=parameters["hidden_layers"]).parameters())
    trial.set_user_attr("parameters", parameter_count)
    args = argparse.Namespace(**{**config["training"], **parameters}, run_dir=run_dir, resume=None)
    latest_score = None
    start = time.monotonic()

    def report(row, result):
        nonlocal latest_score
        scored = evaluation_score(result, initial_distance=config["initial_distance"], initial_tasks=config["initial_tasks"])
        latest_score = scored["objective"]
        summary = {**{k: v for k, v in result.items() if k != "episodes"}, **scored,
                   "total_steps": row["total_steps"]}
        elapsed = time.monotonic() - start
        trial.set_user_attr("validation", summary)
        trial.set_user_attr("elapsed_seconds", elapsed)
        trial.set_user_attr("steps_per_second", row["total_steps"] / max(elapsed, 1e-6))
        # Report shared decision milestones, not slightly different episode ends.
        milestone = (args.steps if row["total_steps"] >= args.steps
                     else row["total_steps"] // args.eval_steps * args.eval_steps)
        with (run_dir / "progress.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"milestone": milestone, **summary}, allow_nan=False) + "\n")
        write_json(run_dir / "validation.json", {**result, **scored})
        trial.report(latest_score, step=milestone)
        print(f"Trial {trial.number}: {scored['wins']}/{scored['games']} Siege, Fortschritt {scored['progress']:.3f}, Score {latest_score:.4f}", flush=True)
        if row["total_steps"] < args.steps and trial.should_prune():
            raise optuna.TrialPruned(f"Nach {row['total_steps']} Entscheidungen; Checkpoint: {run_dir / 'latest.pt'}")

    print(f"\nTrial {trial.number}: {trial.params}; {parameter_count:,} Parameter → {run_dir}", flush=True)
    with (run_dir / "training.log").open("w", encoding="utf-8") as handle, redirect_stdout(Tee(sys.stdout, handle)):
        train(args, on_validation=report)
    if latest_score is None:
        raise RuntimeError("Der Versuch endete ohne Validierung.")
    return latest_score  # Fixed-budget final policy, not the luckiest intermediate checkpoint.


def run(args):
    arg_parser = parser()
    for name in ("trials", "steps", "eval_steps", "eval_games", "threads", "rollout_steps", "epochs", "minibatch_size", "max_steps"):
        if getattr(args, name) < 1:
            arg_parser.error(f"--{name.replace('_', '-')} muss positiv sein.")
    if args.prune_warmup_steps < 0:
        arg_parser.error("--prune-warmup-steps muss nichtnegativ sein.")
    if args.mode == "architecture" and (args.trials > len(ARCHITECTURES) or args.pruner != "none"):
        arg_parser.error(f"Architekturvergleich: höchstens {len(ARCHITECTURES)} Versuche und --pruner none. Weitere Trainings-Seeds über ai.tuning.retrain prüfen.")
    config = experiment_config(args)
    if config["initial_distance"] <= 0 or config["initial_tasks"] <= 0:
        arg_parser.error("Die Strecke braucht positive Anfangsentfernung und Aufgabenanzahl.")
    directory = args.study_dir.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    pruner = (optuna.pruners.MedianPruner(n_startup_trials=4, n_warmup_steps=args.prune_warmup_steps, n_min_trials=3)
              if args.pruner == "median" else optuna.pruners.NopPruner())
    study = optuna.create_study(study_name=directory.name, storage=f"sqlite:///{directory / 'study.sqlite3'}",
                                direction="maximize", load_if_exists=True, pruner=pruner)
    previous = study.user_attrs.get("experiment")
    if previous is not None and previous != config:
        arg_parser.error("Studienkonfiguration oder Trainingscode geändert. Gleiche Argumente verwenden oder neues --study-dir wählen.")
    if previous is None:
        if study.trials:
            arg_parser.error("Bestehende Studie ohne passende Experiment-Metadaten. Neues --study-dir verwenden.")
        study.set_user_attr("experiment", config)
    write_json(directory / "study-config.json", config)
    # No threaded trials: both the engine and torch use process-global RNGs.
    study.sampler = optuna.samplers.TPESampler(seed=args.sampler_seed + len(study.trials))
    for parameters in initial_trials(args.mode):
        study.enqueue_trial(parameters, skip_if_exists=True)
    attempted = sum(trial.state != optuna.trial.TrialState.WAITING for trial in study.trials)
    remaining = max(0, args.trials - attempted)
    print(f"Studie {directory.name}: {remaining} weitere Versuche, je {args.steps:,} Entscheidungen. Ranking: letzte Validierung.", flush=True)
    try:
        if remaining:
            study.optimize(lambda trial: objective(trial, config, directory), n_trials=remaining, n_jobs=1,
                           callbacks=[lambda current, _: export_results(current, directory)], gc_after_trial=True)
    except KeyboardInterrupt:
        print("Studie unterbrochen. Bereits abgeschlossene Versuche bleiben erhalten; der angefangene Versuch zählt als FAIL.", flush=True)
    finally:
        export_results(study, directory)
    if study.get_trials(states=(optuna.trial.TrialState.COMPLETE,)):
        print(f"Beste vollständige Konfiguration: Trial {study.best_trial.number}; Details in {directory / 'best.json'}", flush=True)
    return study


def main():
    run(parser().parse_args())


if __name__ == "__main__":
    main()
