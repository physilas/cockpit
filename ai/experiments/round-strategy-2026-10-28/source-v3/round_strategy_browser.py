"""Optional learned pre-roll proposals; the released hand executor stays frozen."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from backend import bridge
from .briefing import suggest as default_suggest
from .briefing_browser import decision,start_round
from .round_strategy import choose


@lru_cache(maxsize=1)
def released_weights():
    path=Path(__file__).with_name('round_strategy_weights.json')
    if not path.exists():return None
    raw=path.read_bytes();weights=json.loads(raw)
    if not weights.get('release',{}).get('qualification_granted'):
        raise ValueError('Unqualified round-policy weights cannot become the default.')
    return weights,hashlib.sha256(raw).hexdigest()


def suggest(assistance_version=0):
    proposal=default_suggest()
    if assistance_version!=15:return proposal
    loaded=released_weights()
    if loaded is None:return proposal
    weights,sha=loaded;plan=choose(bridge.zustand(),weights)
    for goal in proposal['goals']:goal['selected']=plan[goal['key']]
    proposal['strategy_selection']={'policy':'learned-public-round-v1','weights_sha256':sha,'features':'public-only-before-roll','qualification':weights['release']}
    return proposal
