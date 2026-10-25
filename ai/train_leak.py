"""Bounded public-profile-11/12 PPO on Atlanta's six official leak/card cases.

Fresh phase, existing guided detail branch, frozen foundation. No automatic
publication and no substitution of an average for a weak card combination.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time

import torch

from .checkpoints import load_checkpoint, save_checkpoint, weight_fingerprint, planner_fingerprint
from .module_training_eval import load_cases, case_key
from .modules import ModuleEnv
from .nn_model import build_model
from .public_case_eval import run_public_case
from .train import collect_rollout, ppo_update
from .train_fuel import successful_replay
from .intern_strength_compare import MARGINS, tensor_fingerprint, with_margin


_model, _options, _duty = None, None, None


def phase_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('train_leak.py', 'public_case_eval.py', 'intern_strength_compare.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def initialize_phase(checkpoint, *, device='cpu', assistance_version=11, guide_margin=4.):
    """Copy existing tensors into an explicit phase with a finite prior override.

    ``source_weights_sha256`` names the unmodified input checkpoint; the
    separately recorded initial fingerprint includes the chosen guide margin.
    No optimizer, counters, replay, or RNG state is resumed from that source.
    """
    if assistance_version not in (11, 12):
        raise ValueError('Leak training uses public profile 11 or 12.')
    if type(guide_margin) not in (int, float) or guide_margin not in MARGINS:
        raise ValueError('Use a finite guide margin of 4, 8 or 12.')
    original, payload = load_checkpoint(checkpoint, device)
    if (original.config.get('kind') != 'guided_residual' or original.config['action_count'] != 217
            or original.config['observation_size'] != 489):
        raise ValueError('Use an existing guided schema-3 player, without another network branch.')
    source_sha = weight_fingerprint(original)
    source_tensor_sha = tensor_fingerprint(original)
    frozen_sha = weight_fingerprint(original.source)
    model = with_margin(original, guide_margin)
    if (tensor_fingerprint(model) != source_tensor_sha
            or weight_fingerprint(model.source) != frozen_sha):
        raise RuntimeError('Finite guidance override changed source tensors or the frozen foundation.')
    lineage = dict(source_checkpoint_weights_sha256=source_sha,
        source_weights_sha256=source_sha, initial_weights_sha256=weight_fingerprint(model),
        source_tensor_sha256=source_tensor_sha, initial_tensor_sha256=tensor_fingerprint(model),
        frozen_source_weights_sha256=frozen_sha,
        frozen_source_tensor_sha256=tensor_fingerprint(model.source),
        source_model_config=deepcopy(original.config), initial_model_config=deepcopy(model.config),
        source_phase_steps=payload['total_steps'], source_guide_margin=original.guide_margin,
        guide_margin=model.guide_margin, guide_margin_overridden=original.guide_margin != model.guide_margin,
        phase_kind=('new_public_module_profile_11_leak' if assistance_version == 11
                    else 'new_public_module_profile_12_leak_cards'))
    return model, payload, lineage


def selection_score(rows):
    """Worst official card case first; mean only breaks an exact tie."""
    rates = [row['win_rate'] for row in rows.values()]
    if len(rates) != 6:
        raise ValueError('All six Atlanta leak/card cases must be evaluated.')
    return min(rates), sum(rates)/len(rates)


def _initialize(model_config, options, duty):
    global _model, _options, _duty
    torch.set_num_threads(1)
    _model, _options, _duty = build_model(model_config), options, duty


def _collect(task):
    state, steps, seed, update, ordinal = task
    _model.load_state_dict(state)
    torch.manual_seed(seed + update*1009 + ordinal)
    return collect_rollout(_model, ModuleEnv(**_options), steps,
        seed=f'leak-profile{_options["assistance_version"]}:{seed}:{update}:{ordinal}', episodes_done=0,
        gamma=.995, gae_lambda=.95, uniform_mix=.03, discount_unit='placement',
        cpu_duty_cycle=_duty)


def _evaluate(task):
    state, case, games, seed = task
    _model.load_state_dict(state)
    return run_public_case(_model, case, games, seed, cpu_duty_cycle=_duty,
                           assistance_version=_options['assistance_version'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('ai/releases/crew2-v1/best.pt'))
    parser.add_argument('--matrix', type=Path, default=Path('ai/experiments/modules-30pct-2026-10-25/matrix.json'))
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=80000)
    parser.add_argument('--seconds', type=float, default=600.)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    parser.add_argument('--device', default='mps')
    parser.add_argument('--seed', type=int, default=251054)
    parser.add_argument('--eval-seed', type=int, default=14910000)
    parser.add_argument('--eval-games-per-case', type=int, default=20)
    parser.add_argument('--eval-every', type=int, default=20)
    parser.add_argument('--assistance-version', type=int, choices=(11, 12), default=11)
    parser.add_argument('--guide-margin', type=float, choices=MARGINS, default=4.)
    args = parser.parse_args()
    if (not 1 <= args.workers <= 8 or not 0 < args.cpu_duty_cycle <= .7 or
            args.steps < 1 or not math.isfinite(args.seconds) or not 0 < args.seconds <= 900 or
            not 1 <= args.eval_games_per_case <= 100 or args.eval_every < 1):
        parser.error('Use at most eight workers at .7 duty, 900 seconds and positive bounded budgets.')
    if not 14_000_000 <= args.eval_seed or args.eval_seed+5*100+args.eval_games_per_case >= 15_000_000:
        parser.error('All development cases must stay below reserved qualification seeds.')
    if args.run_dir.exists():
        parser.error('Preserve prior experiments; use a new run directory.')
    if Path('runs/STOP_AI_TRAINING').exists():
        parser.error('Persistent stop is active; explicit resumption is required.')
    cases = [case for case in load_cases(args.matrix) if case['airport'] == 'LOG_ATL_YELLOW']
    if len(cases) != 6 or any(case['modules'] != ['leak'] or len(case['abilities']) != 1 for case in cases):
        parser.error('Use exactly all six official Atlanta-yellow single-card leak cases.')
    keys = {case_key(case) for case in cases}
    torch.set_num_threads(1)
    torch.manual_seed(args.seed)
    try:
        model, source, lineage = initialize_phase(args.source, device=args.device,
            assistance_version=args.assistance_version, guide_margin=args.guide_margin)
    except ValueError as exc:
        parser.error(str(exc))
    initial_sha, frozen_sha = lineage['initial_weights_sha256'], lineage['frozen_source_weights_sha256']
    optimizer = torch.optim.Adam((p for p in model.parameters() if p.requires_grad), lr=5e-5, eps=1e-5)
    options = dict(airport='LOG_ATL_YELLOW', assistance_version=args.assistance_version, max_steps=256,
        curriculum_cases=cases, round_reward=0., sync_weight=.05, sync_tolerance=1., task_weight=.02)
    if args.assistance_version == 12:
        options['planning_cpu_duty_cycle'] = args.cpu_duty_cycle
    config = {**options, 'schema_version':3, 'supported_modules':['leak'],
        'supported_cards':sorted(case['abilities'][0] for case in cases), 'ability_count':1,
        'supported_cases':cases, 'source_checkpoint':args.source.as_posix(),
        **lineage,
        'source_planner_sha256':source['train_config'].get('planner_sha256'),
        'phase_sha256':phase_fingerprint(),
        'planner_sha256':planner_fingerprint(3), 'action_mask_version':2,
        'workers':args.workers, 'cpu_duty_cycle':args.cpu_duty_cycle, 'threads':1, 'device':args.device,
        'seed':args.seed, 'eval_seed':args.eval_seed, 'eval_seed_stride':100,
        'eval_games_per_case':args.eval_games_per_case, 'eval_every':args.eval_every,
        'steps_limit':args.steps, 'training_seconds_limit':args.seconds,
        'learning_rate':5e-5, 'uniform_mix':.03, 'self_imitation_coef':.03,
        'discount_unit':'placement', 'publication_status':'development_only_not_published',
        'independent_qualification_used':False}
    args.run_dir.mkdir(parents=True)
    (args.run_dir/'config.json').write_text(json.dumps(config,indent=2)+'\n')
    steps, episodes, update, elapsed = 0, 0, 0, 0.
    counts, replay, best, best_steps, validations = Counter(), None, None, 0, []
    demo_generator = torch.Generator().manual_seed(args.seed+37)
    wall_start = time.monotonic()

    def state():
        return {key:value.detach().cpu() for key,value in model.state_dict().items()}

    def save(name):
        if weight_fingerprint(model.source) != frozen_sha:
            raise RuntimeError('Frozen original player changed.')
        save_checkpoint(args.run_dir/name, model, train_config=config, total_steps=steps,
            source_phase_steps=source['total_steps'], module_training_steps=source.get('module_training_steps',0)+steps,
            decisions_by_module={'leak':steps}, decisions_by_case=dict(counts),
            episodes=episodes, update=update, training_elapsed_seconds=elapsed,
            optimizer_state=optimizer.state_dict(), torch_rng_state=torch.get_rng_state(),
            mps_rng_state=torch.mps.get_rng_state() if args.device=='mps' else torch.get_rng_state(),
            successful_replay={key:value.cpu() for key,value in replay.items()} if replay else None,
            demo_rng_state=demo_generator.get_state())

    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(model.config,options,args.cpu_duty_cycle)) as pool:
        def validate():
            nonlocal best, best_steps
            tasks = [(state(),case,args.eval_games_per_case,args.eval_seed+ordinal*100)
                     for ordinal,case in enumerate(cases)]
            rows = {}
            for result in pool.map(_evaluate,tasks):
                result.pop('episodes')
                rows[result['case_key']] = result
            if set(rows) != keys:
                raise RuntimeError('Evaluation did not cover the exact requested card cases.')
            score = selection_score(rows)
            row = dict(steps=steps,update=update,cases=rows,score=list(score),release_evidence=False)
            validations.append(row)
            with (args.run_dir/'validation.jsonl').open('a') as stream:
                stream.write(json.dumps(row)+'\n')
            if best is None or score > best:
                best,best_steps = score,steps
                save('best.pt')
            print(json.dumps(dict(validation=True,steps=steps,
                cases={key:{k:value[k] for k in ('games','wins','win_rate')} for key,value in rows.items()},
                worst_case=score[0],release_evidence=False)),flush=True)

        try:
            save('warm.pt')
            validate()
            while steps < args.steps and elapsed < args.seconds:
                started = time.monotonic()
                target = min(2048,args.steps-steps)
                tasks = [(state(),math.ceil(target/args.workers),args.seed,update,ordinal)
                         for ordinal in range(min(args.workers,target))]
                outputs = list(pool.map(_collect,tasks))
                batch = {key:torch.cat([item[0][key] for item in outputs]).to(args.device) for key in outputs[0][0]}
                records = [record for _,rows in outputs for record in rows]
                if any(case_key(dict(airport=record['scenario'],abilities=record['abilities'])) not in keys
                       or record['modules'] != ['leak'] for record in records):
                    raise RuntimeError('Training selected an unexpected route/card/module case.')
                replay = successful_replay(batch,records,replay,limit=4096)
                stats = ppo_update(model,optimizer,batch,epochs=4,minibatch_size=256,
                    clip=.2,value_coef=.5,entropy_coef=.01,uniform_mix=.03,
                    demonstrations=replay,demo_coef=.03 if replay else 0.,demo_generator=demo_generator)
                for record in records:
                    counts[case_key(dict(airport=record['scenario'],abilities=record['abilities']))] += record['steps']
                steps += len(batch['actions']); episodes += len(records); update += 1
                elapsed += time.monotonic()-started
                if sum(counts.values()) != steps:
                    raise RuntimeError('Per-case decisions do not match actual rollout decisions.')
                row = dict(steps=steps,episodes=episodes,update=update,training_elapsed_seconds=elapsed,
                    decisions_by_case=dict(counts),train_wins=sum(r['status']=='gewonnen' for r in records),
                    train_episodes=len(records),**stats)
                with (args.run_dir/'training.jsonl').open('a') as stream:
                    stream.write(json.dumps(row)+'\n')
                save('latest.pt')
                print(json.dumps({key:row[key] for key in ('steps','update','training_elapsed_seconds','train_wins','train_episodes')}),flush=True)
                if update%args.eval_every == 0:
                    validate()
            if validations[-1]['steps'] != steps:
                validate()
        except KeyboardInterrupt:
            config['interrupted'] = True
            raise
        finally:
            save('latest.pt')
    report = dict(format=1,complete=True,release_evidence=False,goal_achieved=False,
        new_training_decisions=steps,episodes=episodes,updates=update,training_elapsed_seconds=elapsed,
        total_wall_seconds=time.monotonic()-wall_start,best_steps=best_steps,config=config,
        decisions_by_case=dict(counts),frozen_source_unchanged=True,
        initial_weights_sha256=initial_sha,latest_weights_sha256=weight_fingerprint(model),validations=validations)
    (args.run_dir/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(complete=True,steps=steps,best_steps=best_steps,training_seconds=elapsed)),flush=True)


if __name__ == '__main__':
    main()
