"""New bounded research comparison: native, preserved microplans, fair prior.

Same actual Crew5 tensors in all three arms,20 games for each of12 official
Wind/Ice single-card cases. Fresh development14987000+100*case; no PPO or
qualification. The earlier experiment's code and cohorts stay unchanged.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time
from unittest.mock import patch

import torch

from . import wind_ice_compare as legacy
from .leak_strength_compare import _write
from .module_training_eval import _development_seed, case_key
from .wind_ice_prior_environment import PriorWindIceEnv


BASE_SEED, STRIDE, GAMES = 14_987_000, 100, 20
ARMS = ('native', 'microplans', 'prior')


def comparison_fingerprint():
    digest = hashlib.sha256(legacy.comparison_fingerprint().encode())
    root = Path(__file__).resolve().parents[1]
    for name in ('ai/public_hand_prior.py', 'ai/wind_ice_prior_advice.py',
                 'ai/wind_ice_prior_environment.py', 'ai/wind_ice_prior_compare.py',
                 'ai/experiments/modules-30pct-2026-10-25/matrix.json',
                 'backend/landekatalog.json', 'backend/landung.py', 'backend/regeln.py', 'backend/wuerfelfeld.py'):
        digest.update(name.encode()); digest.update((root/name).read_bytes())
    return digest.hexdigest()


def run_arm(model, case, arm, seed, games, duty=.7):
    if arm not in ARMS:
        raise ValueError('Use native, microplans or prior.')
    legacy.check_stop()
    if arm != 'prior':
        return legacy.run_arm(model, case, arm, seed, games, duty)

    class Checked(PriorWindIceEnv):
        def info(self):
            result = super().info()
            if result.get('research_wind_ice_prior') is not True:
                raise RuntimeError('The new research environment must be explicitly marked.')
            micro = result['microplans_reference_action_mask']
            if (len(micro) != len(result['action_mask']) or any(type(flag) is not bool for flag in micro)
                    or any(flag and not result['action_mask'][index] for index, flag in enumerate(micro))):
                raise RuntimeError('The saved same-state earlier microplan reference is invalid.')
            return result

    with patch.object(legacy, 'WindIceEnv', Checked):
        return legacy.run_arm(model, case, 'microplans', seed, games, duty)


_model = None


def _initialize(checkpoint, metadata, code_sha):
    global _model
    torch.set_num_threads(1)
    legacy.check_stop()
    _model, actual = legacy.load_model(checkpoint)
    if actual != metadata or comparison_fingerprint() != code_sha:
        raise ValueError('Frozen tensors or new research sources changed.')


def _run(task):
    arm, case, seed, duty = task
    return case_key(case), run_arm(_model, case, arm, seed, GAMES, duty)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=Path('ai/releases/crew5-leak-preview-v1/best.pt'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8 or not math.isfinite(args.cpu_duty_cycle) or not 0 < args.cpu_duty_cycle <= .7:
        parser.error('Use at most8 workers and CPU duty<=.7.')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Preserve earlier evidence; choose a new output path.')
    try:
        legacy.check_stop(); torch.set_num_threads(1)
        _, metadata = legacy.load_model(args.checkpoint)
        selected_cases = legacy.cases()
        for ordinal in range(len(selected_cases)):
            _development_seed(BASE_SEED + STRIDE * ordinal, GAMES)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    code_sha, started = comparison_fingerprint(), time.monotonic()
    report = {'format': 1, 'complete': False, 'phase': 'public_joint_partner_fair_hand_prior',
        'release_evidence': False, 'qualification_used': False, 'ppo_updates': 0,
        'new_training_decisions': 0, 'fresh_development': True, 'same_policy_all_arms': True,
        'model': metadata, 'comparison_sha256': code_sha, 'legacy_comparison_sha256': legacy.comparison_fingerprint(),
        'changes': ['IID_hypothetical_partner_joint_controls', 'public_future_radio_capacity_upper_bound', 'current_Control_card_coffee_gain'],
        'assumptions': ['Fair IID remaining hands are a model, not the posterior after public action selection.',
            'One own plan is fixed before averaging over hypothetical private hands.',
            'Partner radio capacity is optimistic and does not prove matching faces.',
            'No future bonus dice or future coffee generation are assumed.'],
        'games_per_arm_case': GAMES, 'base_seed': BASE_SEED, 'seed_stride': STRIDE,
        'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
        'clock_model': 'engine_wall_clock', 'cases': {case_key(row): {'case': row} for row in selected_cases}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    _write(args.output, report, initial=True)
    try:
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize, initargs=(args.checkpoint, metadata, code_sha)) as pool:
            for arm in ARMS:
                tasks = [(arm, row, BASE_SEED + STRIDE * ordinal, args.cpu_duty_cycle) for ordinal, row in enumerate(selected_cases)]
                for key, output in pool.map(_run, tasks):
                    report['cases'][key][arm] = output
                    if arm == 'prior':
                        report['cases'][key]['paired_native'] = legacy.paired_details(report['cases'][key]['native'], output)
                        report['cases'][key]['paired_microplans'] = legacy.paired_details(report['cases'][key]['microplans'], output)
                    _write(args.output, report)
                    print(json.dumps({'case': key, 'arm': arm, 'wins': output['summary']['wins'],
                        'games': GAMES, 'counts': output['counts']}), flush=True)
        legacy.check_stop()
        if code_sha != comparison_fingerprint() or legacy.load_model(args.checkpoint)[1] != metadata:
            raise RuntimeError('Model or research sources changed during the trial.')
        report.update(complete=True, elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
    except BaseException as exc:
        report.update(complete=False, error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
        raise


if __name__ == '__main__':
    main()
