"""Public-only, pre-roll round-policy features and portable tiny-network inference.

No Torch, hidden dice, airport identity, RNG state or future outcomes are inputs.
The learned policy selects goals; the existing fair hand planner executes them.
"""
import math
from .briefing import proposals as legacy_proposals
from .round_strategy_options import proposals,PLAN_VERSION
from .round_strategy_constraints import constrain

HEADS = (('movement_preference',(0,1,2,None)),('focus',('radio','tasks','coffee','fuel',None)),
         ('coordination',('level','brakes','synchronisation','wind',None)))
MODULES=('kerosene','leak','wind','ice','intern','realtime')
CARDS=('working-together','synchronisation','mastery','control','anticipation','adaptation')
FEATURES=('distance','height','attitude','coffee','fuel','fuel_present','rerolls','wind_position','wind_value',
          'ice','intern','blue','orange','holding','last_round','pace','traffic_total') + tuple('module.'+m for m in MODULES) + tuple('card.'+c for c in CARDS) + tuple(f'{kind}.{i}' for kind,n in [('gear',3),('flaps',4),('brakes',3)] for i in range(n)) + tuple(f'next.{i}.{kind}' for i in range(7) for kind in ('planes','traffic','min','max'))
OFFSETS=(0,4,9,14)
OUTPUTS=OFFSETS[-1]
FORMAT=2
GOALS_SCHEMA=[[key,list(values)] for key,values in HEADS]


def encode(state):
    fuel=state.get('kerosin');distance=state['entfernung'];height=state['hoehe']
    out=[distance/12,height/7000,state['fluglage']/3,state['kaffeetassen']/3,(fuel or 0)/20,float(fuel is not None),
         state.get('neuwurf_plaettchen',0)/3,state.get('wind_position',0)/20,state.get('wind_wert',0)/3,
         state.get('eis_fortschritt',0)/4,len(state.get('praktikant',[]))/6,
         state.get('aerodynamik_blau',4.5)/12,state.get('aerodynamik_orange',8.5)/12,
         float(state['warteschleife']),float(state['letzte_runde']),distance/max(1,height/1000)/2,sum(state['flugzeuge'])/12]
    out += [float(m in state['module']) for m in MODULES]+[float(c in state['faehigkeitskarten']) for c in CARDS]
    out += [float(v) for key in ('fahrwerk_ausgefahren','landeklappen_ausgefahren','bremsen_aktiviert') for v in state[key]]
    for ahead in range(7):
        index=state['laenge']-1-distance+ahead
        def at(key,default):
            values=state.get(key,[]);return values[index] if 0<=index<len(values) else default
        out += [at('flugzeuge',0)/4,at('flugzeugwuerfel',0)/2,at('kurven_min',-2)/2,at('kurven_max',2)/2]
    if len(out)!=len(FEATURES) or not all(math.isfinite(v) for v in out):raise ValueError('Invalid public round features.')
    return [max(-5.,min(5.,v)) for v in out]


def inputs(state):
    proposal=proposals(state);mask=[];prior=[]
    for goal,(_,values) in zip(proposal['goals'],HEADS):
        mask += [any(type(v) is type(o['value']) and v==o['value'] for o in goal['options']) for v in values]
        prior += [1. if v==goal['selected'] else 0. for v in values]
    return encode(state),constrain(state,HEADS,mask),prior


def logits(features,weights):
    if weights['format']!=FORMAT or weights['features']!=list(FEATURES) or weights.get('goals_schema')!=GOALS_SCHEMA:raise ValueError('Incompatible round policy.')
    hidden=[math.tanh(sum(a*b for a,b in zip(row,features))+bias) for row,bias in zip(weights['hidden_weight'],weights['hidden_bias'])]
    return [sum(a*b for a,b in zip(row,hidden))+bias for row,bias in zip(weights['actor_weight'],weights['actor_bias'])]


def choose(state,weights=None):
    if weights is None:
        return {'version':1,'round':state['runde'],**{g['key']:g['selected'] for g in legacy_proposals(state)['goals']}}
    features,mask,prior=inputs(state)
    residual=logits(features,weights) if weights is not None else [0.]*OUTPUTS
    result={'version':PLAN_VERSION,'round':state['runde']}
    for head,(key,values) in enumerate(HEADS):
        start=OFFSETS[head]
        selected=max((i for i in range(len(values)) if mask[start+i]),key=lambda i:prior[start+i]+residual[start+i])
        result[key]=values[selected]
    return result


def potential(state):
    """Bounded public landing-readiness potential, settled to zero at termination.

    Training uses Phi(next)-Phi(now); no persistent reward for farming resources.
    Native wins/losses remain the undiscounted full-episode objective.
    """
    if state['status']!='laeuft':return 0.
    progress=(sum(state['fahrwerk_ausgefahren'])/3+sum(state['landeklappen_ausgefahren'])/4)
    if 'ice' in state['module']:progress+=state.get('eis_fortschritt',0)/4
    else:progress+=sum(state['bremsen_aktiviert'])/3
    if 'intern' in state['module']:progress+=1-len(state.get('praktikant',[]))/6
    fuel=state.get('kerosin')
    value=.18*progress+.04*state['kaffeetassen']/3+.04*((fuel or 0)/20)
    value-=.2*min(2.,state['entfernung']/max(1.,state['hoehe']/1000))
    value-=.12*min(2.,sum(state['flugzeuge'])/12)
    return value
