"""Paired development games for experimental public search teachers.

All modes use identical episode seeds and the same finished source weights.
Per-game outcomes are retained for paired analysis. No release qualification.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path
import time

import torch

from .agents import ModelAgent
from .checkpoints import load_checkpoint, model_schema, planner_fingerprint, weight_fingerprint
from .evaluate import evaluate, summarize_episodes
from .search_teacher import SearchTeacher


_model = None
_payload = None


def _initialize(checkpoint, expected_sha):
    global _model, _payload
    torch.set_num_threads(1)
    _model, _payload = load_checkpoint(checkpoint)
    if weight_fingerprint(_model) != expected_sha:
        raise ValueError('Use a finished, unchanged source checkpoint.')


def _run(task):
    mode, airport, seed, games, duty, beam = task
    agent = ModelAgent(_model) if mode == 'model' else SearchTeacher(_model, mode=mode, beam=beam, cpu_duty_cycle=duty)
    started = time.monotonic()
    result = evaluate(agent, airport=airport, games=games, seed=seed, cpu_duty_cycle=duty,
                      assistance_version=9, round_reward=0.)
    return {'episodes': result['episodes'], 'seconds': time.monotonic() - started,
            'considered': getattr(agent, 'considered', 0), 'overrides': getattr(agent, 'overrides', 0)}


def paired_outcomes(baseline, candidate):
    def outcomes(rows):
        return {(r['scenario'], r['seed']): r['status'] == 'gewonnen' for r in rows}
    before, after = outcomes(baseline), outcomes(candidate)
    if len(before) != len(baseline) or len(after) != len(candidate) or before.keys() != after.keys():
        raise ValueError('Paired comparisons require unique, matching route/seed outcomes.')
    return {'both_win': sum(before[k] and after[k] for k in before),
            'both_lose': sum(not before[k] and not after[k] for k in before),
            'candidate_only': sum(not before[k] and after[k] for k in before),
            'baseline_only': sum(before[k] and not after[k] for k in before)}


def search_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('joint_round.py', 'joint_forecast.py', 'search_teacher.py', 'search_evaluate.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--modes', nargs='+', choices=('model', 'legacy', 'joint', 'joint-finish'), default=['model', 'legacy', 'joint'])
    p.add_argument('--routes', nargs='+', default=['LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN', 'LOG_YUL_GREEN'])
    p.add_argument('--games', type=int, default=100)
    p.add_argument('--seed', type=int, default=14500000)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--beam', type=int, default=64)
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or args.games < 1 or not 1 <= args.beam <= 128:
        p.error('Resource cap: 1–8 workers at at most .7 duty, bounded positive search/game budget.')
    if len(set(args.modes)) != len(args.modes) or len(set(args.routes)) != len(args.routes):
        p.error('Modes/routes must be unique.')
    if args.output.exists():
        p.error('Preserve earlier reports; use a new output path.')
    torch.set_num_threads(1)
    model, payload = load_checkpoint(args.checkpoint)
    if model_schema(model)['version'] != 3:
        p.error('This profile-9 comparison requires a schema-3 base/kerosene player.')
    sha = weight_fingerprint(model)
    report = {'format': 1, 'phase': 'development_search_teacher_only', 'goal_achieved': False,
              'independent_test_used': False, 'checkpoint': args.checkpoint.as_posix(), 'weights_sha256': sha,
              'source_training_steps': payload['total_steps'], 'search_sha256': search_fingerprint(),
              'source_planner_sha256': payload['train_config']['planner_sha256'],
              'planner_sha256': planner_fingerprint(3), 'weights_changed': False,
              'seed': args.seed, 'games_per_route': args.games, 'workers': args.workers,
              'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1, 'beam': args.beam, 'modes': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=_initialize, initargs=(str(args.checkpoint), sha)) as pool:
        for mode in args.modes:
            report['modes'][mode] = {}
            for ordinal, airport in enumerate(args.routes):
                started = time.monotonic()
                tasks = [(mode, airport, args.seed + ordinal * 10000 + start, min(5, args.games - start),
                          args.cpu_duty_cycle, args.beam) for start in range(0, args.games, 5)]
                groups = list(pool.map(_run, tasks))
                rows = [r for g in groups for r in g['episodes']]
                summary = summarize_episodes(rows)
                summary.update(considered=sum(g['considered'] for g in groups),
                               overrides=sum(g['overrides'] for g in groups), elapsed_seconds=time.monotonic() - started)
                if mode != 'model' and 'model' in report['modes']:
                    summary['paired_against_model'] = paired_outcomes(report['modes']['model'][airport]['episodes'], rows)
                if mode == 'joint' and 'legacy' in report['modes']:
                    summary['paired_against_legacy'] = paired_outcomes(report['modes']['legacy'][airport]['episodes'], rows)
                if mode == 'joint-finish' and 'joint' in report['modes']:
                    summary['paired_against_joint'] = paired_outcomes(report['modes']['joint'][airport]['episodes'], rows)
                summary['episodes'] = [{k: row[k] for k in ('scenario', 'seed', 'status', 'reason')} for row in rows]
                report['modes'][mode][airport] = summary
                args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
                print(json.dumps({'mode': mode, 'airport': airport, 'wins': summary['wins'], 'games': summary['games'],
                                  'overrides': summary['overrides'], 'elapsed_seconds': summary['elapsed_seconds'],
                                  'paired': summary.get('paired_against_model')}), flush=True)


if __name__ == '__main__':
    main()
