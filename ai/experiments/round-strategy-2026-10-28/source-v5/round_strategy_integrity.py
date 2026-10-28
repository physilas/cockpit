"""Torch-free binding of a qualified goal network to its measured runtime."""
import hashlib
import json
from pathlib import Path

RUNTIME_SOURCES = (
    'ai/briefing_planner_v2.py', 'ai/briefing_browser_v2.py',
    'ai/round_strategy_integrity.py', 'ai/round_strategy_constraints.py',
    'ai/round_strategy.py', 'ai/round_strategy_browser.py',
    'ai/briefing.py', 'ai/briefing_browser.py', 'ai/briefing_planner.py', 'play_options.py',
)


def network_digest(weights):
    payload={key:value for key,value in weights.items() if key!='release'}
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def runtime_metadata(weights, sources):
    return {'network_sha256':network_digest(weights),
            'runtime_sources':{name:sources[name] for name in RUNTIME_SOURCES}}


def validate_runtime(weights, root=None):
    root=Path(root) if root is not None else Path(__file__).resolve().parents[1]
    release=weights.get('release',{})
    if release.get('qualification_granted') is not True:
        raise ValueError('Unqualified round-policy weights cannot become the default.')
    if network_digest(weights)!=release.get('network_sha256'):
        raise ValueError('Round-policy parameters changed after qualification.')
    sources=release.get('runtime_sources',{})
    if set(sources)!=set(RUNTIME_SOURCES):
        raise ValueError('Incomplete round-policy runtime provenance.')
    for name,expected in sources.items():
        if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
            raise ValueError(f'Round-policy runtime changed after qualification: {name}')
