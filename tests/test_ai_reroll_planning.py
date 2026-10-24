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
        for version in (7,8):
            actual=assisted_mask(view,self.mask((1,2,3)),version=version)
            self.assertEqual([i for i,v in enumerate(actual) if v],
                [ACTION_IDS[Action('reroll_select',subset=2)]])
        self.assertEqual(view,before)

    def test_future_coffee_is_considered_before_rerolling_a_fixable_die(self):
        view=self.view([4,0,0,0],2)
        view['partner_remaining']=1
        view['reroll']['selections']['kopilot']=None
        slot=next(i for i,s in enumerate(SLOTS) if s.target=='ruder' and s.owner=='pilot')
        view['board'][slot]={'owner':'pilot','value':3}
        for version in (7,8):
            actual=assisted_mask(view,self.mask((0,1)),version=version)
            self.assertTrue(actual[ACTION_IDS[Action('reroll_select',subset=0)]])
            self.assertFalse(actual[ACTION_IDS[Action('reroll_select',subset=1)]])

    def test_profile_eight_preserves_crew_one_placement_choices_for_both_roles(self):
        env=CrewEnv('LOG_HND_GREEN');env.reset(seed=5100004)
        for role in ('pilot','kopilot'):
            env.game.am_zug=role
            view,mask=env.view(),env.action_mask()
            self.assertEqual(assisted_mask(view,mask,version=8),assisted_mask(view,mask,version=3))
