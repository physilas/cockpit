"""Development diagnosis of policy freedom under the existing hard planner.

This does not change a planner, train weights, or qualify a model. Only the
acting player's permitted view is inspected; reports contain aggregate counts.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import json
import math
import multiprocessing
from pathlib import Path

import torch

from .checkpoints import load_checkpoint, model_schema, planner_fingerprint, weight_fingerprint
from .environment import CrewEnv
from .evaluate import summarize_episodes
from .fuel import FuelEnv
from .modules import ModuleEnv
from .throttle import CpuBudget


class CaptureRawMask:
    """Observe both masks without altering the environment or its RNG."""
    def _assist(self, mask):
        self.unassisted_mask = list(mask)
        if isinstance(self, FuelEnv) and not self.view()['fuel']['present']:
            self.unassisted_mask[121:125] = [False] * 4
        return super()._assist(mask)


class ProbeCrewEnv(CaptureRawMask, CrewEnv):
    pass


class ProbeFuelEnv(CaptureRawMask, FuelEnv):
    pass


class ProbeModuleEnv(CaptureRawMask, ModuleEnv):
    pass


def capacity_only_mask(view, raw, profile):
    """Reproduce the pre-search budget bounds for the base/fuel diagnosis."""
    from .actions import SLOTS, ACTIONS
    from .fuel import FUEL_ACTIONS, fuel_capacity_mask
    from .tactics import capacity_mask
    modules = view.get('modules_state', {})
    if set(modules.get('modules', [])) - {'kerosene'} or modules.get('cards'):
        raise ValueError('This comparison isolates the base/fuel planner, without cards.')
    mask = list(raw)
    if view['reroll'] or profile == 0:
        return mask
    missing = sum(s.owner == view['role'] and s.target in ('ruder', 'triebwerk')
                  and view['board'][i] is None for i, s in enumerate(SLOTS))
    if sum(bool(v) for v in view['own_dice']) <= missing:
        for i, a in enumerate(FUEL_ACTIONS[:len(mask)]):
            if a.kind == 'place' and (i >= len(ACTIONS) or SLOTS[a.slot].target not in ('ruder', 'triebwerk')):
                mask[i] = False
    mask[:121] = capacity_mask(view, mask[:121], include_traffic=True)
    if view.get('fuel', {}).get('present') and profile in (7, 8, 9):
        mask[:125] = fuel_capacity_mask(view, mask[:125])
    return mask


def action_signature(view, action, slots):
    """Collapse interchangeable equal-face dice, not different board targets."""
    if action.kind == 'place':
        slot = slots[action.slot]
        return (action.kind, slot.target, slot.owner, slot.index, slot.radio_index, view['own_dice'][action.die])
    if action.kind == 'coffee':
        return (action.kind, view['own_dice'][action.die], action.delta)
    if action.kind == 'reroll_select':
        return (action.kind, tuple(sorted(v for i, v in enumerate(view['own_dice']) if action.subset & (1 << i))))
    return (action,)


def measure_choice(view, raw, planned, logits, actions, slots, capacity_mask=None):
    """One decision's sufficient statistics; no hands or observations retained."""
    if len(raw) != len(planned) or len(raw) != len(logits) or not any(planned):
        raise ValueError('Expected matching nonempty decision masks and logits.')
    if any(kept and not legal for legal, kept in zip(raw, planned)):
        raise ValueError('Planner admitted an action outside the raw legal mask.')
    raw_ids = [i for i, allowed in enumerate(raw) if allowed]
    kept_ids = [i for i, allowed in enumerate(planned) if allowed]
    capacity_mask = raw if capacity_mask is None else capacity_mask
    capacity_ids = [i for i, allowed in enumerate(capacity_mask) if allowed]
    if not capacity_ids or len(capacity_mask) != len(raw) or any(kept and not capacity_mask[i] for i, kept in enumerate(planned)):
        raise ValueError('Expected the planner shortlist inside the pre-search capacity mask.')
    best = max(raw_ids, key=lambda i: logits[i])
    peak = max(logits[i] for i in raw_ids)
    weights = {i: math.exp(logits[i] - peak) for i in raw_ids}
    mass = sum(weights.values())
    kept_mass = sum(weights[i] for i in kept_ids)
    semantic = Counter()
    # A separate normalization avoids underflow if all retained logits are low.
    kept_peak = max(logits[i] for i in kept_ids)
    for i in kept_ids:
        semantic[action_signature(view, actions[i], slots)] += math.exp(logits[i] - kept_peak)
    normalizer = sum(semantic.values())
    entropy = -sum((w / normalizer) * math.log(w / normalizer) for w in semantic.values() if w)
    return Counter(decisions=1, raw_actions=len(raw_ids), kept_actions=len(kept_ids),
        capacity_actions=len(capacity_ids), capacity_forced=int(len(capacity_ids) == 1),
        raw_forced=int(len(raw_ids) == 1), planner_forced=int(len(kept_ids) == 1),
        semantic_forced=int(len(semantic) == 1), semantic_choices=len(semantic),
        preferred_action_excluded=int(not planned[best]), kept_policy_mass=kept_mass / mass,
        semantic_entropy=entropy)


def summarize_choices(totals):
    n = totals['decisions']
    return {'decisions': n, **{key: totals[key] / n for key in (
        'raw_actions', 'capacity_actions', 'kept_actions', 'raw_forced', 'capacity_forced', 'planner_forced', 'semantic_forced',
        'semantic_choices', 'preferred_action_excluded', 'kept_policy_mass', 'semantic_entropy')}} if n else {'decisions': 0}


_models = {}


def _initialize():
    torch.set_num_threads(1)


def _run(task):
    checkpoint, expected_sha, route, seed, games, profile, duty = task
    budget = CpuBudget(duty)
    if checkpoint not in _models:
        _models[checkpoint] = load_checkpoint(checkpoint)
    model, payload = _models[checkpoint]
    if weight_fingerprint(model) != expected_sha:
        raise ValueError('Checkpoint changed during the diagnosis; use a finished run.')
    version = model_schema(model)['version']
    env = {1: ProbeCrewEnv, 2: ProbeFuelEnv, 3: ProbeModuleEnv}[version](
        airport=route, assistance_version=profile, round_reward=0.)
    rows = []
    with torch.inference_mode():
        for game in range(games):
            env.reset(seed=seed + game)
            totals = Counter()
            stages = {'before_landing': Counter(), 'landing': Counter()}
            reward_sum = 0.
            while not env.done:
                planned = env.action_mask()
                view = env.view()
                guidance = {'reference_mask':env.info()['reference_action_mask']} if model.config.get('kind')=='guided_residual' else {}
                logits, _ = model.policy_output(torch.tensor(env.observation(), dtype=torch.float32), **guidance)
                values = logits.tolist()
                capacity = capacity_only_mask(view, env.unassisted_mask, profile)
                stats = measure_choice(view, env.unassisted_mask, planned, values, env.actions, env.slots, capacity)
                totals.update(stats)
                stages['landing' if view['last_round'] else 'before_landing'].update(stats)
                chosen = max((i for i, allowed in enumerate(planned) if allowed), key=values.__getitem__)
                _, reward, _, _, _ = env.step(chosen)
                reward_sum += reward
                budget.pause()
            rows.append({'episode': env.episode_record(seed + game, 'both', reward_sum),
                         'choices': dict(totals), 'stages': {k: dict(v) for k, v in stages.items()}})
    return rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoints', type=Path, nargs='+', required=True)
    p.add_argument('--routes', nargs='+', default=['LOG_OSL_GREEN', 'LOG_HND_GREEN', 'LOG_LHR_GREEN', 'LOG_YUL_GREEN'])
    p.add_argument('--games', type=int, default=100, help='Per checkpoint and route.')
    p.add_argument('--seed', type=int, default=14100000, help='Development seeds; not the reserved independent test.')
    p.add_argument('--assistance-version', type=int, choices=(0, 3, 4, 5, 6, 7, 8, 9), default=7)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--cpu-duty-cycle', type=float, default=.7)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or args.games < 1:
        p.error('Resource cap: 1–8 workers at at most .7 duty; positive game budget.')
    torch.set_num_threads(1)
    report = {'format': 1, 'phase': 'development_diagnosis_only', 'seed': args.seed,
              'scope': 'four_route_base_fuel_stage_without_abilities',
              'goal_achieved': False, 'independent_test_used': False,
              'games_per_route': args.games, 'assistance_version': args.assistance_version,
              'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'checkpoints': {}}
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'), initializer=_initialize) as pool:
        for path in args.checkpoints:
            model, payload = load_checkpoint(path)
            sha = weight_fingerprint(model)
            entry = {'weights_sha256': sha, 'planner_sha256': planner_fingerprint(model_schema(model)['version']),
                     'total_steps': payload.get('total_steps'), 'module_training_steps': payload.get('module_training_steps'),
                     'routes': {}}
            report['checkpoints'][path.as_posix()] = entry
            for ordinal, route in enumerate(args.routes):
                tasks = [(str(path), sha, route, args.seed + ordinal * 10000 + start,
                          min(10, args.games - start), args.assistance_version, args.cpu_duty_cycle)
                         for start in range(0, args.games, 10)]
                rows = [r for group in pool.map(_run, tasks) for r in group]
                totals = Counter()
                stages = {'before_landing': Counter(), 'landing': Counter()}
                for row in rows:
                    totals.update(row['choices'])
                    for name in stages:
                        stages[name].update(row['stages'][name])
                result = summarize_episodes([r['episode'] for r in rows])
                entry['routes'][route] = {**{k: v for k, v in result.items() if k != 'episodes'},
                    'choice_summary': summarize_choices(totals),
                    'choice_totals': dict(totals),
                    'by_stage': {k: summarize_choices(v) for k, v in stages.items()}}
                print(json.dumps({'checkpoint': str(path), 'route': route, 'win_rate': result['win_rate'],
                                  'choices': summarize_choices(totals)}), flush=True)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
