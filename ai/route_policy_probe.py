"""Passive action attribution and actor-gradient diagnosis on training states.

No optimizer, policy update, held-out integer seeds or release qualification.
Counterfactual choices receive only the acting role's permitted observation.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import multiprocessing
from pathlib import Path

import torch

from .checkpoints import load_checkpoint, weight_fingerprint
from .gradient_probe import vector_gradient
from .planner_probe import action_signature
from .search_environment import OpenRiskEnv
from .search_evaluate import search_fingerprint
from .throttle import CpuBudget
from .train import collect_rollout


class PolicyProbeEnv(OpenRiskEnv):
    """Observe existing rollouts without changing masks, draws or actions."""
    def __init__(self, *args, control, candidate, uniform_mix, **kwargs):
        self.control, self.candidate, self.uniform_mix = control, candidate, uniform_mix
        self.probe_routes, self.probe_counts, self.probe_transitions = [], {}, {}
        self._probe_info = None
        super().__init__(*args, **kwargs)

    def info(self):
        info = super().info()
        self._probe_info = info
        return info

    def step(self, action):
        info, view = self._probe_info, self.view()
        mask = torch.tensor(info['action_mask'], dtype=torch.bool)
        source = torch.tensor(info['source_action_mask'], dtype=torch.bool)
        reference = torch.tensor(info['reference_action_mask'], dtype=torch.bool)
        observation = torch.tensor(self.observation(), dtype=torch.float32)
        with torch.no_grad():
            old, _ = self.control.policy_output(observation, reference)
            new, _ = self.candidate.policy_output(observation, reference)
            previous = int(old.masked_fill(~source, -torch.inf).argmax())
            warm = int(old.masked_fill(~mask, -torch.inf).argmax())
            learned = int(new.masked_fill(~mask, -torch.inf).argmax())
            extra = mask & ~source
            old_mass = old.masked_fill(~mask, -torch.inf).softmax(-1)
            new_mass = new.masked_fill(~mask, -torch.inf).softmax(-1)
            uniform = mask.float() / mask.sum()
            old_sampling = (1 - self.uniform_mix) * old_mass + self.uniform_mix * uniform
            new_sampling = (1 - self.uniform_mix) * new_mass + self.uniform_mix * uniform
        # Route identity is public metadata, not another hand or a future draw.
        route = self.game.landung.get_code()
        self.probe_routes.append(route)
        totals = self.probe_counts.setdefault(route, Counter())
        signature = lambda i: action_signature(view, self.actions[i], self.slots)
        old_change = learned != warm and bool(source[learned]) and bool(source[warm])
        totals.update(decisions=1, extra_offered=int(extra.any()),
            sampled_extra=int(not source[action]), greedy_extra=int(not source[learned]),
            mask_changes=int(previous != warm), learning_changes=int(warm != learned),
            learning_changes_inside_source=int(old_change),
            semantic_mask_changes=int(signature(previous) != signature(warm)),
            semantic_learning_changes=int(signature(warm) != signature(learned)),
            control_policy_proposal_mass=float(old_mass[extra].sum()),
            candidate_policy_proposal_mass=float(new_mass[extra].sum()),
            control_sampling_proposal_mass=float(old_sampling[extra].sum()),
            candidate_sampling_proposal_mass=float(new_sampling[extra].sum()))
        if old_change:
            def kind(i):
                a = self.actions[i]
                return a.kind + (':' + self.slots[a.slot].target if a.kind == 'place' else '')
            self.probe_transitions.setdefault(route, Counter())[kind(warm) + ' -> ' + kind(learned)] += 1
        return super().step(action)


def gradient_geometry(gradients, weights):
    """Projection concerns this sampled, infinitesimal actor-only surrogate."""
    if not gradients or set(gradients) != set(weights) or any(v <= 0 for v in weights.values()):
        raise ValueError('Matching gradients and positive weights required.')
    total = sum(weights.values())
    combined = sum(gradients[k] * (weights[k] / total) for k in gradients)
    rows, pairs = {}, []
    for route, gradient in gradients.items():
        norm = float(gradient.norm())
        projection = float(torch.dot(gradient, combined))
        rows[route] = dict(norm=norm, weight=weights[route] / total,
                           combined_projection=projection, combined_opposes_route=projection < 0)
    keys = list(gradients)
    for i, left in enumerate(keys):
        for right in keys[i + 1:]:
            a, b = gradients[left], gradients[right]
            denominator = float(a.norm() * b.norm())
            dot = float(torch.dot(a, b))
            pairs.append(dict(left=left, right=right, cosine=dot / denominator if denominator else None,
                              conflict=dot < 0))
    return dict(routes=rows, pairs=pairs)


def actor_gradients(model, batch, route_labels, episode_halves, *, uniform_mix, duty=.7):
    """No .backward(), optimizer step or existing .grad assignment."""
    if len(route_labels) != len(batch['actions']) or len(episode_halves) != len(route_labels):
        raise ValueError('Every decision needs one public route and episode split.')
    parameters = tuple(model.residual.encoder.parameters()) + tuple(model.residual.actor.parameters())
    encoder_size = sum(p.numel() for p in model.residual.encoder.parameters())
    advantages = batch['advantages']
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    routes = sorted(set(route_labels))
    gradients, halves, weights, errors = {}, {}, {}, []
    budget = CpuBudget(duty)
    for route in routes:
        indices = torch.tensor([i for i, label in enumerate(route_labels) if label == route])
        weights[route] = len(indices)
        gradients[route] = torch.zeros(sum(p.numel() for p in parameters))
        half_sums = [torch.zeros_like(gradients[route]), torch.zeros_like(gradients[route])]
        half_counts = [0, 0]
        for half in (0, 1):
            subset = indices[torch.tensor([episode_halves[i] == half for i in indices.tolist()])]
            for selected in subset.split(256):
                if not len(selected):
                    continue
                logp, _, _ = model.evaluate_actions(batch['observations'][selected], batch['masks'][selected],
                    batch['actions'][selected], uniform_mix=uniform_mix,
                    reference_mask=batch['reference_masks'][selected])
                ratio = (logp - batch['log_probs'][selected]).exp()
                loss = -(ratio * advantages[selected]).mean()
                gradient = vector_gradient(loss, parameters).detach()
                gradients[route] += gradient * (len(selected) / len(indices))
                half_sums[half] += gradient * len(selected)
                half_counts[half] += len(selected)
                errors.append(float((ratio.detach() - 1).abs().max()))
                budget.pause()
        a, b = half_sums
        denominator = float(a.norm() * b.norm())
        halves[route] = dict(decisions=half_counts,
            actor_cosine=float(torch.dot(a, b)) / denominator if denominator else None,
            encoder_cosine=(float(torch.dot(a[:encoder_size], b[:encoder_size])) /
                float(a[:encoder_size].norm() * b[:encoder_size].norm()))
                if float(a[:encoder_size].norm() * b[:encoder_size].norm()) else None)
    return dict(full_actor=gradient_geometry(gradients, weights),
        shared_encoder=gradient_geometry({r:g[:encoder_size] for r,g in gradients.items()}, weights),
        independent_episode_halves=halves, max_rollout_ratio_error=max(errors),
        value_entropy_imitation_gradients_included=False,
        note='A noisy local actor-only diagnosis; neither a causal proof nor a predicted change in win rate.')


_candidate, _control, _options, _mix, _duty = None, None, None, None, None


def _initialize(paths, fingerprints, duty):
    global _candidate, _control, _options, _mix, _duty
    torch.set_num_threads(1)
    _control, _ = load_checkpoint(paths['source'])
    _candidate, payload = load_checkpoint(paths['candidate'])
    for name, model in [('source', _control), ('candidate', _candidate)]:
        if weight_fingerprint(model) != fingerprints[name]:
            raise ValueError('Use finished, unchanged checkpoints.')
    config = payload['train_config']
    _options = {k:config[k] for k in ('airport', 'max_steps', 'assistance_version',
        'round_reward', 'sync_weight', 'sync_tolerance', 'task_weight', 'curriculum_airports')}
    _mix, _duty = config['uniform_mix'], duty


def _run(task):
    seed, ordinal, steps = task
    torch.manual_seed(seed + ordinal)
    env = PolicyProbeEnv(**_options, control=_control, candidate=_candidate,
        uniform_mix=_mix, cpu_duty_cycle=_duty)
    batch, records = collect_rollout(_candidate, env, steps,
        seed=f'route-policy-probe:{seed}:{ordinal}', episodes_done=0,
        gamma=.995, gae_lambda=.95, uniform_mix=_mix, discount_unit='placement', cpu_duty_cycle=_duty)
    halves = [((ordinal + episode) % 2) for episode, record in enumerate(records) for _ in range(record['steps'])]
    if len(env.probe_routes) != len(batch['actions']) or len(halves) != len(batch['actions']):
        raise RuntimeError('Probe/rollout alignment changed.')
    if any(not isinstance(r['seed'], str) or not r['seed'].startswith('train:route-policy-probe:') for r in records):
        raise RuntimeError('Only namespaced training states are allowed.')
    return batch, records, env.probe_routes, halves, env.probe_counts, env.probe_transitions


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--steps', type=int, default=8192)
    p.add_argument('--seed', type=int, default=251042)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or args.steps < args.workers:
        p.error('Resource cap: 1–8 workers at at most .7 duty, at least one decision per worker.')
    if args.output.exists():
        p.error('Use a new report path.')
    torch.set_num_threads(1)
    paths = dict(source=str(args.source), candidate=str(args.candidate))
    models = {k:load_checkpoint(path) for k,path in paths.items()}
    fingerprints = {k:weight_fingerprint(model) for k,(model,_) in models.items()}
    config = models['candidate'][1]['train_config']
    if any(m.config.get('kind') != 'guided_residual' or m.config['action_count'] != 217 for m,_ in models.values()):
        p.error('Use the guided schema-3 lineage.')
    if not config.get('research_open_risk') or config['research_search_sha256'] != search_fingerprint():
        p.error('The candidate must match the finished open-risk experiment.')
    if config.get('phase_source_weights_sha256') != fingerprints['source']:
        p.error('The control must contain the exact pre-training source weights.')
    report = dict(format=1, phase='training_state_route_policy_diagnosis_only',
        weights_sha256=fingerprints, checkpoints=paths, seed_namespace=f'train:route-policy-probe:{args.seed}:',
        requested_decisions=args.steps, workers=args.workers, cpu_duty_cycle=args.cpu_duty_cycle,
        threads=1, search_sha256=search_fingerprint(),
        probe_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        independent_test_used=False, weights_changed=False, release_evidence=False, goal_achieved=False)
    tasks = [(args.seed, i, (args.steps + args.workers - 1) // args.workers) for i in range(args.workers)]
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(paths, fingerprints, args.cpu_duty_cycle)) as pool:
        outputs = list(pool.map(_run, tasks))
    batch = {k:torch.cat([o[0][k] for o in outputs]) for k in outputs[0][0]}
    labels = [r for o in outputs for r in o[2]]
    halves = [r for o in outputs for r in o[3]]
    counts, transitions, episodes = {}, {}, Counter()
    for _, records, _, _, totals, changes in outputs:
        for r in records:
            episodes[r['scenario']] += 1
        for route, values in totals.items():
            counts.setdefault(route, Counter()).update(values)
        for route, values in changes.items():
            transitions.setdefault(route, Counter()).update(values)
    report['routes'] = {route:dict(episodes=episodes[route], counts=dict(values),
        old_action_transitions=dict(transitions.get(route, {}))) for route,values in counts.items()}
    report['actual_decisions'] = len(labels)
    report['actor_gradients'] = actor_gradients(models['candidate'][0], batch, labels, halves,
        uniform_mix=config['uniform_mix'], duty=args.cpu_duty_cycle)
    for name, (model, _) in models.items():
        if weight_fingerprint(model) != fingerprints[name]:
            raise RuntimeError('A passive probe must not change weights.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps(report, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
