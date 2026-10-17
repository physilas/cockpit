"""PPO self-play: one shared model controls both roles with separate observations.

Run from the repository root: python -m ai.train --run-dir runs/muc
No gradients pass through the game. Rollouts and their masks stay fixed during
each PPO update. Rewards and advantages are cooperative: never flip their sign
when the active role changes.
"""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean
import time

import torch
from torch import nn

from .checkpoints import load_checkpoint, save_checkpoint
from .environment import CrewEnv
from .evaluate import evaluate
from .agents import ModelAgent
from .nn_model import ActorCritic


METRIC_FIELDS = ["update", "total_steps", "episodes", "elapsed_seconds", "steps_per_second", "learning_rate",
                 "policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "explained_variance",
                 "grad_norm", "train_win_rate", "train_mean_round", "train_mean_return", "train_truncated_rate",
                 "eval_win_rate", "eval_win_ci_low", "eval_win_ci_high", "eval_mean_round", "eval_mean_return"]
EPISODE_FIELDS = ["phase", "update", "total_steps", "seed", "ai_role", "status", "reason", "round", "steps", "return"]


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
        records.append({"seed": episode_seed, "ai_role": "both", "status": info["status"], "reason": info["reason"] or "",
                        "round": info["round"], "steps": info["steps"], "return": sum(rewards)})
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
    result.add_argument("--round-reward", type=float, default=0.02)
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
    best_score = (-1.0, -1.0)
    payload = None
    if args.resume:
        model, payload = load_checkpoint(args.resume, args.device)
        for name in ("airport", "round_reward", "max_steps", "gamma", "gae_lambda", "seed", "hidden_size"):
            setattr(args, name, payload["train_config"][name])
        total_steps, episodes, update = payload["total_steps"], payload["episodes"], payload["update"]
        best_score = tuple(payload["best_score"])
        if any(payload["train_config"].get(key) != getattr(args, key) for key in ("eval_seed", "eval_games")):
            best_score = (-1.0, -1.0)
    else:
        model = ActorCritic(hidden_size=args.hidden_size).to(args.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, eps=1e-5)
    if payload:
        optimizer.load_state_dict(payload["optimizer_state"])
        args.lr = optimizer.param_groups[0]["lr"]
        torch.set_rng_state(payload["torch_rng_state"].cpu())
        if str(args.device).startswith("cuda") and "cuda_rng_state" in payload:
            torch.cuda.set_rng_state_all([s.cpu() for s in payload["cuda_rng_state"]])
        if str(args.device) == "mps" and "mps_rng_state" in payload:
            torch.mps.set_rng_state(payload["mps_rng_state"].cpu())
    env = CrewEnv(args.airport, args.round_reward, args.max_steps)
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
                        best_score=list(best_score), torch_rng_state=torch.get_rng_state(), **device_rng)

    save("latest.pt")
    print(f"Self-play auf {args.airport}; {model.config}; Gerät {args.device}. Ziel: {args.steps:,} Schritte.", flush=True)
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
            row = {"update": update, "total_steps": total_steps, "episodes": episodes, "elapsed_seconds": elapsed,
                   "steps_per_second": (total_steps - starting_steps) / max(elapsed, 1e-6),
                   "learning_rate": optimizer.param_groups[0]["lr"], **stats,
                   "train_win_rate": mean(r["status"] == "gewonnen" for r in records),
                   "train_mean_round": mean(r["round"] for r in records),
                   "train_mean_return": mean(r["return"] for r in records),
                   "train_truncated_rate": mean(r["status"] == "truncated" for r in records)}
            append_rows(args.run_dir / "episodes.csv", EPISODE_FIELDS,
                        [{"phase": "train", "update": update, "total_steps": total_steps, **r} for r in records])
            validation = ""
            if update % args.eval_every == 0 or total_steps >= args.steps:
                model.eval()
                result = evaluate(ModelAgent(model), games=args.eval_games, seed=args.eval_seed,
                                  airport=args.airport, round_reward=args.round_reward, max_steps=args.max_steps)
                for key in ("win_rate", "win_ci_low", "win_ci_high", "mean_round", "mean_return"):
                    row[f"eval_{key}"] = result[key]
                append_rows(args.run_dir / "episodes.csv", EPISODE_FIELDS,
                            [{"phase": "eval", "update": update, "total_steps": total_steps, **r} for r in result["episodes"]])
                score = (result["win_rate"], result["mean_round"])
                if score > best_score:
                    best_score = score
                    save("best.pt")
                validation = f" | Validierung {result['win_rate']:.1%}, Runde {result['mean_round']:.2f}"
            append_rows(metrics_path, METRIC_FIELDS, [row])
            save("latest.pt")
            print(f"Update {update:4d} | {total_steps:8,d} Schritte | Training {row['train_win_rate']:.1%}, "
                  f"Runde {row['train_mean_round']:.2f} | Policy {stats['policy_loss']:.4f}, "
                  f"Value {stats['value_loss']:.4f}, H {stats['entropy']:.3f}{validation}", flush=True)
    except KeyboardInterrupt:
        print("Unterbrochen. latest.pt enthält das letzte vollständig gespeicherte Update.", flush=True)


if __name__ == "__main__":
    main()
