"""Profile-15 provenance, extending the immutable profile-13 dependency hash."""
import hashlib
from pathlib import Path
from .strategy_fingerprint import public_strategy_fingerprint

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('ai/ability_fingerprint.py','ai/ability_planner.py','ai/ability_policy.py',
           'ai/ability_browser.py')


def ability_fingerprint():
    digest = hashlib.sha256(('public-strategy:15:' + public_strategy_fingerprint(13)).encode())
    for name in SOURCES:
        digest.update(name.encode())
        digest.update((ROOT/name).read_bytes())
    return digest.hexdigest()
