"""Evaluate the released Crew-3 policy on every registered route/card case.

This is a new developmental exposure of unchanged profile-10 weights, including
modules and cards absent from their training. Native ModuleEnv rules and real
engine wall time apply. Every zero-win case remains in the report; a positive
case list is only a requested preview filter, never a quality qualification.
Run through ai.job_control with nice15 after the active training job finishes.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import tempfile
import time

import torch

from backend.katalog import landekatalog
from .agents import ModelAgent
from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .evaluate import summarize_episodes
from .module_training_eval import _development_seed, case_key, load_cases
from .modules import ModuleEnv
from .public_case_eval import run_public_case
from .throttle import CpuBudget


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKPOINT = REPOSITORY_ROOT / 'ai/releases/crew3-intern-preview-v1/best.pt'
DEFAULT_MATRIX = REPOSITORY_ROOT / 'ai/experiments/modules-30pct-2026-10-25/matrix.json'
STOP_FILE = REPOSITORY_ROOT / 'runs/STOP_AI_TRAINING'
LEGACY_AIRPORTS = ('FRA', 'LHR', 'MUC', 'MUC_T1', 'MUC_T2', 'MUC_T3')
ASSISTANCE_VERSION = 10
CASE_COUNT = 192
SEED_STRIDE = 100


def _report_path(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def check_stop():
    if STOP_FILE.exists():
        raise ValueError('Persistent training stop is active; explicit resumption is required.')


def validate_seed_budget(seed, games, case_count=CASE_COUNT):
    """Use separate fixed-stride development cohorts, never reserved tests."""
    if (type(seed) is not int or type(games) is not int or not 1 <= games <= SEED_STRIDE
            or type(case_count) is not int or case_count != CASE_COUNT
            or seed < 14_000_000
            or seed + (case_count - 1) * SEED_STRIDE + games > 15_000_000):
        raise ValueError('Use all 192 cases, 1..100 games, with disjoint cohorts below15,000,000.')


def _legacy_cases():
    scenarios = {row['engine_code']: row for row in landekatalog()['scenarios']
                 if row['kind'] == 'custom'}
    if set(scenarios) != set(LEGACY_AIRPORTS):
        raise ValueError('Expected the six existing custom catalogue routes; review catalogue changes explicitly.')
    rows = []
    for airport in LEGACY_AIRPORTS:
        scenario = scenarios[airport]
        if scenario.get('modules') != [] or scenario.get('ability_count') != 0:
            raise ValueError('Legacy catalogue cases must use no modules or cards.')
        rows.append({'airport': airport, 'abilities': [], 'modules': [],
                     'case_scope': 'legacy_catalogue'})
    return rows


def catalogue_cases(matrix_path=DEFAULT_MATRIX):
    """Official 21/186 matrix followed by six explicitly nonofficial cases."""
    official = [{**row, 'case_scope': 'official_matrix'}
                for row in sorted(load_cases(matrix_path), key=case_key)]
    result = official + _legacy_cases()
    if len(result) != CASE_COUNT or len({case_key(row) for row in result}) != CASE_COUNT:
        raise ValueError('The preview requires all 186 official plus six distinct legacy cases.')
    return result


def tensor_fingerprint(model):
    """Tensor identity separately from the policy configuration fingerprint."""
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(str(tensor.dtype).encode())
        digest.update(str(tuple(tensor.shape)).encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def _validate_model(model):
    config = model.config
    margin = config.get('guide_margin')
    if (config.get('kind') != 'guided_residual' or config.get('observation_size') != 489
            or config.get('action_count') != 217 or type(margin) not in (float, int)
            or not math.isfinite(margin) or margin <= 0
            or margin != getattr(model, 'guide_margin', None)):
        raise ValueError('Use the unchanged guided schema-3 Crew-3 policy configuration.')


def load_crew3(checkpoint=DEFAULT_CHECKPOINT, *, reference_checkpoint=DEFAULT_CHECKPOINT):
    """Require exact released policy tensors AND config; metadata may differ.

    The CLI fixes reference_checkpoint to the existing release. The parameter
    permits small independent test fixtures without editing that release.
    """
    checkpoint, reference_checkpoint = Path(checkpoint), Path(reference_checkpoint)
    before_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    model, payload = load_checkpoint(checkpoint)
    _validate_model(model)
    config = payload.get('train_config', {})
    if (config.get('assistance_version') != ASSISTANCE_VERSION
            or any(config.get(flag) for flag in
                   ('research_all_modules', 'research_open_risk', 'research_capacity_guard'))):
        raise ValueError('Use the native released Crew-3 profile10, without a research action wrapper.')
    if checkpoint.resolve() == reference_checkpoint.resolve():
        reference, reference_payload = model, payload
    else:
        reference, reference_payload = load_checkpoint(reference_checkpoint)
        _validate_model(reference)
    if reference_payload.get('train_config', {}).get('assistance_version') != ASSISTANCE_VERSION:
        raise ValueError('The reference release must be the profile-10 Crew-3 player.')
    model_sha, tensor_sha = weight_fingerprint(model), tensor_fingerprint(model)
    if model_sha != weight_fingerprint(reference) or tensor_sha != tensor_fingerprint(reference):
        raise ValueError('Preview evaluation must use the exact released Crew-3 tensors and guide configuration.')
    after_sha = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if after_sha != before_sha:
        raise ValueError('The checkpoint changed while loading.')
    reference_config = reference_payload.get('train_config', {})
    metadata = {
        'checkpoint': _report_path(checkpoint),
        'reference_checkpoint': _report_path(reference_checkpoint),
        'checkpoint_file_sha256': before_sha, 'weights_sha256': model_sha,
        'tensor_sha256': tensor_sha, 'model_config': dict(model.config),
        'frozen_source_weights_sha256': weight_fingerprint(model.source),
        'frozen_source_tensor_sha256': tensor_fingerprint(model.source),
        'recorded_phase_steps': payload.get('total_steps'),
        'original_training_claims': {
            key: reference_config.get(key)
            for key in ('supported_modules', 'supported_cards', 'ability_count',
                        'curriculum_airports', 'phase_kind', 'source_phase_steps',
                        'planner_sha256')},
        'loaded_assistance_version': ASSISTANCE_VERSION,
        'tensor_values_changed': False, 'policy_configuration_changed': False,
    }
    return model, metadata


def evaluation_fingerprint():
    """Fingerprint evaluation, policy, native engine, catalogue and route data."""
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    files = [Path(__file__).with_name(name) for name in
             ('preview_matrix_eval.py', 'public_case_eval.py', 'module_training_eval.py',
              'agents.py', 'evaluate.py', 'nn_model.py', 'checkpoints.py', 'throttle.py')]
    files.extend(path for path in (REPOSITORY_ROOT / 'backend').rglob('*')
                 if path.is_file() and path.suffix in ('.py', '.yaml', '.json'))
    for path in sorted(files):
        digest.update(path.relative_to(REPOSITORY_ROOT).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run_catalogue_case(model, case, games, seed, cpu_duty_cycle=.7):
    """Native self-play for a registered custom base route, without fake cards."""
    _development_seed(seed, games)
    _validate_model(model)
    key = case_key(case)
    registered = {case_key(row): row for row in _legacy_cases()}
    if key not in registered or case.get('modules') != [] or case.get('abilities') != []:
        raise ValueError('Use one of the six registered custom routes without modules/cards.')
    if not math.isfinite(cpu_duty_cycle) or not 0 < cpu_duty_cycle <= .7:
        raise ValueError('Evaluation duty cycle must be in (0,.7].')
    budget = CpuBudget(cpu_duty_cycle)
    env = ModuleEnv(case['airport'], abilities=[], assistance_version=ASSISTANCE_VERSION,
                    max_steps=256, round_reward=0., sync_weight=0., task_weight=0.)
    agent, records = ModelAgent(model), []
    was_training = model.training
    model.eval()
    try:
        for ordinal in range(games):
            check_stop()
            game_seed = seed + ordinal
            _, info = env.reset(seed=game_seed)
            actual = env.view()['modules_state']
            if (env.game.landung.get_code() != case['airport'] or actual['cards'] or actual['modules']):
                raise RuntimeError('The engine selected a different custom route or cards/modules.')
            total_reward = 0.
            departures = decisions = 0
            while not env.done:
                reference = info['reference_action_mask']
                action = agent.select(env.view(), info['action_mask'], reference_mask=reference)
                departures += int(not reference[action])
                decisions += 1
                _, reward, _, _, info = env.step(action)
                total_reward += reward
                budget.pause()
            record = env.episode_record(game_seed, 'both', total_reward)
            record.update(airport=case['airport'], abilities=[], modules=[], case_key=key,
                          reference_departures=departures, decisions=decisions)
            records.append(record)
    finally:
        model.train(was_training)
    departures = sum(row['reference_departures'] for row in records)
    decisions = sum(row['decisions'] for row in records)
    return {'complete': True, 'airport': case['airport'], 'abilities': [], 'modules': [],
            'case_key': key, 'case_scope': 'legacy_catalogue',
            'assistance_version': ASSISTANCE_VERSION, 'clock_model': 'engine_wall_clock',
            'release_evidence': False, 'qualification_used': False,
            'reference_departures': departures, 'decisions': decisions,
            'reference_departure_rate': departures / decisions if decisions else 0.,
            **summarize_episodes(records)}


def run_case(model, case, games, seed, cpu_duty_cycle=.7):
    if case.get('case_scope') == 'legacy_catalogue':
        return run_catalogue_case(model, case, games, seed, cpu_duty_cycle)
    if case.get('case_scope') != 'official_matrix':
        raise ValueError('Each case must explicitly identify its official or legacy scope.')
    result = run_public_case(model, case, games, seed, cpu_duty_cycle=cpu_duty_cycle,
                             assistance_version=ASSISTANCE_VERSION)
    return {**result, 'case_scope': 'official_matrix'}


def validate_result(result, case, games, seed):
    """Check actual identities/counts before accepting a worker's case result."""
    key = case_key(case)
    if (result.get('complete') is not True or result.get('release_evidence') is not False
            or result.get('qualification_used') is not False
            or result.get('assistance_version') != ASSISTANCE_VERSION
            or result.get('clock_model') != 'engine_wall_clock'
            or result.get('case_scope') != case['case_scope']
            or result.get('case_key') != key or result.get('airport') != case['airport']
            or result.get('abilities') != case['abilities'] or result.get('modules') != case['modules']):
        raise RuntimeError('A worker returned a different case, profile, clock or evidence kind.')
    records = result.get('episodes')
    if (not isinstance(records, list) or len(records) != games
            or sorted(row.get('seed', -1) for row in records) != list(range(seed, seed + games))
            or any(row.get('scenario') != case['airport'] or row.get('airport') != case['airport']
                   or row.get('case_key') != key or row.get('abilities') != case['abilities']
                   or row.get('modules') != case['modules'] or row.get('training_budget_failure', False)
                   for row in records)):
        raise RuntimeError('A worker did not preserve the exact native case/seed episode cohort.')
    wins = sum(row['status'] == 'gewonnen' for row in records)
    departures = sum(row['reference_departures'] for row in records)
    decisions = sum(row['decisions'] for row in records)
    if (type(result.get('games')) is not int or result['games'] != games
            or type(result.get('wins')) is not int or result['wins'] != wins
            or result.get('win_rate') != wins / games
            or result.get('reference_departures') != departures or result.get('decisions') != decisions
            or result.get('reference_departure_rate') != (departures / decisions if decisions else 0.)):
        raise RuntimeError('A worker summary disagrees with its individual episode records.')


def _positive_cases(rows):
    """No zero-win rows are removed from the full cases mapping."""
    return {key: {field: row[field] for field in
                  ('airport', 'abilities', 'modules', 'case_scope', 'games', 'wins', 'win_rate')}
            for key, row in sorted(rows.items()) if row['wins'] > 0}


def _write(path, report, *, initial=False):
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                prefix=f'.{path.name}.', suffix='.partial', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(report, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        if initial:
            os.link(temporary, path)
        else:
            temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


_model = None
_metadata = None
_evaluation_sha = None


def _initialize(checkpoint, expected_metadata, expected_fingerprint):
    global _model, _metadata, _evaluation_sha
    torch.set_num_threads(1)
    check_stop()
    _model, _metadata = load_crew3(checkpoint)
    _evaluation_sha = expected_fingerprint
    if _metadata != expected_metadata or evaluation_fingerprint() != expected_fingerprint:
        raise ValueError('Crew-3 checkpoint or evaluation/engine sources changed before worker initialization.')


def _run(task):
    case, seed, games, duty = task
    check_stop()
    before_sha = weight_fingerprint(_model)
    result = run_case(_model, case, games, seed, duty)
    validate_result(result, case, games, seed)
    if before_sha != _metadata['weights_sha256'] or weight_fingerprint(_model) != before_sha:
        raise RuntimeError('Development self-play changed model weights or policy configuration.')
    if evaluation_fingerprint() != _evaluation_sha:
        raise RuntimeError('Evaluation/engine sources changed during a worker case.')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument('--matrix', type=Path, default=DEFAULT_MATRIX)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=20)
    parser.add_argument('--seed', type=int, default=14_960_000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8 or not math.isfinite(args.cpu_duty_cycle) or not 0 < args.cpu_duty_cycle <= .7:
        parser.error('Use at most eight CPU workers at .7 duty.')
    if args.output.exists() or args.output.is_symlink():
        parser.error('Preserve prior results; use a new output path.')
    try:
        check_stop()
        validate_seed_budget(args.seed, args.games)
        cases = catalogue_cases(args.matrix)
        matrix_sha = hashlib.sha256(args.matrix.read_bytes()).hexdigest()
        evaluation_sha = evaluation_fingerprint()
        torch.set_num_threads(1)
        _, metadata = load_crew3(args.checkpoint)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    report = {
        'format': 1, 'phase': 'unchanged_crew3_profile10_full_catalogue_development',
        'complete': False, 'release_evidence': False, 'quality_approved': False,
        'goal_achieved': False, 'qualification_used': False, 'independent_test_used': False,
        'new_training_decisions': 0, 'weights_changed': False, 'policy_configuration_changed': False,
        'weights_sha256': metadata['weights_sha256'], 'model': metadata,
        'assistance_version': ASSISTANCE_VERSION, 'planner_sha256': planner_fingerprint(3),
        'evaluation_sha256': evaluation_sha,
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'matrix_path': _report_path(args.matrix), 'matrix_sha256': matrix_sha,
        'output_path': _report_path(args.output),
        'official_route_count': 21, 'official_case_count': 186,
        'legacy_route_count': 6, 'legacy_case_count': 6,
        'total_route_count': 27, 'expected_case_count': CASE_COUNT,
        'completed_case_count': 0, 'expected_games': CASE_COUNT * args.games,
        'games_per_case': args.games, 'base_seed': args.seed, 'seed_stride': SEED_STRIDE,
        'case_seeds': {case_key(row): args.seed + ordinal * SEED_STRIDE for ordinal, row in enumerate(cases)},
        'case_scopes': {case_key(row): row['case_scope'] for row in cases},
        'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
        'clock_model': 'engine_wall_clock',
        'realtime_note': 'Native elapsed deadlines include actual inference and pacing time; outcomes are runtime dependent.',
        'exposure': {
            'kind': 'new_unqualified_preview_exposure_of_unchanged_weights',
            'additional_training_performed': False,
            'includes_modules_and_cards_absent_from_original_training': True,
            'tested_modules': sorted({module for row in cases for module in row['modules']}),
            'tested_cards': sorted({card for row in cases for card in row['abilities']}),
            'original_training_claims': metadata['original_training_claims'],
        },
        'positive_filter': 'wins>0 development only; all zero-win cases retained in cases',
        'cases': {}, 'good_cases': {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(args.output, report, initial=True)
    except FileExistsError:
        parser.error('Preserve prior results; another invocation created this output path.')
    started = time.monotonic()
    pool = None
    try:
        pool = ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
            initializer=_initialize, initargs=(args.checkpoint, metadata, evaluation_sha))
        futures = {pool.submit(_run, (case, args.seed + ordinal * SEED_STRIDE,
                                     args.games, args.cpu_duty_cycle)): (case, ordinal)
                   for ordinal, case in enumerate(cases)}
        for future in as_completed(futures):
            check_stop()
            case, ordinal = futures[future]
            result = future.result()
            validate_result(result, case, args.games, args.seed + ordinal * SEED_STRIDE)
            report['cases'][case_key(case)] = result
            report['completed_case_count'] = len(report['cases'])
            report['good_cases'] = _positive_cases(report['cases'])
            report['elapsed_seconds'] = time.monotonic() - started
            _write(args.output, report)
            print(json.dumps({'case': case_key(case), 'case_scope': case['case_scope'],
                'wins': result['wins'], 'games': result['games'],
                'reference_departures': result['reference_departures'],
                'completed_cases': report['completed_case_count']}), flush=True)
        pool.shutdown(wait=True)
        pool = None
        check_stop()
        if set(report['cases']) != set(report['case_seeds']) or len(report['cases']) != CASE_COUNT:
            raise RuntimeError('Incomplete catalogue coverage; all 192 results, including zero wins, are required.')
        if evaluation_fingerprint() != evaluation_sha or hashlib.sha256(args.matrix.read_bytes()).hexdigest() != matrix_sha:
            raise RuntimeError('Evaluation, engine, catalogue or matrix sources changed during development.')
        _, finished_metadata = load_crew3(args.checkpoint)
        if finished_metadata != metadata:
            raise RuntimeError('The Crew-3 checkpoint or its recorded lineage changed during development.')
        report.update(complete=True, elapsed_seconds=time.monotonic() - started,
                      games=sum(row['games'] for row in report['cases'].values()),
                      positive_case_count=len(report['good_cases']),
                      positive_route_count=len({row['airport'] for row in report['good_cases'].values()}))
        _write(args.output, report)
    except BaseException as exc:
        report.update(complete=False, error_type=type(exc).__name__, error=str(exc),
                      elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
        raise
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=True)


if __name__ == '__main__':
    main()
