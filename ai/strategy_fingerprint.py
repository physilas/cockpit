"""Versioned public strategy fingerprints without changing legacy hashes."""
import hashlib
from pathlib import Path

from .checkpoints import planner_fingerprint


ROOT=Path(__file__).resolve().parents[1]
SOURCES=('strategy_fingerprint.py','strategy_bridge.py','strategy_environment.py','browser_bridge.py',
         'coherent_advice.py','coherent_safety.py','safety_guard.py','belief_simulator.py',
         'contract_planner.py','assignment_belief.py','public_contract.py','round_responsibility.py',
         'reroll_advice.py','public_hand_prior.py','joint_landing_prior.py','joint_round.py',
         'rollout_search.py','agents.py','nn_model.py','checkpoints.py','export_browser.py')


def public_strategy_fingerprint(profile):
    if type(profile) is not int or profile not in (13,14):
        raise ValueError('Use public profile13 or14.')
    digest=hashlib.sha256(f'public-strategy:{profile}:{planner_fingerprint(3)}'.encode())
    paths=[ROOT/'ai'/name for name in SOURCES]
    paths.append(ROOT/'frontend/web/js/ai-policy.js')
    paths.append(ROOT/'build.py')
    paths.extend(p for p in (ROOT/'backend').rglob('*') if p.is_file() and p.suffix in ('.py','.yaml','.json'))
    for path in sorted(paths):
        digest.update(path.relative_to(ROOT).as_posix().encode());digest.update(path.read_bytes())
    return digest.hexdigest()
