"""Bounded paired development test of finite intern-guide strength.

Launch only after training stops, through ``ai.job_control run`` with nice15.
Margins8/12 change the MODEL CONFIGURATION while retaining the preselected
trained candidate's exact state_dict tensors. The warm player is the control.
No variant edits legality, reference masks or checkpoints.
This comparison cannot qualify or publish a model.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import multiprocessing
from pathlib import Path
import time

import torch

from .agents import ModelAgent
from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .evaluate import summarize_episodes
from .modules import ModuleEnv
from .search_evaluate import paired_outcomes
from .throttle import CpuBudget


ROUTES = ('LOG_ATL_GREEN', 'LOG_LHR_YELLOW')
MARGINS = (4., 8., 12.)


def tensor_fingerprint(model):
    """Hash tensor names/types/shapes/values, independently of configuration."""
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        tensor = value.detach().cpu().contiguous()
        digest.update(json.dumps([name, str(tensor.dtype), list(tensor.shape)]).encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def with_margin(source, margin):
    """Independent model/config copy; never mutate the loaded source."""
    if (source.config.get('kind') != 'guided_residual' or
            source.config.get('observation_size') != 489 or source.config.get('action_count') != 217 or
            source.config.get('guide_margin') != getattr(source, 'guide_margin', None)):
        raise ValueError('Finite-strength comparison requires a consistent guided schema-3 model.')
    if type(margin) not in (int, float) or margin not in MARGINS:
        raise ValueError('This experiment supports only guide margins 4, 8 and 12.')
    result = deepcopy(source)
    result.guide_margin = float(margin)
    result.config['guide_margin'] = float(margin)
    if tensor_fingerprint(result) != tensor_fingerprint(source):
        raise RuntimeError('Changing finite guidance unexpectedly changed tensor values.')
    return result


def load_variants(source_path, candidate_path):
    source, source_payload = load_checkpoint(source_path)
    candidate, candidate_payload = load_checkpoint(candidate_path)
    for label, model, payload in (('source', source, source_payload), ('candidate', candidate, candidate_payload)):
        if (model.config.get('kind') != 'guided_residual' or model.config.get('observation_size') != 489 or
                model.config.get('action_count') != 217 or model.config.get('guide_margin') != 4. or
                model.guide_margin != 4.):
            raise ValueError(f'{label} must be the finished margin-4 guided schema-3 player.')
        config = payload.get('train_config', {})
        if (config.get('assistance_version') != 10 or
                config.get('phase_kind') != 'new_public_module_profile_10' or
                config.get('planner_sha256') != planner_fingerprint(3)):
            raise ValueError(f'{label} must use this exact public profile-10 intern phase.')
    source_sha = weight_fingerprint(source)
    if source_payload.get('total_steps') != 0:
        raise ValueError('The source must be the phase warm checkpoint before new decisions.')
    if any(payload['train_config'].get('source_weights_sha256') != source_sha
           for payload in (source_payload, candidate_payload)):
        raise ValueError('Warm/candidate lineage must name these exact initial source weights.')
    if weight_fingerprint(source.source) != weight_fingerprint(candidate.source):
        raise ValueError('The candidate does not preserve the same frozen foundation.')
    variants = {'source_margin4': with_margin(source, 4)}
    variants.update({f'candidate_margin{int(margin)}': with_margin(candidate, margin) for margin in MARGINS})
    metadata = {}
    for label, model in variants.items():
        trained = label.startswith('candidate_')
        payload, path = (candidate_payload, candidate_path) if trained else (source_payload, source_path)
        metadata[label] = {
            'checkpoint': str(path), 'phase_steps': payload['total_steps'],
            'guide_margin': model.guide_margin,
            'configuration_changed': model.guide_margin != 4.,
            'tensor_values_changed_from_warm': tensor_fingerprint(model) != tensor_fingerprint(source),
            'tensor_values_changed_from_loaded_checkpoint': False,
            'model_fingerprint_sha256': weight_fingerprint(model),
            'tensor_sha256': tensor_fingerprint(model),
            'frozen_source_model_sha256': weight_fingerprint(model.source),
            'frozen_source_tensor_sha256': tensor_fingerprint(model.source),
            'initial_model_fingerprint_sha256': source_sha,
            'recorded_source_phase_steps': payload['train_config'].get('source_phase_steps'),
        }
    return variants, metadata


def validate_seed_budget(seed, games):
    if (type(seed) is not int or type(games) is not int or not 1 <= games <= 1000 or
            not 14_000_000 <= seed or seed + 10_000 + games > 15_000_000):
        raise ValueError('Use 1..1000 development games, both route cohorts below15,000,000.')


def compare_games(model, airport, seed, games, *, duty=.7):
    if airport not in ROUTES:
        raise ValueError('This bounded experiment supports only ATL/LHR intern without cards.')
    if not 0 < duty <= .7:
        raise ValueError('CPU duty must be in (0,.7].')
    if (type(seed) is not int or type(games) is not int or games < 1 or
            not 14_000_000 <= seed or seed+games > 15_000_000):
        raise ValueError('Use only development game seeds below15,000,000.')
    if (model.config.get('kind') != 'guided_residual' or model.config.get('guide_margin') not in MARGINS or
            model.config.get('observation_size') != 489 or model.config.get('action_count') != 217 or
            model.config['guide_margin'] != model.guide_margin):
        raise ValueError('Unknown model/margin for intern strength comparison.')
    env = ModuleEnv(airport, abilities=[], assistance_version=10, max_steps=256,
                    round_reward=0., sync_weight=0., task_weight=0.)
    agent, budget, records = ModelAgent(model), CpuBudget(duty), []
    for game_seed in range(seed, seed+games):
        _, info = env.reset(seed=game_seed)
        total, departures = 0., 0
        while not env.done:
            reference, mask = info['reference_action_mask'], info['action_mask']
            action = agent.select(env.view(), mask, reference_mask=reference)
            departures += int(not reference[action])
            _, reward, _, _, info = env.step(action)
            total += reward
            budget.pause()
        record = env.episode_record(game_seed, 'both', total)
        record['reference_departures'] = departures
        records.append(record)
    return records


_models = None


def _initialize(source, candidate, expected):
    global _models
    torch.set_num_threads(1)
    _models, metadata = load_variants(source, candidate)
    if metadata != expected:
        raise ValueError('Use finished, unchanged checkpoints/configuration during the comparison.')


def _run(task):
    label, route, seed, games, duty = task
    return compare_games(_models[label], route, seed, games, duty=duty)


def _write(path, report):
    temporary = path.with_suffix(path.suffix+'.partial')
    temporary.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Finished stage1/warm.pt, margin4.')
    parser.add_argument('--candidate', type=Path, required=True, help='Preselected stage1/best.pt, margin4.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=40)
    parser.add_argument('--seed', type=int, default=14980000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7:
        parser.error('Use at most eight CPU workers at .7 duty.')
    if args.output.exists(): parser.error('Preserve prior results; use a new output path.')
    if Path('runs/STOP_AI_TRAINING').exists(): parser.error('Persistent training stop is active.')
    try:
        validate_seed_budget(args.seed, args.games)
        torch.set_num_threads(1)
        _, metadata = load_variants(args.source, args.candidate)
    except ValueError as exc:
        parser.error(str(exc))
    report = {'format': 1, 'phase': 'paired_intern_guidance_strength_development',
        'complete': False, 'release_evidence': False, 'goal_achieved': False,
        'independent_test_used': False, 'models': metadata, 'games_per_route': args.games,
        'base_seed': args.seed, 'route_seeds': {route: args.seed+index*10_000 for index, route in enumerate(ROUTES)},
        'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
        'assistance_version': 10, 'planner_sha256': planner_fingerprint(3),
        'comparison_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'variants_are_independently_trained_models': False,
        'candidate_margin_variants_have_identical_tensor_values': True,
        'finite_prior_only_masks_unchanged': True, 'routes': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, report)
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(args.source, args.candidate, metadata)) as pool:
        for ordinal, route in enumerate(ROUTES):
            report['routes'][route] = {}
            for label in metadata:
                started = time.monotonic()
                tasks = [(label, route, args.seed+ordinal*10_000+start,
                          min(5, args.games-start), args.cpu_duty_cycle)
                         for start in range(0, args.games, 5)]
                records = [row for group in pool.map(_run, tasks) for row in group]
                summary = summarize_episodes(records)
                summary.update(reference_departures=sum(row['reference_departures'] for row in records),
                    decisions=sum(row['steps'] for row in records), elapsed_seconds=time.monotonic()-started)
                summary['reference_departure_rate'] = summary['reference_departures']/max(1, summary['decisions'])
                if label != 'source_margin4':
                    summary['paired_against_source_margin4'] = paired_outcomes(
                        report['routes'][route]['source_margin4']['episodes'], records)
                report['routes'][route][label] = summary
                _write(args.output, report)
                print(json.dumps({'route': route, 'variant': label, 'wins': summary['wins'], 'games': args.games,
                    'reference_departures': summary['reference_departures'],
                    'paired_against_source_margin4': summary.get('paired_against_source_margin4')}), flush=True)
    report['complete'] = True
    _write(args.output, report)


if __name__ == '__main__':
    main()
