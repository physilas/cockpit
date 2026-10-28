"""Fresh paired games for residual-learning candidates with identical masks."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import multiprocessing
from pathlib import Path
import re

from .checkpoints import load_checkpoint,weight_fingerprint
from .coherent_advice import CoherentBlueprint
from .coherent_safety import coherent_safe_actions
from .evaluate import summarize_episodes
from .module_training_eval import case_key,_development_seed
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .research_compare import atomic_json,research_fingerprint


_models=None


def initialize(manifest):
    import torch
    global _models
    torch.set_num_threads(1)
    _models={name:load_checkpoint(path)[0] for name,path in manifest.items()}


def play(task):
    case,name,games,seed=task
    _development_seed(seed,games)
    agent=CoherentBlueprint(case['airport'],_models[name])
    env=ModuleEnv(case['airport'],abilities=case['abilities'],assistance_version=0,
                  round_reward=0.,sync_weight=0.,task_weight=0.)
    records=[]
    for ordinal in range(games):
        env.reset(seed=seed+ordinal);total=0.;decisions=unsafe=0
        while not env.done:
            view,raw=env.view(),env.action_mask()
            action=agent.select(view,raw)
            if not raw[action]:raise RuntimeError('Candidate selected outside native engine mask.')
            _,audit=coherent_safe_actions(case['airport'],view,raw)
            unsafe+=int(str(action) in audit['rejected'] and not audit['fallback'])
            decisions+=1
            _,reward,_,_,_=env.step(action);total+=reward
        record=env.episode_record(seed+ordinal,'both',total)
        record.update(decisions=decisions,avoidable_immediate_losses=unsafe)
        records.append(record)
    return dict(case=case,case_key=case_key(case),mode=name,clock_model='engine_wall_clock',
                **summarize_episodes(records))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--all-cards',action='store_true')
    p.add_argument('--games',type=int,default=10)
    p.add_argument('--seed',type=int,default=14955050)
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    manifest=json.loads(args.manifest.read_text())
    if (args.output.exists() or not 1<=args.workers<=4 or not 1<=args.games<=40
            or not isinstance(manifest,dict) or not manifest
            or any(not re.fullmatch('[a-z][a-z0-9-]*',name) for name in manifest)):
        p.error('Use a new report, named checkpoints, 1..4 workers and 1..40 games.')
    cases=sorted(catalogue_cases(),key=case_key)
    if not args.all_cards:cases=list({r['airport']:r for r in reversed(cases)}.values())
    cases.sort(key=case_key)
    _development_seed(args.seed,(len(cases)-1)*100+args.games)
    fingerprints={name:weight_fingerprint(load_checkpoint(path)[0]) for name,path in manifest.items()}
    config=dict(manifest=manifest,weights_sha256=fingerprints,cases=cases,modes=list(manifest),
                games=args.games,seed=args.seed,seed_stride=100,policy='public_coherent_profile14',
                research_sha256=research_fingerprint(),workers=args.workers)
    report=dict(complete=False,release_evidence=False,qualification_used=False,config=config,results={})
    args.output.parent.mkdir(parents=True,exist_ok=True);atomic_json(args.output,report)
    tasks=[(case,name,args.games,args.seed+100*i) for i,case in enumerate(cases) for name in manifest]
    pool=ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(manifest,))
    try:
        for future in as_completed([pool.submit(play,t) for t in tasks]):
            row=future.result();report['results'][row['case_key']+'/'+row['mode']]=row
            atomic_json(args.output,report)
            print(json.dumps(dict(case_key=row['case_key'],mode=row['mode'],wins=row['wins'],games=row['games'])),flush=True)
    except BaseException:
        for worker in pool._processes.values():worker.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    else:pool.shutdown(wait=True)
    report['complete']=True;atomic_json(args.output,report)


if __name__=='__main__':main()
