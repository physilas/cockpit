"""Publish qualified players, or explicitly requested developmental previews.

Preview visibility never implies quality approval or independent qualification.
"""
import argparse
import json
from pathlib import Path
import re

import torch

from backend.katalog import landekatalog
from .checkpoints import load_checkpoint, weight_fingerprint, planner_fingerprint, model_schema
from .export_browser import export_models


def _preview_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'Duplicate development-report key: {key}.')
        result[key] = value
    return result


def _preview_counts(result):
    if (not isinstance(result, dict) or type(result.get('games')) is not int or result['games'] < 1 or
            type(result.get('wins')) is not int or not 0 <= result['wins'] <= result['games'] or
            type(result.get('win_rate')) not in (int, float) or
            result.get('win_rate') != result['wins']/result['games']):
        raise ValueError('Preview results must contain consistent individual-case counts.')
    return {key: result[key] for key in ('games', 'wins', 'win_rate')}


def portable_config(value,root):
    """Release metadata must not expose machine-specific home directories."""
    if isinstance(value,dict):
        return {key:portable_config(item,root) for key,item in value.items()}
    if isinstance(value,list):
        return [portable_config(item,root) for item in value]
    if isinstance(value,str) and Path(value).is_absolute():
        path=Path(value).resolve()
        return path.relative_to(root).as_posix() if path.is_relative_to(root) else f'external/{path.name}'
    return value


def publish_preview(checkpoint, evaluation, release_id, name, *, root=Path(__file__).resolve().parents[1]):
    """Explicit opt-in experimental listing; never grants quality approval.

    The user requested visible interim models, including weak routes. Keep
    development results separate from independent route qualification.
    """
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', release_id):
        raise ValueError('Release ID must contain lowercase letters, digits and hyphens.')
    if not isinstance(name, str) or not name.strip():
        raise ValueError('A preview needs an explicit display name.')
    folder = root/'ai'/'releases'/release_id
    if folder.exists() or folder.is_symlink():
        raise ValueError('Preview release already exists; preserve existing models and use a new release ID.')
    report = json.loads(Path(evaluation).read_text(), object_pairs_hook=_preview_object)
    if (not isinstance(report, dict) or report.get('complete') is not True
            or report.get('release_evidence') is not False):
        raise ValueError('A preview needs a complete, explicitly developmental report.')
    model, payload = load_checkpoint(checkpoint)
    config = payload['train_config']
    if any(config.get(flag) for flag in ('research_all_modules', 'research_open_risk', 'research_capacity_guard')):
        raise ValueError('Research action masks need a matching browser environment before preview.')
    profile = config.get('assistance_version', 0)
    if type(profile) is not int or not 0 <= profile <= 11:
        raise ValueError('Unknown browser assistance profile.')
    if model.config.get('kind') == 'guided_residual' and profile not in (9, 10, 11):
        raise ValueError('Guided browser models require a public reference profile 9, 10 or 11.')
    if (report.get('weights_sha256') != weight_fingerprint(model)
            or type(report.get('assistance_version')) is not int
            or report.get('assistance_version') != profile
            or report.get('planner_sha256') != planner_fingerprint(model_schema(model)['version'])):
        raise ValueError('Development evidence does not match these weights and public planner.')
    preview = {'enabled': True, 'user_requested': True, 'evaluation_kind': 'development',
               'evaluation': f'ai/releases/{release_id}/development.json'}
    if 'cases' in report:
        from .module_training_eval import _official_cases, case_key
        from .modules import CARDS, MODULES
        cases = report['cases']
        if not isinstance(cases, dict) or not cases or report.get('routes'):
            raise ValueError('Use explicit nonempty card cases without mixed route aggregates.')
        if model_schema(model)['version'] != 3 or profile not in (0, 10, 11):
            raise ValueError('Card previews require schema 3 and a public module/card profile.')
        claims = {}
        for field, registered in (('supported_modules', MODULES), ('supported_cards', CARDS)):
            values = config.get(field)
            if (not isinstance(values, (list, tuple)) or any(type(value) is not str for value in values)
                    or len(set(values)) != len(values) or set(values) - set(registered)):
                raise ValueError(f'Card previews require explicit registered {field}.')
            claims[field] = set(values)
        official = _official_cases()
        supported_cases, case_results, seen = [], {}, set()
        for identity, result in cases.items():
            if not isinstance(result, dict):
                raise ValueError('Each preview card case must be an object.')
            key = case_key(result)
            pair = (result['airport'], tuple(sorted(result['abilities'])))
            if (identity != key or key in seen or result.get('case_key', key) != key
                    or pair not in official or not result['abilities']):
                raise ValueError(f'Unknown, duplicate or inconsistent official card case: {identity}.')
            modules = result.get('modules')
            if (not isinstance(modules, (list, tuple)) or any(type(module) is not str for module in modules)
                    or sorted(modules) != official[pair]
                    or set(modules) - claims['supported_modules']
                    or set(result['abilities']) - claims['supported_cards']):
                raise ValueError(f'Unclaimed or mismatched preview modules/cards: {identity}.')
            count = config.get('ability_count')
            if count is not None and count != 'case_specific' and (type(count) is not int or count != len(result['abilities'])):
                raise ValueError('The tested card count differs from the model configuration.')
            case_results[key] = _preview_counts(result)
            supported_cases.append({'airport': result['airport'], 'abilities': sorted(result['abilities'])})
            seen.add(key)
        supported_cases.sort(key=case_key)
        supported_airports = sorted({case['airport'] for case in supported_cases})
        preview.update(supported_cases=supported_cases, case_results=case_results)
    else:
        routes = report.get('routes', {})
        if not isinstance(routes, dict) or not routes:
            raise ValueError('A preview needs explicit tested routes.')
        catalog = {scenario['engine_code']: scenario for scenario in landekatalog()['scenarios']}
        for code, result in routes.items():
            scenario = catalog.get(code)
            if (not scenario or scenario['ability_count'] or
                    set(scenario['modules']) - set(config.get('supported_modules', []))):
                raise ValueError(f'Unsupported preview route modules/cards: {code}.')
            modules = set(scenario['modules'])
            if 'intern' in modules and profile != 10:
                raise ValueError('Intern previews require the matching browser profile 10.')
            if modules - {'kerosene'} and profile not in (0, 10):
                raise ValueError('This browser profile does not support the tested preview modules.')
            _preview_counts(result)
            if scenario['modules'] and model_schema(model)['version'] < 3:
                raise ValueError('This module preview requires the matching schema-3 browser.')
        supported_airports = sorted(routes)
        preview['route_results'] = {code: _preview_counts(result) for code, result in routes.items()}
    folder.mkdir(parents=True)
    payload['train_config'] = portable_config(config, root.resolve())
    payload['train_config'].update(display_name=name, recommended=False, publication_status='experimental_preview',
        supported_airports=supported_airports,
        quality={'approved': False, 'reason': 'Experimental user-requested preview; development evidence only.'},
        preview=preview)
    target = folder/'best.pt'
    torch.save(payload, target)
    (folder/'development.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n')
    return target, export_models(root/'ai'/'releases', root/'frontend'/'web', checkpoints=[target], merge=True)


def publish(checkpoint, evaluation, release_id, name, *, root=Path(__file__).resolve().parents[1], require_all=True):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', release_id):
        raise ValueError('Release ID must contain lowercase letters, digits and hyphens.')
    report = json.loads(Path(evaluation).read_text())
    if report.get('complete') is False:
        raise ValueError('Qualification is still running; publish only a completed report.')
    model, payload = load_checkpoint(checkpoint)
    if any(payload['train_config'].get(flag) for flag in ('research_all_modules', 'research_open_risk')):
        raise ValueError('Research action masks need a matching browser environment before publication.')
    if report.get('weights_sha256') != weight_fingerprint(model):
        raise ValueError('Evaluation does not match these model weights.')
    profile = payload['train_config'].get('assistance_version', 0)
    if report.get('assistance_version') != profile:
        raise ValueError('Evaluation uses a different assistance profile.')
    if profile and report.get('planner_sha256') != planner_fingerprint(model_schema(model)['version']):
        raise ValueError('Planner changed after evaluation; repeat qualification before publishing.')
    expected = {s['engine_code'] for s in landekatalog()['scenarios'] if not s['modules'] and not s['ability_count']}
    qualified = set(report.get('qualified_routes', []))
    scenarios = {s['engine_code']: s for s in landekatalog()['scenarios']}
    allowed_modules = set(payload['train_config'].get('supported_modules', []))
    for code in qualified:
        scenario = scenarios.get(code)
        if scenario is None or scenario['ability_count'] or set(scenario['modules']) - allowed_modules:
            raise ValueError(f'Unsupported route modules/cards: {code}.')
        # The user explicitly lowered the all-module target to 30–40 % on
        # 25 October. Keep the per-route confidence requirement, not a mean.
        if scenario['modules'] and (report['minimum_win_rate'] < .3 or payload.get('module_training_steps',0) < 1):
            raise ValueError('New module releases require actual module training and a quality floor of at least 30%.')
        if scenario['modules'] and model_schema(model)['version'] < 2:
            raise ValueError('Module routes require the module action/observation schema.')

    if not qualified or require_all and not expected.issubset(qualified):
        raise ValueError(f'Unqualified routes: {sorted(expected - qualified)}')
    for airport in qualified:
        result = report['routes'][airport]['self']
        if result['games'] < 200 or result['win_ci_low'] < report['minimum_win_rate']:
            raise ValueError(f'Insufficient held-out evidence for {airport}.')
    folder = root / 'ai' / 'releases' / release_id
    folder.mkdir(parents=True, exist_ok=True)
    payload['train_config']=portable_config(payload['train_config'],root.resolve())
    payload['train_config'].update(display_name=name, recommended=model_schema(model)["version"] == 1,
        supported_airports=sorted(qualified), quality={'approved': True,
            'evaluation': f'ai/releases/{release_id}/evaluation.json',
            'minimum_win_rate': report['minimum_win_rate'], 'games_per_route': report['routes'][next(iter(qualified))]['self']['games']})
    payload['train_config']['quality']['route_results'] = {code: {k: value for k, value in report['routes'][code]['self'].items()
        if k in ('games', 'win_rate', 'win_ci_low', 'win_ci_high')} for code in qualified}
    path = folder / 'best.pt'
    torch.save(payload, path)
    (folder / 'evaluation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    catalog = export_models(root / 'ai' / 'releases', root / 'frontend' / 'web', checkpoints=[path], merge=True)
    return path, catalog


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint', type=Path, required=True)
    p.add_argument('--evaluation', type=Path, required=True)
    p.add_argument('--release-id', required=True)
    p.add_argument('--name', required=True)
    p.add_argument('--qualified-routes-only', action='store_true', help='Publish only independently qualified routes, e.g. a kerosene specialist.')
    p.add_argument('--experimental-preview', action='store_true', help='Explicitly list a developmental test model without granting approval.')
    args = p.parse_args()
    if args.experimental_preview:
        path, _ = publish_preview(args.checkpoint, args.evaluation, args.release_id, args.name)
    else:
        path, _ = publish(args.checkpoint, args.evaluation, args.release_id, args.name, require_all=not args.qualified_routes_only)
    print(path)


if __name__ == '__main__':
    main()
