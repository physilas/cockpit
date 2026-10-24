"""Reproduce a paired, held-out release comparison on independent seed ranges."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path

import torch

from .agents import ModelAgent, HeuristicAgent
from .checkpoints import load_checkpoint
from .evaluate import evaluate, summarize_episodes


def _test(task):
    path, assistance, games, seed, partner, role = task
    torch.set_num_threads(1)
    model, _ = load_checkpoint(path)
    return evaluate(ModelAgent(model), airport='MUC', games=games, seed=seed,
        assistance_version=assistance, partner=HeuristicAgent() if partner else None,
        ai_role=role, round_reward=0, sync_weight=0, task_weight=0)['episodes']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=1000)
    parser.add_argument('--partner-games', type=int, default=200, help='Per role.')
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--seed', type=int, default=6_000_000)
    args = parser.parse_args()
    if min(args.games, args.partner_games, args.workers) < 1:
        parser.error('Game counts and workers must be positive.')
    _, metadata = load_checkpoint(args.checkpoint)
    assistance = metadata['train_config'].get('assistance_version', 0)
    conditions = [('baseline_network', args.baseline, 0, False),
                  ('baseline_with_planner', args.baseline, assistance, False),
                  ('trained_with_planner', args.checkpoint, assistance, False),
                  ('trained_network_only', args.checkpoint, 0, False),
                  ('baseline_with_heuristic_partner', args.baseline, assistance, True),
                  ('trained_with_heuristic_partner', args.checkpoint, assistance, True)]
    results = {}
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for name, path, profile, partner in conditions:
            games = args.partner_games if partner else args.games
            seed = args.seed + 100_000 if partner else args.seed
            tasks = []
            for role in ('pilot', 'kopilot') if partner else ('both',):
                for start in range(0, games, 50):
                    tasks.append((str(path), profile, min(50, games - start), seed + start, partner, role))
            records = [r for batch in pool.map(_test, tasks) for r in batch]
            summary = summarize_episodes(records)
            summary.pop('episodes')
            if partner:
                summary['by_role'] = {}
                for role in ('pilot', 'kopilot'):
                    subset = summarize_episodes([r for r in records if r['ai_role'] == role])
                    subset.pop('episodes')
                    summary['by_role'][role] = subset
            results[name] = {'checkpoint_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                             'assistance_version': profile, 'seed_start': seed, **summary}
            print(f'{name}: {summary["wins"]}/{summary["games"]} = {summary["win_rate"]:.1%}; '
                  f'coffee {summary["mean_coffee_actions"]:.2f}; immediate reroll {summary["first_action_reroll_rate"]:.1%}', flush=True)
    report = {'format': 1, 'airport': 'MUC', 'deterministic': True,
              'notes': ['Fixed held-out seeds shared within self-play and partner comparisons.',
                        'Only the tested AI role receives assistance in partner games.',
                        'Heuristic partner performance is not a human success guarantee.'], 'results': results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
