"""Select a trained checkpoint on development seeds, never on confirmation games."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import json
import multiprocessing
from pathlib import Path
import random
from . import round_strategy_training as training
from .preview_matrix_eval import catalogue_cases
from .module_training_eval import case_key
from .round_strategy_evaluate import digest,SOURCES
from .ability_fingerprint import ability_fingerprint
from .briefing_browser_v2 import execution_fingerprint

_weights={}

def initialize(checkpoint,paths):
    global _weights
    training.initialize_worker(checkpoint);_weights={path:json.loads(Path(path).read_text()) for path in paths}


def play(job):
    _,row=training.play(training._worker_model,job['case'],job['seed'],weights=_weights.get(job['mode']),mode=job['mode'],wall_clock=True)
    return {**row,'mode':job['mode']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--weights',type=Path,nargs='+',required=True);p.add_argument('--checkpoint',default='ai/releases/crew6-abilities-2026-10-28-v1/best.pt');p.add_argument('--cohort',required=True);p.add_argument('--per-route',type=int,default=1);p.add_argument('--output',type=Path,required=True);p.add_argument('--workers',type=int,default=2);args=p.parse_args()
    if not args.cohort.startswith('development:') or args.output.exists() or not 1<=args.per_route<=5 or not 1<=args.workers<=2:raise ValueError('Use fresh development seeds, bounded starts and workers.')
    paths=[str(p) for p in args.weights];cases=[c for c in catalogue_cases() if c['airport'].startswith('LOG_')];routes=sorted({c['airport'] for c in cases});jobs=[]
    for airport in routes:
        options=sorted((c for c in cases if c['airport']==airport),key=lambda c:('synchronisation' not in c['abilities'],'control' not in c['abilities'],case_key(c)))
        for i in range(args.per_route):
            case=options[i%len(options)];seed=f'{args.cohort}:{case_key(case)}:{i}'
            jobs += [{'case':case,'seed':seed,'mode':mode} for mode in ['default','autonomous']+paths]
    random.Random(args.cohort+':order').shuffle(jobs)
    report={'complete':False,'cohort':args.cohort,'selection_rule':'Most landing wins, then fewer audited immediate losses, then earlier checkpoint; independent confirmation is mandatory.','weights_sha256':{path:digest(path) for path in paths},'source_sha256':digest(__file__),'runtime_sources_sha256':{name:digest(name) for name in SOURCES},'legacy_profile15_sha256':ability_fingerprint(),'learned_executor_sha256':execution_fingerprint(),'clock':'native engine wall time, including thermal pauses','records':[]}
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(args.checkpoint,paths)) as pool:
        futures={pool.submit(play,job):job for job in jobs}
        for future in as_completed(futures):
            try:row=future.result()
            except Exception as error:
                for pending in futures:pending.cancel()
                report['failure']={'job':futures[future],'type':type(error).__name__,'message':str(error)}
                training.atomic(args.output,report)
                raise
            report['records'].append(row);training.atomic(args.output,report)
            print(json.dumps({k:row[k] for k in ('mode','case','won','reason','seconds')}),flush=True)
    if digest(__file__)!=report['source_sha256'] or any(digest(name)!=sha for name,sha in report['runtime_sources_sha256'].items()) or any(digest(name)!=sha for name,sha in report['weights_sha256'].items()):raise ValueError('Development sources or weights changed during comparison.')
    totals={mode:sum(row['won'] for row in report['records'] if row['mode']==mode) for mode in ['default','autonomous']+paths}
    selected=max(paths,key=lambda path:(totals[path],-sum(r['avoidable_immediate_losses'] for r in report['records'] if r['mode']==path),-paths.index(path)))
    report.update(complete=True,wins=totals,selected=selected);training.atomic(args.output,report)


if __name__=='__main__':main()
