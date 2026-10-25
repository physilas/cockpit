"""Fresh bounded native/prior/static-joint-landing comparison, no PPO.

Same frozen Crew5 tensors,12 official Wind/Ice card cases,20 games/arm/case.
Development14992000+100*case; old sources and evaluation fingerprints preserved.
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
from unittest.mock import patch

import torch

from .agents import ModelAgent
from .joint_landing_environment import JointLandingEnv
from .leak_strength_compare import _write
from .module_training_eval import _development_seed,case_key
from . import wind_ice_compare as legacy
from . import wind_ice_prior_compare as prior


BASE_SEED,STRIDE,GAMES=14_992_000,100,20
ARMS=('native','prior','joint')
STOP_FILE=Path('runs/STOP_AI_TRAINING')


def check_stop():
    if STOP_FILE.exists():raise ValueError('Persistent training stop is active.')


def comparison_fingerprint():
    digest=hashlib.sha256(prior.comparison_fingerprint().encode())
    root=Path(__file__).resolve().parents[1]
    for name in ('ai/joint_round.py','ai/joint_landing_prior.py','ai/joint_landing_advice.py',
                 'ai/joint_landing_environment.py','ai/joint_landing_compare.py'):
        digest.update(name.encode());digest.update((root/name).read_bytes())
    return digest.hexdigest()


def run_arm(model,case,arm,seed,games,duty=.7):
    check_stop()
    if arm not in ARMS:raise ValueError('Use native,prior or joint.')
    if arm!='joint':return prior.run_arm(model,case,arm,seed,games,duty)
    class Measured(JointLandingEnv):
        def reset(self,**kwargs):
            self._joint_counts=Counter();self._joint_changes=[];self._joint_last_info=None
            return super().reset(**kwargs)

        def info(self):
            result=super().info()
            if result.get('research_joint_landing') is not True:raise RuntimeError('Missing research marker.')
            ref=result['prior_reference_action_mask'];allowed=result['action_mask']
            if (len(ref)!=len(allowed) or any(type(v) is not bool for v in ref)
                    or any(v and not allowed[i] for i,v in enumerate(ref))):
                raise RuntimeError('Invalid same-state prior reference.')
            self._joint_last_info=result
            return result

        def step(self,selected):
            check_stop()
            info=self._joint_last_info;meta=info['joint_landing']
            changed=info['prior_reference_action_mask']!=info['reference_action_mask']
            self._joint_counts['eligible_decisions']+=int(meta['eligible'])
            self._joint_counts['positive_decisions']+=int(meta['positive_candidates']>0)
            self._joint_counts['changed_prior_reference']+=int(changed)
            if changed:
                previous=ModelAgent(model).select(self.view(),info['action_mask'],reference_mask=info['prior_reference_action_mask'])
                self._joint_counts['changed_prior_policy_choices']+=int(previous!=selected)
                self._joint_changes.append(dict(step=self.steps,role=self.current_role,action_id=selected,
                    prior_action_id=previous,maximum_assignment_score=meta['maximum_assignment_score']))
            return super().step(selected)

        def episode_record(self,*args,**kwargs):
            record=super().episode_record(*args,**kwargs)
            record.update(joint_landing_counts=dict(self._joint_counts),joint_landing_changes=list(self._joint_changes))
            return record

    with patch.object(legacy,'WindIceEnv',Measured):
        output=legacy.run_arm(model,case,'microplans',seed,games,duty)
    totals=Counter()
    for row in output['summary']['episodes']:totals.update(row['joint_landing_counts'])
    output['joint_landing_counts']=dict(totals)
    return output


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
        check_stop();torch.set_num_threads(1)
        _,metadata=legacy.load_model(args.checkpoint)
        selected_cases=legacy.cases()
        for ordinal in range(len(selected_cases)):_development_seed(BASE_SEED+STRIDE*ordinal,GAMES)
    except (ValueError,OSError) as exc:parser.error(str(exc))
    code_sha,started=comparison_fingerprint(),time.monotonic()
    report=dict(format=1,complete=False,phase='public_static_joint_landing_tasks',release_evidence=False,
        qualification_used=False,ppo_updates=0,new_training_decisions=0,same_network_tensors_all_arms=True,
        fresh_development=True,model=metadata,comparison_sha256=code_sha,prior_comparison_sha256=prior.comparison_fingerprint(),
        games_per_arm_case=GAMES,base_seed=BASE_SEED,seed_stride=STRIDE,workers=args.workers,
        cpu_duty_cycle=args.cpu_duty_cycle,threads=1,clock_model='engine_wall_clock',
        assumptions=['Fixed own continuation and shared-task ownership before fair IID partner-hand expectation.',
            'All mandatory tasks and controls use distinct dice and one stored coffee budget.',
            'Current macro coffee/Adaptation is modeled; future coffee/Adaptation/cards/bonus generation omitted.',
            'Static assignment does not prove temporal ordering or full engine success.',
            'Only pure Wind/Ice final round; previous prior reference everywhere else.',
            'Assignment score is not a calibrated real-hand posterior or a game win probability.'],
        cases={case_key(row):{'case':row} for row in selected_cases})
    args.output.parent.mkdir(parents=True,exist_ok=True);_write(args.output,report,initial=True)
    try:
        with ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize,initargs=(args.checkpoint,metadata,code_sha)) as pool:
            for arm in ARMS:
                tasks=[(arm,row,BASE_SEED+STRIDE*ordinal,args.cpu_duty_cycle) for ordinal,row in enumerate(selected_cases)]
                for key,output in pool.map(_run,tasks):
                    report['cases'][key][arm]=output
                    if arm=='joint':
                        for baseline in ('native','prior'):
                            report['cases'][key]['paired_'+baseline]=legacy.paired_details(report['cases'][key][baseline],output)
                    _write(args.output,report)
                    print(json.dumps(dict(case=key,arm=arm,wins=output['summary']['wins'],games=GAMES,
                        joint_counts=output.get('joint_landing_counts',{}))),flush=True)
        check_stop()
        if code_sha!=comparison_fingerprint() or legacy.load_model(args.checkpoint)[1]!=metadata:
            raise RuntimeError('Frozen sources or tensors changed during evaluation.')
        report.update(complete=True,elapsed_seconds=time.monotonic()-started);_write(args.output,report)
    except BaseException as exc:
        report.update(complete=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        _write(args.output,report);raise


if __name__=='__main__':main()
