"""Resumable paired development benchmark for public simulator search/shields.

No production policy is replaced. Both roles use independent observation-only
agents; real engine wall time applies to realtime routes, including search.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import json
import hashlib
import multiprocessing
from pathlib import Path
import time

from .checkpoints import load_checkpoint, weight_fingerprint
from .evaluate import summarize_episodes
from .module_training_eval import case_key, _development_seed
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .rollout_search import GuidedBlueprint, RolloutSearchAgent, SearchConfig
from .safety_guard import ShieldedBlueprint, safe_actions


_blueprint = None
_search_config = None


def initialize(checkpoint, config):
    import torch
    global _blueprint, _search_config
    torch.set_num_threads(1)
    model, _ = load_checkpoint(checkpoint)
    model.eval()
    _blueprint, _search_config = GuidedBlueprint(model), config


def run_task(task):
    case, mode, games, seed, audit = task
    _development_seed(seed, games)
    airport = case['airport']
    if mode == 'baseline':
        make_agent = lambda: _blueprint
    elif mode == 'shield':
        make_agent = lambda: ShieldedBlueprint(airport, _blueprint)
    else:
        options = {**_search_config, 'horizon': 'game' if mode == 'game' else 'round'}
        make_agent = lambda: RolloutSearchAgent(airport, _blueprint, config=SearchConfig(**options))
    agents = {role: make_agent() for role in ('pilot', 'kopilot')}
    env = ModuleEnv(airport, abilities=case['abilities'], assistance_version=0,
                    round_reward=0., sync_weight=0., task_weight=0.)
    records = []
    started = time.monotonic()
    for ordinal in range(games):
        env.reset(seed=seed + ordinal)
        decisions = overrides = paired_samples = unsafe = 0
        decision_times = []
        total = 0.
        while not env.done:
            agent = agents[env.current_role]
            view, raw = env.view(), env.action_mask()
            tick = time.monotonic()
            action = agent.select(view, raw)
            decision_times.append(time.monotonic() - tick)
            decisions += 1
            if mode in ('round', 'game'):
                overrides += int(action != agent.last_report['baseline'])
                paired_samples += agent.last_report['samples']
            if audit:
                _, safety = safe_actions(airport, view, raw)
                unsafe += int(str(action) in safety['rejected'] and not safety['fallback'])
            _, reward, _, _, _ = env.step(action)
            total += reward
        record = env.episode_record(seed + ordinal, 'both', total)
        record.update(decisions=decisions, search_overrides=overrides, paired_samples=paired_samples,
                      avoidable_immediate_losses=unsafe,
                      decision_seconds=sum(decision_times), max_decision_seconds=max(decision_times, default=0.))
        records.append(record)
    return dict(case=case, mode=mode, case_key=case_key(case), wall_seconds=time.monotonic()-started,
                clock_model='engine_wall_clock', release_evidence=False, qualification_used=False,
                **summarize_episodes(records))


def atomic_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def research_fingerprint():
    digest = hashlib.sha256()
    for name in ('belief_simulator.py', 'rollout_search.py', 'safety_guard.py', 'research_compare.py'):
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--airports', nargs='*')
    p.add_argument('--one-card-set-per-route', action='store_true')
    p.add_argument('--modes', nargs='+', choices=('baseline', 'shield', 'round', 'game'), default=['baseline', 'shield', 'round'])
    p.add_argument('--games', type=int, default=5)
    p.add_argument('--seed', type=int, default=14900000)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--samples', type=int, default=4)
    p.add_argument('--candidates', type=int, default=6)
    p.add_argument('--max-seconds', type=float, default=2.)
    p.add_argument('--minimum-gain', type=float, default=.03)
    p.add_argument('--audit', action='store_true')
    p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 1 <= args.games <= 100:
        p.error('Use 1..8 workers and 1..100 games per exact case.')
    cases = catalogue_cases()
    if args.airports:
        unknown = set(args.airports) - {row['airport'] for row in cases}
        if unknown:
            p.error(f'Unknown airports: {sorted(unknown)}')
        cases = [row for row in cases if row['airport'] in args.airports]
    if args.one_card_set_per_route:
        cases = list({row['airport']: row for row in reversed(cases)}.values())
    cases = sorted(cases, key=case_key)
    _development_seed(args.seed, (len(cases)-1)*100 + args.games)
    config = asdict(SearchConfig(samples=args.samples, candidates=args.candidates,
                    max_seconds=args.max_seconds, minimum_samples=min(4, args.samples),
                    minimum_gain=args.minimum_gain))
    model, _ = load_checkpoint(args.checkpoint)
    metadata = dict(checkpoint=args.checkpoint, weights_sha256=weight_fingerprint(model),
                    cases=cases, modes=args.modes, games=args.games, seed=args.seed,
                    search=config, audit=args.audit, research_sha256=research_fingerprint())
    del model
    rows = {}
    if args.output.exists():
        if not args.resume:
            p.error('Preserve prior reports; use a new output or explicit --resume.')
        old = json.loads(args.output.read_text())
        if old['config'] != metadata:
            p.error('Resume configuration must exactly match the saved report.')
        rows = old['results']
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tasks = [(case, mode, args.games, args.seed + i*100, args.audit)
             for i, case in enumerate(cases) for mode in args.modes
             if case_key(case)+'/'+mode not in rows]
    report = dict(config=metadata, complete=False, release_evidence=False, results=rows)
    atomic_json(args.output, report)
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize, initargs=(args.checkpoint, config)) as pool:
        futures = [pool.submit(run_task, task) for task in tasks]
        for future in as_completed(futures):
            row = future.result()
            rows[row['case_key']+'/'+row['mode']] = row
            atomic_json(args.output, report)
            print(json.dumps({k: row[k] for k in ('case_key','mode','games','wins','wall_seconds')}), flush=True)
    report['complete'] = True
    atomic_json(args.output, report)


if __name__ == '__main__':
    main()
