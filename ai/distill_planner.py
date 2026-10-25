"""Bootstrap a wider policy by imitating the existing public-information player.

Teacher trajectories use training-only RNG namespaces, never validation games
from PPO or the independent qualification set. This preserves existing behavior
before exploratory PPO; it is not an expert win-rate or module qualification.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path
import random

import torch

from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint, planner_fingerprint
from .modules import ModuleEnv
from .nn_model import ResidualActorCritic
from .throttle import CpuBudget

_teacher = None
_student = None


def _initialize(path, expected_sha, student_path=None, student_sha=None):
    global _teacher, _student
    torch.set_num_threads(1)
    _teacher, _ = load_checkpoint(path)
    if weight_fingerprint(_teacher) != expected_sha:
        raise ValueError('Teacher checkpoint changed during collection.')
    if student_path:
        _student, _ = load_checkpoint(student_path)
        if weight_fingerprint(_student) != student_sha:
            raise ValueError('Student checkpoint changed during collection.')


def teacher_rows(model, airport, seeds, duty=.7, *, student=None, student_fraction=.5):
    """Only own observations, public masks and teacher probabilities are labels."""
    budget = CpuBudget(duty)
    env = ModuleEnv(airport, assistance_version=7, round_reward=0.)
    rows = {k: [] for k in ('observations', 'masks', 'teacher_masks', 'targets')}
    wins = student_decisions = 0
    for seed in seeds:
        behavior_rng = random.Random(f'{seed}:behavior')
        env.reset(seed=seed)
        if env.game.cockpit.module - {'kerosene'} or env.game.zusatz.karten:
            raise ValueError('This teacher stage supports base/fuel routes without cards.')
        while not env.done:
            observation = env.observation()
            narrow = env.action_mask()
            env.assistance_version = 9
            wide = env.action_mask()
            env.assistance_version = 7
            if any(a and not b for a, b in zip(narrow, wide)):
                raise ValueError('Teacher support must remain available to the student.')
            with torch.inference_mode():
                logits, _ = model(torch.tensor(observation, dtype=torch.float32))
                logits = logits.masked_fill(~torch.tensor(narrow), torch.finfo(logits.dtype).min)
                target = logits.softmax(-1)
                selected = int(logits.argmax())
            for key, value in zip(rows, (observation, wide, narrow, target.tolist())):
                rows[key].append(value)
            if student is not None and behavior_rng.random() < student_fraction:
                with torch.inference_mode():
                    student_logits, _ = student(torch.tensor(observation, dtype=torch.float32))
                    selected = int(student_logits.masked_fill(~torch.tensor(wide), torch.finfo(student_logits.dtype).min).argmax())
                student_decisions += 1
            # DAgger labels still come from the fixed teacher, while execution
            # may visit states produced by the wider student's own decisions.
            env.assistance_version = 9 if student is not None else 7
            env.step(selected)
            env.assistance_version = 7
            budget.pause()
        wins += env.game.status == 'gewonnen'
    tensors = {k: torch.tensor(v, dtype=torch.bool if k.endswith('masks') else torch.float32) for k, v in rows.items()}
    return tensors, {'route': airport, 'games': len(seeds), 'wins': wins, 'decisions': len(rows['targets']),
                     'student_decisions': student_decisions}


def _collect(task):
    route, seeds, duty, fraction = task
    return teacher_rows(_teacher, route, seeds, duty, student=_student, student_fraction=fraction)


def distillation_loss(logits, masks, targets):
    logp = logits.masked_fill(~masks, torch.finfo(logits.dtype).min).log_softmax(-1)
    return -(targets * logp).sum(-1).mean()


def metrics(model, data, size=512):
    device = next(model.parameters()).device
    loss = entropy = agreement = support = 0.
    n = len(data['targets'])
    with torch.inference_mode():
        for start in range(0, n, size):
            rows = {k: v[start:start + size].to(device) for k, v in data.items()}
            logits, _ = model(rows['observations'])
            masked = logits.masked_fill(~rows['masks'], torch.finfo(logits.dtype).min)
            count = len(logits)
            loss += count * float(distillation_loss(logits, rows['masks'], rows['targets']))
            entropy += float(-(rows['targets'] * rows['targets'].clamp_min(1e-30).log()).sum())
            agreement += int((masked.argmax(-1) == rows['targets'].argmax(-1)).sum())
            support += float((masked.softmax(-1) * rows['teacher_masks']).sum())
    return {'examples': n, 'cross_entropy': loss / n, 'kl': max(0., (loss - entropy) / n),
            'teacher_action_agreement': agreement / n, 'teacher_support_mass': support / n}


def make_student(source):
    model = ResidualActorCritic(source, source.config['observation_size'], source.config['action_count'])
    if isinstance(source, ResidualActorCritic) and source.residual.config['hidden_size'] == 256 and source.residual.config['hidden_layers'] == 2:
        model.residual.encoder.load_state_dict(source.residual.encoder.state_dict())
    # Policy-only warm-up avoids moving the inherited value function.
    model.residual.critic.requires_grad_(False)
    return model


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--student', type=Path, help='Existing student for DAgger; the original teacher remains fixed.')
    p.add_argument('--initial-data', type=Path, help='Earlier training/validation teacher-data.pt to aggregate.')
    p.add_argument('--student-fraction', type=float, default=.5)
    p.add_argument('--routes', nargs='+', default=['LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN', 'LOG_YUL_GREEN'])
    p.add_argument('--train-games-per-route', type=int, default=100)
    p.add_argument('--validation-games-per-route', type=int, default=25)
    p.add_argument('--epochs', type=int, default=40)
    p.add_argument('--seed', type=int, default=251028)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--device', default='mps')
    args = p.parse_args()
    if args.run_dir.exists(): p.error('Use a new run directory.')
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7:
        p.error('Resource cap: 1–8 workers, at most .7 CPU duty.')
    if min(args.train_games_per_route, args.validation_games_per_route, args.epochs) < 1:
        p.error('Positive data and epoch budgets required.')
    if bool(args.student) != bool(args.initial_data) or not 0 <= args.student_fraction <= 1:
        p.error('DAgger requires both --student and --initial-data; fraction must be in [0,1].')
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    source, payload = load_checkpoint(args.source)
    if source.config['observation_size'] != 489 or source.config['action_count'] != 217:
        p.error('This stage requires a schema-3 teacher.')
    sha = weight_fingerprint(source)
    initial = student_sha = None
    if args.student:
        student_model, student_payload = load_checkpoint(args.student)
        if not isinstance(student_model, ResidualActorCritic) or weight_fingerprint(student_model.source) != sha:
            p.error('DAgger student must retain this exact frozen teacher.')
        if student_payload.get('teacher_source_weights_sha256') != sha:
            p.error('Student teacher provenance mismatch.')
        student_model.residual.critic.requires_grad_(False)
        student_sha = weight_fingerprint(student_model)
        initial = torch.load(args.initial_data, map_location='cpu', weights_only=True)
        if len(initial['train']['targets']) != student_payload.get('policy_pretraining_examples'):
            p.error('Initial data does not match the student training-example count.')
    args.run_dir.mkdir(parents=True)
    report = {'format': 1, 'phase': 'policy_bootstrap_only', 'goal_achieved': False,
        'independent_test_used': False, 'source': str(args.source), 'source_weights_sha256': sha,
        'source_phase_decisions': payload.get('total_steps'), 'inherited_module_steps': payload.get('module_training_steps', 0),
        'planner_sha256': planner_fingerprint(3), 'teacher_assistance_version': 7, 'student_assistance_version': 9,
        'seed': args.seed, 'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle,
        'student_start': str(args.student) if args.student else None, 'student_weights_sha256': student_sha,
        'initial_data': str(args.initial_data) if args.initial_data else None,
        'student_behavior_fraction': args.student_fraction if args.student else 0.,
        'dataset_games': {}, 'epochs': []}
    datasets = {}
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=_initialize, initargs=(str(args.source), sha, str(args.student) if args.student else None, student_sha)) as pool:
        for split, games in (('train', args.train_games_per_route), ('validation', args.validation_games_per_route)):
            tasks = []
            for route in args.routes:
                for start in range(0, games, 10):
                    seeds = [f'planner-teacher:{args.seed}:{split}:{route}:{i}' for i in range(start, min(games, start + 10))]
                    tasks.append((route, seeds, args.cpu_duty_cycle, args.student_fraction))
            outputs = list(pool.map(_collect, tasks))
            datasets[split] = {k: torch.cat([data[k] for data, _ in outputs]) for k in outputs[0][0]}
            if initial:
                datasets[split] = {k: torch.cat((initial[split][k], v)) for k, v in datasets[split].items()}
            report['dataset_games'][split] = [r for _, r in outputs]
            print(json.dumps({'split': split, 'examples': len(datasets[split]['targets'])}), flush=True)
    torch.save(datasets, args.run_dir / 'teacher-data.pt')
    model = (student_model if args.student else make_student(source)).to(args.device)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=3e-4)
    generator = torch.Generator().manual_seed(args.seed + 1)
    budget = CpuBudget(args.cpu_duty_cycle)
    config = {**payload['train_config'], 'assistance_version': 9, 'planner_sha256': planner_fingerprint(3)}
    rule_examples = payload.get('rule_pretraining_examples', config.get('rule_pretraining_examples', 0))
    best = float('inf')

    def validate(epoch):
        nonlocal best
        result = {'epoch': epoch, **metrics(model, datasets['validation'])}
        report['epochs'].append(result)
        if result['kl'] < best:
            best = result['kl']
            report['best_epoch'] = epoch
            save_checkpoint(args.run_dir / 'distilled.pt', model, train_config=config,
                total_steps=0, module_training_steps=payload.get('module_training_steps', 0),
                rule_pretraining_examples=rule_examples, policy_pretraining_examples=len(datasets['train']['targets']),
                teacher_source_weights_sha256=sha, teacher_source_phase_decisions=payload.get('total_steps'))
        (args.run_dir / 'distillation.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(result), flush=True)

    validate(0)
    for epoch in range(1, args.epochs + 1):
        model.train()
        permutation = torch.randperm(len(datasets['train']['targets']), generator=generator)
        for indices in permutation.split(512):
            batch = {k: v[indices].to(args.device) for k, v in datasets['train'].items()}
            logits, _ = model(batch['observations'])
            loss = distillation_loss(logits, batch['masks'], batch['targets'])
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            optimizer.step()
            budget.pause()
        model.eval()
        validate(epoch)
    if weight_fingerprint(model.source) != sha:
        raise RuntimeError('The frozen teacher changed during distillation.')


if __name__ == '__main__':
    main()
