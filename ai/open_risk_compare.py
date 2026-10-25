"""Fresh paired development comparisons for learned open-risk policies.

Three arms separate changes to the action space from changes to weights:
the original profile-9 source, initial weights with proposals, and a trained
candidate with proposals. These games cannot qualify a production model.
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
from .checkpoints import load_checkpoint, weight_fingerprint
from .evaluate import summarize_episodes
from .modules import ModuleEnv
from .search_environment import OpenRiskEnv
from .search_evaluate import paired_outcomes, search_fingerprint
from .throttle import CpuBudget


def compare_games(model, airport, seed, games, *, opened, duty=.7, beam=64):
    env = (OpenRiskEnv(airport, assistance_version=9, round_reward=0., proposal_beam=beam, cpu_duty_cycle=duty)
           if opened else ModuleEnv(airport, assistance_version=9, round_reward=0.))
    agent, budget, records = ModelAgent(model), CpuBudget(duty), []
    for game_seed in range(seed, seed + games):
        _, info = env.reset(seed=game_seed)
        total, proposals, opportunities, departures = 0., 0, 0, 0
        while not env.done:
            mask, reference = info['action_mask'], info['reference_action_mask']
            source = info.get('source_action_mask', mask)
            action = agent.select(env.view(), mask, reference_mask=reference)
            proposals += int(not source[action])
            opportunities += int(any(allowed and not old for allowed, old in zip(mask, source)))
            departures += int(not reference[action])
            _, reward, _, _, info = env.step(action)
            total += reward
            budget.pause()
        row = env.episode_record(game_seed, 'both', total)
        row.update(proposal_actions=proposals, proposal_opportunities=opportunities, reference_departures=departures)
        records.append(row)
    return records


_models = None


def _initialize(paths, expected):
    global _models
    torch.set_num_threads(1)
    _models, loaded = {}, {}
    for label, path in paths.items():
        if expected[label] not in loaded:
            model, _ = load_checkpoint(path)
            if weight_fingerprint(model) != expected[label]:
                raise ValueError('Compare only finished, unchanged checkpoints.')
            loaded[expected[label]] = model
        _models[label] = loaded[expected[label]]


def _run(task):
    label, route, seed, games, duty, beam = task
    return compare_games(_models[label], route, seed, games, opened=label != 'source', duty=duty, beam=beam)


def validate_seed_budget(seed, games, routes):
    if games < 1 or not 14_000_000 <= seed or seed + (len(routes) - 1) * 10000 + games > 15_000_000:
        raise ValueError('Use development seeds below the reserved 15,000,000 qualification partition.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--warm', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--routes', nargs='+', default=['LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN', 'LOG_YUL_GREEN'])
    p.add_argument('--seed', type=int, default=14700000)
    p.add_argument('--games', type=int, default=200)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--beam', type=int, default=64)
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or not 1 <= args.beam <= 128:
        p.error('Resource cap: at most eight workers at .7 duty and bounded beam.')
    if len(set(args.routes)) != len(args.routes) or args.output.exists():
        p.error('Use unique routes and a new output path.')
    try:validate_seed_budget(args.seed, args.games, args.routes)
    except ValueError as e:p.error(str(e))
    torch.set_num_threads(1)
    paths = {label: str(getattr(args, label)) for label in ('source', 'warm', 'candidate')}
    metadata = {}
    for label, path in paths.items():
        model, payload = load_checkpoint(path)
        if model.config.get('kind') != 'guided_residual' or model.config['action_count'] != 217:
            p.error('Use the finished guided schema-3 research lineage.')
        if label == 'candidate' and (not payload['train_config'].get('research_open_risk') or
                payload['train_config'].get('research_search_sha256') != search_fingerprint()):
            p.error('The candidate must use this exact open-risk environment.')
        metadata[label] = dict(path=path, weights_sha256=weight_fingerprint(model), phase_steps=payload['total_steps'],
                               phase_source_steps=payload['train_config'].get('phase_source_steps'),
                               module_training_steps=payload.get('module_training_steps'))
    report = dict(format=1, phase='fresh_paired_open_risk_development_only', goal_achieved=False,
                  independent_test_used=False, release_evidence=False, models=metadata,
                  source_equals_warm=metadata['source']['weights_sha256'] == metadata['warm']['weights_sha256'],
                  search_sha256=search_fingerprint(), comparison_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  seed=args.seed, games_per_route=args.games, workers=args.workers, cpu_duty_cycle=args.cpu_duty_cycle,
                  threads=1, beam=args.beam, routes={}, complete=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'), initializer=_initialize,
                             initargs=(paths, {k:v['weights_sha256'] for k,v in metadata.items()})) as pool:
        for ordinal, route in enumerate(args.routes):
            report['routes'][route] = {}
            for label in paths:
                started = time.monotonic()
                tasks = [(label, route, args.seed + ordinal * 10000 + start, min(5, args.games - start),
                          args.cpu_duty_cycle, args.beam) for start in range(0, args.games, 5)]
                records = [row for group in pool.map(_run, tasks) for row in group]
                summary = summarize_episodes(records)
                for key in ('proposal_actions', 'proposal_opportunities', 'reference_departures'):
                    summary[key] = sum(r[key] for r in records)
                summary['decisions'] = sum(r['steps'] for r in records)
                summary['elapsed_seconds'] = time.monotonic() - started
                summary['episodes'] = [{k:r[k] for k in ('scenario', 'seed', 'status', 'reason', 'round', 'steps',
                                                       'proposal_actions', 'proposal_opportunities', 'reference_departures')}
                                       for r in records]
                report['routes'][route][label] = summary
                if label == 'candidate':
                    for control in ('source', 'warm'):
                        summary['paired_against_' + control] = paired_outcomes(report['routes'][route][control]['episodes'], summary['episodes'])
                args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
                print(json.dumps(dict(route=route, label=label, wins=summary['wins'], games=args.games,
                                      proposal_actions=summary['proposal_actions'],
                                      paired_against_source=summary.get('paired_against_source'))), flush=True)
    report['complete'] = True
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
