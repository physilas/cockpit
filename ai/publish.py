"""Publish only a checkpoint with a matching held-out route qualification."""
import argparse
import json
from pathlib import Path
import re

import torch

from backend.katalog import landekatalog
from .checkpoints import load_checkpoint, weight_fingerprint, planner_fingerprint
from .export_browser import export_models


def publish(checkpoint, evaluation, release_id, name, *, root=Path(__file__).resolve().parents[1], require_all=True):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]*', release_id):
        raise ValueError('Release ID must contain lowercase letters, digits and hyphens.')
    report = json.loads(Path(evaluation).read_text())
    model, payload = load_checkpoint(checkpoint)
    if report.get('weights_sha256') != weight_fingerprint(model):
        raise ValueError('Evaluation does not match these model weights.')
    profile = payload['train_config'].get('assistance_version', 0)
    if report.get('assistance_version') != profile:
        raise ValueError('Evaluation uses a different assistance profile.')
    if profile and report.get('planner_sha256') != planner_fingerprint():
        raise ValueError('Planner changed after evaluation; repeat qualification before publishing.')
    expected = {s['engine_code'] for s in landekatalog()['scenarios'] if not s['modules'] and not s['ability_count']}
    qualified = set(report.get('qualified_routes', []))
    if not qualified or require_all and not expected.issubset(qualified):
        raise ValueError(f'Unqualified routes: {sorted(expected - qualified)}')
    for airport in qualified:
        result = report['routes'][airport]['self']
        if result['games'] < 200 or result['win_ci_low'] < report['minimum_win_rate']:
            raise ValueError(f'Insufficient held-out evidence for {airport}.')
    folder = root / 'ai' / 'releases' / release_id
    folder.mkdir(parents=True, exist_ok=True)
    payload['train_config'].update(display_name=name, recommended=True,
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
    args = p.parse_args()
    path, _ = publish(args.checkpoint, args.evaluation, args.release_id, args.name)
    print(path)


if __name__ == '__main__':
    main()
