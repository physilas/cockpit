"""Passive first-1000ft/final-entry diagnostic on new TRAINING namespaces.

Two games for each of twelve Wind/Ice card cases, unchanged prior player. No
PPO or new development cohort, and no private faces recorded or used by probe.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import torch

from .agents import ModelAgent
from .landing_task_budget import task_budget
from .leak_strength_compare import _write
from .module_training_eval import case_key
from .throttle import CpuBudget
from .wind_ice_prior_environment import PriorWindIceEnv
from . import wind_ice_compare as legacy
from .wind_ice_prior_compare import comparison_fingerprint as prior_fingerprint


def probe_fingerprint():
    root=Path(__file__).resolve().parents[1]
    fingerprint=hashlib.sha256(prior_fingerprint().encode())
    for name in ('ai/landing_task_budget.py','ai/landing_budget_probe.py'):
        fingerprint.update(name.encode());fingerprint.update((root/name).read_bytes())
    return fingerprint.hexdigest()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint',type=Path,default=Path('ai/releases/crew5-leak-preview-v1/best.pt'))
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.output.exists() or args.output.is_symlink():parser.error('Preserve earlier evidence; choose a new path.')
    try:legacy.check_stop();torch.set_num_threads(1);model,metadata=legacy.load_model(args.checkpoint)
    except (ValueError,OSError) as exc:parser.error(str(exc))
    code_sha=prior_fingerprint()
    probe_sha=probe_fingerprint()
    started=time.monotonic()
    report=dict(format=1,complete=False,phase='passive_training_task_deadline_probe',release_evidence=False,
        qualification_used=False,ppo_updates=0,new_training_decisions=0,sampled_training_decisions=0,
        model=metadata,probe_sha256=probe_sha,prior_comparison_sha256=code_sha,workers=1,cpu_duty_cycle=.7,threads=1,
        games_per_case=2,seed_namespace='train:landing-budget-probe:251070:',episodes=[])
    args.output.parent.mkdir(parents=True,exist_ok=True);_write(args.output,report,initial=True)
    model.eval();agent=ModelAgent(model);budget=CpuBudget(.7)
    try:
        for ordinal,case in enumerate(legacy.cases()):
            for game_number in range(2):
                legacy.check_stop()
                seed=f'train:landing-budget-probe:251070:{ordinal}:{game_number}'
                env=PriorWindIceEnv(case['airport'],abilities=case['abilities'],planning_cpu_duty_cycle=.7,
                    max_steps=256,round_reward=0.,sync_weight=0.,task_weight=0.)
                _,info=env.reset(seed=seed);seen=set();entries=[]
                while not env.done:
                    legacy.check_stop();view=env.view()
                    stage='final' if view['last_round'] else '1000ft' if view['height']==1000 else None
                    if stage is not None and stage not in seen:
                        seen.add(stage)
                        entries.append(dict(stage=stage,round=view['round'],height=view['height'],distance=view['distance'],
                            budget=task_budget(view)))
                    selected=agent.select(view,info['action_mask'],reference_mask=info['reference_action_mask'])
                    _,_,_,_,info=env.step(selected)
                    report['sampled_training_decisions']+=1;budget.pause()
                report['episodes'].append(dict(seed=seed,case_key=case_key(case),entries=entries,
                    status=env.game.status,reason=env.game.verlust_grund))
                _write(args.output,report)
        grouped={}
        for stage in ('1000ft','final'):
            counts=Counter()
            for row in report['episodes']:
                for entry in row['entries']:
                    if entry['stage']==stage:counts[str(entry['budget']['possible'])]+=1
            grouped[stage]=dict(counts)
        legacy.check_stop()
        if prior_fingerprint()!=code_sha or probe_fingerprint()!=probe_sha or legacy.load_model(args.checkpoint)[1]!=metadata:
            raise RuntimeError('Sources or frozen model changed during probe.')
        report.update(complete=True,entry_counts=grouped,elapsed_seconds=time.monotonic()-started)
        _write(args.output,report);print(json.dumps(dict(complete=True,entries=grouped,seconds=report['elapsed_seconds'])))
    except BaseException as exc:
        report.update(complete=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        _write(args.output,report);raise


if __name__=='__main__':main()
