from copy import deepcopy
import unittest

from ai.actions import ACTIONS,ACTION_IDS,Action,SLOTS
from ai.environment import CrewEnv
from ai.tactics import assisted_mask


class RerollPlanningTests(unittest.TestCase):
    def view(self,dice,coffee):
        env=CrewEnv();env.reset(seed=5100007)
        view=env.view()
        view.update(role='pilot',height=0,distance=0,last_round=True,own_dice=dice,
            partner_remaining=0,gear=[True]*3,flaps=[True]*4,brake_progress=[False]*3,
            brakes=0,coffee=coffee,board=[None]*len(SLOTS),
            reroll={'initiator':'pilot','selections':{'pilot':None,'kopilot':[]}})
        for cell in view['track']:
            cell['planes']=0
        for target,role,value in [('ruder','kopilot',3),('triebwerk','pilot',1),('triebwerk','kopilot',1)]:
            slot=next(i for i,s in enumerate(SLOTS) if s.target==target and s.owner==role)
            view['board'][slot]={'owner':role,'value':value}
        return view

    def mask(self,subsets):
        return [a.kind=='reroll_select' and a.subset in subsets for a in ACTIONS]

    def test_preserves_the_only_die_matching_the_known_partner_control(self):
        view=self.view([3,6,0,0],0)
        before=deepcopy(view)
        actual=assisted_mask(view,self.mask((1,2,3)),version=7)
        self.assertEqual([i for i,v in enumerate(actual) if v],
            [ACTION_IDS[Action('reroll_select',subset=2)]])
        self.assertEqual(view,before)

    def test_future_coffee_is_considered_before_rerolling_a_fixable_die(self):
        view=self.view([4,0,0,0],2)
        view['partner_remaining']=1
        view['reroll']['selections']['kopilot']=None
        slot=next(i for i,s in enumerate(SLOTS) if s.target=='ruder' and s.owner=='pilot')
        view['board'][slot]={'owner':'pilot','value':3}
        actual=assisted_mask(view,self.mask((0,1)),version=7)
        self.assertTrue(actual[ACTION_IDS[Action('reroll_select',subset=0)]])
        self.assertFalse(actual[ACTION_IDS[Action('reroll_select',subset=1)]])
