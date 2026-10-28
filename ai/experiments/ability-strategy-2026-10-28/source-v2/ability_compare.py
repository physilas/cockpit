"""Paired, replayable profile-13/profile-15 games with frozen source hashes.

Development and confirmation use disjoint named seed cohorts. Confirmation
cannot be resumed or reused for tuning; its marker reserves the complete cohort.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import fcntl
import json
import multiprocessing
from pathlib import Path
import time
from .ability_fingerprint import ability_fingerprint
from .checkpoints import load_checkpoint, weight_fingerprint
from .coherent_safety import coherent_safe_actions
from .evaluate import summarize_episodes
from .module_training_eval import case_key
from .modules import MODULE_ACTIONS, ModuleEnv
from .preview_matrix_eval import catalogue_cases
from .research_compare import atomic_json

_model = None


def initialize(checkpoint):
    import torch
    global _model
    torch.set_num_threads(1)
    _model = load_checkpoint(checkpoint)[0]
    _model.eval()


def play(task):
    case, mode, games, cohort = task
    from .ability_policy import AbilityAgent
    from .public_contract import PublicContractAgent
    agent = (AbilityAgent if mode == 'candidate' else PublicContractAgent)(case['airport'], _model)
    env = ModuleEnv(case['airport'], abilities=case['abilities'], assistance_version=0,max_steps=256,
                    round_reward=0., sync_weight=0., task_weight=0.)
    records = []
    for ordinal in range(games):
        seed = f'{cohort}:{case_key(case)}:{ordinal}'
        env.reset(seed=seed)
        total = 0.; unsafe = stranded = previous = decisions = bonuses = refills = 0
        last_round = False; landing_wind = None; times = []; cpu_times = []; regular_refills = bonus_refills = range_events = 0; previous_range_dead = False
        while not env.done:
            view, raw = env.view(), env.action_mask()
            tick = time.monotonic(); cpu_tick = time.process_time(); action = agent.select(view, raw); times.append(time.monotonic()-tick); cpu_times.append(time.process_time()-cpu_tick)
            if not raw[action]:
                raise RuntimeError('Planner left the native mask.')
            _, audit = coherent_safe_actions(case['airport'], view, raw)
            unsafe += int(str(action) in audit['rejected'] and not audit['fallback'])
            chosen = MODULE_ACTIONS[action]
            bonuses += int(chosen.kind == 'bonus_roll')
            if chosen.kind in ('place','bonus_place'):
                slot = chosen.slot
                refill = int(7 <= slot < 10 and view['gear'][slot-7] or 10 <= slot < 14 and view['flaps'][slot-10])
                refills += refill
                regular_refills += refill * int(chosen.kind=='place')
                bonus_refills += refill * int(chosen.kind=='bonus_place')
            decisions += 1
            _, reward, _, _, _ = env.step(action); total += reward
            public = env.view()
            count = sum(c['planes'] for c in public['track'] if c['distance'] > public['distance'])
            stranded += int(count > previous); previous = count
            maximum = 2 if 'wind' in public['modules_state']['modules'] else (int(12>=public['aero_blue'])+int(12>=public['aero_orange']))
            range_dead = public['distance']>maximum*max(0,public['height']//1000)
            range_events += int(range_dead and not previous_range_dead); previous_range_dead = range_dead
            if public['last_round']:
                last_round = True; landing_wind = public['modules_state']['wind_value']
        record = env.episode_record(seed, 'both', total)
        record.update(avoidable_immediate_losses=unsafe,stranded_plane_events=stranded,
                      stranded_planes=previous,decisions=decisions,synchronisation_bonuses=bonuses,
                      switch_refills=refills,regular_switch_refills=regular_refills,bonus_switch_refills=bonus_refills,irreversible_range_events=range_events,reached_landing=last_round,landing_wind=landing_wind,
                      decision_seconds=sum(times),max_decision_seconds=max(times,default=0.),cpu_decision_seconds=sum(cpu_times),max_cpu_decision_seconds=max(cpu_times,default=0.))
        records.append(record)
    return dict(case=case,case_key=case_key(case),mode=mode,clock_model='engine_wall_clock',**summarize_episodes(records))


def selected_cases(focus=False):
    cases = sorted(catalogue_cases(), key=case_key)
    if not focus:
        return cases
    # One synchronization case per affected route, plus Control on windy routes.
    selected = {}
    for case in cases:
        if 'synchronisation' in case['abilities']:
            selected.setdefault(case['airport'], case)
    result = list(selected.values())
    for case in cases:
        if 'wind' in case['modules'] and 'control' in case['abilities'] and 'synchronisation' not in case['abilities']:
            if not any(r['airport']==case['airport'] and 'control' in r['abilities'] for r in result):
                result.append(case)
    return sorted(result,key=case_key)


def source_sha():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def freeze(checkpoint, games, cohort, focus=False, confirmation=False):
    if not isinstance(cohort,str) or not cohort or type(games) is not int or not 1<=games<=40:
        raise ValueError('Use a named seed cohort and 1..40 games.')
    if type(focus) is not bool or type(confirmation) is not bool or not cohort.startswith('confirmation:' if confirmation else 'development:'):
        raise ValueError('Declare a disjoint development or confirmation cohort.')
    import build
    sources=json.loads((Path('frontend/web/js/engine-src.js')).read_text().split('const ENGINE_SRC = ',1)[1].rstrip(';\n'))
    for name in build.PYTHON_DATEIEN + ['ai/ability_planner.py','ai/ability_policy.py','ai/ability_browser.py']:
        if sources.get(name)!=Path(name).read_text():
            raise ValueError('Browser bundle is stale: '+name)
    model = load_checkpoint(checkpoint)[0]
    return dict(version=1,max_steps=256,checkpoint=str(checkpoint),weights_sha256=weight_fingerprint(model),
                planner_sha256=ability_fingerprint(),evaluation_sha256=source_sha(),
                cases=selected_cases(focus),games=games,cohort=cohort,focus=focus,confirmation=confirmation,
                modes=['baseline','candidate'],selection_rule='At least5 extra wins and a higher equal-route mean in full confirmation; zero avoidable immediate losses/truncations; unchanged cases identical. No tuning on confirmation outcomes.',
                qualification_granted=False)


def run(manifest_path, output, workers):
    manifest = json.loads(manifest_path.read_text())
    fresh = freeze(manifest['checkpoint'],manifest['games'],manifest['cohort'],manifest['focus'],manifest['confirmation'])
    if fresh != manifest:
        raise ValueError('Source/checkpoint/protocol changed after freeze.')
    if output.exists() or not 1<=workers<=2:
        raise ValueError('Use a new report and 1..2 workers.')
    if manifest['confirmation']:
        ledger = Path('runs/ability-confirmation-cohorts.jsonl')
        ledger.parent.mkdir(parents=True,exist_ok=True)
        with ledger.open('a+') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX);stream.seek(0)
            if any(json.loads(line)['cohort']==manifest['cohort'] for line in stream):
                raise ValueError('Confirmation cohort already used.')
            stream.write(json.dumps(dict(cohort=manifest['cohort'],manifest=str(manifest_path)))+'\n');stream.flush()
    marker = manifest_path.with_suffix('.started')
    with marker.open('x') as stream:
        stream.write(hashlib.sha256(manifest_path.read_bytes()).hexdigest()+'\n')
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(complete=False,release_evidence=manifest['confirmation'],qualification_granted=False,config=manifest,results={})
    atomic_json(output,report)
    tasks = [(case,mode,manifest['games'],manifest['cohort']) for case in manifest['cases'] for mode in manifest['modes']]
    pool = ProcessPoolExecutor(workers,mp_context=multiprocessing.get_context('spawn'),initializer=initialize,initargs=(manifest['checkpoint'],))
    try:
        for future in as_completed([pool.submit(play,task) for task in tasks]):
            row = future.result(); report['results'][row['case_key']+'/'+row['mode']] = row
            atomic_json(output,report)
            print(json.dumps(dict(case_key=row['case_key'],mode=row['mode'],wins=row['wins'],games=row['games'])),flush=True)
    except BaseException:
        for worker in pool._processes.values():worker.terminate()
        pool.shutdown(wait=True,cancel_futures=True);raise
    else:
        pool.shutdown(wait=True)
    if ability_fingerprint()!=manifest['planner_sha256'] or source_sha()!=manifest['evaluation_sha256']:
        raise ValueError('Source changed while evaluation was running; results are invalid.')
    report['complete']=True;atomic_json(output,report)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('freeze','run'));p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--output',type=Path);p.add_argument('--checkpoint',default='ai/releases/crew5-planner-2026-10-28-v1/best.pt')
    p.add_argument('--games',type=int,default=3);p.add_argument('--cohort',default='development:ability-v1:2026-10-28')
    p.add_argument('--focus',action='store_true');p.add_argument('--confirmation',action='store_true');p.add_argument('--workers',type=int,default=2)
    args=p.parse_args()
    if args.action=='freeze':
        manifest=freeze(args.checkpoint,args.games,args.cohort,args.focus,args.confirmation)
        args.manifest.parent.mkdir(parents=True,exist_ok=True)
        with args.manifest.open('x') as stream:stream.write(json.dumps(manifest,indent=2)+'\n')
    else:
        if args.output is None:p.error('Output required.')
        run(args.manifest,args.output,args.workers)


if __name__=='__main__':main()
