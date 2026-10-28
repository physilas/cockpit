"""Collect observation-limited search labels from TRAINING seed namespaces.

No development/test episode is imported. Labels carry the exact allowed and
reference masks and their empirical search gain. This is a heuristic teacher,
not a proof of a winning action; results must be checked after distillation.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import hashlib
import multiprocessing
from pathlib import Path
import random
import time

import torch

from .checkpoints import load_checkpoint, weight_fingerprint
from .information_search import InformationSearchAgent
from .module_training_eval import balanced_cases, case_key
from .modules import ModuleEnv, module_encode
from .preview_matrix_eval import catalogue_cases
from .robust_policy import RobustBlueprint
from .belief_simulator import PlanningClock
from .coherent_safety import coherent_safe_actions
from .module_capacity import reserve_controls
from .rollout_search import semantic_action


_model = _settings = None
_teacher_kind = None
_execution = None


def initialize(checkpoint, settings):
    global _model, _settings, _teacher_kind, _execution
    torch.set_num_threads(1)
    _model, _ = load_checkpoint(checkpoint)
    _model.eval()
    _settings = dict(settings)
    _teacher_kind = _settings.pop('kind')
    _execution = _settings.pop('execute')


def collect_episode(task):
    case, seed = task
    clock = PlanningClock()
    env = ModuleEnv(case['airport'], abilities=case['abilities'], assistance_version=0,
                    clock=clock, round_reward=0., sync_weight=0., task_weight=0.)
    env.reset(seed=seed)
    policy = RobustBlueprint(case['airport'], _model)
    if _teacher_kind in ('contract','hybrid'):
        from .contract_planner import ContractAgent
        factory=lambda:ContractAgent(case['airport'],policy,**_settings)
    else:
        factory=lambda:InformationSearchAgent(case['airport'], policy, **_settings)
    agents = {role: factory() for role in ('pilot', 'kopilot')}
    execution_rng=random.Random(seed+':execute')
    rows = []
    while not env.done:
        view, raw = env.view(), env.action_mask()
        allowed, safety=coherent_safe_actions(case['airport'],view,raw)
        allowed=reserve_controls(view,allowed)
        _, reference = policy.masks(view, allowed)
        reference=[bool(a and r) for a,r in zip(allowed,reference)]
        if not any(reference):reference=list(allowed)
        actor = agents[env.current_role]
        preserve=(_teacher_kind=='hybrid' and not set(case['modules'])&{'wind','ice'})
        if preserve:
            action=policy.select(view,allowed)
            report=dict(baseline=action,ranks={},planning_mode='baseline_preservation')
        else:
            action = actor.select(view, raw)
            report = actor.last_report
        if not allowed[action]:
            raise RuntimeError('Teacher selected outside its recorded public mask.')
        changed = action != report['baseline']
        targets={action}
        if _teacher_kind in ('contract','hybrid'):
            chosen=report['ranks'].get(action)
            baseline=report['ranks'].get(report['baseline'])
            gain=(chosen-baseline)/10000 if chosen is not None and baseline is not None else None
            if chosen is not None:
                targets.update(i for i,value in report['ranks'].items() if value>=chosen-1. and allowed[i])
            weight=(.5 if preserve else 1. if report['planning_mode']=='round_contract' else .2)
            if safety['unavoidable_closing_loss']:weight=.05
            simulations=0
        else:
            values = report['values']
            chosen, baseline = values[str(action)], values[str(report['baseline'])]
            gain = chosen['value'] - baseline['value']
            weight=1. if changed and gain>=.1 else .1
            simulations=report['simulations']
        # All examples use exactly the actor's permitted observation. The
        # engine's private partner dice and its RNG are not stored in the data.
        equivalent={semantic_action(view,i) for i in targets}
        target_mask=[bool(ok and semantic_action(view,i) in equivalent) for i,ok in enumerate(allowed)]
        rows.append(dict(observation=module_encode(view), mask=allowed, reference=reference,
                         targets=target_mask,
                         action=action, baseline=report['baseline'], search_gain=gain,
                         simulations=simulations, changed=changed, weight=weight))
        clock.now += 1.
        execute_student=_execution=='student' or _execution=='mix' and execution_rng.random()<.5
        env.step(policy.select(view,allowed) if execute_student else action)
    return dict(case_key=case_key(case), seed=seed,status=env.info()['status'], reason=env.info()['reason'],
                decisions=len(rows), rows=rows)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--episodes', type=int, default=100)
    p.add_argument('--workers', type=int, default=3)
    p.add_argument('--seed', type=int, default=281100)
    p.add_argument('--simulations', type=int, default=64)
    p.add_argument('--width', type=int, default=8)
    p.add_argument('--max-seconds', type=float, default=.5)
    p.add_argument('--teacher',choices=('contract','hybrid','uct'),default='contract')
    p.add_argument('--execute',choices=('teacher','student','mix'),default='teacher')
    p.add_argument('--beam',type=int,default=24)
    p.add_argument('--seconds', type=float, default=1800.)
    p.add_argument('--airports', nargs='*')
    args = p.parse_args()
    if (not 1 <= args.workers <= 8 or not 1 <= args.episodes <= 10000 or args.output.exists()
            or not 0 < args.seconds <= 6*3600):
        p.error('Use a new output, 1..8 workers, 1..10000 training episodes.')
    if args.teacher in ('contract','hybrid'):
        if not 1<=args.beam<=128:
            p.error('Use a bounded contract beam.')
        settings=dict(beam=args.beam)
    else:
        settings = dict(simulations=args.simulations, width=args.width, max_seconds=args.max_seconds)
        InformationSearchAgent('MUC', None, **settings)
    settings.update(kind=args.teacher,execute=args.execute)
    cases = catalogue_cases()
    if args.airports:
        if set(args.airports) - {c['airport'] for c in cases}:
            p.error('Unknown requested airport.')
        cases = [c for c in cases if c['airport'] in args.airports]
    curriculum = balanced_cases(cases)
    rng = random.Random(f'train:search-labels:{args.seed}')
    tasks = [(rng.choice(curriculum), f'train:search-labels:{args.seed}:{i}') for i in range(args.episodes)]
    model, _ = load_checkpoint(args.checkpoint)
    fingerprint = weight_fingerprint(model)
    code=hashlib.sha256()
    for name in ('search_demonstrations.py','contract_planner.py','coherent_safety.py','assignment_belief.py',
                 'robust_policy.py','safety_guard.py','rollout_search.py'):
        code.update(name.encode());code.update(Path(__file__).with_name(name).read_bytes())
    del model
    rows, episodes = [], []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    last_save=started

    def save():
        nonlocal last_save
        data = dict(observations=torch.tensor([r['observation'] for r in rows], dtype=torch.float32),
                    masks=torch.tensor([r['mask'] for r in rows], dtype=torch.bool),
                    reference_masks=torch.tensor([r['reference'] for r in rows], dtype=torch.bool),
                    actions=torch.tensor([r['action'] for r in rows], dtype=torch.long),
                    target_masks=torch.tensor([r['targets'] for r in rows],dtype=torch.bool),
                    weights=torch.tensor([r['weight'] for r in rows], dtype=torch.float32))
        temporary = args.output.with_suffix('.tmp')
        torch.save(dict(data=data, episodes=episodes, source_weights_sha256=fingerprint,
                        settings=settings, training_seed_namespace=f'train:search-labels:{args.seed}',
                        collector_sha256=code.hexdigest(),
                        collector_clock='logical_seconds_per_decision',
                        decisions=len(rows), complete=len(episodes)==args.episodes), temporary)
        temporary.replace(args.output)
        last_save=time.monotonic()

    pool = ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                    initializer=initialize, initargs=(args.checkpoint, settings))
    try:
        futures = [pool.submit(collect_episode, task) for task in tasks]
        for future in as_completed(futures, timeout=args.seconds):
            result = future.result()
            rows.extend(result.pop('rows'))
            episodes.append(result)
            if len(episodes)%25==0 or time.monotonic()-last_save>=30:
                save()
            print(json.dumps(dict(episodes=len(episodes), decisions=len(rows),
                wins=sum(r['status']=='gewonnen' for r in episodes),
                search_overrides=sum(r['changed'] for r in rows), seconds=time.monotonic()-started)), flush=True)
    except BaseException as exc:
        for worker in pool._processes.values():
            worker.terminate()
        pool.shutdown(wait=True, cancel_futures=True)
        if rows:
            save()
        if not isinstance(exc, TimeoutError):
            raise
    else:
        pool.shutdown(wait=True)
        if rows:save()


if __name__ == '__main__':
    main()
