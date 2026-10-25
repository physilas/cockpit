"""Wall-time-bounded all-module PPO research; no automatic model publication."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time

import torch

from .all_modules_environment import AllModulesEnv
from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint, planner_fingerprint
from .module_training_eval import load_cases, balanced_cases, case_key, run_case
from .modules import MODULES, CARDS
from .nn_model import build_model
from .train import collect_rollout, ppo_update
from .train_fuel import successful_replay


_model, _options, _duty = None, None, None


def environment_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('all_modules_environment.py', 'module_training_eval.py', 'train_all_modules.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def _initialize(config, options, duty):
    global _model, _options, _duty
    torch.set_num_threads(1)
    _model, _options, _duty = build_model(config), options, duty


def _collect(task):
    state, steps, seed, update, ordinal = task
    _model.load_state_dict(state)
    torch.manual_seed(seed + update * 1009 + ordinal)
    env = AllModulesEnv(**_options)
    return collect_rollout(_model, env, steps, seed=f'allmodules:{seed}:{update}:{ordinal}',
        episodes_done=0, gamma=.995, gae_lambda=.95, uniform_mix=.03,
        discount_unit='placement', cpu_duty_cycle=_duty)


def _evaluate(task):
    state, case, games, seed = task
    _model.load_state_dict(state)
    # Explicit case; never pass the training curriculum into evaluation.
    return run_case(_model, case, games, seed, duty=min(.7, _duty))


def development_score(rows, target=.3):
    """Training checkpoint selection only; small-sample rates are not release proof."""
    rates = [row['win_rate'] for row in rows.values()]
    return (sum(rate >= target for rate in rates), min(rates), sum(rates) / len(rates))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, default=Path('ai/releases/crew2-v1/best.pt'))
    p.add_argument('--matrix', type=Path, default=Path('ai/experiments/modules-30pct-2026-10-25/matrix.json'))
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--training-seconds', type=float, default=1200.)
    p.add_argument('--steps', type=int, default=10_000_000)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--device', default='mps')
    p.add_argument('--seed', type=int, default=251045)
    p.add_argument('--eval-seed', type=int, default=14800000)
    p.add_argument('--eval-games-per-case', type=int, default=3)
    p.add_argument('--eval-interval-seconds', type=float, default=600.)
    p.add_argument('--learning-rate', type=float, default=5e-5)
    args = p.parse_args()
    if (not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .8
            or not 0 < args.training_seconds <= 1200 or args.steps < 1
            or not 1 <= args.eval_games_per_case <= 100 or not math.isfinite(args.eval_interval_seconds)
            or args.eval_interval_seconds <= 0 or not math.isfinite(args.learning_rate)
            or args.learning_rate <= 0):
        p.error('Bounded phase: at most 1200 seconds, eight workers at .8 duty, positive budgets.')
    if args.run_dir.exists():
        p.error('Preserve prior runs; use a new directory.')
    cases = load_cases(args.matrix)
    if not 14_000_000 <= args.eval_seed or args.eval_seed + 100 * len(cases) + args.eval_games_per_case >= 15_000_000:
        p.error('Use development seeds below 15,000,000.')
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    model, source = load_checkpoint(args.source, args.device)
    if model.config.get('kind') != 'guided_residual' or model.config['action_count'] != 217:
        p.error('Use the existing guided schema-3 source, without another network branch.')
    source_sha, frozen_sha = weight_fingerprint(model), weight_fingerprint(model.source)
    optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate, eps=1e-5)
    options = dict(airport='LOG_OSL_GREEN', assistance_version=9, max_steps=256,
        round_reward=0., sync_weight=.05, sync_tolerance=1., task_weight=.02,
        curriculum_cases=balanced_cases(cases), step_seconds=1.)
    config = dict(airport='LOG_OSL_GREEN', assistance_version=9, max_steps=256,
        schema_version=3, supported_modules=list(MODULES), supported_cards=list(CARDS),
        ability_count='case_specific', research_all_modules=True,
        research_environment_sha256=environment_fingerprint(),
        source_checkpoint=args.source.as_posix(), source_weights_sha256=source_sha,
        source_phase_steps=source['total_steps'], seed=args.seed, eval_seed=args.eval_seed,
        eval_games_per_case=args.eval_games_per_case, eval_seed_stride=100,
        eval_interval_seconds=args.eval_interval_seconds,
        matrix=args.matrix.as_posix(), matrix_sha256=hashlib.sha256(args.matrix.read_bytes()).hexdigest(),
        cases=len(cases), routes=21, curriculum='uniform_route_then_uniform_allowed_cards',
        step_seconds=1., realtime_clock='logical_seconds_per_decision_training_proxy',
        workers=args.workers, cpu_duty_cycle=args.cpu_duty_cycle, threads=1, device=args.device,
        training_seconds_limit=args.training_seconds, steps_limit=args.steps,
        learning_rate=args.learning_rate, uniform_mix=.03, self_imitation_coef=.03,
        discount_unit='placement', round_reward=0., sync_weight=.05, sync_tolerance=1., task_weight=.02,
        planner_sha256=planner_fingerprint(3), action_mask_version=2,
        publication_status='research_only_requires_matching_browser_and_independent_case_tests',
        target_win_rate_range=[.3,.4], qualification_used=False)
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    steps, episodes, update, training_elapsed = 0, 0, 0, 0.
    counts, module_counts, card_counts = Counter(), Counter(), Counter()
    replay, best_score = None, None
    best_steps = 0
    validations = []
    demo_generator = torch.Generator().manual_seed(args.seed + 37)

    def state():
        return {key:value.detach().cpu() for key,value in model.state_dict().items()}

    def save(name):
        save_checkpoint(args.run_dir/name, model, train_config=config, total_steps=steps,
            module_training_steps=source.get('module_training_steps',0)+sum(
                counts[case_key(c)] for c in cases if c['modules'] or c['abilities']),
            source_phase_steps=source['total_steps'], episodes=episodes, update=update,
            training_elapsed_seconds=training_elapsed, decisions_by_case=dict(counts),
            decisions_by_module=dict(module_counts), decisions_by_card=dict(card_counts),
            optimizer_state=optimizer.state_dict(), torch_rng_state=torch.get_rng_state(),
            mps_rng_state=torch.mps.get_rng_state() if args.device=='mps' else torch.get_rng_state(),
            successful_replay={k:v.cpu() for k,v in replay.items()} if replay else None,
            demo_rng_state=demo_generator.get_state())

    wall_start = time.monotonic()
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(model.config, options, args.cpu_duty_cycle)) as pool:
        def validate():
            nonlocal best_score, best_steps
            weights = state()
            tasks = [(weights, case, args.eval_games_per_case, args.eval_seed + ordinal*100)
                     for ordinal,case in enumerate(cases)]
            rows = {}
            for result in pool.map(_evaluate, tasks):
                result.pop('episodes')
                rows[result['case_key']] = result
            score = development_score(rows)
            row = dict(steps=steps, update=update, training_elapsed_seconds=training_elapsed,
                cases=rows, score=list(score), release_evidence=False)
            validations.append(row)
            with (args.run_dir/'validation.jsonl').open('a') as f:
                f.write(json.dumps(row)+'\n')
            if best_score is None or score > best_score:
                best_score, best_steps = score, steps
                save('best.pt')
            print(json.dumps(dict(validation=True, steps=steps, cases=len(rows),
                observed_cases_at_30pct=score[0], minimum_case_win_rate=score[1],
                descriptive_mean_case_win_rate=score[2], release_evidence=False)), flush=True)

        save('warm.pt')
        validate()
        last_eval, last_save = 0., 0.
        try:
            while training_elapsed < args.training_seconds and steps < args.steps:
                started = time.monotonic()
                remaining = min(2048, args.steps-steps)
                tasks = [(state(), (remaining+args.workers-1)//args.workers, args.seed, update, ordinal)
                         for ordinal in range(args.workers)]
                outputs = list(pool.map(_collect, tasks))
                batch = {k:torch.cat([o[0][k] for o in outputs]).to(args.device) for k in outputs[0][0]}
                records = [record for _,rows in outputs for record in rows]
                replay = successful_replay(batch, records, replay, limit=4096)
                stats = ppo_update(model, optimizer, batch, epochs=4, minibatch_size=256,
                    clip=.2, value_coef=.5, entropy_coef=.01, uniform_mix=.03,
                    demonstrations=replay, demo_coef=.03 if replay else 0., demo_generator=demo_generator)
                for record in records:
                    counts[case_key(dict(airport=record['scenario'], abilities=record['abilities']))] += record['steps']
                    for module in record['modules']:module_counts[module] += record['steps']
                    for card in record['abilities']:card_counts[card] += record['steps']
                steps += len(batch['actions']); episodes += len(records); update += 1
                training_elapsed += time.monotonic()-started
                row = dict(steps=steps, update=update, episodes=episodes,
                    training_elapsed_seconds=training_elapsed, decisions_by_case=dict(counts),
                    decisions_by_module=dict(module_counts), decisions_by_card=dict(card_counts),
                    train_wins=sum(r['status']=='gewonnen' for r in records), train_episodes=len(records),
                    budget_failures=sum(r['training_budget_failure'] for r in records), **stats)
                with (args.run_dir/'training.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
                if update==1 or training_elapsed-last_save >= 30:
                    if weight_fingerprint(model.source) != frozen_sha:raise RuntimeError('Frozen source changed.')
                    save('latest.pt'); last_save=training_elapsed
                    print(json.dumps({k:row[k] for k in ('steps','update','training_elapsed_seconds','train_wins','train_episodes','budget_failures')}),flush=True)
                if training_elapsed-last_eval >= args.eval_interval_seconds:
                    validate(); last_eval=training_elapsed
        except KeyboardInterrupt:
            config['interrupted'] = True
            raise
        finally:
            save('latest.pt')
        if validations[-1]['steps'] != steps:validate()
    if weight_fingerprint(model.source) != frozen_sha:raise RuntimeError('Frozen source changed.')
    report = dict(format=1, complete=True, goal_achieved=False, release_evidence=False,
        qualification_used=False, new_training_decisions=steps, episodes=episodes, updates=update,
        training_elapsed_seconds=training_elapsed, total_wall_seconds=time.monotonic()-wall_start,
        best_steps=best_steps, decisions_by_case=dict(counts), decisions_by_module=dict(module_counts),
        decisions_by_card=dict(card_counts), case_coverage=len(counts), config=config,
        frozen_source_unchanged=True, initial_weights_sha256=source_sha,
        latest_weights_sha256=weight_fingerprint(model), validations=validations)
    (args.run_dir/'report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    print(json.dumps(dict(complete=True, steps=steps, training_seconds=training_elapsed,
        cases_visited=len(counts), best_steps=best_steps)),flush=True)


if __name__ == '__main__':
    main()
