"""Held-out route-by-route qualification of a shared base-game player."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path

import torch

from backend.katalog import landekatalog
from .agents import ModelAgent, HeuristicAgent
from .checkpoints import load_checkpoint, weight_fingerprint, planner_fingerprint
from .evaluate import evaluate, summarize_episodes


def _run(task):
    checkpoint, airport, assistance, seed, games, partner, role = task
    torch.set_num_threads(1)
    model, _ = load_checkpoint(checkpoint)
    return evaluate(ModelAgent(model), airport=airport, assistance_version=assistance,
        games=games, seed=seed, round_reward=0, partner=HeuristicAgent() if partner else None,
        ai_role=role)['episodes']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--airports', nargs='+', default=None)
    p.add_argument('--games', type=int, default=500)
    p.add_argument('--partner-games', type=int, default=100)
    p.add_argument('--seed', type=int, default=7_000_000)
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--assistance-version', type=int, default=None)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--minimum-win-rate', type=float, default=.2)
    args = p.parse_args()
    if min(args.games, args.partner_games, args.workers) < 1 or not 0 <= args.minimum_win_rate <= 1:
        p.error('Positive game counts/workers and a minimum win rate in [0,1] are required.')
    model, payload = load_checkpoint(args.checkpoint)
    profile = payload['train_config'].get('assistance_version', 0) if args.assistance_version is None else args.assistance_version
    routes = args.airports or list(dict.fromkeys(s['engine_code'] for s in landekatalog()['scenarios']
                                                if not s['modules'] and not s['ability_count']))
    report = {'format': 1, 'checkpoint_sha256': hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
              'weights_sha256': weight_fingerprint(model),
              'planner_sha256': planner_fingerprint() if profile else None,
              'assistance_version': profile, 'seed': args.seed, 'minimum_win_rate': args.minimum_win_rate,
              'routes': {}, 'qualified_routes': [],
              'note': 'Self-play qualification; heuristic partner results are separate and do not predict human win rates.'}
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn')) as pool:
        for airport in routes:
            route = {}
            for kind, partner, roles, n in [('self', False, ('both',), args.games),
                                           ('heuristic_partner', True, ('pilot', 'kopilot'), args.partner_games)]:
                seed = args.seed + (100_000 if partner else 0)
                tasks = [(str(args.checkpoint), airport, profile, seed + start, min(25, n - start), partner, role)
                         for role in roles for start in range(0, n, 25)]
                records = [r for group in pool.map(_run, tasks) for r in group]
                summary = summarize_episodes(records)
                summary.pop('episodes')
                if partner:
                    summary['by_role'] = {}
                    for role in roles:
                        sub = summarize_episodes([r for r in records if r['ai_role'] == role])
                        sub.pop('episodes')
                        summary['by_role'][role] = sub
                route[kind] = summary
            report['routes'][airport] = route
            if route['self']['win_ci_low'] >= args.minimum_win_rate:
                report['qualified_routes'].append(airport)
            print(f"{airport}: self {route['self']['wins']}/{args.games} ({route['self']['win_rate']:.1%}); "
                  f"partner {route['heuristic_partner']['win_rate']:.1%}", flush=True)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n')


if __name__ == '__main__':
    main()
