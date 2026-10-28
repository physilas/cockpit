"""Paired public-strategy cross-play with unchanged historical crews.

Every actor receives only its permitted view. These AI partners are proxies,
not evidence about human win rates. Both learner roles are always reported.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import multiprocessing
from pathlib import Path
import time

from .checkpoints import load_checkpoint,weight_fingerprint
from .coherent_advice import CoherentBlueprint
from .coherent_safety import coherent_safe_actions
from .evaluate import summarize_episodes
from .module_training_eval import _development_seed,case_key
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .public_contract import PublicContractAgent
from .research_compare import atomic_json,research_fingerprint
from .rollout_search import GuidedBlueprint
from .safety_guard import ShieldedBlueprint


_model=_partners=None


def initialize(source,partners):
    import torch
    global _model,_partners
    torch.set_num_threads(1)
    _model=load_checkpoint(source)[0]
    _partners={name:load_checkpoint(path)[0] for name,path in partners.items()}


def play(task):
    case,partner,role,mode,games,seed=task
    _development_seed(seed,games)
    airport=case['airport']
    if mode=='public':learner=PublicContractAgent(airport,_model)
    elif mode=='responsive':
        from .response_contract import ResponseContractAgent
        learner=ResponseContractAgent(airport,_model)
    elif mode=='coherent':learner=CoherentBlueprint(airport,_model)
    else:learner=ShieldedBlueprint(airport,GuidedBlueprint(_model))
    teammate=GuidedBlueprint(_partners[partner])
    env=ModuleEnv(airport,abilities=case['abilities'],assistance_version=0,
                  round_reward=0.,sync_weight=0.,task_weight=0.)
    records=[];start=time.monotonic()
    for ordinal in range(games):
        env.reset(seed=seed+ordinal)
        total=0.;own=other=unsafe=partner_unsafe=0
        while not env.done:
            view,raw=env.view(),env.action_mask()
            own_turn=env.current_role==role
            chosen=(learner if own_turn else teammate).select(view,raw)
            if not raw[chosen]:raise RuntimeError('Cross-play actor left the native engine mask.')
            _,audit=coherent_safe_actions(airport,view,raw)
            bad=int(str(chosen) in audit['rejected'] and not audit['fallback'])
            if own_turn:own+=1;unsafe+=bad
            else:other+=1;partner_unsafe+=bad
            _,reward,_,_,_=env.step(chosen);total+=reward
        record=env.episode_record(seed+ordinal,role,total)
        record.update(learner_decisions=own,partner_decisions=other,
                      avoidable_immediate_losses=unsafe,partner_avoidable_immediate_losses=partner_unsafe)
        records.append(record)
    return dict(case=case,case_key=case_key(case),partner=partner,learner_role=role,mode=mode,
                clock_model='engine_wall_clock',wall_seconds=time.monotonic()-start,
                **summarize_episodes(records))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--partners',type=int,nargs='+',choices=(1,2,3,4),default=[1,3,4])
    p.add_argument('--modes',nargs='+',choices=('shield','public','responsive','coherent'),default=['shield','public'])
    p.add_argument('--all-cards',action='store_true')
    p.add_argument('--games',type=int,default=5)
    p.add_argument('--seed',type=int,default=14983050)
    p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.output.exists() or not 1<=args.workers<=4 or not 1<=args.games<=20:
        p.error('Use a new report, 1..4 workers and 1..20 games per exact condition.')
    cases=sorted(catalogue_cases(),key=case_key)
    if not args.all_cards:cases=list({r['airport']:r for r in reversed(cases)}.values())
    cases.sort(key=case_key)
    _development_seed(args.seed,(len(cases)-1)*100+40+args.games)
    partners={f'crew{i}':f'ai/releases/crew{i}-allroutes-2026-10-26-v1/best.pt' for i in args.partners}
    model=load_checkpoint(args.source)[0]
    config=dict(source=args.source,weights_sha256=weight_fingerprint(model),
        partner_checkpoints=partners,partner_weights_sha256={n:weight_fingerprint(load_checkpoint(p)[0]) for n,p in partners.items()},
        cases=cases,modes=args.modes,games=args.games,seed=args.seed,seed_stride=100,
        role_seed_offset=40,research_sha256=research_fingerprint(),workers=args.workers)
    del model
    report=dict(complete=False,release_evidence=False,qualification_used=False,
                scope='AI partner cross-play; no human win-rate claim.',config=config,results={})
    args.output.parent.mkdir(parents=True,exist_ok=True);atomic_json(args.output,report)
    tasks=[(case,partner,role,mode,args.games,args.seed+100*i+40*j)
           for i,case in enumerate(cases) for partner in partners for j,role in enumerate(('pilot','kopilot')) for mode in args.modes]
    pool=ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),
                             initializer=initialize,initargs=(args.source,partners))
    try:
        futures=[pool.submit(play,task) for task in tasks]
        for future in as_completed(futures):
            row=future.result();key='/'.join((row['case_key'],row['partner'],row['learner_role'],row['mode']))
            report['results'][key]=row;atomic_json(args.output,report)
            print(json.dumps(dict(condition=key,wins=row['wins'],games=row['games'])),flush=True)
    except BaseException:
        for worker in pool._processes.values():worker.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    else:pool.shutdown(wait=True)
    report['complete']=True;atomic_json(args.output,report)


if __name__=='__main__':main()
