"""Frozen Crew5/native, prior, and prior+engine-proven terminal search.

Fresh development14990000+100*case,20 games per official Wind/Ice card case.
No PPO, training labels, altered rules, or qualification. The search is a new
player overlay, not a retrained model. All paired outcomes remain in the report.
"""
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

from .agents import ModelAgent
from .checkpoints import weight_fingerprint
from .evaluate import summarize_episodes
from .leak_strength_compare import _write
from .module_training_eval import _development_seed,case_key
from .modules import ModuleEnv
from .solo_landing_environment import SoloLandingEnv
from .throttle import CpuBudget
from . import wind_ice_compare as legacy
from .wind_ice_prior_compare import comparison_fingerprint as prior_fingerprint
from .wind_ice_prior_environment import PriorWindIceEnv


BASE_SEED,STRIDE,GAMES=14_990_000,100,20
ARMS=('native','prior','terminal')
STOP_FILE=Path('runs/STOP_AI_TRAINING')


def check_stop():
    if STOP_FILE.exists():raise ValueError('Persistent training stop is active.')


def comparison_fingerprint():
    digest=hashlib.sha256(prior_fingerprint().encode())
    root=Path(__file__).resolve().parents[1]
    for name in ('ai/solo_landing.py','ai/solo_landing_environment.py','ai/solo_landing_compare.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


def run_arm(model,case,arm,seed,games,duty=.7):
    _development_seed(seed,games)
    if (arm not in ARMS or type(games) is not int or not 1<=games<=GAMES or case not in legacy.cases()
            or not math.isfinite(duty) or not 0<duty<=.7 or model.config.get('guide_margin')!=12.):
        raise ValueError('Use a bounded official Wind/Ice case, frozen margin12 policy, duty<=.7.')
    check_stop()
    klass={'native':ModuleEnv,'prior':PriorWindIceEnv,'terminal':SoloLandingEnv}[arm]
    env=klass(case['airport'],abilities=case['abilities'],assistance_version=12,max_steps=256,
        round_reward=0.,sync_weight=0.,task_weight=0.,planning_cpu_duty_cycle=duty)
    agent,budget=ModelAgent(model),CpuBudget(duty)
    before=weight_fingerprint(model)
    records,measurements=[],[]
    was_training=model.training;model.eval()
    try:
        for ordinal in range(games):
            check_stop();game_seed=seed+ordinal
            _,info=env.reset(seed=game_seed)
            actual=env.view()['modules_state']
            if (env.game.landung.get_code()!=case['airport'] or sorted(actual['cards'])!=sorted(case['abilities'])
                    or sorted(actual['modules'])!=sorted(case['modules'])):
                raise RuntimeError('The actual engine route/card case differs.')
            counts,changes,total_return=Counter(),[],0.
            while not env.done:
                check_stop()
                mask,reference=info['action_mask'],info['reference_action_mask']
                native=agent.select(env.view(),mask,reference_mask=reference)
                action=native
                if arm=='terminal':
                    if info.get('research_solo_landing') is not True:raise RuntimeError('Missing research flag.')
                    proof=info['landing_proof']
                    counts['eligible_decisions']+=int(proof['eligible'])
                    counts['search_nodes']+=proof['nodes']
                    counts['search_exhausted']+=int(proof['exhausted'])
                    counts['unknown_roll_abstentions']+=int(proof['unknown_roll'])
                    if proof['actions']:
                        action=proof['actions'][0]
                        if not mask[action]:raise RuntimeError('The engine-proven first action is outside the real mask.')
                        counts['proven_decisions']+=1
                        counts['changed_policy_decisions']+=int(action!=native)
                        changes.append(dict(step=env.steps,role=env.current_role,action_id=action,
                            policy_action_id=native,proof=list(proof['actions']),nodes=proof['nodes']))
                counts['decisions']+=1
                counts['reference_departures']+=int(not reference[action])
                _,reward,_,_,info=env.step(action);total_return+=reward
                budget.pause()
            record=env.episode_record(game_seed,'both',total_return)
            record.update(airport=case['airport'],abilities=sorted(case['abilities']),modules=sorted(case['modules']),
                case_key=case_key(case),reference_departures=counts['reference_departures'],decisions=counts['decisions'])
            records.append(record)
            measurements.append(dict(seed=game_seed,counts=dict(counts),changes=changes))
    finally:model.train(was_training)
    if weight_fingerprint(model)!=before:raise RuntimeError('Weights changed during search evaluation.')
    totals=Counter()
    for row in measurements:totals.update(row['counts'])
    summary=dict(complete=True,airport=case['airport'],abilities=sorted(case['abilities']),modules=sorted(case['modules']),
        case_key=case_key(case),assistance_version=12,clock_model='engine_wall_clock',release_evidence=False,
        qualification_used=False,decisions=totals['decisions'],reference_departures=totals['reference_departures'],
        reference_departure_rate=totals['reference_departures']/max(1,totals['decisions']),**summarize_episodes(records))
    return dict(summary=summary,counts=dict(totals),measurements=measurements)


_model=None


def _initialize(checkpoint,metadata,code_sha):
    global _model
    torch.set_num_threads(1);check_stop()
    _model,actual=legacy.load_model(checkpoint)
    if actual!=metadata or comparison_fingerprint()!=code_sha:raise ValueError('Sources or frozen tensors changed.')


def _run(task):
    arm,case,seed,duty=task
    return case_key(case),run_arm(_model,case,arm,seed,GAMES,duty)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,default=Path('ai/releases/crew5-leak-preview-v1/best.pt'))
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--cpu-duty-cycle',type=float,default=.7)
    args=parser.parse_args(argv)
    if not 1<=args.workers<=8 or not math.isfinite(args.cpu_duty_cycle) or not 0<args.cpu_duty_cycle<=.7:
        parser.error('Use at most8 workers, duty<=.7.')
    if args.output.exists() or args.output.is_symlink():parser.error('Preserve existing reports; choose a new path.')
    try:
        check_stop();torch.set_num_threads(1)
        _,metadata=legacy.load_model(args.checkpoint)
        selected_cases=legacy.cases()
        for ordinal in range(len(selected_cases)):_development_seed(BASE_SEED+STRIDE*ordinal,GAMES)
    except (ValueError,OSError) as exc:parser.error(str(exc))
    code_sha,started=comparison_fingerprint(),time.monotonic()
    report=dict(format=1,complete=False,phase='public_engine_proven_solo_landing',release_evidence=False,
        qualification_used=False,ppo_updates=0,new_training_decisions=0,same_policy_all_arms=True,fresh_development=True,
        model=metadata,comparison_sha256=code_sha,prior_comparison_sha256=prior_fingerprint(),
        games_per_arm_case=GAMES,base_seed=BASE_SEED,seed_stride=STRIDE,workers=args.workers,
        cpu_duty_cycle=args.cpu_duty_cycle,threads=1,clock_model='engine_wall_clock',
        limitations=['Partner has no regular dice left; final round only.',
            'Only already rolled issued black bonus dice, no speculative future dice.',
            'Search abstains on stochastic, intern, realtime and unsupported branches.',
            'A failed or budget-limited search does not prove the game lost.',
            'A winning engine path proves that continuation, not the whole-game win rate.'],
        cases={case_key(row):{'case':row} for row in selected_cases})
    args.output.parent.mkdir(parents=True,exist_ok=True);_write(args.output,report,initial=True)
    try:
        with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize,initargs=(args.checkpoint,metadata,code_sha)) as pool:
            for arm in ARMS:
                tasks=[(arm,row,BASE_SEED+STRIDE*ordinal,args.cpu_duty_cycle) for ordinal,row in enumerate(selected_cases)]
                for key,output in pool.map(_run,tasks):
                    report['cases'][key][arm]=output
                    if arm=='terminal':
                        for baseline in ('native','prior'):
                            report['cases'][key]['paired_'+baseline]=legacy.paired_details(report['cases'][key][baseline],output)
                    _write(args.output,report)
                    print(json.dumps(dict(case=key,arm=arm,wins=output['summary']['wins'],games=GAMES,counts=output['counts'])),flush=True)
        check_stop()
        if code_sha!=comparison_fingerprint() or legacy.load_model(args.checkpoint)[1]!=metadata:
            raise RuntimeError('Frozen sources or weights changed during evaluation.')
        report.update(complete=True,elapsed_seconds=time.monotonic()-started);_write(args.output,report)
    except BaseException as exc:
        report.update(complete=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        _write(args.output,report);raise


if __name__=='__main__':main()
