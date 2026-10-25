"""Bounded paired development: unchanged Crew5, native vs wind/ice reference.

Twelve official single-card cases,20 games each, fresh development14985000
with stride100. No PPO, qualification, browser release or tensor changes.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time
from unittest.mock import patch

import torch

from .agents import ModelAgent
from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .leak_strength_compare import _report_path, _write
from .module_training_eval import _development_seed, case_key, load_cases
from .modules import MODULE_ACTIONS, ModuleEnv
from .public_case_eval import run_public_case
from .search_evaluate import paired_outcomes
from .wind_ice_environment import WindIceEnv


BASE_SEED, GAMES, STRIDE = 14_985_000, 20, 100
WEIGHTS = 'e59d9f7bee62b12ed0faf094c80945cc2b1d984544eb619547940c752238bb83'
STOP_FILE = Path('runs/STOP_AI_TRAINING')
ARMS = ('native', 'microplans')
AIRPORTS = {'LOG_GIG_YELLOW': ['wind'], 'LOG_KEF_YELLOW': ['ice']}
MATRIX = Path('ai/experiments/modules-30pct-2026-10-25/matrix.json')


def check_stop():
    if STOP_FILE.exists():
        raise ValueError('Persistent training stop is active; explicit resumption is required.')


def cases():
    result = sorted((row for row in load_cases(MATRIX) if row['airport'] in AIRPORTS), key=case_key)
    if (len(result) != 12 or any(len(row['abilities']) != 1 or row['modules'] != AIRPORTS[row['airport']] for row in result)):
        raise ValueError('Require all six official single-card cases on each of GIG/KEF yellow.')
    return result


def comparison_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    root = Path(__file__).resolve().parents[1]
    for name in ('ai/wind_ice_advice.py', 'ai/wind_ice_environment.py', 'ai/wind_ice_compare.py',
                 'ai/public_case_eval.py', 'ai/leak_strength_compare.py', 'ai/module_training_eval.py',
                 'ai/agents.py', 'ai/nn_model.py', 'backend/cockpit.py', 'backend/spielplan.py', 'backend/zusatzregeln.py'):
        digest.update(name.encode()); digest.update((root/name).read_bytes())
    return digest.hexdigest()


def load_model(path):
    path = Path(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    model, payload = load_checkpoint(path)
    config = payload.get('train_config', {})
    if (weight_fingerprint(model) != WEIGHTS or model.config.get('kind') != 'guided_residual'
            or model.config.get('guide_margin') != 12. or getattr(model, 'guide_margin', None) != 12.
            or model.config.get('observation_size') != 489 or model.config.get('action_count') != 217
            or type(payload.get('total_steps')) is not int or payload['total_steps'] != 80_139
            or config.get('assistance_version') != 12 or config.get('planner_sha256') != planner_fingerprint(3)):
        raise ValueError('Use the unchanged actual Crew5 profile12/guide12 latest release.')
    if before != hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('Checkpoint changed during loading.')
    return model, {'checkpoint': _report_path(path), 'file_sha256': before,
        'weights_sha256': WEIGHTS, 'model_config': dict(model.config), 'phase_steps': 80_139,
        'frozen_source_weights_sha256': weight_fingerprint(model.source)}


def run_arm(model, case, arm, seed, games, duty=.7):
    _development_seed(seed, games)
    if arm not in ARMS or type(games) is not int or not 1 <= games <= GAMES:
        raise ValueError('Use native/microplans and1..20 development games.')
    if (not math.isfinite(duty) or not 0 < duty <= .7
            or case not in cases() or model.config.get('guide_margin') != 12.
            or getattr(model, 'guide_margin', None) != 12.):
        raise ValueError('Use an explicit GIG/KEF card case, duty<=.7 and margin12.')
    check_stop()
    captured, before = [], weight_fingerprint(model)
    environment = ModuleEnv if arm == 'native' else WindIceEnv

    class Instrumented(environment):
        def __init__(self, *args, **kwargs):
            self._last_info, self._measurements = None, []
            self._counts, self._changes = Counter(), []
            super().__init__(*args, **kwargs)
            captured.append(self)

        def reset(self, **kwargs):
            check_stop()
            self._counts, self._changes = Counter(), []
            return super().reset(**kwargs)

        def info(self):
            self._last_info = super().info()
            return self._last_info

        def step(self, selected):
            check_stop()
            info = self._last_info
            allowed, reference = info['action_mask'], info['reference_action_mask']
            source = info.get('source_reference_action_mask', reference)
            if (not allowed[selected] or len(source) != len(allowed)
                    or any(type(flag) is not bool for flag in source)
                    or any(flag and not allowed[index] for index, flag in enumerate(source))):
                raise RuntimeError('Invalid same-state native/legal/reference alignment.')
            if arm == 'microplans' and info.get('research_wind_ice') is not True:
                raise RuntimeError('Research reference must be explicitly marked.')
            changed = source != reference
            self._counts['decisions'] += 1
            self._counts['changed_reference_decisions'] += int(changed)
            self._counts['reference_departures'] += int(not reference[selected])
            if changed:
                view = self.view()
                native_choice = ModelAgent(model).select(view, allowed, reference_mask=source)
                different = native_choice != selected
                self._counts['changed_native_preferences'] += int(different)
                self._counts['changed_kind_' + MODULE_ACTIONS[selected].kind] += int(different)
                if different:
                    self._changes.append({'step': self.steps, 'role': view['role'], 'height': view['height'],
                        'distance': view['distance'], 'action_id': selected, 'native_action_id': native_choice})
            return super().step(selected)

        def episode_record(self, *args, **kwargs):
            record = super().episode_record(*args, **kwargs)
            self._measurements.append({'seed': record['seed'], 'counts': dict(self._counts), 'changes': list(self._changes)})
            return record

    with patch('ai.public_case_eval.ModuleEnv', Instrumented):
        summary = run_public_case(model, case, games, seed, cpu_duty_cycle=duty, assistance_version=12)
    measurements = [row for env in captured for row in env._measurements]
    expected = list(range(seed, seed + games))
    if (weight_fingerprint(model) != before or [row['seed'] for row in measurements] != expected
            or [row['seed'] for row in summary['episodes']] != expected
            or any(row['case_key'] != case_key(case) for row in summary['episodes'])):
        raise RuntimeError('Comparison changed weights or episode pairing.')
    totals = Counter()
    for row in measurements: totals.update(row['counts'])
    return {'summary': summary, 'counts': dict(totals), 'measurements': measurements}


def paired_details(native, candidate):
    before, after = native['summary']['episodes'], candidate['summary']['episodes']
    if ([row['seed'] for row in before] != [row['seed'] for row in after]
            or [row['case_key'] for row in before] != [row['case_key'] for row in after]):
        raise ValueError('Pair the same route/card/seed episodes only.')
    return {'outcomes': paired_outcomes(before, after),
        'episodes': [{'seed': first['seed'], 'case_key': first['case_key'],
                      'native_status': first['status'], 'candidate_status': second['status'],
                      'native_reason': first['reason'], 'candidate_reason': second['reason']}
                     for first, second in zip(before, after)]}


_model = None


def _initialize(checkpoint, metadata, code_sha):
    global _model
    torch.set_num_threads(1)
    check_stop()
    _model, actual = load_model(checkpoint)
    if actual != metadata or comparison_fingerprint() != code_sha:
        raise ValueError('Frozen model or research sources changed.')


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
        check_stop(); torch.set_num_threads(1)
        _, metadata = load_model(args.checkpoint)
        selected_cases = cases()
        for ordinal in range(len(selected_cases)):
            _development_seed(BASE_SEED + STRIDE * ordinal, GAMES)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    code_sha, started = comparison_fingerprint(), time.monotonic()
    report = {'format': 1, 'complete': False, 'phase': 'isolated_public_wind_ice_microplans',
        'release_evidence': False, 'qualification_used': False, 'ppo_updates': 0,
        'new_training_decisions': 0, 'fresh_development': True, 'same_policy_both_arms': True,
        'model': metadata, 'planner_sha256': planner_fingerprint(3), 'comparison_sha256': code_sha,
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
                    if arm == 'microplans':
                        report['cases'][key]['paired'] = paired_details(report['cases'][key]['native'], output)
                    _write(args.output, report)
                    print(json.dumps({'case': key, 'arm': arm, 'wins': output['summary']['wins'],
                        'games': GAMES, 'counts': output['counts']}), flush=True)
        check_stop()
        if code_sha != comparison_fingerprint() or load_model(args.checkpoint)[1] != metadata:
            raise RuntimeError('Model or research sources changed during comparison.')
        report.update(complete=True, elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
    except BaseException as exc:
        report.update(complete=False, error_type=type(exc).__name__, error=str(exc), elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
        raise


if __name__ == '__main__':
    main()
