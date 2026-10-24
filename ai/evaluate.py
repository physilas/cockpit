"""Held-out rollouts, partner comparisons, public replays and Wilson intervals."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean

from .actions import ACTIONS, ACTION_MASK_VERSION
from .agents import HeuristicAgent, ModelAgent, RandomAgent
from .environment import CrewEnv


PERFORMANCE_METRICS = ("win_rate", "mean_round", "mean_return", "truncated_rate",
    "mean_outcome_return", "mean_round_return", "mean_sync_return", "mean_tasks_return", "mean_tasks_undone", "mean_distance_remaining",
    "airport_reached_rate", "landing_round_rate", "mean_sync_error", "mean_coffee_actions", "mean_coffee_units",
    "mean_rerolls", "mean_coffee_reversals", "first_action_reroll_rate", "capacity_impossible_rate")


def wilson_interval(wins, games):
    p, z = wins / games, 1.96
    denominator = 1 + z * z / games
    center = (p + z * z / (2 * games)) / denominator
    margin = z * math.sqrt(p * (1 - p) / games + z * z / (4 * games * games)) / denominator
    return max(0.0, center - margin), min(1.0, center + margin)


def evaluate(agent, *, games=100, seed=1_000_000, airport="MUC", partner=None,
             ai_role="both", round_reward=0.02, max_steps=256, sync_weight=0.0, sync_tolerance=1.0,
             task_weight=0.0, replay=None, render=False, assistance_version=0,cpu_duty_cycle=1,policy_seed=None):
    from .throttle import CpuBudget
    cpu_budget=CpuBudget(cpu_duty_cycle)
    if games < 1 or ai_role not in ("both", "pilot", "kopilot"):
        raise ValueError("Mindestens eine Partie und eine gültige Rolle sind erforderlich.")
    env = CrewEnv(airport, round_reward, max_steps, sync_weight=sync_weight, sync_tolerance=sync_tolerance, task_weight=task_weight,
                  assistance_version=assistance_version)
    records = []
    # With a partner, 'both' means games per role, on the same seed set.
    roles = ("pilot", "kopilot") if partner is not None and ai_role == "both" else (ai_role,)
    for tested_role in roles:
        env.assisted_roles = ('pilot', 'kopilot') if partner is None else (tested_role,)
        for game_index in range(games):
            game_seed = seed + game_index
            if policy_seed is not None:
                # Reset AFTER loading models, independently of architecture,
                # worker assignment and the previous game's action count.
                import torch
                torch.manual_seed(policy_seed+game_index)
            _, info = env.reset(seed=game_seed)
            total_reward = 0.0
            while not env.done:
                view = env.view()
                active = agent if partner is None or env.current_role == tested_role else partner
                action_id = active.select(view, info["action_mask"])
                action = ACTIONS[action_id]
                played_value = view["own_dice"][action.die] if action.kind == "place" else None
                _, reward, _, _, info = env.step(action_id)
                total_reward += reward
                cpu_budget.pause()
                if render:
                    suffix = f" [Wert {played_value}]" if played_value is not None else ""
                    print(f"{view['role']}: {action.label()}{suffix}")
                if replay is not None:
                    # Deliberately public only: neither private hand appears in a replay.
                    public = env.view()
                    public.pop("own_dice")
                    replay.write(json.dumps({"game": game_index, "seed": game_seed, "ai_role": tested_role,
                        "acting_role": view["role"], "action_id": action_id, "action": action.to_dict(),
                        "played_value": played_value, "reward": reward, "public_state": public,
                        "reward_components": info["reward_components"],
                        "outcome": info["status"]}, ensure_ascii=False) + "\n")
            records.append(env.episode_record(game_seed, tested_role, total_reward))
    return summarize_episodes(records)


def summarize_episodes(records):
    wins = sum(r["status"] == "gewonnen" for r in records)
    low, high = wilson_interval(wins, len(records))
    return {"games": len(records), "wins": wins, "win_rate": wins / len(records),
            "win_ci_low": low, "win_ci_high": high, "mean_round": mean(r["round"] for r in records),
            "mean_return": mean(r["return"] for r in records),
            "truncated_rate": mean(r["status"] == "truncated" for r in records),
            **{f"mean_{key}": mean(r[key] for r in records) for key in ("outcome_return", "round_return", "sync_return", "tasks_return", "tasks_undone", "distance_remaining", "sync_error")},
            "airport_reached_rate": mean(r["airport_reached"] for r in records),
            "landing_round_rate": mean(r["landing_round_started"] for r in records),
            **{f'mean_{key}': mean(r.get(key, 0) for r in records) for key in
               ('coffee_actions', 'coffee_units', 'rerolls', 'coffee_reversals')},
            **{f'{key}_rate': mean(r.get(key, 0) for r in records) for key in ('first_action_reroll', 'capacity_impossible')},
            "truncated": sum(r["status"] == "truncated" for r in records),
            "loss_reasons": dict(Counter(reason for r in records for reason in r["reason"].split(",") if reason)),
            "episodes": records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--checkpoint", type=Path)
    source.add_argument("--baseline", choices=("random", "heuristic"))
    parser.add_argument("--partner", choices=("self", "random", "heuristic"), default="self")
    parser.add_argument("--ai-role", choices=("both", "pilot", "kopilot"), default="both")
    parser.add_argument("--airport", default=None, help="Standard: Strecke aus dem Checkpoint, sonst MUC.")
    parser.add_argument("--games", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2_000_000, help="Separate final-test seeds; training validation starts at 1,000,000.")
    parser.add_argument("--stochastic", action="store_true", help="Sample model actions instead of argmax.")
    parser.add_argument("--round-reward", type=float, default=None)
    parser.add_argument("--sync-weight", type=float, default=None, help="0 schaltet die Synchronisationsstrafe ab; sonst Checkpoint-Wert.")
    parser.add_argument("--sync-tolerance", type=float, default=None)
    parser.add_argument("--task-weight", type=float, default=None, help="Growing penalty for unfinished landing tasks; 0 disables it; default from checkpoint.")
    parser.add_argument("--uniform-mix", type=float, default=None, help="Exploration for --stochastic: default from checkpoint; deterministic evaluation uses no mixture.")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--json", type=Path, help="Save summary and per-game results, readable by the notebook.")
    parser.add_argument("--render", action="store_true")
    parser.add_argument('--assistance-version', type=int, choices=(0, 1, 2, 3, 4, 5, 6, 7, 8), default=None,
                        help='Default from checkpoint; 0 evaluates the network without the optional planner.')
    args = parser.parse_args()
    import torch
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    config = {}
    if args.checkpoint:
        from .checkpoints import load_checkpoint
        model, payload = load_checkpoint(args.checkpoint)
        config = payload.get("train_config", {})
        uniform_mix = args.uniform_mix if args.uniform_mix is not None else config.get("uniform_mix", 0.0)
        if not 0 <= uniform_mix <= 1:
            parser.error("--uniform-mix must be between 0 and 1.")
        agent = ModelAgent(model, deterministic=not args.stochastic, uniform_mix=uniform_mix)
    else:
        agent = HeuristicAgent() if args.baseline == "heuristic" else RandomAgent(args.seed + 17)
    airport = args.airport or config.get("airport", "MUC")
    assistance = config.get('assistance_version', 0) if args.assistance_version is None else args.assistance_version
    reward_options = {key: getattr(args, key) if getattr(args, key) is not None else config.get(key, default)
                      for key, default in (("round_reward", 0.02), ("sync_weight", 0.0), ("sync_tolerance", 1.0), ("task_weight", 0.0))}
    partner = None if args.partner == "self" else HeuristicAgent() if args.partner == "heuristic" else RandomAgent(args.seed + 31)
    handle = None
    try:
        if args.replay:
            args.replay.parent.mkdir(parents=True, exist_ok=True)
            handle = args.replay.open("w", encoding="utf-8")
        result = evaluate(agent, games=args.games, seed=args.seed, airport=airport,
                          partner=partner, ai_role=args.ai_role, replay=handle, render=args.render,
                          max_steps=config.get("max_steps", 256), assistance_version=assistance, **reward_options)
    finally:
        if handle:
            handle.close()
    print(f"{result['wins']}/{result['games']} Siege = {result['win_rate']:.1%} "
          f"(95%-Intervall {result['win_ci_low']:.1%}–{result['win_ci_high']:.1%})")
    print(f"Mittlere erreichte Runde: {result['mean_round']:.2f}; Abbrüche: {result['truncated']}")
    print(f"Mittlere Restentfernung: {result['mean_distance_remaining']:.2f}; "
          f"Flughafen erreicht: {result['airport_reached_rate']:.1%}; Landerunde begonnen: {result['landing_round_rate']:.1%}")
    print(f"Offene Vorbereitungsschritte: {result['mean_tasks_undone']:.2f}; Aufgabenreward: {result['mean_tasks_return']:+.3f}")
    print("Verlustgründe:", json.dumps(result["loss_reasons"], ensure_ascii=False))
    if partner is not None and args.ai_role == "both":
        for role in ("pilot", "kopilot"):
            records = [r for r in result["episodes"] if r["ai_role"] == role]
            print(f"  KI als {role}: {sum(r['status'] == 'gewonnen' for r in records)}/{len(records)} Siege")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"airport": airport, "partner": args.partner,
                                        "action_mask_version": ACTION_MASK_VERSION,
                                        "stochastic": args.stochastic,
                                        "uniform_mix": agent.uniform_mix if args.checkpoint and args.stochastic else 0.0,
                                        'assistance_version': assistance, **reward_options, **result}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
