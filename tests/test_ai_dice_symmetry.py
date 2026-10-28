from copy import deepcopy
import unittest

import torch

from ai.actions import Action,ROLES
from ai.dice_symmetry import PERMUTATIONS,permute_rows
from ai.modules import MODULE_ACTIONS,MODULE_FEATURES,ModuleEnv,module_encode


class DiceSymmetryTests(unittest.TestCase):
    def test_all24_permutations_match_the_actual_engine_and_preserve_legal_labels(self):
        env=ModuleEnv('LOG_KEF_YELLOW',abilities=['adaptation'])
        env.reset(seed='train:dice-symmetry:engine')
        raw=torch.tensor(env.action_mask())[None]
        action=next(i for i,ok in enumerate(raw[0]) if ok)
        data=dict(observations=torch.tensor(env.observation())[None],masks=raw,reference_masks=raw,
                  target_masks=raw,actions=torch.tensor([action]),weights=torch.ones(1))
        role=env.current_role
        for index,p in enumerate(PERMUTATIONS):
            branch=deepcopy(env)
            dice=branch.game._wuerfel_liste(role)
            setattr(branch.game,'pilot_wuerfel' if role=='pilot' else 'kopilot_wuerfel',[dice[i] for i in p])
            result=permute_rows(data,torch.tensor([index]))
            self.assertTrue(torch.equal(torch.tensor(branch.observation()),result['observations'][0]),p)
            self.assertTrue(torch.equal(torch.tensor(branch.action_mask()),result['masks'][0]),p)
            self.assertTrue(result['masks'][0,result['actions'][0]])

    def test_public_own_selections_move_and_partner_indices_stay_untouched(self):
        env=ModuleEnv('MUC');env.reset(seed='train:dice-symmetry:public')
        view=env.view('pilot')
        view['reroll']={'initiator':'pilot','selections':{'pilot':[0,3],'kopilot':[1]}}
        view['modules_state']['swap']={'wartet_auf':'pilot','auswahl':{'pilot':0,'kopilot':2},
                                      'bestaetigt':{'pilot':False,'kopilot':True}}
        data=dict(observations=torch.tensor(module_encode(view))[None])
        p=(3,2,1,0);index=PERMUTATIONS.index(p)
        expected=deepcopy(view)
        expected['own_dice']=[view['own_dice'][i] for i in p]
        expected['reroll']['selections']['pilot']=[3,0]
        expected['modules_state']['swap']['auswahl']['pilot']=3
        result=permute_rows(data,torch.tensor([index]))
        self.assertTrue(torch.equal(torch.tensor(module_encode(expected)),result['observations'][0]))

    def test_subset_bits_and_inverse_permutation_round_trip(self):
        env=ModuleEnv('MUC');env.reset(seed='train:dice-symmetry:inverse')
        raw=torch.ones((1,len(MODULE_ACTIONS)),dtype=torch.bool)
        old=MODULE_ACTIONS.index(Action('reroll_select',subset=1|4))
        data=dict(observations=torch.tensor(env.observation())[None],masks=raw,reference_masks=raw,
                  target_masks=raw,actions=torch.tensor([old]),weights=torch.ones(1))
        for index,p in enumerate(PERMUTATIONS):
            changed=permute_rows(data,torch.tensor([index]))
            bits=MODULE_ACTIONS[changed['actions'][0]].subset
            self.assertEqual(sum(1<<p.index(i) for i in (0,2)),bits)
            inverse=PERMUTATIONS.index(tuple(p.index(i) for i in range(4)))
            restored=permute_rows(changed,torch.tensor([inverse]))
            for key in data:self.assertTrue(torch.equal(data[key],restored[key]),(p,key))
