"""Fixed public planner, paired development comparison of two frozen blueprints.

No training, source changes or held-out outcomes select the blueprint here.
Actors see permitted views; every route receives equal development games.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import multiprocessing
from pathlib import Path
import time

from .checkpoints import load_checkpoint,weight_fingerprint
from .coherent_safety import coherent_safe_actions
from .evaluate import summarize_episodes
from .module_training_eval import _development_seed,case_key
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .public_contract import PublicContractAgent
from .research_compare import atomic_json
from .strategy_fingerprint import public_strategy_fingerprint


_models=None


def initialize(paths):
    import torch
    global _models
    torch.set_num_threads(1)
    _models={name:load_checkpoint(path)[0] for name,path in paths.items()}
    for model in _models.values():model.eval()


def select_blueprint(report):
    if report.get('complete') is not True:raise ValueError('Use the complete paired development comparison.')
    cases=report['config']['cases'];games=report['config']['games'];totals={}
    if not cases or len(report['results'])!=2*len(cases):raise ValueError('Every case and both blueprints are required.')
    for mode in ('crew4','crew3'):
        records=[]
        for case in cases:
            key=case_key(case);row=report['results'][key+'/'+mode]
            if row['games']!=games or len(row['episodes'])!=games:raise ValueError('Incomplete game batch.')
            other=report['results'][key+'/'+('crew3' if mode=='crew4' else 'crew4')]
            seeds=[e['seed'] for e in row['episodes']]
            if len(set(seeds))!=games or set(seeds)!={e['seed'] for e in other['episodes']}:
                raise ValueError('Blueprints must play the identical unique seed cohort.')
            records.extend(row['episodes'])
        totals[mode]=dict(games=len(records),wins=sum(e['status']=='gewonnen' for e in records),
            coffee_reversals=sum(e['coffee_reversals'] for e in records),
            stranded_plane_events=sum(e['stranded_plane_events'] for e in records),
            avoidable_immediate_losses=sum(e['avoidable_immediate_losses'] for e in records),
            truncations=sum(e['status']=='unentschieden_abgebrochen' for e in records))
    a,b=totals['crew4'],totals['crew3']
    selected=(b['wins']>=a['wins']+5 and b['coffee_reversals']<=a['coffee_reversals']
              and b['stranded_plane_events']<=a['stranded_plane_events']
              and b['avoidable_immediate_losses']==0 and b['truncations']==0)
    return dict(selected='crew3' if selected else 'crew4',totals=totals,
                rule='At least5 additional wins, no additional coffee reversals/stranding, no detected avoidable immediate losses or truncations.')


def play(task):
    case,mode,games,seed=task
    _development_seed(seed,games)
    airport=case['airport'];agent=PublicContractAgent(airport,_models[mode])
    env=ModuleEnv(airport,abilities=case['abilities'],assistance_version=0,
                  round_reward=0.,sync_weight=0.,task_weight=0.)
    episodes=[];started=time.monotonic()
    for ordinal in range(games):
        env.reset(seed=seed+ordinal);total=0.;unsafe=stranding=previous=decisions=0
        while not env.done:
            view,raw=env.view(),env.action_mask();chosen=agent.select(view,raw)
            if not raw[chosen]:raise RuntimeError('Blueprint comparison left the native mask.')
            _,audit=coherent_safe_actions(airport,view,raw)
            unsafe+=int(str(chosen) in audit['rejected'] and not audit['fallback']);decisions+=1
            _,reward,_,_,_=env.step(chosen);total+=reward
            public=env.view();count=sum(c['planes'] for c in public['track'] if c['distance']>public['distance'])
            stranding+=int(count>previous);previous=count
        record=env.episode_record(seed+ordinal,'both',total)
        record.update(avoidable_immediate_losses=unsafe,stranded_plane_events=stranding,
                      stranded_planes=previous,decisions=decisions)
        episodes.append(record)
    return dict(case=case,case_key=case_key(case),mode=mode,clock_model='engine_wall_clock',
                wall_seconds=time.monotonic()-started,**summarize_episodes(episodes))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--games',type=int,default=5)
    p.add_argument('--seed',type=int,default=14997050);p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.output.exists() or not 1<=args.workers<=2 or not 1<=args.games<=10:
        p.error('Use a new output, 1..2 workers and 1..10 development games.')
    cases=sorted(catalogue_cases(),key=case_key)
    cases=list({r['airport']:r for r in reversed(cases)}.values());cases.sort(key=case_key)
    _development_seed(args.seed,(len(cases)-1)*100+args.games)
    paths={f'crew{i}':f'ai/releases/crew{i}-allroutes-2026-10-26-v1/best.pt' for i in (4,3)}
    config=dict(checkpoints=paths,weights_sha256={n:weight_fingerprint(load_checkpoint(path)[0]) for n,path in paths.items()},
                profile=13,public_strategy_sha256=public_strategy_fingerprint(13),cases=cases,
                modes=list(paths),games=args.games,seed=args.seed,seed_stride=100)
    report=dict(complete=False,release_evidence=False,qualification_used=False,config=config,results={})
    args.output.parent.mkdir(parents=True,exist_ok=True);atomic_json(args.output,report)
    tasks=[(c,mode,args.games,args.seed+100*i) for i,c in enumerate(cases) for mode in paths]
    pool=ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(paths,))
    try:
        for future in as_completed([pool.submit(play,t) for t in tasks]):
            row=future.result();report['results'][row['case_key']+'/'+row['mode']]=row;atomic_json(args.output,report)
            print(json.dumps(dict(case_key=row['case_key'],mode=row['mode'],games=row['games'],wins=row['wins'])),flush=True)
    except BaseException:
        for worker in pool._processes.values():worker.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    else:pool.shutdown(wait=True)
    report['complete']=True;report['selection']=select_blueprint(report);atomic_json(args.output,report)


if __name__=='__main__':main()
