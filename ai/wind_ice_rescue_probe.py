"""Passive public diagnosis on40 namespaced TRAINING games, no updates.

Specifically locates fatal rudders still chosen by the unchanged Crew5 under
microplans. Only own hand and placed public controls are retained; no unseen
partner values, engine RNG state or future rolls are accessed by the probe.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import time

import torch

from .agents import ModelAgent
from .leak_strength_compare import _write
from .module_physics import predict_rudder
from .modules import MODULE_ACTIONS, MODULE_SLOTS
from .throttle import CpuBudget
from .wind_ice_advice import eligible, wind_ice_plans
from .wind_ice_compare import check_stop, comparison_fingerprint, load_model
from .wind_ice_environment import WindIceEnv


def fatal_rudder(view, action):
    if action.kind not in ('place', 'bonus_place') or MODULE_SLOTS[action.slot].target != 'ruder':
        return False
    owner = MODULE_SLOTS[action.slot].owner
    if action.kind == 'bonus_place':
        pending = view['modules_state']['pending']
        face = pending['value'] if pending else None
    else:
        face = view['own_dice'][action.die]
    if face is None or view['board'][1 if owner == 'pilot' else 0] is None:
        return False
    return predict_rudder(view, **{f'{owner}_value': face})['stalled']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    check_stop()
    if args.output.exists() or args.output.is_symlink(): parser.error('Preserve previous evidence.')
    torch.set_num_threads(1)
    model, metadata = load_model('ai/releases/crew5-leak-preview-v1/best.pt')
    model.eval()
    rng, torch_rng = random.getstate(), torch.get_rng_state().clone()
    fingerprint = comparison_fingerprint()
    own_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = {'complete': False, 'phase': 'passive_wind_ice_fatal_rudder_probe', 'ppo_updates': 0,
        'release_evidence': False, 'qualification_used': False, 'training_games': 40,
        'training_namespace': 'train:wind-ice-rescue-probe:251066:',
        'model': metadata, 'comparison_sha256': fingerprint, 'probe_sha256': own_sha,
        'workers': 1, 'cpu_duty_cycle': .7, 'threads': 1, 'episodes': [], 'fatal_rudders': []}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, report, initial=True)
    started, counts, budget = time.monotonic(), Counter(), CpuBudget(.7)
    try:
        agent = ModelAgent(model)
        for ordinal in range(40):
            airport, card = ('LOG_GIG_YELLOW', 'adaptation') if ordinal < 20 else ('LOG_KEF_YELLOW', 'control')
            env = WindIceEnv(airport, abilities=[card], planning_cpu_duty_cycle=.7)
            seed = report['training_namespace'] + str(ordinal)
            _, info = env.reset(seed=seed)
            total = 0.
            while not env.done:
                check_stop()
                view = env.view()
                selected = agent.select(view, info['action_mask'], reference_mask=info['reference_action_mask'])
                action = MODULE_ACTIONS[selected]
                if fatal_rudder(view, action):
                    plans = wind_ice_plans(view, info['action_mask'], cpu_duty_cycle=.7)
                    reroll = next(i for i, item in enumerate(MODULE_ACTIONS) if item.kind == 'reroll_start')
                    row = {'seed': seed, 'airport': airport, 'card': card, 'step': env.steps,
                        'height': view['height'], 'distance': view['distance'], 'role': view['role'],
                        'attitude': view['attitude'], 'coffee': view['coffee'],
                        'own_dice': list(view['own_dice']), 'partner_remaining': view['partner_remaining'],
                        'public_controls': view['board'][:4], 'action_id': selected,
                        'pending': view['modules_state']['pending'], 'eligible': eligible(view),
                        'microplans_empty': not plans, 'reroll_engine_legal': info['action_mask'][reroll],
                        'reference_is_source': info['reference_action_mask'] == info['source_reference_action_mask']}
                    report['fatal_rudders'].append(row)
                    counts['fatal_rudders'] += 1
                    counts['empty_plans_with_legal_reroll'] += int(not plans and info['action_mask'][reroll])
                    counts['pending_bonus'] += int(view['modules_state']['pending'] is not None)
                _, reward, _, _, info = env.step(selected)
                total += reward
                budget.pause()
            report['episodes'].append(env.episode_record(seed, 'both', total))
        if (not torch.equal(torch_rng, torch.get_rng_state()) or random.getstate() != rng
                or comparison_fingerprint() != fingerprint or load_model('ai/releases/crew5-leak-preview-v1/best.pt')[1] != metadata):
            raise RuntimeError('Probe changed RNG, model or research sources.')
        report.update(complete=True, counts=dict(counts), elapsed_seconds=time.monotonic() - started)
    except BaseException as exc:
        report.update(error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
        raise
    finally:
        _write(args.output, report)
    print(json.dumps({'complete': report['complete'], 'counts': report['counts'], 'elapsed_seconds': report['elapsed_seconds']}))


if __name__ == '__main__':
    main()
