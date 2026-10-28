"""Group physically equivalent recorded actions without seeing hidden dice."""
import json


def signature(action, schema, observation):
    die=action.get('die',-1)
    if die>=0:
        name=f'die.{die}.0'
        start=schema['features'].index(name) if name in schema['features'] else -1
        values=observation[start:start+7] if start>=0 else []
        face=values.index(max(values)) if values else None
    else:
        name='pending.value'
        face=round(observation[schema['features'].index(name)]*6) if name in schema['features'] else None
    kind=action['kind']
    if kind in ('place','bonus_place'):
        slot=schema['slots'][action['slot']]
        data=[kind,slot['target'],slot['owner'],None if slot['target'] in ('konzentration','funk') else slot['index'],face]
    elif kind in ('coffee','bonus_coffee'):
        data=[kind,face,action['delta']]
    elif kind in ('adaptation','anticipation','swap_choose'):
        data=[kind,face]
    else:
        data=[kind,action.get('die'),action.get('slot'),action.get('delta'),action.get('subset')]
    return json.dumps(data,separators=(',',':'))


def equivalent_actions(schema, observation, mask, action_id):
    key=signature(schema['actions'][action_id],schema,observation)
    return tuple(i for i,action in enumerate(schema['actions']) if mask[i] and signature(action,schema,observation)==key)
