"""Measure actor/critic interference on fresh training states without updating weights.

This is a development diagnosis, not a model qualification. Rollouts use only
the acting role's permitted inputs and the usual separate training RNG namespace.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean, median

import torch

from .checkpoints import load_checkpoint, weight_fingerprint
from .parallel import ParallelGames
from .throttle import CpuBudget


def vector_gradient(loss, parameters):
    gradients = torch.autograd.grad(loss, parameters, retain_graph=True, allow_unused=True)
    return torch.cat([(torch.zeros_like(p) if g is None else g).reshape(-1)
                      for p, g in zip(parameters, gradients)])


def interference(policy, value, demonstration=None):
    """A negative policy projection means this joint descent raises policy loss."""
    demo = torch.zeros_like(policy) if demonstration is None else demonstration
    if policy.shape != value.shape or policy.shape != demo.shape:
        raise ValueError('All gradients must describe the same shared parameters.')
    norm_policy, norm_value, norm_demo = (float(g.norm()) for g in (policy, value, demo))
    dot = float(torch.dot(policy, value))
    projection = float(torch.dot(policy, policy + value + demo))
    result = {
        'policy_norm': norm_policy, 'weighted_value_norm': norm_value,
        'weighted_demo_norm': norm_demo,
        'value_policy_norm_ratio': norm_value / norm_policy if norm_policy else None,
        'policy_value_cosine': dot / (norm_policy * norm_value) if norm_policy and norm_value else None,
        'policy_value_conflict': dot < 0,
        'joint_gradient_opposes_policy': projection < 0,
        'joint_policy_projection': projection,
    }
    if not all(v is None or math.isfinite(v) for v in result.values()):
        raise ValueError('Nonfinite gradient diagnosis.')
    return result


def diagnose(model, batch, *, minibatch_size=256, value_coef=.5, uniform_mix=.03,
             demonstrations=None, demo_coef=.03, seed=0, cpu_duty_cycle=.7):
    """Use the PPO loss at rollout weights; no optimizer step or gradient mutation."""
    branch = getattr(model, 'residual', model)
    parameters = tuple(p for p in branch.encoder.parameters() if p.requires_grad)
    if not parameters:
        raise ValueError('A trainable shared encoder is required for this diagnosis.')
    advantages = batch['advantages']
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    generator = torch.Generator().manual_seed(seed)
    order = torch.randperm(len(advantages), generator=generator)
    budget = CpuBudget(cpu_duty_cycle)
    rows = []
    for indices in order.split(minibatch_size):
        guidance = {'reference_mask': batch['reference_masks'][indices]} if 'reference_masks' in batch else {}
        log_prob, _, value = model.evaluate_actions(batch['observations'][indices], batch['masks'][indices],
            batch['actions'][indices], uniform_mix=uniform_mix, **guidance)
        # At rollout weights, the unclipped PPO ratio is 1 and its derivative
        # equals the vanilla policy gradient. Keep the ratio to audit parity.
        ratio = (log_prob - batch['log_probs'][indices]).exp()
        actor_loss = -(ratio * advantages[indices]).mean()
        critic_loss = value_coef * .5 * (value - batch['returns'][indices]).square().mean()
        actor_gradient = vector_gradient(actor_loss, parameters)
        critic_gradient = vector_gradient(critic_loss, parameters)
        demo_gradient = None
        if demonstrations and demo_coef:
            selected = torch.randint(len(demonstrations['actions']), (64,), generator=generator)
            guidance = ({'reference_mask': demonstrations['reference_masks'][selected]}
                        if 'reference_masks' in demonstrations else {})
            demo_logp, _, _ = model.evaluate_actions(demonstrations['observations'][selected],
                demonstrations['masks'][selected], demonstrations['actions'][selected], **guidance)
            demo_gradient = vector_gradient(-demo_coef * demo_logp.mean(), parameters)
        row = interference(actor_gradient, critic_gradient, demo_gradient)
        row['max_rollout_ratio_error'] = float((ratio.detach() - 1).abs().max())
        rows.append(row)
        budget.pause()
    summary = {'minibatches': len(rows), 'decisions': len(advantages),
               'value_coefficient': value_coef, 'demo_coefficient': demo_coef if demonstrations else 0.,
               'entropy_gradient_included': False,
               'policy_value_conflict_fraction': mean(r['policy_value_conflict'] for r in rows),
               'joint_gradient_opposes_policy_fraction': mean(r['joint_gradient_opposes_policy'] for r in rows)}
    for key in ('policy_norm', 'weighted_value_norm', 'weighted_demo_norm',
                'value_policy_norm_ratio', 'policy_value_cosine', 'max_rollout_ratio_error'):
        values = [r[key] for r in rows if r[key] is not None]
        summary[key] = ({'mean': mean(values), 'median': median(values), 'min': min(values), 'max': max(values)}
                        if values else None)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--steps', type=int, default=8192)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--seed', type=int, default=251033)
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or args.steps < 1:
        p.error('Resource cap: 1–8 workers, duty in (0,.7]; positive decisions.')
    if args.output.exists():
        p.error('Preserve earlier reports; use a new output path.')
    torch.set_num_threads(1)
    model, payload = load_checkpoint(args.checkpoint)
    before = weight_fingerprint(model)
    config = payload['train_config']
    options = {k: config[k] for k in ('airport', 'max_steps', 'assistance_version',
                                    'round_reward', 'sync_weight', 'sync_tolerance', 'task_weight')}
    options['curriculum_airports'] = config.get('curriculum_airports', [])
    pool = ParallelGames(args.workers, model.config, options, cpu_duty_cycle=args.cpu_duty_cycle)
    try:
        batch, records = pool.collect(model, args.steps, seed=args.seed, update=0,
            gamma=.995, gae_lambda=.95, uniform_mix=config['uniform_mix'], discount_unit=config['discount_unit'])
    finally:
        pool.close()
    result = diagnose(model, batch, value_coef=config.get('value_coef', .5), uniform_mix=config['uniform_mix'],
        demonstrations=payload.get('successful_replay'), demo_coef=config['self_imitation_coef'],
        seed=args.seed, cpu_duty_cycle=args.cpu_duty_cycle)
    if weight_fingerprint(model) != before:
        raise RuntimeError('The diagnosis must not change model parameters.')
    counts = Counter()
    for record in records:
        counts[record['scenario']] += record['steps']
    report = {'format': 1, 'phase': 'development_gradient_diagnosis_only',
              'checkpoint': args.checkpoint.as_posix(), 'weights_sha256': before,
              'training_steps_at_checkpoint': payload['total_steps'], 'seed': args.seed,
              'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
              'weights_changed': False, 'independent_test_used': False,
              'decisions_by_route': dict(counts), 'episodes': len(records), 'shared_encoder': result}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
