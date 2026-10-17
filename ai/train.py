"""PPO self-play: one shared model controls both roles with separate observations.

Run from the repository root: python -m ai.train --run-dir runs/muc
No gradients pass through the game. Rollouts and their masks stay fixed during
each PPO update. Rewards and advantages are cooperative: never flip their sign
when the active role changes.
"""
import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean
import time

import torch
from torch import nn

from .checkpoints import load_checkpoint, save_checkpoint
from .environment import CrewEnv
from .evaluate import PERFORMANCE_METRICS, evaluate, summarize_episodes
from .agents import ModelAgent
from .nn_model import ActorCritic


METRIC_FIELDS = ["update", "total_steps", "episodes", "elapsed_seconds", "steps_per_second", "learning_rate",
                 "policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "explained_variance",
                 "grad_norm", "train_win_rate", "train_mean_round", "train_mean_return", "train_truncated_rate",
                 "eval_win_rate", "eval_win_ci_low", "eval_win_ci_high", "eval_mean_round", "eval_mean_return"]
METRIC_FIELDS += [f"{phase}_{name}" for phase in ("train", "eval") for name in PERFORMANCE_METRICS
                  if f"{phase}_{name}" not in METRIC_FIELDS]
EPISODE_FIELDS = ["phase", "update", "total_steps", "seed", "ai_role", "status", "reason", "round", "steps", "return"]
EPISODE_FIELDS += ["outcome_return", "round_return", "sync_return", "distance_remaining", "height_remaining",
                   "airport_reached", "landing_round_started", "sync_error", "gear_count", "flap_count", "brake_strength", "planes_remaining"]
BEST_SCORE_VERSION = 2


def reward_config(args, previous=None):
    """Explicit CLI values override saved rewards; omitted values preserve them.

    Missing keys in old checkpoints mean the original unshaped environment.
    Fresh training defaults to synchronization shaping without a round bonus.
    """
    defaults = {"round_reward": 0.0, "sync_weight": 0.05, "sync_tolerance": 1.0}
    if previous is not None:
        defaults = {"round_reward": previous.get("round_reward", 0.02),
                    "sync_weight": previous.get("sync_weight", 0.0),
                    "sync_tolerance": previous.get("sync_tolerance", 1.0)}
    return {key: getattr(args, key) if getattr(args, key) is not None else value for key, value in defaults.items()}


def validation_score(result):
    # Survival alone must not make a stationary policy the "best" checkpoint.
    return (result["win_rate"], result["landing_round_rate"], result["airport_reached_rate"],
            -result["mean_distance_remaining"], result["mean_round"])


def compute_gae(rewards, values, bootstrap=0.0, gamma=0.995, gae_lambda=0.95):
    """One complete cooperative episode; bootstrap only on time-limit truncation."""
    advantages = [0.0] * len(rewards)
    advantage, next_value = 0.0, bootstrap
    for i in reversed(range(len(rewards))):
        delta = rewards[i] + gamma * next_value - values[i]
        advantage = delta + gamma * gae_lambda * advantage
        advantages[i] = advantage
        next_value = values[i]
    return advantages, [a + v for a, v in zip(advantages, values)]


def collect_rollout(model, env, minimum_steps, *, seed, episodes_done, gamma, gae_lambda):
    device = next(model.parameters()).device
    data = {name: [] for name in ("observations", "masks", "actions", "log_probs", "values", "advantages", "returns")}
    records = []
    model.eval()
    while len(data["actions"]) < minimum_steps:
        # String namespaces keep training seeds disjoint from integer validation/test seeds.
        episode_seed = f"train:{seed}:{episodes_done + len(records)}"
        observation, info = env.reset(seed=episode_seed)
        rewards, values = [], []
        while not env.done:
            mask = info["action_mask"]
            with torch.no_grad():
                action, log_prob, value = model.act(torch.tensor(observation, dtype=torch.float32, device=device), mask)
            data["observations"].append(observation)
            data["masks"].append(mask)
            data["actions"].append(int(action.item()))
            data["log_probs"].append(float(log_prob.item()))
            data["values"].append(float(value.item()))
            values.append(float(value.item()))
            observation, reward, terminated, truncated, info = env.step(int(action.item()))
            rewards.append(reward)
        bootstrap = 0.0
        if truncated and not terminated:
            with torch.no_grad():
                _, final_value = model(torch.tensor(observation, dtype=torch.float32, device=device))
            bootstrap = float(final_value.item())
        advantages, returns = compute_gae(rewards, values, bootstrap, gamma, gae_lambda)
        data["advantages"].extend(advantages)
        data["returns"].extend(returns)
        records.append(env.episode_record(episode_seed, "both", sum(rewards)))
    tensors = {name: torch.tensor(items, dtype=torch.bool if name == "masks" else torch.long if name == "actions" else torch.float32,
                                  device=device) for name, items in data.items()}
    return tensors, records


def ppo_update(model, optimizer, batch, *, epochs=4, minibatch_size=256, clip=0.2,
               value_coef=0.5, entropy_coef=0.01, max_grad_norm=0.5, target_kl=0.03):
    model.train()
    advantages = batch["advantages"]
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    count = len(advantages)
    metrics = {name: [] for name in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "grad_norm")}
    for _ in range(epochs):
        permutation = torch.randperm(count, device=advantages.device)
        epoch_kls = []
        for indices in permutation.split(minibatch_size):
            log_prob, entropy, value = model.evaluate_actions(batch["observations"][indices], batch["masks"][indices], batch["actions"][indices])
            log_ratio = log_prob - batch["log_probs"][indices]
            ratio = log_ratio.exp()
            objective = torch.minimum(ratio * advantages[indices], ratio.clamp(1 - clip, 1 + clip) * advantages[indices])
            policy_loss = -objective.mean()
            value_loss = 0.5 * (value - batch["returns"][indices]).square().mean()
            entropy_mean = entropy.mean()
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy_mean
            if not bool(torch.isfinite(loss)):
                raise RuntimeError("Nicht-endliche PPO-Loss; Training wurde angehalten.")
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            grad_norm = nn.utils.clip_grad_norm_(model.parameters(), max_grad_norm, error_if_nonfinite=True)
            optimizer.step()
            with torch.no_grad():
                kl = ((ratio - 1) - log_ratio).mean().item()
                clipped = ((ratio - 1).abs() > clip).float().mean().item()
            for name, value_ in (("policy_loss", policy_loss.item()), ("value_loss", value_loss.item()),
                                  ("entropy", entropy_mean.item()), ("approx_kl", kl),
                                  ("clip_fraction", clipped), ("grad_norm", float(grad_norm))):
                metrics[name].append(value_)
            epoch_kls.append(kl)
        if target_kl > 0 and mean(epoch_kls) > target_kl:
            break
    variance = batch["returns"].var(unbiased=False)
    explained = (1 - (batch["returns"] - batch["values"]).var(unbiased=False) / variance).item() if variance.item() > 1e-8 else float("nan")
    return {**{name: mean(values) for name, values in metrics.items()}, "explained_variance": explained}


def append_rows(path, fields, rows):
    exists = path.exists() and path.stat().st_size > 0
    if exists:
        with path.open(newline="", encoding="utf-8") as handle:
            existing_fields = next(csv.reader(handle))
        if existing_fields != fields:
            if not set(existing_fields).issubset(fields):
                raise ValueError(f"Unbekanntes CSV-Format in {path}; bitte ein neues Laufverzeichnis verwenden.")
            # Upgrade old logs atomically; unknown historical metrics stay blank.
            temporary = path.with_suffix(path.suffix + ".tmp")
            with path.open(newline="", encoding="utf-8") as source, temporary.open("w", newline="", encoding="utf-8") as target:
                writer = csv.DictWriter(target, fieldnames=fields)
                writer.writeheader()
                writer.writerows(csv.DictReader(source))
            temporary.replace(path)
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--airport", default="MUC")
    result.add_argument("--run-dir", type=Path, default=Path("runs/muc"))
    result.add_argument("--steps", type=int, default=200_000, help="Target TOTAL decisions, including a resumed checkpoint; whole episodes may overshoot slightly.")
    result.add_argument("--rollout-steps", type=int, default=2048)
    result.add_argument("--epochs", type=int, default=4)
    result.add_argument("--minibatch-size", type=int, default=256)
    result.add_argument("--hidden-size", type=int, default=128)
    result.add_argument("--lr", type=float, default=3e-4)
    result.add_argument("--gamma", type=float, default=0.995)
    result.add_argument("--gae-lambda", type=float, default=0.95)
    result.add_argument("--clip", type=float, default=0.2)
    result.add_argument("--value-coef", type=float, default=0.5)
    result.add_argument("--entropy-coef", type=float, default=0.01)
    result.add_argument("--round-reward", type=float, default=None, help="Frischer Lauf: 0; beim Fortsetzen gespeicherter Wert, sofern nicht ausdrücklich angegeben.")
    result.add_argument("--sync-weight", type=float, default=None, help="Strafe pro Feld Rückstand nach Toleranz: frisch 0.05; 0 schaltet sie ab; Resume übernimmt sonst den Checkpoint-Wert.")
    result.add_argument("--sync-tolerance", type=float, default=None, help="Tolerierter Rückstand in Feldern, frisch 1; beim Fortsetzen sonst Checkpoint-Wert.")
    result.add_argument("--max-steps", type=int, default=256)
    result.add_argument("--eval-every", type=int, default=5)
    result.add_argument("--eval-games", type=int, default=100)
    result.add_argument("--eval-seed", type=int, default=1_000_000)
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--device", default="cpu", help="cpu, cuda or mps; CPU is usually useful for this small sequential model.")
    result.add_argument("--threads", type=int, default=1)
    result.add_argument("--resume", type=Path)
    return result


def main():
    arg_parser = parser()
    args = arg_parser.parse_args()
    for name in ("steps", "rollout_steps", "epochs", "minibatch_size", "hidden_size", "eval_every", "eval_games", "threads", "max_steps"):
        if getattr(args, name) < 1:
            arg_parser.error(f"--{name.replace('_', '-')} muss positiv sein.")
    if not 0 < args.gamma <= 1 or not 0 <= args.gae_lambda <= 1 or args.lr <= 0 or not 0 < args.clip < 1:
        arg_parser.error("Ungültige Lernrate, Discount-, GAE- oder Clip-Einstellung.")
    torch.set_num_threads(args.threads)
    torch.manual_seed(args.seed)
    total_steps = episodes = update = 0
    best_score = (-1.0,) * 5
    payload = None
    if args.resume:
        model, payload = load_checkpoint(args.resume, args.device)
        for name in ("airport", "max_steps", "gamma", "gae_lambda", "seed", "hidden_size"):
            setattr(args, name, payload["train_config"][name])
        total_steps, episodes, update = payload["total_steps"], payload["episodes"], payload["update"]
        if payload.get("best_score_version") == BEST_SCORE_VERSION:
            best_score = tuple(payload["best_score"])
        if any(payload["train_config"].get(key) != getattr(args, key) for key in ("eval_seed", "eval_games")):
            best_score = (-1.0,) * 5
    else:
        model = ActorCritic(hidden_size=args.hidden_size).to(args.device)
    previous_config = payload["train_config"] if payload else None
    effective_rewards = reward_config(args, previous_config)
    reward_changed = payload is not None and effective_rewards != {
        "round_reward": previous_config.get("round_reward", 0.02),
        "sync_weight": previous_config.get("sync_weight", 0.0),
        "sync_tolerance": previous_config.get("sync_tolerance", 1.0)}
    if reward_changed:
        if args.run_dir.resolve() == args.resume.resolve().parent:
            arg_parser.error("Geänderte Rewards brauchen ein neues --run-dir, damit die Lernkurven vergleichbar bleiben.")
        best_score = (-1.0,) * 5
    for key, value in effective_rewards.items():
        setattr(args, key, value)
    if any(not math.isfinite(v) or v < 0 for v in effective_rewards.values()) or args.round_reward > 0.1:
        arg_parser.error("Reward-Gewichte/Toleranz müssen endlich und nichtnegativ sein; --round-reward maximal 0.1.")
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, eps=1e-5)
    if payload:
        optimizer.load_state_dict(payload["optimizer_state"])
        args.lr = optimizer.param_groups[0]["lr"]
        torch.set_rng_state(payload["torch_rng_state"].cpu())
        if str(args.device).startswith("cuda") and "cuda_rng_state" in payload:
            torch.cuda.set_rng_state_all([s.cpu() for s in payload["cuda_rng_state"]])
        if str(args.device) == "mps" and "mps_rng_state" in payload:
            torch.mps.set_rng_state(payload["mps_rng_state"].cpu())
    env = CrewEnv(args.airport, args.round_reward, args.max_steps, sync_weight=args.sync_weight, sync_tolerance=args.sync_tolerance)
    env.reset(seed=args.seed)  # Validate the scenario before creating output files.
    args.run_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = args.run_dir / "metrics.csv"
    if metrics_path.exists():
        if not args.resume:
            arg_parser.error("Dieser Lauf enthält bereits Metriken. Nutze --resume oder ein neues --run-dir.")
        with metrics_path.open(encoding="utf-8", newline="") as handle:
            old_metrics = list(csv.DictReader(handle))
        if old_metrics and int(old_metrics[-1]["total_steps"]) != total_steps:
            arg_parser.error("Checkpoint und Log-Ende passen nicht zusammen. Für diesen Checkpoint ein neues --run-dir verwenden.")
    config = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    config.update({"resumed_from_steps": total_steps, "reward_changed_on_resume": reward_changed})
    (args.run_dir / "config.json").write_text(json.dumps({**config, "torch_version": str(torch.__version__)}, indent=2), encoding="utf-8")
    start, starting_steps = time.monotonic(), total_steps

    def save(name):
        device_rng = {}
        if str(args.device).startswith("cuda"):
            device_rng["cuda_rng_state"] = torch.cuda.get_rng_state_all()
        elif str(args.device) == "mps":
            device_rng["mps_rng_state"] = torch.mps.get_rng_state()
        save_checkpoint(args.run_dir / name, model, optimizer_state=optimizer.state_dict(),
                        train_config=config, total_steps=total_steps, episodes=episodes, update=update,
                        best_score=list(best_score), best_score_version=BEST_SCORE_VERSION,
                        torch_rng_state=torch.get_rng_state(), **device_rng)

    save("latest.pt")
    print(f"Self-play auf {args.airport}; {model.config}; Gerät {args.device}. Ziel: {args.steps:,} Schritte.", flush=True)
    print(f"Rewards: Rundenbonus {args.round_reward:g}, Synchronisationsgewicht {args.sync_weight:g}, "
          f"Toleranz {args.sync_tolerance:g} Feld(er).", flush=True)
    try:
        while total_steps < args.steps:
            batch, records = collect_rollout(model, env, min(args.rollout_steps, args.steps - total_steps),
                                             seed=args.seed, episodes_done=episodes, gamma=args.gamma, gae_lambda=args.gae_lambda)
            stats = ppo_update(model, optimizer, batch, epochs=args.epochs, minibatch_size=args.minibatch_size,
                               clip=args.clip, value_coef=args.value_coef, entropy_coef=args.entropy_coef)
            total_steps += len(batch["actions"])
            episodes += len(records)
            update += 1
            elapsed = time.monotonic() - start
            training = summarize_episodes(records)
            row = {"update": update, "total_steps": total_steps, "episodes": episodes, "elapsed_seconds": elapsed,
                   "steps_per_second": (total_steps - starting_steps) / max(elapsed, 1e-6),
                   "learning_rate": optimizer.param_groups[0]["lr"], **stats,
                   **{f"train_{key}": training[key] for key in PERFORMANCE_METRICS}}
            append_rows(args.run_dir / "episodes.csv", EPISODE_FIELDS,
                        [{"phase": "train", "update": update, "total_steps": total_steps, **r} for r in records])
            validation = ""
            if update % args.eval_every == 0 or total_steps >= args.steps:
                model.eval()
                result = evaluate(ModelAgent(model), games=args.eval_games, seed=args.eval_seed,
                                  airport=args.airport, round_reward=args.round_reward, max_steps=args.max_steps,
                                  sync_weight=args.sync_weight, sync_tolerance=args.sync_tolerance)
                for key in (*PERFORMANCE_METRICS, "win_ci_low", "win_ci_high"):
                    row[f"eval_{key}"] = result[key]
                append_rows(args.run_dir / "episodes.csv", EPISODE_FIELDS,
                            [{"phase": "eval", "update": update, "total_steps": total_steps, **r} for r in result["episodes"]])
                score = validation_score(result)
                if score > best_score:
                    best_score = score
                    save("best.pt")
                validation = (f" | Validierung {result['win_rate']:.1%}, Restdistanz {result['mean_distance_remaining']:.2f}, "
                              f"Landerunde {result['landing_round_rate']:.1%}")
            append_rows(metrics_path, METRIC_FIELDS, [row])
            save("latest.pt")
            print(f"Update {update:4d} | {total_steps:8,d} Schritte | Training {row['train_win_rate']:.1%}, "
                  f"Runde {row['train_mean_round']:.2f}, Restdistanz {training['mean_distance_remaining']:.2f}, "
                  f"Sync {training['mean_sync_return']:+.3f} | Policy {stats['policy_loss']:.4f}, "
                  f"Value {stats['value_loss']:.4f}, H {stats['entropy']:.3f}{validation}", flush=True)
    except KeyboardInterrupt:
        print("Unterbrochen. latest.pt enthält das letzte vollständig gespeicherte Update.", flush=True)


if __name__ == "__main__":
    main()
