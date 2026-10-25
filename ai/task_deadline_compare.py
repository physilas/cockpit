"""Fresh paired prior/joint/early-task-deadline development, frozen tensors.

12 official Wind/Ice single-card cases,20 games per arm/case,14994000+100*i.
Same-round count losses are separated from round-boundary events. No PPO or
independent qualification. Earlier profiles, cohorts and reports stay intact.
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
from .joint_landing_environment import JointLandingEnv
from .landing_task_budget import task_budget
from .leak_strength_compare import _write
from .module_training_eval import _development_seed,case_key
from .modules import MODULE_ACTIONS,MODULE_SLOTS
from .task_deadline_environment import TaskDeadlineEnv
from .throttle import CpuBudget
from .wind_ice_prior_environment import PriorWindIceEnv
from . import joint_landing_compare as previous
from . import wind_ice_compare as legacy


BASE_SEED,STRIDE,GAMES=14_994_000,100,20
ARMS=('prior','joint','deadline')
STOP_FILE=Path('runs/STOP_AI_TRAINING')


def check_stop():
    if STOP_FILE.exists():raise ValueError('Persistent training stop is active.')


def comparison_fingerprint():
    digest=hashlib.sha256(previous.comparison_fingerprint().encode())
    root=Path(__file__).resolve().parents[1]
    for name in ('ai/landing_task_budget.py','ai/task_deadline_guard.py',
                 'ai/task_deadline_environment.py','ai/task_deadline_compare.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


def run_arm(model,case,arm,seed,games,duty=.7):
    _development_seed(seed,games)
    if (arm not in ARMS or type(games) is not int or not 1<=games<=GAMES or case not in legacy.cases()
            or not math.isfinite(duty) or not 0<duty<=.7 or model.config.get('guide_margin')!=12.):
        raise ValueError('Use one official Wind/Ice case,1..20 development games and duty<=.7.')
    check_stop()
    klass={'prior':PriorWindIceEnv,'joint':JointLandingEnv,'deadline':TaskDeadlineEnv}[arm]
    env=klass(case['airport'],abilities=case['abilities'],assistance_version=12,max_steps=256,
        round_reward=0.,sync_weight=0.,task_weight=0.,planning_cpu_duty_cycle=duty)
    agent,budget=ModelAgent(model),CpuBudget(duty)
    before=weight_fingerprint(model);was_training=model.training;model.eval()
    records,measurements=[],[]
    try:
        for ordinal in range(games):
            check_stop();game_seed=seed+ordinal
            _,info=env.reset(seed=game_seed)
            x=env.view()['modules_state']
            if (env.game.landung.get_code()!=case['airport'] or sorted(x['cards'])!=sorted(case['abilities'])
                    or sorted(x['modules'])!=sorted(case['modules'])):raise RuntimeError('Engine selected a different case.')
            counts,entries,changes,total_return=Counter(),{},[],0.
            while not env.done:
                check_stop();view=env.view();current_budget=task_budget(view)
                stage='final' if view['last_round'] else '1000ft' if view['height']==1000 else None
                if stage is not None and stage not in entries:entries[stage]=current_budget
                counts['budget_pass_states']+=int(current_budget['possible'] is True)
                counts['budget_fail_states']+=int(current_budget['possible'] is False)
                counts['budget_abstain_states']+=int(current_budget['possible'] is None)
                mask,reference=info['action_mask'],info['reference_action_mask']
                if (len(reference)!=len(mask) or any(type(v) is not bool for v in reference)
                        or any(v and not mask[i] for i,v in enumerate(reference))):
                    raise RuntimeError('The actual reference must fit the actual mask.')
                action=agent.select(view,mask,reference_mask=reference)
                if arm=='deadline':
                    if info.get('research_task_deadline') is not True:raise RuntimeError('Missing new-mask research marker.')
                    original,original_ref=info['pre_guard_action_mask'],info['pre_guard_reference_action_mask']
                    if (len(original)!=len(mask) or len(original_ref)!=len(mask)
                            or any(v and not original[i] for i,v in enumerate(mask))
                            or any(v and not original[i] for i,v in enumerate(original_ref))):
                        raise RuntimeError('Original mask/reference must be paired separately from the narrowed mask.')
                    different=mask!=original
                    counts['guard_eligible_states']+=int(info['task_deadline']['eligible'])
                    counts['guard_fallbacks']+=int(info['task_deadline']['fallback'])
                    counts['narrowed_mask_states']+=int(different)
                    counts['removed_placement_options']+=sum(a and not b for a,b in zip(original,mask))
                    if different:
                        previous_action=agent.select(view,original,reference_mask=original_ref)
                        counts['changed_policy_choices']+=int(previous_action!=action)
                        counts['prevented_old_placement_choices']+=int(not mask[previous_action])
                        if not mask[previous_action]:
                            a=MODULE_ACTIONS[previous_action]
                            counts['prevented_target_'+MODULE_SLOTS[a.slot].target]+=1
                        if len(changes)<32:
                            changes.append(dict(step=env.steps,round=view['round'],height=view['height'],
                                kind='guard',role=view['role'],action_id=action,previous_action_id=previous_action,
                                previous_choice_removed=not mask[previous_action],budget=current_budget))
                counts['decisions']+=1;counts['reference_departures']+=int(not reference[action])
                _,reward,_,_,info=env.step(action);total_return+=reward
                if current_budget['possible'] is True and env.game.status=='laeuft':
                    after=env.view();after_budget=task_budget(after)
                    if after_budget['possible'] is False:
                        same_round=after['round']==view['round']
                        fixed_nonlevel=bool(after['last_round'] and after['board'][0] and after['board'][1] and after['attitude']!=0)
                        counts['same_round_count_losses' if same_round else 'round_boundary_count_losses']+=1
                        if same_round and fixed_nonlevel:counts['same_round_losses_fixed_nonlevel_rudder']+=1
                        if len(changes)<32:
                            changes.append(dict(step=env.steps,kind='capacity_transition',same_round=same_round,
                                fixed_nonlevel_final_rudder=fixed_nonlevel,action_id=action,
                                before=current_budget,after=after_budget,
                                net_plane_change=sum(r['planes'] for r in after['track'])-sum(r['planes'] for r in view['track'])))
                budget.pause()
            record=env.episode_record(game_seed,'both',total_return)
            record.update(airport=case['airport'],abilities=sorted(case['abilities']),modules=sorted(case['modules']),
                case_key=case_key(case),reference_departures=counts['reference_departures'],decisions=counts['decisions'])
            records.append(record)
            measurements.append(dict(seed=game_seed,counts=dict(counts),entry_budgets=entries,changes=changes))
    finally:model.train(was_training)
    if weight_fingerprint(model)!=before:raise RuntimeError('Weights changed during evaluation.')
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
    if actual!=metadata or comparison_fingerprint()!=code_sha:raise ValueError('Frozen sources or tensors changed.')


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
        parser.error('Use at most8 workers and duty<=.7.')
    if args.output.exists() or args.output.is_symlink():parser.error('Preserve earlier evidence; choose a new path.')
    try:
        check_stop();torch.set_num_threads(1);_,metadata=legacy.load_model(args.checkpoint)
        selected_cases=legacy.cases()
        for ordinal in range(len(selected_cases)):_development_seed(BASE_SEED+STRIDE*ordinal,GAMES)
    except (ValueError,OSError) as exc:parser.error(str(exc))
    code_sha,started=comparison_fingerprint(),time.monotonic()
    report=dict(format=1,complete=False,phase='public_early_task_capacity_guard',release_evidence=False,
        qualification_used=False,ppo_updates=0,new_training_decisions=0,same_network_tensors_all_arms=True,
        fresh_development=True,model=metadata,comparison_sha256=code_sha,joint_comparison_sha256=previous.comparison_fingerprint(),
        games_per_arm_case=GAMES,base_seed=BASE_SEED,seed_stride=STRIDE,workers=args.workers,
        cpu_duty_cycle=args.cpu_duty_cycle,threads=1,clock_model='engine_wall_clock',
        assumptions=['Only necessary public count feasibility, not face/ordering/coffee sufficiency.',
            'Helpers, dialogs, future synchronization uncertainty and already infeasible states abstain.',
            'No empty-action terminal is introduced; empty-result guard falls back.',
            'Original masks/references are preserved separately; this is a new research mask phase.',
            'Same-round count losses and round-boundary events are measured separately.',
            'Per-episode diagnostic traces are capped at32 events; outcomes/counts are complete.'],
        cases={case_key(row):{'case':row} for row in selected_cases})
    args.output.parent.mkdir(parents=True,exist_ok=True);_write(args.output,report,initial=True)
    try:
        with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize,initargs=(args.checkpoint,metadata,code_sha)) as pool:
            for arm in ARMS:
                tasks=[(arm,row,BASE_SEED+STRIDE*ordinal,args.cpu_duty_cycle) for ordinal,row in enumerate(selected_cases)]
                for key,output in pool.map(_run,tasks):
                    report['cases'][key][arm]=output
                    if arm=='deadline':
                        for baseline in ('prior','joint'):
                            report['cases'][key]['paired_'+baseline]=legacy.paired_details(report['cases'][key][baseline],output)
                    _write(args.output,report)
                    print(json.dumps(dict(case=key,arm=arm,wins=output['summary']['wins'],games=GAMES,counts=output['counts'])),flush=True)
        check_stop()
        if code_sha!=comparison_fingerprint() or legacy.load_model(args.checkpoint)[1]!=metadata:
            raise RuntimeError('Frozen sources or tensors changed during evaluation.')
        report.update(complete=True,elapsed_seconds=time.monotonic()-started);_write(args.output,report)
    except BaseException as exc:
        report.update(complete=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        _write(args.output,report);raise


if __name__=='__main__':main()
