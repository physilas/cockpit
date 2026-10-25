"""Replay development counterexamples using only each acting role's input.

Instrumentation records whether the beam actually scored the source action.
No private partner hand, future engine RNG or hidden state enters the agent.
These selected failures are a diagnosis, not a new win-rate estimate.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import cProfile
import hashlib
import json
import multiprocessing
from pathlib import Path
import pstats
import time
from unittest.mock import patch

import torch

from .agents import ModelAgent
from .checkpoints import load_checkpoint, weight_fingerprint
from .modules import ModuleEnv, MODULE_ACTIONS, MODULE_SLOTS
from .search_evaluate import search_fingerprint
from .search_teacher import SearchTeacher
from .throttle import CpuBudget


@contextmanager
def capture_plan():
    from . import search_teacher
    original = search_teacher.plan_actions
    captured = {}
    def observe(*args, **kwargs):
        ranks, sequences = original(*args, **kwargs)
        captured.update(ranks=dict(ranks), sequences=dict(sequences))
        return ranks, sequences
    with patch.object(search_teacher, 'plan_actions', observe):
        yield captured


def public_context(view):
    result = {k: view[k] for k in ('role', 'round', 'height', 'distance', 'attitude', 'coffee',
                                  'gear', 'flaps', 'brake_progress', 'partner_remaining')}
    result['own_remaining'] = sum(bool(d) for d in view['own_dice'])
    result['fuel'] = view.get('fuel')
    result['planes'] = [(c['distance'], c['planes']) for c in view['track'] if c['planes']]
    result['board'] = view['board']
    return result


def cache_counts():
    from . import joint_round
    return {k: getattr(joint_round, k).cache_info()._asdict()
            for k in ('_prior', '_compatible_hands', '_options', '_task_cost')}


_model = None


def _initialize(checkpoint, expected_sha):
    global _model
    torch.set_num_threads(1)
    _model, _ = load_checkpoint(checkpoint)
    if weight_fingerprint(_model) != expected_sha:
        raise ValueError('The source must remain unchanged.')


def _run(task):
    route, seed, mode, expected, duty, beam, profiling = task
    env = ModuleEnv(route, assistance_version=9, round_reward=0.)
    _, info = env.reset(seed=seed)
    source = ModelAgent(_model)
    active = source if mode == 'model' else SearchTeacher(_model, mode=mode, beam=beam, cpu_duty_cycle=duty)
    budget = CpuBudget(duty)
    rows, total_return = [], 0.
    started, cpu_started = time.monotonic(), time.process_time()
    before = cache_counts()
    profile = cProfile.Profile(timer=time.process_time)
    if profiling:profile.enable()
    while not env.done:
        view, mask = env.view(), info['action_mask']
        guidance = {'reference_mask': info['reference_action_mask']}
        baseline = source.select(view, mask, **guidance)
        with capture_plan() as captured:
            chosen = baseline if mode == 'model' else active.select(view, mask, **guidance)
        ranks, sequences = captured.get('ranks', {}), captured.get('sequences', {})
        rows.append({'step': env.steps, 'context': public_context(view), 'source_action': baseline,
                     'chosen_action': chosen, 'source_label': MODULE_ACTIONS[baseline].label(MODULE_SLOTS),
                     'chosen_label': MODULE_ACTIONS[chosen].label(MODULE_SLOTS), 'override': chosen != baseline,
                     'plan_checked': bool(captured), 'source_plan_present': baseline in ranks,
                     'source_score': ranks.get(baseline), 'chosen_score': ranks.get(chosen),
                     # The sequence describes only this role's own visible hand.
                     'source_sequence': sequences.get(baseline), 'chosen_sequence': sequences.get(chosen)})
        _, reward, _, _, info = env.step(chosen)
        total_return += reward
        budget.pause()
    if profiling:profile.disable()
    episode = env.episode_record(seed, 'both', total_return)
    if (episode['status'], episode['reason']) != (expected['status'], expected['reason']):
        raise ValueError(f'Instrumented replay changed the recorded result: {route}/{seed}/{mode}.')
    hotspots = []
    if profiling:
        for (filename, line, name), (_, calls, own, cumulative, _) in pstats.Stats(profile).stats.items():
            if '/ai/' in filename:
                hotspots.append({'file': Path(filename).name, 'line': line, 'name': name,
                                 'calls': calls, 'self_cpu_seconds': own, 'cumulative_cpu_seconds': cumulative})
    return {'route': route, 'seed': seed, 'mode': mode, 'episode': episode,
            'elapsed_seconds': time.monotonic() - started, 'cpu_seconds': time.process_time() - cpu_started,
            'decisions': rows, 'cache_before': before, 'cache_after': cache_counts(),
            'hotspots': sorted(hotspots, key=lambda x: x['cumulative_cpu_seconds'], reverse=True)[:20]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--comparison', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--routes', nargs='+', default=['LOG_HND_GREEN'])
    p.add_argument('--limit', type=int, default=6, help='At most this many selected counterexamples per route.')
    p.add_argument('--seeds', type=int, nargs='+', help='Restrict selected counterexamples to these development seeds.')
    p.add_argument('--workers', type=int, default=2)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--beam', type=int, default=64)
    p.add_argument('--profile', action='store_true')
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or not 1 <= args.beam <= 128 or args.limit < 1:
        p.error('Use bounded workers, duty, beam and counterexamples.')
    if args.output.exists():p.error('Preserve earlier reports; use a new output path.')
    torch.set_num_threads(1)
    model, _ = load_checkpoint(args.checkpoint)
    if model.config.get('kind') != 'guided_residual':
        p.error('This diagnosis requires the guided source used in the comparison.')
    sha = weight_fingerprint(model)
    comparison = json.loads(args.comparison.read_text())
    if comparison['weights_sha256'] != sha or comparison['search_sha256'] != search_fingerprint():
        p.error('Diagnosis needs the exact same finished model and search code.')
    tasks = []
    for route in args.routes:
        episodes = {mode: {row['seed']: row for row in comparison['modes'][mode][route]['episodes']}
                    for mode in ('model', 'legacy', 'joint')}
        seeds = sorted(k for k, row in episodes['model'].items() if
                       (not args.seeds or k in args.seeds) and row['status'] == 'gewonnen' and
                       any(episodes[m][k]['status'] != 'gewonnen' for m in ('legacy', 'joint')))[:args.limit]
        for seed in seeds:
            tasks.extend((route, seed, mode, episodes[mode][seed], args.cpu_duty_cycle, args.beam, args.profile)
                         for mode in ('model', 'legacy', 'joint'))
    if not tasks:p.error('No selected development counterexamples match this request.')
    report = {'format': 2, 'phase': 'selected_development_failure_diagnosis_only',
              'comparison': args.comparison.as_posix(), 'weights_sha256': sha, 'search_sha256': search_fingerprint(),
              'instrumentation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
              'beam': args.beam, 'profiling': args.profile, 'independent_test_used': False,
              'new_training_decisions': 0, 'replays': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=_initialize, initargs=(str(args.checkpoint), sha)) as pool:
        for row in pool.map(_run, tasks):
            report['replays'].append(row)
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
            overrides = [r for r in row['decisions'] if r['override']]
            print(json.dumps({'route': row['route'], 'seed': row['seed'], 'mode': row['mode'],
                              'status': row['episode']['status'], 'reason': row['episode']['reason'],
                              'overrides': len(overrides), 'source_not_scored': sum(not r['source_plan_present'] for r in overrides)}), flush=True)


if __name__ == '__main__':
    main()
