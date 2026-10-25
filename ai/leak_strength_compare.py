"""Paired development comparison of finite leak-guidance strengths.

The finished warm and preselected trained checkpoints are each copied at guide
margins 4, 8 and 12. Only that model configuration changes: all tensors, legal
actions, public reference masks and frozen foundations remain intact. Run this
bounded development experiment through ``ai.job_control run`` with nice15;
it performs no training, qualification or publication.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import tempfile
import time

import torch

from .checkpoints import load_checkpoint, planner_fingerprint, weight_fingerprint
from .evaluate import summarize_episodes
from .intern_strength_compare import MARGINS, tensor_fingerprint, with_margin
from .module_training_eval import _official_cases, case_key, load_cases
from .public_case_eval import run_public_case
from .search_evaluate import paired_outcomes


AIRPORT = 'LOG_ATL_YELLOW'
SEED_STRIDE = 100
VARIANTS = tuple(f'{origin}_margin{int(margin)}'
                 for origin in ('source', 'candidate') for margin in MARGINS)
STOP_FILE = Path('runs/STOP_AI_TRAINING')
REPOSITORY_ROOT = Path(__file__).resolve().parent.parent


def _report_path(path):
    """Portable repository metadata; external user paths retain their location."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def check_stop():
    """Persistent user stop also prohibits starting a development comparison."""
    if STOP_FILE.exists():
        raise ValueError('Persistent training stop is active; explicit resumption is required.')


def phase_fingerprint():
    """Same current source contract as the finished profile-11 training phase."""
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('train_leak.py', 'public_case_eval.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def comparison_fingerprint():
    digest = hashlib.sha256(planner_fingerprint(3).encode())
    for name in ('leak_strength_compare.py', 'intern_strength_compare.py',
                 'public_case_eval.py', 'module_training_eval.py'):
        digest.update(name.encode())
        digest.update(Path(__file__).with_name(name).read_bytes())
    return digest.hexdigest()


def atlanta_cases(matrix_path):
    """Return every official Atlanta-yellow single-card case, in stable order."""
    cases = sorted((row for row in load_cases(matrix_path) if row['airport'] == AIRPORT),
                   key=case_key)
    if (len(cases) != 6 or len({case_key(row) for row in cases}) != 6 or
            any(row['modules'] != ['leak'] or len(row['abilities']) != 1 for row in cases)):
        raise ValueError('Use exactly all six official Atlanta-yellow single-card leak cases.')
    return cases


def validate_seed_budget(seed, games):
    """Disjoint card cohorts use only fresh development seeds below 15 million."""
    if (type(seed) is not int or type(games) is not int or not 1 <= games <= 100 or
            seed < 14_000_000 or seed + 5 * SEED_STRIDE + games > 15_000_000):
        raise ValueError('Use 1..100 games per card case, with all six cohorts below15,000,000.')


def _validate_model(model):
    config = model.config
    if (config.get('kind') != 'guided_residual' or config.get('observation_size') != 489 or
            config.get('action_count') != 217 or config.get('guide_margin') not in MARGINS or
            type(config.get('guide_margin')) not in (int, float) or
            config.get('guide_margin') != getattr(model, 'guide_margin', None)):
        raise ValueError('Use a consistent guided schema-3 model at margin4,8 or12.')


def load_variants(source_path, candidate_path):
    """Load finished related phase checkpoints and make six independent copies."""
    source_path, candidate_path = Path(source_path), Path(candidate_path)
    source, source_payload = load_checkpoint(source_path)
    candidate, candidate_payload = load_checkpoint(candidate_path)
    current_planner, current_phase = planner_fingerprint(3), phase_fingerprint()
    for label, model, payload in (('source', source, source_payload),
                                   ('candidate', candidate, candidate_payload)):
        _validate_model(model)
        config = payload.get('train_config', {})
        if model.guide_margin != 4.:
            raise ValueError(f'{label} must be the finished margin-4 guided player.')
        if (config.get('assistance_version') != 11 or
                config.get('phase_kind') != 'new_public_module_profile_11_leak' or
                config.get('planner_sha256') != current_planner or
                config.get('phase_sha256') != current_phase):
            raise ValueError(f'{label} must use this exact current public profile-11 leak phase.')
        if type(payload.get('total_steps')) is not int or payload['total_steps'] < 0:
            raise ValueError('Checkpoint phase decision counts must be nonnegative integers.')
    if source_payload['total_steps'] != 0:
        raise ValueError('The source must be the phase warm checkpoint before new decisions.')
    initial_sha = weight_fingerprint(source)
    if any(payload['train_config'].get('source_weights_sha256') != initial_sha
           for payload in (source_payload, candidate_payload)):
        raise ValueError('Warm/candidate lineage must name these exact initial source weights.')
    if weight_fingerprint(source.source) != weight_fingerprint(candidate.source):
        raise ValueError('The candidate does not preserve the same frozen foundation.')
    variants, metadata = {}, {}
    for origin, loaded, payload, path in (('source', source, source_payload, source_path),
                                          ('candidate', candidate, candidate_payload, candidate_path)):
        loaded_tensor_sha = tensor_fingerprint(loaded)
        loaded_model_sha = weight_fingerprint(loaded)
        checkpoint_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        for margin in MARGINS:
            label = f'{origin}_margin{int(margin)}'
            model = variants[label] = with_margin(loaded, margin)
            tensor_sha = tensor_fingerprint(model)
            if tensor_sha != loaded_tensor_sha:
                raise RuntimeError('Finite guide-strength override changed checkpoint tensors.')
            metadata[label] = {
                'checkpoint': _report_path(path), 'run_path': _report_path(path.parent),
                'checkpoint_file_sha256': checkpoint_sha, 'origin': origin,
                'phase_steps': payload['total_steps'], 'guide_margin': model.guide_margin,
                'configuration_changed': margin != 4.,
                'tensor_values_changed_from_loaded_checkpoint': False,
                'tensor_values_changed_from_warm': tensor_sha != tensor_fingerprint(source),
                'model_fingerprint_sha256': weight_fingerprint(model), 'tensor_sha256': tensor_sha,
                'loaded_model_fingerprint_sha256': loaded_model_sha,
                'frozen_source_model_sha256': weight_fingerprint(model.source),
                'frozen_source_tensor_sha256': tensor_fingerprint(model.source),
                'initial_model_fingerprint_sha256': initial_sha,
                'recorded_source_phase_steps': payload['train_config'].get('source_phase_steps'),
                'planner_sha256': current_planner, 'phase_sha256': current_phase,
            }
    return variants, metadata


def compare_case(model, case, seed, games, *, duty=.7):
    """One explicit official card case; original engine outcomes and clock."""
    _validate_model(model)
    pair = (case.get('airport'), tuple(sorted(case.get('abilities', []))))
    if (pair not in _official_cases() or pair[0] != AIRPORT or len(pair[1]) != 1 or
            case.get('modules') != ['leak']):
        raise ValueError('This comparison supports only official Atlanta-yellow single-card leak cases.')
    if (type(seed) is not int or type(games) is not int or not 1 <= games <= 100 or
            seed < 14_000_000 or seed + games > 15_000_000):
        raise ValueError('Use 1..100 development games below15,000,000.')
    if not math.isfinite(duty) or not 0 < duty <= .7:
        raise ValueError('CPU duty must be in (0,.7].')
    return run_public_case(model, case, games, seed, cpu_duty_cycle=duty, assistance_version=11)


def paired_summaries(rows):
    """Attach both fixed controls without replacing any per-case game record."""
    if set(rows) != set(VARIANTS):
        raise ValueError('All six strength variants are required for paired summaries.')
    identities = {(row.get('airport'), tuple(row.get('abilities', [])), tuple(row.get('modules', [])))
                  for row in rows.values()}
    if len(identities) != 1:
        raise ValueError('Paired summaries must describe the same route/card case.')
    result = {}
    for label in VARIANTS:
        result[label] = {**rows[label], **{
            f'paired_against_{baseline}': paired_outcomes(rows[baseline]['episodes'], rows[label]['episodes'])
            for baseline in ('source_margin4', 'candidate_margin4')}}
    return result


_models = None


def _initialize(source, candidate, expected, expected_comparison):
    global _models
    torch.set_num_threads(1)
    check_stop()
    _models, metadata = load_variants(source, candidate)
    if metadata != expected or comparison_fingerprint() != expected_comparison:
        raise ValueError('Use finished unchanged checkpoints and comparison/planning sources.')


def _run(task):
    label, case, seed, games, duty = task
    check_stop()
    return compare_case(_models[label], case, seed, games, duty=duty)


def _write(path, report, *, initial=False):
    """Atomic snapshots; the first publication never overwrites another report."""
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
            os.link(temporary, path)  # Exclusive and atomic, including between concurrent invocations.
        else:
            temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path('runs/leak-profile11-stage1/warm.pt'))
    parser.add_argument('--candidate', type=Path, default=Path('runs/leak-profile11-stage1/best.pt'))
    parser.add_argument('--matrix', type=Path,
        default=Path('ai/experiments/modules-30pct-2026-10-25/matrix.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--games', type=int, default=20)
    parser.add_argument('--seed', type=int, default=14_920_000)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--cpu-duty-cycle', type=float, default=.7)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8 or not math.isfinite(args.cpu_duty_cycle) or not 0 < args.cpu_duty_cycle <= .7:
        parser.error('Use at most eight CPU workers at .7 duty.')
    if args.output.exists():
        parser.error('Preserve prior results; use a new output path.')
    try:
        check_stop()
        validate_seed_budget(args.seed, args.games)
        cases = atlanta_cases(args.matrix)
        torch.set_num_threads(1)
        _, metadata = load_variants(args.source, args.candidate)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    comparison_sha = comparison_fingerprint()
    report = {
        'format': 1, 'phase': 'paired_leak_guidance_strength_development',
        'complete': False, 'release_evidence': False, 'goal_achieved': False,
        'independent_test_used': False, 'qualification_used': False,
        'models': metadata, 'games_per_case': args.games, 'base_seed': args.seed,
        'case_seeds': {case_key(case): args.seed + ordinal * SEED_STRIDE for ordinal, case in enumerate(cases)},
        'workers': args.workers, 'cpu_duty_cycle': args.cpu_duty_cycle, 'threads': 1,
        'assistance_version': 11, 'clock_model': 'engine_wall_clock',
        'planner_sha256': planner_fingerprint(3), 'phase_sha256': phase_fingerprint(),
        'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'comparison_sha256': comparison_sha, 'output_path': _report_path(args.output),
        'matrix_path': _report_path(args.matrix),
        'matrix_sha256': hashlib.sha256(args.matrix.read_bytes()).hexdigest(),
        'variants_are_independently_trained_models': False,
        'within_each_origin_margin_variants_have_identical_tensor_values': True,
        'finite_prior_only_masks_unchanged': True, 'cases': {},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write(args.output, report, initial=True)
    except FileExistsError:
        parser.error('Preserve prior results; another invocation created this output path.')
    started = time.monotonic()
    try:
        with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context('spawn'),
                initializer=_initialize, initargs=(args.source, args.candidate, metadata, comparison_sha)) as pool:
            for ordinal, case in enumerate(cases):
                check_stop()
                key, seed = case_key(case), args.seed + ordinal * SEED_STRIDE
                rows = report['cases'][key] = {}
                for label in VARIANTS:
                    check_stop()
                    variant_start = time.monotonic()
                    chunk = max(1, math.ceil(args.games / args.workers))
                    tasks = [(label, case, seed + offset, min(chunk, args.games - offset), args.cpu_duty_cycle)
                             for offset in range(0, args.games, chunk)]
                    groups = list(pool.map(_run, tasks))
                    records = [record for group in groups for record in group['episodes']]
                    if (len(records) != args.games or sorted(row['seed'] for row in records) != list(range(seed, seed + args.games)) or
                            any(row.get('case_key') != key for row in records)):
                        raise RuntimeError('Comparison did not return exactly the requested case/seed cohort.')
                    summary = summarize_episodes(records)
                    departures = sum(row['reference_departures'] for row in records)
                    decisions = sum(row['decisions'] for row in records)
                    summary.update(airport=case['airport'], abilities=case['abilities'], modules=case['modules'],
                        case_key=key, reference_departures=departures, decisions=decisions,
                        reference_departure_rate=departures / decisions if decisions else 0.,
                        elapsed_seconds=time.monotonic() - variant_start)
                    rows[label] = summary
                    _write(args.output, report)
                    print(json.dumps({'case': key, 'variant': label, 'wins': summary['wins'],
                        'games': summary['games'], 'reference_departures': departures}), flush=True)
                report['cases'][key] = paired_summaries(rows)
                _write(args.output, report)
        if comparison_fingerprint() != comparison_sha:
            raise RuntimeError('Comparison/planning sources changed during development games.')
        _, finished_metadata = load_variants(args.source, args.candidate)
        if finished_metadata != metadata:
            raise RuntimeError('A source checkpoint changed during development games.')
        report.update(complete=True, elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
    except BaseException as exc:
        report.update(complete=False, error_type=type(exc).__name__, error=str(exc),
                      elapsed_seconds=time.monotonic() - started)
        _write(args.output, report)
        raise


if __name__ == '__main__':
    main()
