"""Freeze one selected public policy, then use the reserved cold cohort once.

This is a paired independent confirmation, not automatic quality approval.
No per-route win floor is silently relaxed. Every zero-win case is retained.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import fcntl
import json
import multiprocessing
from pathlib import Path
import time

from .checkpoints import load_checkpoint,weight_fingerprint
from .coherent_advice import CoherentBlueprint
from .coherent_safety import coherent_safe_actions
from .evaluate import summarize_episodes
from .module_training_eval import case_key
from .modules import ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .public_contract import PublicContractAgent
from .research_compare import atomic_json
from .rollout_search import GuidedBlueprint
from .safety_guard import ShieldedBlueprint
from .strategy_fingerprint import public_strategy_fingerprint,ROOT


_candidate=_baseline=_profile=None


def file_sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_bundle():
    from build import PYTHON_DATEIEN
    text=(ROOT/'frontend/web/js/engine-src.js').read_text()
    sources=json.loads(text.split('const ENGINE_SRC = ',1)[1].strip().rstrip(';'))
    for name in PYTHON_DATEIEN:
        if sources.get(name)!=(ROOT/name).read_text():
            raise ValueError('Browser bundle is stale; rebuild before freezing: '+name)


def freeze(checkpoint,profile,baseline,seed,games):
    if type(profile) is not int or profile not in (13,14):raise ValueError('Select public profile13 or14.')
    if not 1<=games<=100 or not 15_400_000<=seed or seed+191*100+games>15_500_000:
        raise ValueError('Use the reserved15.4M cohort, fixed stride100 and1..100 games.')
    validate_bundle()
    candidate,payload=load_checkpoint(checkpoint);control,_=load_checkpoint(baseline)
    if payload['train_config'].get('assistance_version')!=profile:
        raise ValueError('The frozen checkpoint must declare the selected public profile.')
    if (payload['train_config'].get('max_steps')!=256 or
            payload['train_config'].get('planner_sha256')!=public_strategy_fingerprint(profile)):
        raise ValueError('Candidate configuration must match the tested256-decision public policy.')
    return dict(version=1,kind='frozen_public_strategy_confirmation',candidate_checkpoint=checkpoint,
        candidate_file_sha256=file_sha(checkpoint),candidate_weights_sha256=weight_fingerprint(candidate),
        profile=profile,max_steps=256,baseline_checkpoint=baseline,baseline_file_sha256=file_sha(baseline),
        baseline_weights_sha256=weight_fingerprint(control),baseline_policy='shielded_legacy_profile12',
        public_strategy_sha256=public_strategy_fingerprint(profile),seed=seed,games=games,seed_stride=100,
        confirmation_code_sha256=file_sha(__file__),
        cases=sorted(catalogue_cases(),key=case_key),
        selection_rule='Policy selected on development data before this manifest; no tuning or selection on these outcomes.',
        qualification_granted=False)


def check_manifest(manifest):
    fresh=freeze(manifest['candidate_checkpoint'],manifest['profile'],manifest['baseline_checkpoint'],
                 manifest['seed'],manifest['games'])
    if manifest!=fresh:raise ValueError('Frozen files, strategy, cases or protocol changed; do not reuse the cold cohort.')


def initialize(manifest):
    import torch
    global _candidate,_baseline,_profile
    torch.set_num_threads(1)
    _candidate=load_checkpoint(manifest['candidate_checkpoint'])[0]
    _baseline=load_checkpoint(manifest['baseline_checkpoint'])[0]
    _profile=manifest['profile']


def claim_cohort(manifest,manifest_path,output,*,ledger=None):
    ledger=ledger or ROOT/'runs/confirmation-cohorts.jsonl'
    ledger.parent.mkdir(parents=True,exist_ok=True)
    proposed={manifest['seed']+100*i+j for i in range(len(manifest['cases'])) for j in range(manifest['games'])}
    with ledger.open('a+') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0)
        for line in stream:
            old=json.loads(line)
            used={old['seed']+100*i+j for i in range(old['cases']) for j in range(old['games'])}
            if proposed&used:raise ValueError('This reserved seed cohort was already claimed; do not reuse confirmation outcomes.')
        stream.write(json.dumps(dict(seed=manifest['seed'],games=manifest['games'],cases=len(manifest['cases']),
            manifest=str(manifest_path),output=str(output)))+'\n');stream.flush()


def play(task):
    case,mode,games,seed=task
    airport=case['airport']
    if mode=='baseline':agent=ShieldedBlueprint(airport,GuidedBlueprint(_baseline))
    elif _profile==13:agent=PublicContractAgent(airport,_candidate)
    else:agent=CoherentBlueprint(airport,_candidate)
    env=ModuleEnv(airport,abilities=case['abilities'],assistance_version=0,
                  round_reward=0.,sync_weight=0.,task_weight=0.)
    records=[]
    for ordinal in range(games):
        env.reset(seed=seed+ordinal);total=0.;decisions=unsafe=stranding=range_dead_events=0
        previous_stranded=0;previous_range_dead=False;decision_times=[]
        while not env.done:
            view,raw=env.view(),env.action_mask()
            tick=time.monotonic()
            action=agent.select(view,raw)
            decision_times.append(time.monotonic()-tick)
            if not raw[action]:raise RuntimeError('Frozen policy left the native engine mask.')
            _,audit=coherent_safe_actions(airport,view,raw)
            unsafe+=int(str(action) in audit['rejected'] and not audit['fallback']);decisions+=1
            _,reward,_,_,_=env.step(action);total+=reward
            public=env.view()
            count=sum(c['planes'] for c in public['track'] if c['distance']>public['distance'])
            stranding+=int(count>previous_stranded);previous_stranded=count
            maximum=2 if 'wind' in public['modules_state']['modules'] else (
                int(12>=public['aero_blue'])+int(12>=public['aero_orange']))
            range_dead=public['distance']>maximum*max(0,public['height']//1000)
            range_dead_events+=int(range_dead and not previous_range_dead)
            previous_range_dead=range_dead
        record=env.episode_record(seed+ordinal,'both',total)
        record.update(decisions=decisions,avoidable_immediate_losses=unsafe,
                      stranded_plane_events=stranding,stranded_planes=previous_stranded,
                      irreversible_range_events=range_dead_events,
                      decision_seconds=sum(decision_times),max_decision_seconds=max(decision_times,default=0.))
        records.append(record)
    return dict(case=case,case_key=case_key(case),mode=mode,clock_model='engine_wall_clock',
                **summarize_episodes(records))


def run(manifest_path,output,workers):
    manifest=json.loads(manifest_path.read_text());check_manifest(manifest)
    if output.exists() or not 1<=workers<=4:raise ValueError('Use a new report and1..4 workers.')
    marker=manifest_path.with_suffix('.started')
    if marker.exists():raise ValueError('This frozen manifest was already started; keep incomplete evidence incomplete.')
    claim_cohort(manifest,manifest_path,output)
    with marker.open('x') as stream:stream.write(file_sha(manifest_path)+'\n')
    report=dict(complete=False,release_evidence=False,qualification_used=True,qualification_granted=False,
        evidence_kind='held_out_confirmation',frozen_manifest_sha256=file_sha(manifest_path),
        config=dict(cases=manifest['cases'],modes=['baseline','candidate'],seed=manifest['seed'],games=manifest['games'],
                    protocol=manifest),results={})
    output.parent.mkdir(parents=True,exist_ok=True);atomic_json(output,report)
    tasks=[(case,mode,manifest['games'],manifest['seed']+i*100)
           for i,case in enumerate(manifest['cases']) for mode in ('baseline','candidate')]
    # The new report path acts as the one-run marker. No resume/restart on the
    # reserved cohort; incomplete evidence remains explicitly incomplete.
    pool=ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(manifest,))
    try:
        for future in as_completed([pool.submit(play,t) for t in tasks]):
            row=future.result();report['results'][row['case_key']+'/'+row['mode']]=row
            atomic_json(output,report)
            print(json.dumps(dict(case_key=row['case_key'],mode=row['mode'],wins=row['wins'],games=row['games'])),flush=True)
    except BaseException:
        for worker in pool._processes.values():worker.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    else:pool.shutdown(wait=True)
    check_manifest(manifest)
    report['complete']=True;atomic_json(output,report)
    evidence=dict(complete=True,release_evidence=False,evaluation_kind='held_out_confirmation_development_preview',
        qualification_used=True,qualification_granted=False,weights_sha256=manifest['candidate_weights_sha256'],
        assistance_version=manifest['profile'],max_steps=manifest['max_steps'],planner_sha256=manifest['public_strategy_sha256'],
        frozen_manifest_sha256=file_sha(manifest_path),cases={})
    for case in manifest['cases']:
        key=case_key(case);row=report['results'][key+'/candidate']
        evidence['cases'][key]={**case,**{k:v for k,v in row.items() if k not in ('case','mode')}}
    atomic_json(output.with_name(output.stem+'-candidate.json'),evidence)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=('freeze','run'))
    p.add_argument('--manifest',type=Path,required=True);p.add_argument('--checkpoint')
    p.add_argument('--profile',type=int,choices=(13,14),default=13)
    p.add_argument('--baseline',default='ai/releases/crew4-allroutes-2026-10-26-v1/best.pt')
    p.add_argument('--seed',type=int,default=15400000);p.add_argument('--games',type=int,default=20)
    p.add_argument('--output',type=Path);p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.action=='freeze':
        if not args.checkpoint or args.manifest.exists():p.error('Use a checkpoint and a new frozen manifest.')
        atomic_json(args.manifest,freeze(args.checkpoint,args.profile,args.baseline,args.seed,args.games))
    else:
        if args.output is None:p.error('A new output path is required.')
        run(args.manifest,args.output,args.workers)


if __name__=='__main__':main()
