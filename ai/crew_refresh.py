"""Explicit all-route development of canonical crews; historical releases survive.

Selection uses equal weight per official route, not per card count. It is a
user-requested preview selection, never a claim that each case meets a floor.
"""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from copy import deepcopy
import hashlib
import json
import multiprocessing
from pathlib import Path
import time
import torch
from .checkpoints import load_checkpoint, save_checkpoint, model_schema, planner_fingerprint, weight_fingerprint
from .modules import module_schema, MODULES, CARDS
from .nn_model import GuidedResidualActorCritic
from .module_training_eval import load_cases, case_key, _development_seed
from .public_case_eval import run_public_case
from .intern_strength_compare import tensor_fingerprint

ROOT=Path(__file__).resolve().parents[1]
MATRIX=ROOT/'ai/experiments/modules-30pct-2026-10-25/matrix.json'
SOURCES={'crew1':'crew-basegame-v1','crew2-base':'crew2-v1','crew2-fuel':'crew2-kerosene-v1',
         'crew3-intern':'crew3-current-preview-v2','crew3-leak':'crew5-leak-preview-v1',
         'crew4-old':'crew4-leak-preview-v1'}
_CACHE={}

def check_stop():
    if (ROOT/'runs/STOP_AI_TRAINING').exists():
        raise ValueError('Persistent stop is active; explicit resumption is required.')

def evaluation_fingerprint():
    digest=hashlib.sha256(planner_fingerprint(3).encode())
    paths=[Path(__file__),ROOT/'ai/public_case_eval.py']
    paths.extend(p for p in (ROOT/'backend').rglob('*') if p.is_file() and p.suffix in ('.py','.json','.yaml'))
    for p in sorted(paths):
        digest.update(p.relative_to(ROOT).as_posix().encode());digest.update(p.read_bytes())
    return digest.hexdigest()

def selection_score(rows):
    grouped=defaultdict(list)
    for row in rows.values():grouped[row['airport']].append(row['win_rate'])
    if len(rows)!=186 or len(grouped)!=21:raise ValueError('Selection requires all 186 official cases.')
    means=[sum(values)/len(values) for values in grouped.values()]
    base=[r['win_rate'] for r in rows.values() if not r['modules']]
    return sum(means)/len(means),sum(base)/len(base),min(means)

def prepare(folder):
    folder=Path(folder).resolve()
    if folder.exists():raise ValueError('Preserve previous phase sources.')
    folder.mkdir(parents=True)
    torch.set_num_threads(1);torch.manual_seed(261001)
    cases=load_cases(MATRIX);manifest={}
    for identity,release in SOURCES.items():
        path=ROOT/f'ai/releases/{release}/best.pt';source,payload=load_checkpoint(path)
        original_sha=weight_fingerprint(source)
        if identity=='crew1':
            old,new=model_schema(source),module_schema()
            if any(old[k]!=new[k][:len(old[k])] for k in ('features','actions')):
                raise ValueError('Old schema is not an exact prefix.')
            model=GuidedResidualActorCritic(source,489,217,guide_margin=4.)
            if weight_fingerprint(model.source)!=original_sha:raise RuntimeError('Foundation changed.')
        else:model=source
        lineage={'source_checkpoint':str(path.relative_to(ROOT)),
          'source_weights_sha256':original_sha,'source_tensor_sha256':tensor_fingerprint(source),
          'source_training_config':deepcopy(payload['train_config']),
          'source_phase_steps':payload['total_steps'],
          'adapter_added':identity=='crew1','new_training_decisions':0,
          'phase_kind':'explicit_public_all_route_exposure_2026_10_26',
          'evaluation_fingerprint':evaluation_fingerprint()}
        config={**lineage,'schema_version':3,'assistance_version':12,'action_mask_version':2,
          'planner_sha256':planner_fingerprint(3),'supported_modules':list(MODULES),
          'supported_cards':list(CARDS),'ability_count':'case_specific','supported_cases':cases,
          'publication_status':'development_preview_only','independent_qualification_used':False}
        destination=folder/f'{identity}.pt'
        save_checkpoint(destination,model,train_config=config,total_steps=payload['total_steps'],
                        module_training_steps=payload.get('module_training_steps',0))
        manifest[identity]=str(destination.relative_to(ROOT))
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

def _init():torch.set_num_threads(1)

def _evaluate(task):
    identity,path,case,games,seed,duty=task
    check_stop()
    if path not in _CACHE:_CACHE[path]=load_checkpoint(path)[0]
    model=_CACHE[path]
    return identity,run_public_case(model,case,games,seed,cpu_duty_cycle=duty,assistance_version=12)

def compare(manifest,output,*,seed,games,workers=8,duty=.6):
    check_stop()
    if not 1<=workers<=8 or not 0<duty<=.6:raise ValueError('At most eight workers at .6 duty.')
    _development_seed(seed+185*100,games)
    if not 1<=games<=100:raise ValueError('Use 1..100 games per case.')
    if output.exists():raise ValueError('Preserve previous comparison reports.')
    cases=sorted(load_cases(MATRIX),key=case_key)
    started=time.monotonic();reports={}
    for identity,path in manifest.items():
        model,payload=load_checkpoint(path)
        reports[identity]={'complete':False,'release_evidence':False,'qualification_used':False,
          'weights_sha256':weight_fingerprint(model),'tensor_sha256':tensor_fingerprint(model),
          'assistance_version':12,'planner_sha256':planner_fingerprint(3),
          'evaluation_fingerprint':evaluation_fingerprint(),'checkpoint':str(path),
          'seed':seed,'seed_stride':100,'games_per_case':games,'cases':{}}
    output.parent.mkdir(parents=True,exist_ok=True)
    def write():
        tmp=output.with_suffix('.tmp');tmp.write_text(json.dumps({'complete':all(r['complete'] for r in reports.values()),
          'release_evidence':False,'selection':'equal_route_mean_then_base_mean_then_worst_route',
          'workers':workers,'cpu_duty_cycle':duty,'threads':1,'total_wall_seconds':time.monotonic()-started,
          'models':reports},indent=2,allow_nan=False)+'\n');tmp.replace(output)
    write()
    tasks=[(identity,str(path),case,games,seed+i*100,duty) for identity,path in manifest.items()
           for i,case in enumerate(cases)]
    with ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn'),initializer=_init) as pool:
        futures=[pool.submit(_evaluate,task) for task in tasks]
        for ordinal,future in enumerate(as_completed(futures),1):
            identity,row=future.result();reports[identity]['cases'][row['case_key']]=row
            if len(reports[identity]['cases'])==186:
                reports[identity].update(complete=True,selection_score=list(selection_score(reports[identity]['cases'])))
                print(json.dumps({'model':identity,'score':reports[identity]['selection_score'],'cases':186}),flush=True)
            if ordinal%30==0:write()
    write()
    for identity,report in reports.items():
        output.with_name(output.stem+'-'+identity+'.json').write_text(json.dumps(report,indent=2)+'\n')
    return reports

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['prepare','compare'])
    p.add_argument('--folder',type=Path,default=Path('runs/crew-refresh-2026-10-26'))
    p.add_argument('--manifest',type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--seed',type=int,default=14820000);p.add_argument('--games',type=int,default=10)
    p.add_argument('--workers',type=int,default=8);p.add_argument('--cpu-duty-cycle',type=float,default=.6)
    a=p.parse_args()
    if a.action=='prepare':prepare(a.folder)
    else:
        if not a.output:p.error('--output is required')
        manifest=json.loads((a.manifest or a.folder/'manifest.json').read_text())
        compare(manifest,a.output,seed=a.seed,games=a.games,workers=a.workers,duty=a.cpu_duty_cycle)
if __name__=='__main__':main()
