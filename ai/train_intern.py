"""Bounded transfer to the public profile-10 intern player, never auto-publish."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import time

import torch

from .checkpoints import load_checkpoint, save_checkpoint, planner_fingerprint, weight_fingerprint
from .evaluate import summarize_episodes
from .parallel import ParallelGames
from .train import ppo_update
from .train_fuel import successful_replay


ROUTES = ('LOG_ATL_GREEN', 'LOG_LHR_YELLOW')


def selection_score(summary):
    """Each target route first; pooled success cannot hide a weak route."""
    rates = [summary['by_route'][route]['win_rate'] for route in ROUTES]
    return min(rates), sum(rates)/len(rates)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('ai/releases/crew2-v1/best.pt'))
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=120000)
    parser.add_argument('--seconds', type=float, default=900.)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    parser.add_argument('--device', default='mps')
    parser.add_argument('--seed', type=int, default=251050)
    parser.add_argument('--eval-seed', type=int, default=14940000)
    parser.add_argument('--eval-games-per-route', type=int, default=80)
    parser.add_argument('--eval-every', type=int, default=25)
    args = parser.parse_args()
    if (not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7
            or args.steps < 1 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 900
            or not 1 <= args.eval_games_per_route <= 1000 or args.eval_every < 1):
        parser.error('Use at most eight workers at .7, 900 training seconds and positive bounded budgets.')
    if not 14_000_000 <= args.eval_seed or args.eval_seed + 10000 + args.eval_games_per_route >= 15_000_000:
        parser.error('Development seeds must stay below 15,000,000.')
    if args.run_dir.exists():
        parser.error('Preserve prior experiments; use a new directory.')
    if Path('runs/STOP_AI_TRAINING').exists():
        parser.error('Persistent stop is active; explicit resumption is required.')
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    model, source = load_checkpoint(args.source, args.device)
    if model.config.get('kind') != 'guided_residual' or model.config['action_count'] != 217:
        parser.error('Use an existing guided schema-3 player.')
    initial_sha, frozen_sha = weight_fingerprint(model), weight_fingerprint(model.source)
    optimizer = torch.optim.Adam((parameter for parameter in model.parameters() if parameter.requires_grad),
                                 lr=5e-5, eps=1e-5)
    options = dict(airport=ROUTES[0], assistance_version=10, max_steps=256,
        curriculum_airports=ROUTES, abilities=[], round_reward=0., sync_weight=.05,
        sync_tolerance=1., task_weight=.02)
    config = {**options, 'schema_version': 3, 'supported_modules': ['intern'], 'supported_cards': [],
        'ability_count': 0, 'source_checkpoint': args.source.as_posix(),
        'source_weights_sha256': initial_sha, 'source_phase_steps': source['total_steps'],
        'source_planner_sha256': source['train_config'].get('planner_sha256'),
        'phase_kind': 'new_public_module_profile_10', 'seed': args.seed,
        'eval_seed': args.eval_seed, 'eval_games_per_route': args.eval_games_per_route,
        'eval_every': args.eval_every, 'eval_airports': list(ROUTES),
        'planner_sha256': planner_fingerprint(3), 'action_mask_version': 2,
        'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
        'device': args.device, 'steps_limit': args.steps, 'training_seconds_limit': args.seconds,
        'learning_rate': 5e-5, 'uniform_mix': .03, 'self_imitation_coef': .03,
        'discount_unit': 'placement', 'publication_status': 'requires_independent_route_qualification'}
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    steps, episodes, update, training_seconds = 0, 0, 0, 0.
    counts, best, best_steps, replay = Counter(), None, 0, None
    validations = []
    demo_generator = torch.Generator().manual_seed(args.seed+37)
    wall_start = time.monotonic()
    games = ParallelGames(args.workers, model.config, options, cpu_duty_cycle=args.cpu_duty_cycle)

    def save(name):
        if weight_fingerprint(model.source) != frozen_sha:
            raise RuntimeError('Frozen original player changed.')
        save_checkpoint(args.run_dir/name, model, train_config=config, total_steps=steps,
            source_phase_steps=source['total_steps'], module_training_steps=source.get('module_training_steps',0)+steps,
            decisions_by_module={'intern': steps}, decisions_by_route=dict(counts),
            episodes=episodes, update=update, training_elapsed_seconds=training_seconds,
            optimizer_state=optimizer.state_dict(), torch_rng_state=torch.get_rng_state(),
            mps_rng_state=torch.mps.get_rng_state() if args.device=='mps' else torch.get_rng_state(),
            successful_replay={key:value.cpu() for key,value in replay.items()} if replay else None,
            demo_rng_state=demo_generator.get_state())

    def validate():
        nonlocal best, best_steps
        result = games.evaluate(model, games=2*args.eval_games_per_route, seed=args.eval_seed,
                                airports=ROUTES)
        records = result.pop('episodes')
        if {record['scenario'] for record in records} != set(ROUTES):
            raise RuntimeError('Validation selected an unexpected route.')
        result['by_route'] = {}
        for route in ROUTES:
            grouped = summarize_episodes([record for record in records if record['scenario'] == route])
            grouped.pop('episodes')
            result['by_route'][route] = grouped
        score = selection_score(result)
        row = dict(steps=steps, update=update, release_evidence=False, result=result, score=list(score))
        validations.append(row)
        with (args.run_dir/'validation.jsonl').open('a') as stream:
            stream.write(json.dumps(row)+'\n')
        if best is None or score > best:
            best, best_steps = score, steps
            save('best.pt')
        print(json.dumps(dict(validation=True, steps=steps,
            routes={key:{k:val[k] for k in ('games','wins','win_rate')} for key,val in result['by_route'].items()},
            weakest_route=score[0], release_evidence=False)), flush=True)

    try:
        save('warm.pt')
        validate()
        while steps < args.steps and training_seconds < args.seconds:
            started = time.monotonic()
            batch, records = games.collect(model, min(2048, args.steps-steps), seed=args.seed,
                update=update, gamma=.995, gae_lambda=.95, uniform_mix=.03, discount_unit='placement')
            if any(record['scenario'] not in ROUTES for record in records):
                raise RuntimeError('Training selected an unexpected route.')
            replay = successful_replay(batch, records, replay, limit=4096)
            stats = ppo_update(model, optimizer, batch, epochs=4, minibatch_size=256,
                clip=.2, value_coef=.5, entropy_coef=.01, uniform_mix=.03,
                demonstrations=replay, demo_coef=.03 if replay else 0., demo_generator=demo_generator)
            for record in records:
                counts[record['scenario']] += record['steps']
            steps += len(batch['actions']); episodes += len(records); update += 1
            training_seconds += time.monotonic()-started
            row = dict(steps=steps, update=update, episodes=episodes,
                training_seconds=training_seconds, decisions_by_route=dict(counts),
                train_wins=sum(record['status']=='gewonnen' for record in records),
                train_episodes=len(records), **stats)
            with (args.run_dir/'training.jsonl').open('a') as stream:
                stream.write(json.dumps(row)+'\n')
            save('latest.pt')
            print(json.dumps({key:row[key] for key in ('steps','update','training_seconds','train_wins','train_episodes')}),flush=True)
            if update % args.eval_every == 0:
                validate()
        if validations[-1]['steps'] != steps:
            validate()
    except KeyboardInterrupt:
        config['interrupted'] = True
        raise
    finally:
        save('latest.pt')
        games.close()
    report = dict(format=1, complete=True, release_evidence=False, goal_achieved=False,
        new_training_decisions=steps, episodes=episodes, updates=update,
        training_elapsed_seconds=training_seconds, total_wall_seconds=time.monotonic()-wall_start,
        best_steps=best_steps, config=config, validations=validations, decisions_by_route=dict(counts),
        frozen_source_unchanged=True, initial_weights_sha256=initial_sha,
        latest_weights_sha256=weight_fingerprint(model))
    (args.run_dir/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(complete=True, steps=steps, best_steps=best_steps, training_seconds=training_seconds)),flush=True)


if __name__ == '__main__':
    main()
