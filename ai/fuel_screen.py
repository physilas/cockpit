"""Development-only comparison of fuel planners on identical model weights."""
import argparse
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
from pathlib import Path

import torch
from .agents import ModelAgent
from .checkpoints import load_checkpoint, planner_fingerprint
from .evaluate import evaluate,summarize_episodes


def _run(task):
    checkpoint,profile,start,games=task
    torch.set_num_threads(1)
    model,_=load_checkpoint(checkpoint)
    return evaluate(ModelAgent(model),airport='LOG_OSL_GREEN',assistance_version=profile,
                    games=games,seed=start,round_reward=0,cpu_duty_cycle=.5)['episodes']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True)
    p.add_argument('--games',type=int,default=80)
    p.add_argument('--seed',type=int,default=14000000)
    p.add_argument('--profiles',nargs='+',type=int,default=[3,4,5,6])
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.games<1 or not set(args.profiles).issubset({3,4,5,6,7,8}):p.error('Invalid development budget/profile.')
    report={'format':1,'phase':'development_only','seed':args.seed,'planner_sha256':planner_fingerprint(),'profiles':{}}
    with ProcessPoolExecutor(6,mp_context=multiprocessing.get_context('spawn')) as pool:
        for profile in args.profiles:
            tasks=[(str(args.checkpoint),profile,args.seed+start,min(20,args.games-start)) for start in range(0,args.games,20)]
            rows=[r for group in pool.map(_run,tasks) for r in group]
            result=summarize_episodes(rows)
            report['profiles'][str(profile)]={k:v for k,v in result.items() if k!='episodes'}
            print(profile,result['win_rate'],result['loss_reasons'],flush=True)
            args.output.parent.mkdir(parents=True,exist_ok=True)
            args.output.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
