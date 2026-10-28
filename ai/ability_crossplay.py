"""Fixed-policy diagnostic: Crew 6 as either role alongside the unchanged Crew 5.

This does not train, select hyperparameters or grant release approval. The same
frozen real-engine harness runs baseline and mixed crews on independent seeds.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import multiprocessing
from pathlib import Path
from unittest.mock import patch

from .ability_compare import initialize, play, selected_cases, source_sha
from .ability_fingerprint import ability_fingerprint
from .checkpoints import load_checkpoint, weight_fingerprint
from .research_compare import atomic_json


def mixed_game(task):
    case,mode,games,cohort=task
    if mode=='baseline':return play(task)
    from .ability_policy import AbilityAgent
    from .public_contract import PublicContractAgent
    role=mode.removeprefix('candidate_')
    class MixedAgent:
        def __init__(self,airport,model):
            self.new=AbilityAgent(airport,model);self.old=PublicContractAgent(airport,model)
        def select(self,view,mask):
            return (self.new if view['role']==role else self.old).select(view,mask)
    # Injection is process-local; the frozen engine, planner files and weights
    # are untouched. The original class is restored even on a failed game.
    with patch('ai.ability_policy.AbilityAgent',MixedAgent):
        row=play((case,'candidate',games,cohort))
    row['mode']=mode
    return row


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--games',type=int,default=3);p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.output.exists() or not 1<=args.games<=10 or not 1<=args.workers<=2:raise ValueError('Fresh report, 1..10 games and 1..2 workers required.')
    model,payload=load_checkpoint(args.checkpoint)
    if payload['train_config'].get('assistance_version')!=15 or payload['train_config'].get('planner_sha256')!=ability_fingerprint():raise ValueError('Prepared current candidate required.')
    cases=selected_cases(True);modes=['baseline','candidate_pilot','candidate_kopilot']
    manifest=dict(cohort='development:ability-crossplay:v1:2026-10-28',games=args.games,cases=cases,modes=modes,
        weights_sha256=weight_fingerprint(model),planner_sha256=ability_fingerprint(),evaluation_sha256=source_sha(),
        diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        purpose='Independent mixed-crew diagnostic; no training, candidate selection or qualification.')
    del model
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.with_suffix('.started').open('x') as stream:stream.write(json.dumps(manifest,indent=2)+'\n')
    report=dict(complete=False,release_evidence=False,qualification_granted=False,config=manifest,results={})
    atomic_json(args.output,report)
    pool=ProcessPoolExecutor(args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(args.checkpoint,))
    try:
        tasks=[(case,mode,args.games,manifest['cohort']) for case in cases for mode in modes]
        for future in as_completed([pool.submit(mixed_game,task) for task in tasks]):
            row=future.result();report['results'][row['case_key']+'/'+row['mode']]=row;atomic_json(args.output,report)
        pool.shutdown(wait=True)
    except BaseException:
        for process in pool._processes.values():process.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    if manifest['planner_sha256']!=ability_fingerprint() or manifest['evaluation_sha256']!=source_sha():raise ValueError('Frozen policy/harness changed during diagnostic.')
    if len(report['results'])!=len(cases)*len(modes):raise ValueError('Incomplete diagnostic.')
    report['summary']={mode:{'games':sum(r['games'] for r in report['results'].values() if r['mode']==mode),
        'wins':sum(r['wins'] for r in report['results'].values() if r['mode']==mode),
        'avoidable_immediate_losses':sum(e['avoidable_immediate_losses'] for r in report['results'].values() if r['mode']==mode for e in r['episodes']),
        'truncations':sum(e['status']=='unentschieden_abgebrochen' for r in report['results'].values() if r['mode']==mode for e in r['episodes'])} for mode in modes}
    report['complete']=True;atomic_json(args.output,report);print(json.dumps(report['summary'],indent=2))


if __name__=='__main__':main()
