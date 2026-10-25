"""Opt-in offline actor-head refinement from explicit human thumbs.

Run only as a separate controlled job, for example::

    nice -n15 python -m ai.job_control run -- python -m ai.train_feedback \
        --checkpoint ai/releases/crew2-v1/best.pt --data exported-feedback.json \
        --run-dir runs/feedback-candidate-v1

This never publishes or alters a release. Current sparse schema-1 archives do
not meet the data threshold and cannot be padded into a schema-3 model.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path

import torch

from .checkpoints import load_checkpoint, model_schema, save_checkpoint, weight_fingerprint
from .feedback import load_feedback
from .throttle import CpuBudget


def session_split(session_ids, *, seed=251046, validation_fraction=.25):
    """Keep every rated move from a session wholly on one side."""
    sessions = sorted(set(session_ids), key=lambda name: hashlib.sha256(f'{seed}:{name}'.encode()).digest())
    if len(sessions) < 2 or not 0 < validation_fraction < 1:
        raise ValueError('Session validation needs at least two groups and a fraction in (0,1).')
    count = min(len(sessions)-1, max(1, math.ceil(len(sessions)*validation_fraction)))
    held_out = set(sessions[:count])
    return ([index for index, name in enumerate(session_ids) if name not in held_out],
            [index for index, name in enumerate(session_ids) if name in held_out])


def _head(model):
    kind = model.config.get('kind')
    if kind in ('guided_residual', 'residual'):
        return model.residual.actor
    if kind is None:
        return model.actor
    raise ValueError('Offline feedback supports a shared actor or its existing residual head.')


def _distribution(model, batch):
    guidance = {'reference_mask': batch['reference_masks']} if model.config.get('kind') == 'guided_residual' else {}
    return model.distribution(batch['observations'], batch['masks'], **guidance)[0]


def feedback_loss(distribution, actions, ratings):
    """Positive likelihood and negative unlikelihood, with finite extremes."""
    log_probability = distribution.log_prob(actions)
    negative = -torch.log1p(-log_probability.exp().clamp(max=1-1e-6))
    return torch.where(ratings > 0, -log_probability, negative).mean()


def candidate_config(source_config, *, feedback_sha, source_sha, source_checkpoint):
    """Changed weights never inherit the source release's approval or routes."""
    stale = {'quality', 'approved', 'recommended', 'display_name', 'name', 'id', 'release_id'}
    result = {key: deepcopy(value) for key, value in source_config.items()
              if key not in stale and not key.startswith('supported_')}
    result.update(research_offline_feedback=True, feedback_actor_only=True,
        feedback_sha256=feedback_sha, feedback_source_weights_sha256=source_sha,
        feedback_source_checkpoint=str(source_checkpoint),
        publication_status='unqualified_offline_candidate', recommended=False,
        display_name='Offline feedback research candidate', supported_airports=[],
        quality={'approved': False, 'reason': 'Changed actor head requires fresh independent qualification.'})
    return result


def refine_actor(model, dataset, *, learning_rate=1e-4, epochs=4, batch_size=64,
                 feedback_coefficient=.02, kl_coefficient=1., maximum_validation_kl=.01,
                 seed=251046, cpu_duty_cycle=.7, minimum_labels=64, minimum_sessions=4):
    """Change ONLY the current actor head; encoders/base/critic remain exact.

    The initial head is eligible. A trained head is retained only when a whole
    held-out session improves and its full masked-policy KL stays bounded.
    This is a weak-preference check, not a route win-rate qualification.
    """
    if (not 0 < learning_rate <= 1e-3 or type(epochs) is not int or not 1 <= epochs <= 8 or
            type(batch_size) is not int or batch_size < 1 or not 0 < feedback_coefficient <= .05 or
            not math.isfinite(kl_coefficient) or kl_coefficient < .1 or
            not 0 < maximum_validation_kl <= .05 or not 0 < cpu_duty_cycle <= .7 or
            type(minimum_labels) is not int or minimum_labels < 64 or
            type(minimum_sessions) is not int or minimum_sessions < 4):
        raise ValueError('Use bounded learning/epochs, weak feedback, positive KL and duty <= .7.')
    schema = model_schema(model)
    if dataset.manifest['schema_version'] != schema['version']:
        raise ValueError('Feedback and model schemas differ; padding is forbidden.')
    if model.config.get('kind') == 'guided_residual' and dataset.reference_masks is None:
        raise ValueError('Guided refinement requires original saved reference masks.')
    count = len(dataset.actions)
    if (any(len(rows) != count for rows in (dataset.observations, dataset.masks, dataset.ratings, dataset.session_ids)) or
            any(type(rating) is not int or rating not in (-1, 1) for rating in dataset.ratings)):
        raise ValueError('Feedback rows/labels are inconsistent.')
    informative = [index for index, mask in enumerate(dataset.masks) if sum(mask) > 1]
    sessions = [dataset.session_ids[index] for index in informative]
    if len(informative) < minimum_labels or len(set(sessions)) < minimum_sessions:
        raise ValueError(f'Insufficient feedback: need {minimum_labels} informative labels from '
                         f'{minimum_sessions} sessions; found {len(informative)} from {len(set(sessions))}.')
    train_local, valid_local = session_split(sessions, seed=seed)
    train_indices = [informative[index] for index in train_local]
    valid_indices = [informative[index] for index in valid_local]
    if len(train_indices) < minimum_labels // 2 or len(valid_indices) < max(2, minimum_labels // 8):
        raise ValueError('Whole-session split has too few training/validation ratings; collect more sessions.')
    device = next(model.parameters()).device
    data = dataset.tensors(device)
    names = tuple(name for name in data if name != 'ratings')
    head = _head(model)
    active_ids = {id(parameter) for parameter in head.parameters()}
    if not active_ids:
        raise ValueError('The source has no trainable actor head.')
    active_names = {name for name, parameter in model.named_parameters() if id(parameter) in active_ids}
    fixed = {name: value.detach().clone() for name, value in model.state_dict().items()
             if name not in active_names}
    original = deepcopy(model).eval().requires_grad_(False)
    flags = [(parameter, parameter.requires_grad) for parameter in model.parameters()]
    was_training = model.training
    optimizer = torch.optim.Adam(head.parameters(), lr=learning_rate, eps=1e-5)
    generator = torch.Generator(device='cpu').manual_seed(seed)
    budget = CpuBudget(cpu_duty_cycle)

    def batch(indices):
        selected = torch.tensor(indices, dtype=torch.long, device=device)
        return {name: data[name][selected] for name in (*names, 'ratings')}

    validation = batch(valid_indices)
    with torch.no_grad():
        reference_validation = _distribution(original, validation)
        baseline_loss = float(feedback_loss(reference_validation, validation['actions'], validation['ratings']))
    best, best_loss, best_epoch = deepcopy(head.state_dict()), baseline_loss, 0
    history = []
    try:
        for parameter in model.parameters(): parameter.requires_grad_(id(parameter) in active_ids)
        model.eval()
        for epoch in range(1, epochs+1):
            order = torch.randperm(len(train_indices), generator=generator).tolist()
            losses = []
            for start in range(0, len(order), batch_size):
                rows = batch([train_indices[index] for index in order[start:start+batch_size]])
                with torch.no_grad():
                    reference = _distribution(original, rows)
                current = _distribution(model, rows)
                preference = feedback_loss(current, rows['actions'], rows['ratings'])
                kl = torch.distributions.kl_divergence(reference, current).mean()
                loss = feedback_coefficient*preference + kl_coefficient*kl
                if not torch.isfinite(loss): raise ValueError('Nonfinite offline feedback loss.')
                optimizer.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(head.parameters(), .1)
                optimizer.step()
                losses.append(float(loss.detach()))
                budget.pause()
            with torch.no_grad():
                current = _distribution(model, validation)
                valid_loss = float(feedback_loss(current, validation['actions'], validation['ratings']))
                valid_kl = float(torch.distributions.kl_divergence(reference_validation, current).mean())
            if not math.isfinite(valid_loss) or not math.isfinite(valid_kl):
                raise ValueError('Nonfinite offline validation; original head restored.')
            history.append({'epoch': epoch, 'train_objective': sum(losses)/len(losses),
                            'validation_feedback_loss': valid_loss, 'validation_policy_kl': valid_kl})
            if valid_loss < best_loss-1e-6 and valid_kl <= maximum_validation_kl:
                best, best_loss, best_epoch = deepcopy(head.state_dict()), valid_loss, epoch
        head.load_state_dict(best)
        if any(not torch.equal(model.state_dict()[name], value) for name, value in fixed.items()):
            raise RuntimeError('Offline feedback changed a frozen encoder/base/critic tensor.')
    except BaseException:
        head.load_state_dict(_head(original).state_dict())
        raise
    finally:
        for parameter, required in flags: parameter.requires_grad_(required)
        model.train(was_training)
    return {'complete': True, 'candidate_accepted': best_epoch > 0, 'best_epoch': best_epoch,
            'baseline_validation_feedback_loss': baseline_loss, 'selected_validation_feedback_loss': best_loss,
            'training_labels': len(train_indices), 'validation_labels': len(valid_indices),
            'train_sessions': sorted({dataset.session_ids[index] for index in train_indices}),
            'validation_sessions': sorted({dataset.session_ids[index] for index in valid_indices}),
            'ignored_single_choice_labels': len(dataset.actions)-len(informative),
            'feedback_coefficient': feedback_coefficient, 'kl_coefficient': kl_coefficient,
            'maximum_validation_kl': maximum_validation_kl, 'history': history,
            'frozen_base_encoders_and_critic_unchanged': True, 'release_evidence': False,
            'goal_achieved': False, 'on_policy_rollouts': False, 'dataset': dataset.manifest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--data', nargs='+', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--device', default='cpu')
    parser.add_argument('--epochs', type=int, default=4)
    parser.add_argument('--seed', type=int, default=251046)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args()
    if args.run_dir.exists(): parser.error('Use a new run directory; preserve existing models.')
    if Path('runs/STOP_AI_TRAINING').exists(): parser.error('Training stop is active; explicit resumption is required.')
    torch.set_num_threads(1)
    model, payload = load_checkpoint(args.checkpoint, args.device)
    original_sha = weight_fingerprint(model)
    try:
        dataset = load_feedback(args.data, schema_version=model_schema(model)['version'],
            require_reference_masks=model.config.get('kind') == 'guided_residual')
        result = refine_actor(model, dataset, epochs=args.epochs, seed=args.seed,
                              cpu_duty_cycle=args.cpu_duty_cycle)
    except ValueError as exc:
        parser.error(str(exc))
    result.update(source_checkpoint=args.checkpoint.as_posix(), source_weights_sha256=original_sha,
                  candidate_weights_sha256=weight_fingerprint(model), seed=args.seed)
    args.run_dir.mkdir(parents=True)
    save_checkpoint(args.run_dir/'candidate.pt', model,
        train_config=candidate_config(payload.get('train_config', {}),
            feedback_sha=dataset.manifest['sha256'], source_sha=original_sha,
            source_checkpoint=args.checkpoint),
        total_steps=payload.get('total_steps', 0), new_environment_decisions=0,
        module_training_steps=payload.get('module_training_steps', 0),
        feedback_refinement=result)
    (args.run_dir/'report.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({key: result[key] for key in ('candidate_accepted', 'best_epoch', 'training_labels',
        'validation_labels', 'frozen_base_encoders_and_critic_unchanged', 'release_evidence')}))


if __name__ == '__main__':
    main()
