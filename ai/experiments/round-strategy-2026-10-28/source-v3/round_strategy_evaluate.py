"""Fresh paired evaluation of a frozen round selector, with a native engine clock."""
import argparse
import fcntl
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import random
from . import round_strategy_training as training
from .preview_matrix_eval import catalogue_cases
from .module_training_eval import case_key
from .ability_fingerprint import ability_fingerprint
from .briefing import policy_fingerprint

SOURCES=('ai/round_strategy.py','ai/round_strategy_training.py','ai/round_strategy_evaluate.py','ai/round_strategy_publish.py','ai/round_strategy_browser.py',
         'ai/briefing.py','ai/briefing_browser.py','ai/briefing_planner.py','play_options.py')
MODES=('default','learned','autonomous')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paired_statistics(records):
    groups={}
    for row in records:
        modes=groups.setdefault(row['seed'],{})
        if row['mode'] in modes:raise ValueError('Duplicate comparison row.')
        modes[row['mode']]=row
    if not groups or any(set(rows)!=set(MODES) for rows in groups.values()):raise ValueError('Incomplete paired comparison.')
    wins={mode:sum(rows[mode]['won'] for rows in groups.values()) for mode in MODES}
    better=sum(rows['learned']['won'] and not rows['default']['won'] for rows in groups.values())
    worse=sum(rows['default']['won'] and not rows['learned']['won'] for rows in groups.values())
    n=better+worse;p=sum(math.comb(n,k) for k in range(better,n+1))/2**n if n else 1.
    safe=all(not r['truncated'] and not r['avoidable_immediate_losses'] for r in records)
    strata={}
    for name,field,flag in [('wind','modules','wind'),('synchronisation','abilities','synchronisation')]:
        selected=[rows for rows in groups.values() if flag in rows['default'].get(field,[])]
        if selected:
            strata[name]={'games_per_mode':len(selected),'wins':{mode:sum(rows[mode]['won'] for rows in selected) for mode in MODES}}
    no_stratum_regression=all(row['wins']['learned']>=max(row['wins']['default'],row['wins']['autonomous']) for row in strata.values())
    return {'games_per_mode':len(groups),'wins':wins,'paired_improvements':better,'paired_regressions':worse,
            'one_sided_p':p,'safe':safe,'strata':strata,'no_stratum_regression':no_stratum_regression,'qualification_granted':safe and no_stratum_regression and better-worse>=3 and p<=.1 and wins['learned']>=wins['autonomous']}


def freeze(weights,checkpoint,cohort,per_route):
    if not cohort.startswith('confirmation:') or not 1<=per_route<=20:raise ValueError('Declare a fresh confirmation cohort and bounded starts.')
    expected=Path(__file__).resolve().parents[1]/'ai/releases/crew6-abilities-2026-10-28-v1/best.pt'
    if digest(checkpoint)!=digest(expected):raise ValueError('Confirmation must use the exact released Crew6 blueprint.')
    cases=[c for c in catalogue_cases() if c['airport'].startswith('LOG_')]
    routes=sorted({c['airport'] for c in cases});jobs=[]
    for airport in routes:
        options=sorted((c for c in cases if c['airport']==airport),key=lambda c:('synchronisation' not in c['abilities'],'control' not in c['abilities'],case_key(c)))
        for i in range(per_route):
            case=options[i%len(options)];seed=f'{cohort}:{case_key(case)}:{i}'
            for mode in MODES:jobs.append({'case':case,'seed':seed,'mode':mode})
    random.Random(cohort+':order').shuffle(jobs)
    return {'format':1,'legacy_profile15_sha256':ability_fingerprint(),'briefing_executor_sha256':policy_fingerprint(),'cohort':cohort,'weights':str(weights),'weights_sha256':digest(weights),'checkpoint':str(checkpoint),'checkpoint_sha256':digest(checkpoint),
            'sources':{p:digest(p) for p in SOURCES},'clock':'native engine wall time; thermal pauses remain part of elapsed time',
            'per_route':per_route,'routes':routes,'jobs':jobs,'rule':'At least 3 net wins over fixed briefing, paired one-sided binomial p<=0.1, no fewer wins than autonomous Crew6; no audited immediate loss or truncation; no lower wind/synchronisation win count than either control. No tuning on confirmation outcomes.'}


_weights=None

def initialize(checkpoint,weights):
    global _weights
    training.initialize_worker(checkpoint);_weights=json.loads(Path(weights).read_text())


def evaluate(job):
    _,row=training.play(training._worker_model,job['case'],job['seed'],weights=_weights if job['mode']=='learned' else None,mode=job['mode'],wall_clock=True)
    return {**row,'mode':job['mode']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['freeze','run']);p.add_argument('--weights',type=Path);p.add_argument('--checkpoint',type=Path,default=Path('ai/releases/crew6-abilities-2026-10-28-v1/best.pt'));p.add_argument('--cohort');p.add_argument('--per-route',type=int,default=2);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--output',type=Path);p.add_argument('--workers',type=int,default=2);args=p.parse_args()
    if args.mode=='freeze':
        if args.manifest.exists():raise ValueError('Use a new immutable manifest.')
        training.atomic(args.manifest,freeze(args.weights,args.checkpoint,args.cohort,args.per_route));return
    manifest=json.loads(args.manifest.read_text())
    expected=freeze(Path(manifest['weights']),Path(manifest['checkpoint']),manifest['cohort'],manifest['per_route'])
    if manifest!=expected:raise ValueError('Source, weights, cases or protocol changed after freeze.')
    if args.output is None or args.output.exists() or not 1<=args.workers<=2:raise ValueError('Use a fresh output and 1..2 workers.')
    ledger=Path('runs/round-strategy-confirmation-cohorts.jsonl');ledger.parent.mkdir(parents=True,exist_ok=True)
    with ledger.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0)
        if any(json.loads(line)['cohort']==manifest['cohort'] for line in stream):raise ValueError('Confirmation cohort already used; do not tune and reuse.')
        stream.write(json.dumps({'cohort':manifest['cohort'],'manifest':str(args.manifest),'manifest_sha256':digest(args.manifest)})+'\n');stream.flush()
    with args.manifest.with_suffix('.started').open('x') as marker:marker.write(digest(args.manifest)+'\n')
    report={'complete':False,'protocol':manifest,'records':[]}
    with ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(manifest['checkpoint'],manifest['weights'])) as pool:
        for future in as_completed([pool.submit(evaluate,job) for job in manifest['jobs']]):
            row=future.result();report['records'].append(row);training.atomic(args.output,report)
            print(json.dumps({k:row[k] for k in ('mode','case','won','reason','seconds')}),flush=True)
    report['statistics']=paired_statistics(report['records']);report['complete']=True;training.atomic(args.output,report)


if __name__=='__main__':main()
