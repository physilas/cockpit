"""Independent paired kerosene qualification, with a separate partner probe.

Select the checkpoint before running this command. Never use these seeds to
pick a checkpoint or tune a planner. Self-play is not a human success estimate.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
from statistics import mean,stdev

import torch

from .agents import HeuristicAgent,ModelAgent
from .checkpoints import load_checkpoint,weight_fingerprint,planner_fingerprint,model_schema
from .evaluate import evaluate,summarize_episodes


def _run(task):
    checkpoint,profile,seed,games,role,partner=task
    torch.set_num_threads(1)
    model,_=load_checkpoint(checkpoint)
    return evaluate(ModelAgent(model),airport='LOG_OSL_GREEN',assistance_version=profile,
                    games=games,seed=seed,ai_role=role,partner=HeuristicAgent() if partner else None,
                    round_reward=0,cpu_duty_cycle=.5)['episodes']


def compact(records):
    return {k:v for k,v in summarize_episodes(records).items() if k!='episodes'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    p.add_argument('--games',type=int,default=500)
    p.add_argument('--partner-games',type=int,default=100)
    p.add_argument('--seed',type=int,default=15000000)
    p.add_argument('--minimum-win-rate',type=float,default=.5)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.games<200 or args.partner_games<1 or not .5<=args.minimum_win_rate<=1:
        p.error('At least 200 independent self-play games and a quality floor >=.5 are required.')
    torch.set_num_threads(1)
    model,payload=load_checkpoint(args.checkpoint)
    baseline,_=load_checkpoint(args.baseline)
    if payload.get('module_training_steps',0)<=0 or weight_fingerprint(model)==weight_fingerprint(baseline):
        p.error('The candidate must contain actual new module training.')
    profile=payload['train_config']['assistance_version']
    report={'format':1,'date':'2026-10-25','schema_version':model_schema(model)['version'],
            'checkpoint_sha256':hashlib.sha256(args.checkpoint.read_bytes()).hexdigest(),
            'weights_sha256':weight_fingerprint(model),'planner_sha256':planner_fingerprint(model_schema(model)['version']),
            'assistance_version':profile,'seed':args.seed,'minimum_win_rate':args.minimum_win_rate,
            'module_training_steps':payload['module_training_steps'],'routes':{},'qualified_routes':[],
            'note':'Independent self-play qualification. Untrained padded source uses the same fuel planner. Heuristic partner results do not predict human win rates.'}
    with ProcessPoolExecutor(6,mp_context=multiprocessing.get_context('spawn')) as pool:
        conditions={}
        for name,path in [('trained',args.checkpoint),('untrained_expansion',args.baseline)]:
            tasks=[(str(path),profile,args.seed+start,min(25,args.games-start),'both',False)
                   for start in range(0,args.games,25)]
            conditions[name]=[r for group in pool.map(_run,tasks) for r in group]
            print(name,compact(conditions[name])['win_rate'],flush=True)
        diffs=[int(a['status']=='gewonnen')-int(b['status']=='gewonnen')
               for a,b in zip(conditions['trained'],conditions['untrained_expansion'])]
        delta=mean(diffs)
        margin=1.96*stdev(diffs)/math.sqrt(len(diffs))
        report['neural_comparison']={'baseline_weights_sha256':weight_fingerprint(baseline),
            'baseline':compact(conditions['untrained_expansion']),'pairs':len(diffs),
            'improved':diffs.count(1),'worse':diffs.count(-1),'win_rate_delta':delta,
            'paired_normal_ci95':[delta-margin,delta+margin],
            'reliable_improvement':delta-margin>0,
            'outcomes':[{'seed':a['seed'],'trained':a['status'],'baseline':b['status']}
                        for a,b in zip(conditions['trained'],conditions['untrained_expansion'])]}
        partner_rows=[]
        for role in ('pilot','kopilot'):
            tasks=[(str(args.checkpoint),profile,args.seed+100000+start,min(25,args.partner_games-start),role,True)
                   for start in range(0,args.partner_games,25)]
            partner_rows += [r for group in pool.map(_run,tasks) for r in group]
        partner=compact(partner_rows)
        partner['by_role']={r:compact([e for e in partner_rows if e['ai_role']==r]) for r in ('pilot','kopilot')}
        result=compact(conditions['trained'])
        report['routes']['LOG_OSL_GREEN']={'self':result,'heuristic_partner':partner}
        if result['win_ci_low']>=args.minimum_win_rate:report['qualified_routes'].append('LOG_OSL_GREEN')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'qualified':report['qualified_routes'],'self_win_rate':result['win_rate'],
                     'paired_delta':delta,'paired_ci95':[delta-margin,delta+margin],'partner_win_rate':partner['win_rate']}),flush=True)


if __name__=='__main__':main()
