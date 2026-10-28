"""Exact own-die-index symmetry for schema-3 training examples.

Faces, colors, roles and field numbers are never interchanged. Public reroll
bits and cooperation indices belonging to the renamed own dice move with them.
"""
from dataclasses import replace
from itertools import permutations

import torch

from .actions import ROLES
from .modules import MODULE_ACTIONS,MODULE_FEATURES


PERMUTATIONS=tuple(permutations(range(4)))
_IDS={action:i for i,action in enumerate(MODULE_ACTIONS)}
_FEATURES={name:i for i,name in enumerate(MODULE_FEATURES)}


def tables():
    feature_maps=[];action_maps=[];inverse_actions=[];inverses=[]
    for permutation in PERMUTATIONS:
        inverse=tuple(permutation.index(i) for i in range(4));inverses.append(inverse)
        maps=[]
        for role in ROLES:
            mapping=list(range(len(MODULE_FEATURES)))
            for new,old in enumerate(permutation):
                for face in range(7):mapping[_FEATURES[f'die.{new}.{face}']]=_FEATURES[f'die.{old}.{face}']
                mapping[_FEATURES[f'reroll.{role}.selected.{new}']]=_FEATURES[f'reroll.{role}.selected.{old}']
            maps.append(mapping)
        feature_maps.append(maps)
        forward=[]
        for action in MODULE_ACTIONS:
            changed=replace(action,die=inverse[action.die]) if action.die>=0 else action
            if action.kind=='reroll_select':
                bits=sum(1<<inverse[old] for old in range(4) if action.subset&(1<<old))
                changed=replace(changed,subset=bits)
            forward.append(_IDS[changed])
        gather=[forward.index(new) for new in range(len(MODULE_ACTIONS))]
        if len(set(forward))!=len(MODULE_ACTIONS):raise RuntimeError('Die symmetry is not bijective.')
        action_maps.append(gather);inverse_actions.append(forward)
    return tuple(torch.tensor(x) for x in (feature_maps,action_maps,inverse_actions,inverses))


_TABLES=None


def permute_rows(data,indices):
    global _TABLES
    if _TABLES is None:_TABLES=tables()
    features,actions,forward,inverses=_TABLES
    observation=data['observations'];count=observation.shape[0]
    if observation.shape!=(count,489) or indices.shape!=(count,) or not ((indices>=0)&(indices<24)).all():
        raise ValueError('Use schema-3 rows and one valid permutation index per row.')
    role=(observation[:,_FEATURES['role.kopilot']]>.5).long()
    selected=features[indices,role]
    changed=observation.gather(1,selected)
    # Cooperation stores a one-based die index divided by4, with0 for absent.
    for owner,r in enumerate(ROLES):
        column=_FEATURES[f'swap.{r}.index']
        old=observation[:,column]
        active=(role==owner)&(old>0)
        raw=(old*4).round().long()-1
        new=(inverses[indices,raw.clamp(0,3)]+1).to(old.dtype)/4
        changed[:,column]=torch.where(active,new,old)
    result={**data,'observations':changed}
    for name in ('masks','reference_masks','target_masks'):
        if name in data:result[name]=data[name].gather(1,actions[indices])
    if 'actions' in data:result['actions']=forward[indices,data['actions']]
    return result
