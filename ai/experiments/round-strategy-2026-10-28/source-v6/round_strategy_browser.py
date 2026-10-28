"""Optional learned pre-roll proposals; the released hand executor stays frozen."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from backend import bridge
from .briefing import suggest as default_suggest
from .briefing_browser import decision as original_decision,start_round
from .briefing_browser_v2 import decision as planned_decision,execution_fingerprint
from .round_strategy_integrity import validate_runtime
from .round_strategy import FEATURES,HEADS,OFFSETS,choose,inputs,logits


@lru_cache(maxsize=1)
def released_weights():
    path=Path(__file__).with_name('round_strategy_weights.json')
    if not path.exists():return None
    raw=path.read_bytes();weights=json.loads(raw)
    validate_runtime(weights)
    return weights,hashlib.sha256(raw).hexdigest()


def decision(role=None,reroll_json='null',steps=0,max_steps=256,assistance_version=0,schema_version=1,plan_json='null'):
    executor=original_decision
    if assistance_version==15 and json.loads(plan_json) is not None and released_weights() is not None:
        executor=planned_decision
    return executor(role,reroll_json,steps,max_steps,assistance_version,schema_version,plan_json)


def suggest(assistance_version=0):
    proposal=default_suggest()
    if assistance_version!=15:return proposal
    loaded=released_weights()
    if loaded is None:return proposal
    weights,sha=loaded;state=bridge.zustand();plan=choose(state,weights)
    proposal['execution_policy']='briefing-v2'
    proposal['execution_sha256']=execution_fingerprint()
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
