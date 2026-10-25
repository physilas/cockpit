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

from .checkpoints import load_checkpoint, save_checkpoint, planner_fingerprint
from .environment import CrewEnv
from .evaluate import PERFORMANCE_METRICS, evaluate, summarize_episodes
from .agents import ModelAgent
from .actions import ACTION_MASK_VERSION
from .nn_model import ActorCritic
from .demonstrations import coefficient as demo_coefficient, load_demonstrations


METRIC_FIELDS = ["update", "total_steps", "episodes", "elapsed_seconds", "steps_per_second", "learning_rate",
                 "policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "explained_variance",
                 "grad_norm", "train_win_rate", "train_mean_round", "train_mean_return", "train_truncated_rate",
                 "eval_win_rate", "eval_win_ci_low", "eval_win_ci_high", "eval_mean_round", "eval_mean_return"]
METRIC_FIELDS += ["uniform_mix"]
METRIC_FIELDS += ["demo_loss", "demo_coef", "demo_decisions"]
METRIC_FIELDS += [f"{phase}_{name}" for phase in ("train", "eval") for name in PERFORMANCE_METRICS
                  if f"{phase}_{name}" not in METRIC_FIELDS]
EPISODE_FIELDS = ["phase", "update", "total_steps", "seed", "ai_role", "status", "reason", "round", "steps", "return"]
EPISODE_FIELDS += ["outcome_return", "round_return", "sync_return", "distance_remaining", "height_remaining",
                   "airport_reached", "landing_round_started", "sync_error", "gear_count", "flap_count", "brake_strength", "planes_remaining"]
EPISODE_FIELDS += ["tasks_return", "tasks_undone", "gear_undone", "flaps_undone", "braking_undone", "traffic_undone"]
EPISODE_FIELDS += ['coffee_actions', 'coffee_units', 'rerolls', 'coffee_reversals', 'first_action_reroll', 'capacity_impossible']
EPISODE_FIELDS += ['scenario']
BEST_SCORE_VERSION = 2


def reward_config(args, previous=None):
    """Explicit CLI values override saved rewards; omitted values preserve them.

    Missing keys in old checkpoints mean the original unshaped environment.
    Fresh training uses synchronization and task shaping without a round bonus.
    """
    defaults = {"round_reward": 0.0, "sync_weight": 0.05, "sync_tolerance": 1.0, "task_weight": 0.02}
    if previous is not None:
        defaults = {"round_reward": previous.get("round_reward", 0.02),
                    "sync_weight": previous.get("sync_weight", 0.0),
                    "sync_tolerance": previous.get("sync_tolerance", 1.0),
                    "task_weight": previous.get("task_weight", 0.0)}
    return {key: getattr(args, key) if getattr(args, key) is not None else value for key, value in defaults.items()}


def validation_score(result):
    # Survival alone must not make a stationary policy the "best" checkpoint.
    return (result["win_rate"], result["landing_round_rate"], result["airport_reached_rate"],
            -result["mean_distance_remaining"], result["mean_round"])


def resolve_uniform_mix(value, previous=None):
    """No silent exploration change when loading an older checkpoint."""
    if value is not None:
        return value
    return previous.get("uniform_mix", 0.0) if previous is not None else 0.03


def compute_gae(rewards, values, bootstrap=0.0, gamma=0.995, gae_lambda=0.95, *, discounts=None, traces=None):
    """One complete cooperative episode; bootstrap only on time-limit truncation."""
    advantages = [0.0] * len(rewards)
    advantage, next_value = 0.0, bootstrap
    for i in reversed(range(len(rewards))):
        discount = gamma if discounts is None else discounts[i]
        trace = gae_lambda if traces is None else traces[i]
        delta = rewards[i] + discount * next_value - values[i]
        advantage = delta + discount * trace * advantage
        advantages[i] = advantage
        next_value = values[i]
    return advantages, [a + v for a, v in zip(advantages, values)]


def collect_rollout(model, env, minimum_steps, *, seed, episodes_done, gamma, gae_lambda, uniform_mix=0.0, discount_unit='action',
                    partner=None, ai_role='both', cpu_duty_cycle=1.0):
    from .throttle import CpuBudget
    cpu_budget=CpuBudget(cpu_duty_cycle)
    device = next(model.parameters()).device
    data = {name: [] for name in ("observations", "masks", "actions", "log_probs", "values", "advantages", "returns")}
    guided = model.config.get('kind') == 'guided_residual'
    if guided: data['reference_masks'] = []
    records = []
    env.assisted_roles = ('pilot', 'kopilot') if partner is None else (ai_role,)
    model.eval()
    while len(data["actions"]) < minimum_steps:
        # String namespaces keep training seeds disjoint from integer validation/test seeds.
        episode_seed = f"train:{seed}:{episodes_done + len(records)}"
        observation, info = env.reset(seed=episode_seed)
        rewards, values, discounts, traces = [], [], [], []
        while not env.done:
            mask = info["action_mask"]
            if partner is not None and env.current_role != ai_role:
                from .actions import ACTIONS
                partner_guidance = ({'reference_mask': info['reference_action_mask']}
                                    if getattr(getattr(partner, 'model', None), 'config', {}).get('kind') == 'guided_residual' else {})
                selected = partner.select(env.view(), mask, **partner_guidance)
                observation, reward, terminated, truncated, info = env.step(selected)
                advances = discount_unit == 'action' or env.actions[selected].kind in ('place','bonus_place')
                if rewards:
                    rewards[-1] += discounts[-1] * reward
                    discounts[-1] *= gamma if advances else 1.0
                    traces[-1] *= gae_lambda if advances else 1.0
                cpu_budget.pause()
                continue
            with torch.no_grad():
                guidance = {'reference_mask': info['reference_action_mask']} if guided else {}
                action, log_prob, value = model.act(torch.tensor(observation, dtype=torch.float32, device=device), mask,
                                                    uniform_mix=uniform_mix, **guidance)
            data["observations"].append(observation)
            data["masks"].append(mask)
            if guided: data['reference_masks'].append(info['reference_action_mask'])
            data["actions"].append(int(action.item()))
            data["log_probs"].append(float(log_prob.item()))
            data["values"].append(float(value.item()))
            values.append(float(value.item()))
            from .actions import ACTIONS
            advances = discount_unit == 'action' or env.actions[int(action.item())].kind in ('place','bonus_place')
            discounts.append(gamma if advances else 1.0)
            traces.append(gae_lambda if advances else 1.0)
            observation, reward, terminated, truncated, info = env.step(int(action.item()))
            rewards.append(reward)
            cpu_budget.pause()
        bootstrap = 0.0
        if truncated and not terminated:
            with torch.no_grad():
                _, final_value = model(torch.tensor(observation, dtype=torch.float32, device=device))
            bootstrap = float(final_value.item())
        advantages, returns = compute_gae(rewards, values, bootstrap, gamma, gae_lambda,
                                          discounts=discounts, traces=traces)
        data["advantages"].extend(advantages)
        data["returns"].extend(returns)
        records.append(env.episode_record(episode_seed, ai_role, sum(rewards)))
    tensors = {name: torch.tensor(items, dtype=torch.bool if name in ("masks", "reference_masks") else torch.long if name == "actions" else torch.float32,
                                  device=device) for name, items in data.items()}
    return tensors, records


def ppo_update(model, optimizer, batch, *, epochs=4, minibatch_size=256, clip=0.2,
               value_coef=0.5, entropy_coef=0.01, max_grad_norm=0.5, target_kl=0.03, uniform_mix=0.0,
               demonstrations=None, demo_coef=0.0, demo_batch_size=64, demo_generator=None):
    if not math.isfinite(demo_coef) or demo_coef < 0 or demo_batch_size < 1:
        raise ValueError("Ungültiges Demonstrationsgewicht oder Batchgröße.")
    if demo_coef and (demonstrations is None or not len(demonstrations["actions"])):
        raise ValueError("Ein Demonstrationsterm benötigt gültige Beispiele.")
    if demo_coef and demo_generator is None:
        demo_generator = torch.Generator().manual_seed(0)
    model.train()
    advantages = batch["advantages"]
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    count = len(advantages)
    metrics = {name: [] for name in ("policy_loss", "value_loss", "entropy", "approx_kl", "clip_fraction", "grad_norm", "demo_loss")}
    for _ in range(epochs):
        permutation = torch.randperm(count, device=advantages.device)
        epoch_kls = []
        for indices in permutation.split(minibatch_size):
            guidance = {'reference_mask': batch['reference_masks'][indices]} if 'reference_masks' in batch else {}
            log_prob, entropy, value = model.evaluate_actions(batch["observations"][indices], batch["masks"][indices], batch["actions"][indices],
                                                               uniform_mix=uniform_mix, **guidance)
            log_ratio = log_prob - batch["log_probs"][indices]
            ratio = log_ratio.exp()
            objective = torch.minimum(ratio * advantages[indices], ratio.clamp(1 - clip, 1 + clip) * advantages[indices])
            policy_loss = -objective.mean()
            value_loss = 0.5 * (value - batch["returns"][indices]).square().mean()
            entropy_mean = entropy.mean()
            loss = policy_loss + value_coef * value_loss - entropy_coef * entropy_mean
            demo_loss = 0.0
            if demo_coef:
                examples = demonstrations
                if len(examples["actions"]) > demo_batch_size:
                    selected = torch.randint(len(examples["actions"]), (demo_batch_size,), generator=demo_generator)
                    examples = {key: value[selected.to(value.device)] for key, value in examples.items()}
                # Pure masked policy, without the uniform exploration floor. No
                # human log_probs, PPO advantages, rewards, or critic targets.
                demo_guidance = {'reference_mask': examples['reference_masks']} if 'reference_masks' in examples else {}
                demo_logp, _, _ = model.evaluate_actions(examples["observations"], examples["masks"], examples["actions"], **demo_guidance)
                imitation_loss = -demo_logp.mean()
                loss = loss + demo_coef * imitation_loss
                demo_loss = imitation_loss.detach().item()
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
                                  ("clip_fraction", clipped), ("grad_norm", float(grad_norm)), ("demo_loss", demo_loss)):
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
    result.add_argument("--hidden-layers", type=int, default=2)
    result.add_argument("--lr", type=float, default=3e-4)
    result.add_argument("--gamma", type=float, default=0.995)
    result.add_argument("--gae-lambda", type=float, default=0.95)
    result.add_argument("--clip", type=float, default=0.2)
    result.add_argument("--value-coef", type=float, default=0.5)
    result.add_argument("--entropy-coef", type=float, default=0.01)
    result.add_argument("--uniform-mix", type=float, default=None, help="Uniform exploration over legal actions: fresh run 0.03, resume otherwise keeps saved value; 0 disables.")
    result.add_argument("--demo-data", type=Path, nargs="+", default=None, help="JSON-Dateien/Ordner mit KI-no-Beispielen; ohne Angabe beim Resume gespeicherte Quellen.")
    result.add_argument("--demo-coef", type=float, default=None, help="Gewicht des zusätzlichen Nachahmungsterms: bei expliziten Beispielen frisch 0.01; sonst aus, Resume übernimmt den Wert. 0 deaktiviert.")
    result.add_argument("--demo-decay-steps", type=int, default=None, help="Gewicht über so viele NEUE Selbstspiel-Entscheidungen auf 0 senken; frisch 100000, 0 hält es konstant.")
    result.add_argument("--demo-batch-size", type=int, default=None, help="Höchstens so viele Beispielzüge pro PPO-Minibatch; frisch 64, kleinere Sammlungen werden vollständig verwendet.")
    result.add_argument("--round-reward", type=float, default=None, help="Frischer Lauf: 0; beim Fortsetzen gespeicherter Wert, sofern nicht ausdrücklich angegeben.")
    result.add_argument("--sync-weight", type=float, default=None, help="Strafe pro Feld Rückstand nach Toleranz: frisch 0.05; 0 schaltet sie ab; Resume übernimmt sonst den Checkpoint-Wert.")
    result.add_argument("--sync-tolerance", type=float, default=None, help="Tolerierter Rückstand in Feldern, frisch 1; beim Fortsetzen sonst Checkpoint-Wert.")
    result.add_argument("--task-weight", type=float, default=None, help="Penalty budget per unfinished landing task: fresh run 0.02; 0 disables; resume otherwise keeps saved value.")
    result.add_argument("--max-steps", type=int, default=256)
    result.add_argument("--eval-every", type=int, default=5)
    result.add_argument("--eval-steps", type=int, default=None, help="Validate at decision milestones instead of --eval-every updates.")
    result.add_argument("--eval-games", type=int, default=100)
    result.add_argument("--eval-seed", type=int, default=1_000_000)
    result.add_argument('--eval-airports',nargs='+',default=None,
                        help='Optional validation route mixture; training curriculum remains separate.')
    result.add_argument('--eval-partner-fraction',type=float,default=None,
                        help='Fraction of validation games with the frozen partner league instead of self-play.')
    result.add_argument("--seed", type=int, default=42)
    result.add_argument("--device", default="cpu", help="cpu, cuda or mps; CPU is usually useful for this small sequential model.")
    result.add_argument("--threads", type=int, default=1)
    result.add_argument("--resume", type=Path)
    result.add_argument('--assistance-version', type=int, choices=(0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10), default=None,
                        help='Optional public own-hand planner; fresh runs 0, resume preserves saved profile.')
    result.add_argument('--discount-unit', choices=('action', 'placement'), default=None,
                        help='placement does not discount through coffee/reroll helper decisions.')
    result.add_argument('--workers', type=int, default=1, help='Isolated CPU rollout processes; PPO runs on --device.')
    result.add_argument('--cpu-duty-cycle', type=float, default=1,
                        help='Simulation CPU duty cycle per worker, e.g. 0.5 inserts equal work/rest time.')
    result.add_argument('--partner-fraction', type=float, default=0,
                        help='Fraction of parallel rollout batches paired with the independent heuristic (both roles).')
    result.add_argument('--partner-checkpoints', nargs='+', type=Path, default=None,
                        help='Frozen partner league: independent heuristic plus deterministic/noisy versions of each checkpoint.')
    result.add_argument('--transfer-airport', default=None,
                        help='Explicit curriculum transfer to another base-game route; needs resume and a new run directory.')
    result.add_argument('--curriculum-airports', nargs='+', default=None,
                        help='Training-only route mixture; repeat a route for more weight. Validation always uses --airport.')
    return result


def train(args, *, on_validation=None):
    """Run PPO; optional callback(row, evaluation) runs after logs/checkpoint commit.

    Callback exceptions (including Optuna pruning) propagate, leaving latest.pt
    usable. This module has no dependency on Optuna.
    """
    arg_parser = parser()
    for name in ("steps", "rollout_steps", "epochs", "minibatch_size", "hidden_size", "hidden_layers", "eval_every", "eval_games", "threads", "max_steps"):
        if getattr(args, name) < 1:
            arg_parser.error(f"--{name.replace('_', '-')} muss positiv sein.")
    if args.eval_steps is not None and args.eval_steps < 1:
        arg_parser.error("--eval-steps muss positiv sein.")
    if args.workers < 1 or not 0 <= args.partner_fraction <= 1:
        arg_parser.error('workers must be positive and partner-fraction must be in [0,1].')
    if not math.isfinite(args.cpu_duty_cycle) or not 0 < args.cpu_duty_cycle <= 1:
        arg_parser.error('--cpu-duty-cycle must be in (0, 1].')
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
        args.hidden_layers = model.config["hidden_layers"]
        total_steps, episodes, update = payload["total_steps"], payload["episodes"], payload["update"]
        if payload.get("best_score_version") == BEST_SCORE_VERSION:
            best_score = tuple(payload["best_score"])
        if any(payload["train_config"].get(key) != getattr(args, key) for key in ("eval_seed", "eval_games")):
            best_score = (-1.0,) * 5
    else:
        model = ActorCritic(hidden_size=args.hidden_size, hidden_layers=args.hidden_layers).to(args.device)
    previous_config = payload["train_config"] if payload else None
    if args.transfer_airport and not payload:
        arg_parser.error('--transfer-airport requires an existing --resume checkpoint.')
    airport_changed = bool(payload and args.transfer_airport and args.transfer_airport != args.airport)
    if airport_changed:
        args.airport = args.transfer_airport
    previous_options = previous_config or {}
    args.eval_airports=args.eval_airports if args.eval_airports is not None else previous_options.get('eval_airports') or []
    args.eval_partner_fraction=args.eval_partner_fraction if args.eval_partner_fraction is not None else previous_options.get('eval_partner_fraction') or 0
    if not math.isfinite(args.eval_partner_fraction) or not 0<=args.eval_partner_fraction<=1:
        arg_parser.error('--eval-partner-fraction must be in [0,1].')
    validation_changed=payload is not None and (update>0 and previous_options.get('validation_protocol',1)!=2
        or args.eval_airports!=(previous_options.get('eval_airports') or [])
        or args.eval_partner_fraction!=(previous_options.get('eval_partner_fraction') or 0))
    if validation_changed:
        best_score=(-1.0,)*5
    args.partner_checkpoints = [str(Path(p).resolve()) for p in
        (args.partner_checkpoints if args.partner_checkpoints is not None else previous_options.get('partner_checkpoints') or [])]
    from .partners import partner_specs
    league = partner_specs(args.partner_checkpoints)
    # Fail before training if a frozen partner is missing or incompatible.
    from .checkpoints import weight_fingerprint
    partner_manifest = []
    for path in args.partner_checkpoints:
        partner_model, partner_payload = load_checkpoint(path)
        partner_manifest.append({'checkpoint': path, 'weights_sha256': weight_fingerprint(partner_model),
            'assistance_version': partner_payload['train_config'].get('assistance_version', 0)})
    partner_changed = payload is not None and (partner_manifest != previous_options.get('partner_manifest', [])
        or args.partner_fraction != previous_options.get('partner_fraction', 0))
    args.curriculum_airports = args.curriculum_airports if args.curriculum_airports is not None else (previous_options.get('curriculum_airports') or [])
    curriculum_changed = payload is not None and args.curriculum_airports != (previous_options.get('curriculum_airports') or [])
    args.assistance_version = args.assistance_version if args.assistance_version is not None else (previous_options.get('assistance_version') or 0)
    args.discount_unit = args.discount_unit or previous_options.get('discount_unit') or 'action'
    planning_changed = payload is not None and any(getattr(args, k) != (previous_options.get(k) or d)
        for k, d in (('assistance_version', 0), ('discount_unit', 'action')))
    planner_hash = planner_fingerprint() if args.assistance_version else None
    if payload and args.assistance_version and previous_options.get('planner_sha256') != planner_hash:
        planning_changed = True
    previous_demo = previous_config or {}
    explicit_demo_paths = getattr(args, "demo_data", None)
    demo_paths = explicit_demo_paths if explicit_demo_paths is not None else previous_demo.get("demo_data", [])
    default_demo_coef = previous_demo.get("demo_coef", 0.0)
    if explicit_demo_paths and not default_demo_coef:
        default_demo_coef = 0.01
    args.demo_coef = (getattr(args, "demo_coef", None) if getattr(args, "demo_coef", None) is not None
                      else default_demo_coef)
    args.demo_decay_steps = (getattr(args, "demo_decay_steps", None) if getattr(args, "demo_decay_steps", None) is not None
                             else previous_demo.get("demo_decay_steps", 100_000))
    args.demo_batch_size = (getattr(args, "demo_batch_size", None) if getattr(args, "demo_batch_size", None) is not None
                            else previous_demo.get("demo_batch_size", 64))
    if (not math.isfinite(args.demo_coef) or args.demo_coef < 0
            or args.demo_decay_steps < 0 or args.demo_batch_size < 1):
        arg_parser.error("Demonstrationsgewicht muss endlich und nichtnegativ sein, Decay >= 0, Batchgröße >= 1.")
    args.demo_data = [str(Path(path).resolve()) for path in (demo_paths or [])] if args.demo_coef else []
    demos = None
    if args.demo_coef:
        try:
            demos = load_demonstrations(args.demo_data, args.airport)
        except (ValueError, KeyError, TypeError, OSError) as error:
            arg_parser.error(str(error))
    demo_manifest = demos.manifest if demos else None
    def demo_signature(config):
        if not config.get("demo_coef", 0):
            return None
        return (config["demo_coef"], config.get("demo_decay_steps", 100_000),
                config.get("demo_batch_size", 64), (config.get("demo_manifest") or {}).get("sha256"))
    demo_changed = payload is not None and demo_signature(previous_demo) != demo_signature({
        "demo_coef": args.demo_coef, "demo_decay_steps": args.demo_decay_steps,
        "demo_batch_size": args.demo_batch_size, "demo_manifest": demo_manifest})
    demo_start_step = (previous_demo.get("demo_start_step", total_steps)
                       if payload and not demo_changed else total_steps)
    args.uniform_mix = resolve_uniform_mix(args.uniform_mix, previous_config)
    if not 0 <= args.uniform_mix <= 1:
        arg_parser.error("--uniform-mix must be between 0 and 1.")
    exploration_changed = payload is not None and args.uniform_mix != previous_config.get("uniform_mix", 0.0)
    mask_changed = payload is not None and previous_config.get("action_mask_version", 1) != ACTION_MASK_VERSION
    effective_rewards = reward_config(args, previous_config)
    reward_changed = payload is not None and effective_rewards != {
        "round_reward": previous_config.get("round_reward", 0.02),
        "sync_weight": previous_config.get("sync_weight", 0.0),
        "sync_tolerance": previous_config.get("sync_tolerance", 1.0),
        "task_weight": previous_config.get("task_weight", 0.0)}
    if reward_changed or exploration_changed or mask_changed or demo_changed or planning_changed or airport_changed or curriculum_changed or partner_changed or validation_changed:
        if args.run_dir.resolve() == args.resume.resolve().parent:
            arg_parser.error("Geänderte Rewards, Exploration, Aktionsmasken oder Demonstrationen brauchen ein neues --run-dir, damit die Lernkurven vergleichbar bleiben.")
        best_score = (-1.0,) * 5
    for key, value in effective_rewards.items():
        setattr(args, key, value)
    if any(not math.isfinite(v) or v < 0 for v in effective_rewards.values()) or args.round_reward > 0.1:
        arg_parser.error("Reward-Gewichte/Toleranz müssen endlich und nichtnegativ sein; --round-reward maximal 0.1.")
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr, eps=1e-5)
    demo_generator = torch.Generator().manual_seed(args.seed + 7_919)
    if payload and not demo_changed and "demo_rng_state" in payload:
        demo_generator.set_state(payload["demo_rng_state"].cpu())
    if payload:
        optimizer.load_state_dict(payload["optimizer_state"])
        args.lr = optimizer.param_groups[0]["lr"]
        torch.set_rng_state(payload["torch_rng_state"].cpu())
        if str(args.device).startswith("cuda") and "cuda_rng_state" in payload:
            torch.cuda.set_rng_state_all([s.cpu() for s in payload["cuda_rng_state"]])
        if str(args.device) == "mps" and "mps_rng_state" in payload:
            torch.mps.set_rng_state(payload["mps_rng_state"].cpu())
    env = CrewEnv(args.airport, args.round_reward, args.max_steps, sync_weight=args.sync_weight,
                  sync_tolerance=args.sync_tolerance, task_weight=args.task_weight, assistance_version=args.assistance_version,
                  curriculum_airports=args.curriculum_airports)
    for airport in set(args.curriculum_airports):
        CrewEnv(airport, assistance_version=args.assistance_version).reset(seed=args.seed)
    for airport in set(args.eval_airports):
        CrewEnv(airport, assistance_version=args.assistance_version).reset(seed=args.eval_seed)
    env.reset(seed=args.seed)  # Validate the scenario before creating output files.
    demo_tensors = demos.tensors(args.device) if demos else None
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
    config.update({"resumed_from_steps": total_steps, "reward_changed_on_resume": reward_changed,
                   "exploration_changed_on_resume": exploration_changed,
                   "demo_manifest": demo_manifest, "demo_start_step": demo_start_step,
                   "demo_changed_on_resume": demo_changed,
                   'planning_changed_on_resume': planning_changed,
                   'planner_sha256': planner_hash,
                   'airport_changed_on_resume': airport_changed,
                   'curriculum_changed_on_resume': curriculum_changed,
                   'partner_manifest': partner_manifest, 'partner_changed_on_resume': partner_changed,
                   'validation_changed_on_resume':validation_changed,
                   'validation_protocol':2,
                   "action_mask_version": ACTION_MASK_VERSION, "mask_changed_on_resume": mask_changed})
    (args.run_dir / "config.json").write_text(json.dumps({**config, "torch_version": str(torch.__version__)}, indent=2), encoding="utf-8")
    start, starting_steps = time.monotonic(), total_steps
    next_eval = ((total_steps // args.eval_steps) + 1) * args.eval_steps if args.eval_steps else None

    def save(name):
        device_rng = {}
        if str(args.device).startswith("cuda"):
            device_rng["cuda_rng_state"] = torch.cuda.get_rng_state_all()
        elif str(args.device) == "mps":
            device_rng["mps_rng_state"] = torch.mps.get_rng_state()
        if demos:
            device_rng["demo_rng_state"] = demo_generator.get_state()
        save_checkpoint(args.run_dir / name, model, optimizer_state=optimizer.state_dict(),
                        train_config=config, total_steps=total_steps, episodes=episodes, update=update,
                        best_score=list(best_score), best_score_version=BEST_SCORE_VERSION,
                        torch_rng_state=torch.get_rng_state(), **device_rng)

    save("latest.pt")
    parallel = None
    if args.workers > 1 or args.partner_fraction or args.eval_airports or args.eval_partner_fraction:
        from .parallel import ParallelGames
        parallel = ParallelGames(args.workers, model.config, dict(airport=args.airport, round_reward=args.round_reward,
            max_steps=args.max_steps, sync_weight=args.sync_weight, sync_tolerance=args.sync_tolerance,
            task_weight=args.task_weight, assistance_version=args.assistance_version,
            curriculum_airports=args.curriculum_airports), partner_specs=league, cpu_duty_cycle=args.cpu_duty_cycle)
    print(f"Self-play auf {args.airport}; {model.config}; Gerät {args.device}. Ziel: {args.steps:,} Schritte.", flush=True)
    print(f"Rewards: Rundenbonus {args.round_reward:g}, Synchronisationsgewicht {args.sync_weight:g}, "
          f"Toleranz {args.sync_tolerance:g} Feld(er), Aufgabengewicht {args.task_weight:g}.", flush=True)
    print(f"Exploration: {args.uniform_mix:.1%} uniform über erlaubte Aktionen, {1 - args.uniform_mix:.1%} Modell.", flush=True)
    print("Aktionsmaske: Verbleibende Würfel werden für offene Ruder- und Schubfelder reserviert.", flush=True)
    print(f"CPU: {args.workers} Worker, {args.cpu_duty_cycle:.0%} Rechenanteil je Worker.",flush=True)
    if demos:
        print(f"Demonstrationen: {demo_manifest['sessions']} gewonnene Partie(n), {len(demos.actions)} Züge; "
              f"Gewicht {args.demo_coef:g}, Decay {args.demo_decay_steps:,} neue Entscheidungen ab {demo_start_step:,}.", flush=True)
    try:
        while total_steps < args.steps:
            rollout_steps = min(args.rollout_steps, args.steps - total_steps)
            if next_eval is not None:
                rollout_steps = min(rollout_steps, next_eval - total_steps)
            if parallel:
                batch, records = parallel.collect(model, rollout_steps, seed=args.seed, update=update,
                    gamma=args.gamma, gae_lambda=args.gae_lambda, uniform_mix=args.uniform_mix,
                    discount_unit=args.discount_unit, partner_fraction=args.partner_fraction)
            else:
                batch, records = collect_rollout(model, env, rollout_steps,
                                             seed=args.seed, episodes_done=episodes, gamma=args.gamma, gae_lambda=args.gae_lambda,
                                             uniform_mix=args.uniform_mix, discount_unit=args.discount_unit,
                                             cpu_duty_cycle=args.cpu_duty_cycle)
            effective_demo_coef = demo_coefficient(args.demo_coef, total_steps, demo_start_step, args.demo_decay_steps)
            stats = ppo_update(model, optimizer, batch, epochs=args.epochs, minibatch_size=args.minibatch_size,
                               clip=args.clip, value_coef=args.value_coef, entropy_coef=args.entropy_coef,
                               uniform_mix=args.uniform_mix, demonstrations=demo_tensors,
                               demo_coef=effective_demo_coef, demo_batch_size=args.demo_batch_size, demo_generator=demo_generator)
            total_steps += len(batch["actions"])
            episodes += len(records)
            update += 1
            elapsed = time.monotonic() - start
            training = summarize_episodes(records)
            row = {"update": update, "total_steps": total_steps, "episodes": episodes, "elapsed_seconds": elapsed,
                   "steps_per_second": (total_steps - starting_steps) / max(elapsed, 1e-6),
                   "learning_rate": optimizer.param_groups[0]["lr"], "uniform_mix": args.uniform_mix,
                   "demo_coef": effective_demo_coef, "demo_decisions": len(demos.actions) if demos else 0, **stats,
                   **{f"train_{key}": training[key] for key in PERFORMANCE_METRICS}}
            append_rows(args.run_dir / "episodes.csv", EPISODE_FIELDS,
                        [{"phase": "train", "update": update, "total_steps": total_steps, **r} for r in records])
            validation = ""
            result = None
            validation_due = total_steps >= next_eval if next_eval is not None else update % args.eval_every == 0
            if validation_due or total_steps >= args.steps:
                model.eval()
                with torch.random.fork_rng(devices=[]):
                    result = parallel.evaluate(model, games=args.eval_games, seed=args.eval_seed,
                                      airports=args.eval_airports,partner_fraction=args.eval_partner_fraction) if parallel else evaluate(ModelAgent(model), games=args.eval_games, seed=args.eval_seed,
                                      airport=args.airport, round_reward=args.round_reward, max_steps=args.max_steps,
                                      sync_weight=args.sync_weight, sync_tolerance=args.sync_tolerance, task_weight=args.task_weight,
                                      assistance_version=args.assistance_version, policy_seed=args.eval_seed)
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
                if next_eval is not None:
                    next_eval = ((total_steps // args.eval_steps) + 1) * args.eval_steps
            append_rows(metrics_path, METRIC_FIELDS, [row])
            save("latest.pt")
            print(f"Update {update:4d} | {total_steps:8,d} Schritte | Training {row['train_win_rate']:.1%}, "
                  f"Runde {row['train_mean_round']:.2f}, Restdistanz {training['mean_distance_remaining']:.2f}, "
                  f"Sync {training['mean_sync_return']:+.3f}, Aufgaben {training['mean_tasks_return']:+.3f} | Policy {stats['policy_loss']:.4f}, "
                  f"Value {stats['value_loss']:.4f}, H {stats['entropy']:.3f}"
                  f"{(' | Demo ' + format(stats['demo_loss'], '.4f') + ' × ' + format(effective_demo_coef, '.4g')) if demos else ''}"
                  f"{validation}", flush=True)
            if result is not None and on_validation is not None:
                on_validation(row, result)
    except KeyboardInterrupt:
        print("Unterbrochen. latest.pt enthält das letzte vollständig gespeicherte Update.", flush=True)
        raise
    finally:
        if parallel:
            parallel.close()


def main():
    try:
        train(parser().parse_args())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
