"""Optional learned pre-roll proposals; the released hand executor stays frozen."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from backend import bridge
from .briefing import suggest as default_suggest
from .briefing_browser import decision,start_round
from .round_strategy_integrity import validate_runtime
from .round_strategy import FEATURES,HEADS,OFFSETS,choose,inputs,logits


@lru_cache(maxsize=1)
def released_weights():
    path=Path(__file__).with_name('round_strategy_weights.json')
    if not path.exists():return None
    raw=path.read_bytes();weights=json.loads(raw)
    validate_runtime(weights)
    return weights,hashlib.sha256(raw).hexdigest()


def suggest(assistance_version=0):
    proposal=default_suggest()
    if assistance_version!=15:return proposal
    loaded=released_weights()
    if loaded is None:return proposal
    weights,sha=loaded;state=bridge.zustand();plan=choose(state,weights)
    features,mask,prior=inputs(state)
    scores=[a+b for a,b in zip(prior,logits(features,weights))]
    for head,goal in enumerate(proposal['goals']):
        goal['selected']=plan[goal['key']]
        start=OFFSETS[head];values=HEADS[head][1]
        ranked=sorted((i for i in range(len(values)) if mask[start+i]),key=lambda i:(-scores[start+i],i))
        goal['ai_suggestions']=[values[i] for i in ranked]
    proposal['strategy_selection']={'policy':'learned-public-round-v2','weights_sha256':sha,'features':'public-only-before-roll','qualification':weights['release'],
        'training_context':{'version':2,'feature_names':list(FEATURES),'public_features':features,'goal_mask':mask,'default_prior':prior}}
    return proposal
