"""Bounded, new shielded PPO phase; matched self-play or frozen partner pool.

Fresh optimizer/counters, unchanged inherited tensors at initialization. No
automatic publication, no real hidden dice, no development examples in replay.
Run through ai.job_control --max-temperature 75 run -- ... .
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time

import torch

from .agents import ModelAgent
from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint
from .evaluate import summarize_episodes
from .module_training_eval import balanced_cases, case_key, _development_seed
from .modules import ModuleEnv
from .nn_model import build_model
from .preview_matrix_eval import catalogue_cases
from .robust_policy import RobustBlueprint
from .safe_environment import SafeResearchEnv
from .train import collect_rollout, ppo_update
from .train_fuel import successful_replay


_model = _options = _partners = None


def phase_fingerprint():
    digest = hashlib.sha256()
    for name in ('train_robust.py', 'safe_environment.py', 'robust_policy.py', 'safety_guard.py',
                 'belief_simulator.py', 'rollout_search.py'):
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def initialize(config, options, partners):
    global _model, _options, _partners
    torch.set_num_threads(1)
    _model, _options = build_model(config), options
    _partners = {name: load_checkpoint(path)[0].eval() for name, path in partners.items()}


def collect(task):
    weights, steps, seed, update, ordinal, identity, role = task
    _model.load_state_dict(weights)
    torch.manual_seed(seed + update*1009 + ordinal)
    partner = ModelAgent(_model if identity == 'self' else _partners[identity])
    batch, records = collect_rollout(_model, SafeResearchEnv(**_options), steps,
        seed=f'robust:{seed}:{update}:{ordinal}', episodes_done=0, gamma=.995,
        gae_lambda=.95, uniform_mix=.03, discount_unit='placement',
        partner=partner, ai_role=role)
    for row in records:
        row.update(partner_id=identity, learner_role=role)
    if sum(row['steps'] for row in records) != len(batch['actions']):
        raise RuntimeError('Partner decisions contaminated learner counters.')
    return batch, records


def evaluate_case(task):
    weights, case, games, seed = task
    _development_seed(seed, games)
    _model.load_state_dict(weights)
    _model.eval()
    policy = RobustBlueprint(case['airport'], _model)
    env = ModuleEnv(case['airport'], abilities=case['abilities'], assistance_version=0,
                    round_reward=0., sync_weight=0., task_weight=0.)
    records = []
    for ordinal in range(games):
        env.reset(seed=seed+ordinal)
        total = 0.
        while not env.done:
            action = policy.select(env.view(), env.action_mask())
            _, reward, _, _, _ = env.step(action)
            total += reward
        records.append(env.episode_record(seed+ordinal, 'both', total))
    return dict(case_key=case_key(case), case=case, clock_model='engine_wall_clock',
                release_evidence=False, **summarize_episodes(records))


def score(rows):
    routes = defaultdict(list)
    for row in rows.values():
        routes[row['case']['airport']].append(row['win_rate'])
    means = [sum(values)/len(values) for values in routes.values()]
    return sum(means)/len(means), min(means)


def load_teacher(path):
    payload = torch.load(path, map_location='cpu', weights_only=True)
    if not payload.get('training_seed_namespace', '').startswith('train:'):
        raise ValueError('Only explicitly namespaced training search examples are allowed.')
    data = payload['data']
    count = len(data['actions'])
    if (not count or data['actions'].dtype != torch.long or data['masks'].dtype != torch.bool
            or data['reference_masks'].dtype != torch.bool
            or data['observations'].shape != (count,489) or data['masks'].shape != (count,217)
            or data['reference_masks'].shape != (count,217)
            or data['weights'].shape != (count,) or not torch.isfinite(data['observations']).all()
            or not torch.isfinite(data['weights']).all() or not (data['weights'] > 0).all()
            or not ((data['actions'] >= 0) & (data['actions'] < 217)).all()
            or not data['masks'][torch.arange(count),data['actions']].all()
            or not data['reference_masks'].any(-1).all()
            or (data['reference_masks'] & ~data['masks']).any()):
        raise ValueError('Search labels violate the observation/action/reference schema.')
    return payload


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--partner-mode', choices=('self', 'population'), required=True)
    p.add_argument('--seconds', type=float, default=1200.)
    p.add_argument('--steps', type=int, default=1_000_000)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--seed', type=int, default=281001)
    p.add_argument('--eval-seed', type=int, default=14910000)
    p.add_argument('--eval-games', type=int, default=5)
    p.add_argument('--eval-interval', type=float, default=300.)
    p.add_argument('--device', default='cpu')
    p.add_argument('--learning-rate', type=float, default=5e-5)
    p.add_argument('--demonstrations', type=Path)
    p.add_argument('--imitation-weight', type=float, default=.03)
    args = p.parse_args()
    if (not 1 <= args.workers <= 8 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 6*3600
            or args.steps < 1 or not 1 <= args.eval_games <= 100 or not args.eval_interval > 0
            or not math.isfinite(args.learning_rate) or args.learning_rate <= 0
            or not math.isfinite(args.imitation_weight) or not 0 <= args.imitation_weight <= 1):
        p.error('Use bounded positive budgets and at most eight workers.')
    if args.run_dir.exists():
        p.error('Preserve prior runs; use a new run directory.')
    if Path('runs/STOP_AI_TRAINING').exists():
        p.error('Persistent user stop is active.')
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    model, _ = load_checkpoint(args.source, args.device)
    if model.config.get('kind') != 'guided_residual' or model.config['observation_size'] != 489:
        p.error('Use a guided schema-3 source without architectural changes.')
    initial_sha = weight_fingerprint(model)
    frozen_sha = weight_fingerprint(model.source)
    partners = ({f'crew{i}': f'ai/releases/crew{i}-allroutes-2026-10-26-v1/best.pt'
                 for i in (1, 2, 3)} if args.partner_mode == 'population' else {})
    cases = catalogue_cases()
    route_cases = list({row['airport']: row for row in reversed(cases)}.values())
    route_cases.sort(key=case_key)
    _development_seed(args.eval_seed, (len(route_cases)-1)*100 + args.eval_games)
    options = dict(airport='MUC', abilities=[], curriculum_cases=balanced_cases(cases),
                   assistance_version=12, round_reward=0., sync_weight=.05,
                   task_weight=.02, max_steps=192)
    config = dict(source=args.source, initial_weights_sha256=initial_sha,
        frozen_source_weights_sha256=frozen_sha, partner_mode=args.partner_mode,
        partners=partners, options=options, workers=args.workers, seed=args.seed,
        phase_sha256=phase_fingerprint(), policy='research_safe_wide_profile12',
        eval_seed=args.eval_seed, eval_games=args.eval_games, eval_cases=route_cases,
        device=args.device, learning_rate=args.learning_rate, seconds=args.seconds,
        steps=args.steps, release_evidence=False, training_clock='logical_seconds_per_decision')
    teacher = load_teacher(args.demonstrations) if args.demonstrations else None
    config.update(demonstrations=str(args.demonstrations) if args.demonstrations else None,
                  teacher_weights_sha256=teacher['source_weights_sha256'] if teacher else None,
                  imitation_weight=args.imitation_weight)
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'config.json').write_text(json.dumps(config, indent=2)+'\n')
    optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=args.learning_rate, eps=1e-5)
    steps = episodes = update = 0
    elapsed = 0.
    replay = None
    best = None
    counts, partner_counts = Counter(), Counter()
    demo_rng = torch.Generator().manual_seed(args.seed + 37)
    teacher_rows = None
    if teacher:
        selected = torch.multinomial(teacher['data']['weights'], min(8192, len(teacher['data']['actions'])),
                                     replacement=True, generator=demo_rng)
        teacher_rows = {key: teacher['data'][key][selected].to(args.device)
                        for key in ('observations','masks','reference_masks','actions')}
    validations = []
    started = time.monotonic()

    def weights():
        return {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    def save(name):
        if weight_fingerprint(model.source) != frozen_sha:
            raise RuntimeError('Frozen inherited source changed.')
        save_checkpoint(args.run_dir/name, model, train_config=config, total_steps=steps,
            episodes=episodes, update=update, optimizer_state=optimizer.state_dict(),
            torch_rng_state=torch.get_rng_state(), training_elapsed_seconds=elapsed)

    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=initialize, initargs=(model.config, options, partners)) as pool:
        def validate():
            nonlocal best
            rows = {row['case_key']: row for row in pool.map(evaluate_case,
                [(weights(), case, args.eval_games, args.eval_seed + i*100) for i, case in enumerate(route_cases)])}
            value = score(rows)
            result = dict(steps=steps, score=value, results=rows, release_evidence=False)
            validations.append(dict(steps=steps, score=value))
            (args.run_dir/f'evaluation-{steps:09d}.json').write_text(json.dumps(result, indent=2)+'\n')
            if best is None or value > best:
                best = value
                save('best.pt')
            print(json.dumps(dict(validation=True, steps=steps, score=value)), flush=True)

        save('initial.pt')
        validate()
        last_eval = time.monotonic()
        try:
            while elapsed < args.seconds and steps < args.steps:
                tick = time.monotonic()
                styles = ['self'] if args.partner_mode == 'self' else ['self', 'self', *partners]
                tasks = []
                current_weights = weights()
                for ordinal in range(args.workers):
                    number = update*args.workers + ordinal
                    identity = styles[(number//2) % len(styles)]
                    role = 'pilot' if number % 2 == 0 else 'kopilot'
                    tasks.append((current_weights, 256, args.seed, update, ordinal, identity, role))
                outputs = list(pool.map(collect, tasks))
                batch = {key: torch.cat([row[0][key] for row in outputs]).to(args.device) for key in outputs[0][0]}
                records = [record for _, rows in outputs for record in rows]
                replay = successful_replay(batch, records, replay, limit=8192)
                examples = replay
                if teacher_rows:
                    examples = ({key: torch.cat((teacher_rows[key], replay[key])) for key in teacher_rows}
                                if replay else teacher_rows)
                stats = ppo_update(model, optimizer, batch, epochs=4, minibatch_size=256,
                    entropy_coef=.01, uniform_mix=.03, demonstrations=examples,
                    demo_coef=args.imitation_weight if examples else 0., demo_generator=demo_rng)
                steps += len(batch['actions'])
                episodes += len(records)
                update += 1
                elapsed += time.monotonic() - tick
                for row in records:
                    counts[case_key(dict(airport=row['scenario'], abilities=row['abilities']))] += row['steps']
                    partner_counts[row['partner_id']+'/'+row['learner_role']] += row['steps']
                if sum(counts.values()) != steps:
                    raise RuntimeError('Per-case learner counters disagree.')
                log = dict(steps=steps, episodes=episodes, update=update,
                    training_seconds=elapsed, wins=sum(r['status']=='gewonnen' for r in records),
                    games=len(records), decisions_by_case=dict(counts),
                    decisions_by_partner_role=dict(partner_counts), **stats)
                with (args.run_dir/'training.jsonl').open('a') as stream:
                    stream.write(json.dumps(log)+'\n')
                save('latest.pt')
                print(json.dumps({k: log[k] for k in ('steps','update','training_seconds','wins','games')}), flush=True)
                if time.monotonic() - last_eval >= args.eval_interval:
                    validate()
                    last_eval = time.monotonic()
            validate()
        finally:
            save('latest.pt')
    report = dict(complete=True, release_evidence=False, steps=steps, episodes=episodes,
                  training_seconds=elapsed, total_wall_seconds=time.monotonic()-started,
                  best_score=best, validations=validations,
                  decisions_by_case=dict(counts), decisions_by_partner_role=dict(partner_counts))
    (args.run_dir/'report.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
