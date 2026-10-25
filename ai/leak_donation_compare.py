"""Fresh paired WorkingTogether hypothesis test, without PPO or qualification.

One unchanged warm0/guide12 policy plays native ModuleEnv12 and the isolated
DonationEnv. Only the research reference changes. Use ai.job_control/nice15;
the preregistered main cohort is 50 games from development seed14,984,000.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from copy import deepcopy
import hashlib
import json
import math
import multiprocessing
from pathlib import Path
import time
from unittest.mock import patch

import torch

from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .evaluate import summarize_episodes
from .leak_donation_environment import DonationEnv
from .leak_strength_compare import _report_path, _write
from .module_training_eval import _development_seed
from .modules import MODULE_ACTIONS, ModuleEnv
from .public_case_eval import run_public_case
from .search_evaluate import paired_outcomes
from .train_leak import phase_fingerprint


CASE = {'airport': 'LOG_ATL_YELLOW', 'modules': ['leak'], 'abilities': ['working-together']}
CASE_KEY = 'LOG_ATL_YELLOW|working-together'
BASE_SEED = 14_984_000
GAMES = 50
ARMS = ('native', 'donation')
SWAPS = ('swap_start', 'swap_choose', 'swap_cancel')
STOP_FILE = Path('runs/STOP_AI_TRAINING')
COUNTERS = ('swap_legal_decisions', 'swap_reference_decisions', 'additional_swap_reference_decisions',
            'swap_chosen_actions', 'additional_swap_chosen_actions')


def check_stop():
    if STOP_FILE.exists():
        raise ValueError('Persistent training stop is active; explicit resumption is required.')


def comparison_fingerprint():
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('ai/leak_donation_environment.py', 'ai/leak_donation_advice.py',
                 'ai/leak_donation_compare.py', 'ai/public_case_eval.py', 'ai/leak_strength_compare.py',
                 'ai/module_training_eval.py', 'ai/agents.py', 'ai/train_leak.py',
                 'backend/spielplan.py', 'backend/cockpit.py', 'backend/zusatzregeln.py'):
        digest.update(name.encode()); digest.update((root/name).read_bytes())
    return digest.hexdigest()


def load_warm(checkpoint):
    path = Path(checkpoint)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    model, payload = load_checkpoint(path)
    config = payload.get('train_config', {})
    if (model.config.get('kind') != 'guided_residual' or model.config.get('observation_size') != 489
            or model.config.get('action_count') != 217 or model.config.get('guide_margin') != 12.
            or getattr(model, 'guide_margin', None) != 12. or payload.get('total_steps') != 0
            or type(payload.get('total_steps')) is not int
            or config.get('assistance_version') != 12
            or config.get('phase_kind') != 'new_public_module_profile_12_leak_cards'
            or config.get('planner_sha256') != planner_fingerprint(3)
            or config.get('phase_sha256') != phase_fingerprint()
            or config.get('initial_weights_sha256') != weight_fingerprint(model)):
        raise ValueError('Use the unchanged finished public profile12/guide12 warm0 checkpoint.')
    if hashlib.sha256(path.read_bytes()).hexdigest() != before:
        raise ValueError('Checkpoint changed while loading.')
    return model, {'checkpoint': _report_path(path), 'checkpoint_file_sha256': before,
        'weights_sha256': weight_fingerprint(model), 'model_config': deepcopy(model.config),
        'frozen_source_weights_sha256': weight_fingerprint(model.source), 'phase_steps': 0,
        'assistance_version': 12, 'guide_margin': 12., 'tensor_values_changed': False}


def run_arm(model, arm, seed, games, *, cpu_duty_cycle=.7):
    """Keep stock public-case selection/rewards; count same-state extra swaps."""
    _development_seed(seed, games)
    if arm not in ARMS or type(games) is not int or not 1 <= games <= GAMES:
        raise ValueError('Use native/donation and1..50 explicit development games.')
    if (model.config.get('kind') != 'guided_residual' or model.config.get('guide_margin') != 12.
            or getattr(model, 'guide_margin', None) != 12.):
        raise ValueError('Both arms require the identical guided margin12 model.')
    check_stop()
    base = ModuleEnv if arm == 'native' else DonationEnv
    before = weight_fingerprint(model)
    captured = []

    class Instrumented(base):
        def __init__(self, *args, **kwargs):
            self._comparison_info = None
            self._counts = {key: Counter() for key in COUNTERS}
            self._swap_events, self._instrumentation = [], []
            super().__init__(*args, **kwargs)
            captured.append(self)

        def reset(self, **kwargs):
            check_stop()
            self._counts = {key: Counter() for key in COUNTERS}
            self._swap_events = []
            return super().reset(**kwargs)

        def info(self):
            info = super().info()
            self._comparison_info = info
            return info

        def step(self, selected):
            check_stop()
            info = self._comparison_info
            allowed, reference = info['action_mask'], info['reference_action_mask']
            source = info.get('source_reference_action_mask', reference)
            if (len(source) != len(allowed) or any(type(flag) is not bool for flag in source)
                    or any(flag and not allowed[index] for index, flag in enumerate(source))
                    or not allowed[selected]):
                raise RuntimeError('Invalid same-state source/legal/reference correspondence.')
            if arm == 'donation' and (info.get('research_leak_donation') is not True
                                      or 'source_reference_action_mask' not in info):
                raise RuntimeError('The isolated donation environment must expose its original reference.')
            for kind in SWAPS:
                indices = [index for index, action in enumerate(MODULE_ACTIONS) if action.kind == kind]
                self._counts['swap_legal_decisions'][kind] += int(any(allowed[index] for index in indices))
                self._counts['swap_reference_decisions'][kind] += int(any(reference[index] for index in indices))
                self._counts['additional_swap_reference_decisions'][kind] += int(any(reference[index] and not source[index] for index in indices))
            action = MODULE_ACTIONS[selected]
            if action.kind in SWAPS:
                self._counts['swap_chosen_actions'][action.kind] += 1
                additional = not source[selected]
                self._counts['additional_swap_chosen_actions'][action.kind] += int(additional)
                view = self.view()
                self._swap_events.append({'step': self.steps, 'role': view['role'], 'round': view['round'],
                    'height': view['height'], 'distance': view['distance'],
                    'action_id': selected, 'kind': action.kind, 'die': action.die,
                    'reference_selected': bool(reference[selected]), 'additional_to_native_reference': additional})
            return super().step(selected)

        def episode_record(self, *args, **kwargs):
            record = super().episode_record(*args, **kwargs)
            self._instrumentation.append({'seed': record['seed'], 'scenario': record['scenario'],
                **{key: dict(value) for key, value in self._counts.items()},
                'swap_events': deepcopy(self._swap_events)})
            return record

    with patch('ai.public_case_eval.ModuleEnv', Instrumented):
        summary = run_public_case(model, CASE, games, seed, cpu_duty_cycle=cpu_duty_cycle, assistance_version=12)
    instrumentation = [row for env in captured for row in env._instrumentation]
    if (weight_fingerprint(model) != before or len(instrumentation) != games
            or [row['seed'] for row in instrumentation] != list(range(seed, seed+games))):
        raise RuntimeError('Comparison changed tensors or episode alignment.')
    return {'summary': summary, 'instrumentation': instrumentation}


def combine_chunks(outputs, seed, games):
    episodes = [row for output in outputs for row in output['summary']['episodes']]
    instrumentation = [row for output in outputs for row in output['instrumentation']]
    expected = list(range(seed, seed+games))
    if (len(episodes) != games or [row['seed'] for row in episodes] != expected
            or [row['seed'] for row in instrumentation] != expected
            or any(row.get('case_key') != CASE_KEY for row in episodes)):
        raise ValueError('Require exact unique paired WorkingTogether development episodes.')
    summary = summarize_episodes(episodes)
    summary.update(airport=CASE['airport'], modules=CASE['modules'], abilities=CASE['abilities'], case_key=CASE_KEY,
        reference_departures=sum(row['reference_departures'] for row in episodes),
        decisions=sum(row['decisions'] for row in episodes))
    totals = {}
    for key in COUNTERS:
        aggregate = Counter()
        for row in instrumentation: aggregate.update(row[key])
        totals[key] = dict(aggregate)
    return {'summary': summary, 'instrumentation': instrumentation, **totals}


def paired_details(arms):
    if set(arms) != set(ARMS):
        raise ValueError('Both native and donation controls are required.')
    native, donation = (arms[arm]['summary']['episodes'] for arm in ARMS)
    counts = paired_outcomes(native, donation)
    if (any(row.get('case_key') != CASE_KEY for row in native+donation)
            or [row['seed'] for row in native] != [row['seed'] for row in donation]):
        raise ValueError('Pair only identical route/card/seed cases.')
    events = {row['seed']: row for row in arms['donation']['instrumentation']}
    rows = [{'seed': before['seed'], 'native_status': before['status'], 'donation_status': after['status'],
             'native_reason': before['reason'], 'donation_reason': after['reason'],
             'native_round': before['round'], 'donation_round': after['round'],
             'donation_swap_chosen_actions': events[after['seed']]['swap_chosen_actions'],
             'donation_additional_swap_chosen_actions': events[after['seed']]['additional_swap_chosen_actions']}
            for before, after in zip(native, donation)]
    return {'outcomes': counts, 'episodes': rows}


_model = None


def _initialize(checkpoint, expected, expected_code):
    global _model
    torch.set_num_threads(1)
    check_stop()
    _model, metadata = load_warm(checkpoint)
    if metadata != expected or comparison_fingerprint() != expected_code:
        raise ValueError('Frozen checkpoint or comparison/planning sources changed.')


def _run(task):
    arm, seed, games, duty = task
    return run_arm(_model, arm, seed, games, cpu_duty_cycle=duty)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=Path('runs/leak-profile12-stage1/warm.pt'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=GAMES)
    parser.add_argument('--seed', type=int, default=BASE_SEED)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args(argv)
    if (args.games != GAMES or args.seed != BASE_SEED or not 1 <= args.workers <= 8
            or not math.isfinite(args.cpu_duty_cycle) or not 0 < args.cpu_duty_cycle <= .7):
        parser.error('Use the preregistered50 games at14984000, at most8 workers and duty<=.7.')
    _development_seed(args.seed, args.games)
    if args.output.exists() or args.output.is_symlink():
        parser.error('Preserve earlier evidence; choose a new output path.')
    try:
        check_stop()
        torch.set_num_threads(1)
        _, metadata = load_warm(args.checkpoint)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    code_sha = comparison_fingerprint()
    report = {'format': 1, 'phase': 'isolated_working_together_donation_hypothesis',
        'complete': False, 'release_evidence': False, 'qualification_used': False,
        'independent_test_used': False, 'fresh_development': True, 'ppo_updates': 0,
        'weights_changed': False, 'same_policy_both_arms': True,
        'model': metadata, 'case': CASE, 'case_key': CASE_KEY, 'base_seed': args.seed,
        'games_per_arm': args.games, 'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle,
        'threads': 1, 'clock_model': 'engine_wall_clock', 'assistance_version': 12,
        'guide_margin': 12., 'planner_sha256': planner_fingerprint(3),
        'comparison_sha256': code_sha, 'hypothesis': 'Narrow public donations may improve late rudder coordination.',
        'output_path': _report_path(args.output), 'arms': {}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(args.output, report, initial=True)
    except FileExistsError:
        parser.error('Another invocation created this path; preserve it.')
    started = time.monotonic()
    try:
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize, initargs=(args.checkpoint, metadata, code_sha)) as pool:
            for arm in ARMS:
                check_stop()
                chunk = math.ceil(args.games/args.workers)
                tasks = [(arm, args.seed+offset, min(chunk,args.games-offset), args.cpu_duty_cycle)
                         for offset in range(0,args.games,chunk)]
                report['arms'][arm] = combine_chunks(list(pool.map(_run,tasks)),args.seed,args.games)
                _write(args.output,report)
                print(json.dumps({'arm':arm, **{key:report['arms'][arm]['summary'][key] for key in ('games','wins','win_rate')},
                    'additional_swap_chosen_actions':report['arms'][arm]['additional_swap_chosen_actions']}),flush=True)
        report['paired'] = paired_details(report['arms'])
        if comparison_fingerprint() != code_sha or load_warm(args.checkpoint)[1] != metadata:
            raise RuntimeError('Frozen checkpoint or comparison/planning sources changed during the trial.')
        check_stop()
        report.update(complete=True,elapsed_seconds=time.monotonic()-started)
        _write(args.output,report)
    except BaseException as exc:
        report.update(complete=False,error_type=type(exc).__name__,error=str(exc),elapsed_seconds=time.monotonic()-started)
        _write(args.output,report)
        raise


if __name__=='__main__':
    main()
