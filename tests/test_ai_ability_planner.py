from copy import deepcopy
from itertools import permutations, product
import unittest

from ai.actions import Action
from ai.ability_planner import (
    IDS, _wind_horizon, ability_value, plan_ability_round, synchronisation_value,
    weighted_task_value, wind_pair_values,
)
from ai.contract_planner import progress_value
from ai.modules import MODULE_ACTIONS, ModuleEnv
from ai.public_contract import public_contract_inputs
from ai.ability_policy import ability_inputs


class AbilityPlannerTests(unittest.TestCase):
    def view(self, card='synchronisation', airport='LOG_KUL_YELLOW'):
        env = ModuleEnv(airport, abilities=[card], clock=lambda:0.)
        env.reset(seed='development:ability-unit')
        return env, env.view()

    def test_joint_weighted_belief_matches_ordered_hand_enumeration(self):
        pairs = tuple(r == t for r,t in product(range(1,7),repeat=2))
        other = tuple(r+t <= 5 for r,t in product(range(1,7),repeat=2))
        values = tuple(float(r*7+t) for r,t in product(range(1,7),repeat=2))
        groups = [(pairs,((1,2),),values),(other,((2,3),),tuple(v+10 for v in values))]
        total = 0.
        for hand in product(range(1,7),repeat=3):
            best = 0.
            for allowed,tasks,utility in groups:
                for ordered in permutations(hand):
                    for r,t,extra in product(range(1,7),range(1,7),tasks[0]):
                        cost = abs(r-ordered[0])+abs(t-ordered[1])+abs(extra-ordered[2])
                        if cost <= 1 and allowed[(r-1)*6+t-1]:
                            best = max(best,utility[(r-1)*6+t-1])
            total += best
        self.assertAlmostEqual(total/216,weighted_task_value(groups,3,1),places=10)
        self.assertEqual(0.,weighted_task_value(groups,2,3),'one die cannot pay two tasks')

    def test_match_partner_switch_before_making_coffee_in_both_roles(self):
        for role, own, other, slot, face in (('pilot',0,1,7,2),('kopilot',1,0,10,2)):
            _, base = self.view()
            view = deepcopy(base)
            view.update(role=role, own_dice=[face,0,0,0],partner_remaining=0,coffee=0)
            for i in (0,1,2,3):view['board'][i]={'value':3 if i<2 else 1,'owner':('pilot','kopilot')[i%2]}
            for cell in view['track']:cell['planes']=0
            partner_slot=10 if role=='pilot' else 7
            view['board'][partner_slot]={'value':2,'owner':('pilot','kopilot')[other]}
            view['flaps' if role=='pilot' else 'gear'][0]=True
            allowed=[False]*len(MODULE_ACTIONS)
            gear=IDS[Action('place',die=0,slot=slot)]
            coffee=IDS[Action('place',die=0,slot=17)]
            allowed[gear]=allowed[coffee]=True
            ranks=plan_ability_round(view,allowed,beam=12)
            self.assertTrue(ranks)
            self.assertEqual(gear,max(ranks,key=ranks.get))

    def test_preserve_future_pairs_but_allow_one_unpaired_copilot_flap(self):
        _,root=self.view();root['modules_state']['sync_triggered']=True
        root.update(height=4000,last_round=False)
        first=deepcopy(root);first['flaps'][0]=True
        first['board'][10]={'value':1,'owner':'kopilot'}
        second=deepcopy(first);second['flaps'][1]=True
        second['board'][11]={'value':2,'owner':'kopilot'}
        utility=lambda view:progress_value(root,view)+synchronisation_value(root,view)
        self.assertGreater(utility(first),utility(root))
        self.assertLess(utility(second),utility(first))

    def test_no_bonus_credit_when_partner_has_no_spare_die(self):
        _,root=self.view();root.update(partner_remaining=2,coffee=0)
        placed=deepcopy(root);placed['board'][7]={'value':2,'owner':'pilot'}
        placed['gear'][0]=True
        # Two partner dice must still occupy rudder/thrust. No third die exists.
        self.assertEqual(synchronisation_value(root,placed),45*min(2,4,root['height']//1000))

    def test_refilling_both_green_switches_is_not_a_bonus_farm(self):
        _,root=self.view();root['gear']=[True]*3;root['flaps']=[True]*4
        placed=deepcopy(root)
        placed['board'][7]={'value':1,'owner':'pilot'}
        placed['board'][10]={'value':1,'owner':'kopilot'}
        self.assertLess(synchronisation_value(root,placed),0)

    def test_headwind_is_good_for_landing_but_can_destroy_remaining_range(self):
        curves=((-2,2),)*3
        def value(position,distance,rounds):
            return _wind_horizon(position,0,distance,rounds,7.5,12.5,7.5,12.5,curves,0,False)
        self.assertGreater(value(8,0,1),value(0,0,1))
        self.assertEqual(0.,value(8,2,2))
        self.assertGreater(value(0,2,2),value(8,2,2))

    def test_equal_rudders_can_rotate_wind_while_holding_a_bank(self):
        _,root=self.view('control','LOG_GIG_YELLOW')
        root.update(attitude=1,height=1000,last_round=False,distance=0)
        root['modules_state'].update(wind_position=4,wind_value=1)
        placed=deepcopy(root)
        placed['board'][0]={'value':4,'owner':'pilot'}
        placed['board'][2]={'value':1,'owner':'pilot'}
        values=wind_pair_values(root,placed)
        # 4/4 preserves bank+1 and therefore advances the wind ring to index5.
        curves=tuple((c['min'],c['max']) for c in sorted(root['track'],key=lambda c:c['distance']))
        expected=400*_wind_horizon(5,1,0,1,root['aero_blue'],root['aero_orange'],
            root['aero_blue']+3,root['aero_orange']+4,curves,0,False)
        self.assertEqual(expected,values[(4-1)*6+1-1])

    def test_unaffected_routes_keep_exact_old_inputs(self):
        env=ModuleEnv('MUC',clock=lambda:0.);env.reset(seed='development:ability-unaffected')
        args=('MUC',env.view(),env.action_mask())
        self.assertEqual(public_contract_inputs(*args),ability_inputs(*args))

    def test_real_hidden_partner_faces_and_rng_do_not_change_scores(self):
        env,view=self.view()
        first=plan_ability_round(view,env.action_mask(),beam=12)
        for die in env.game.kopilot_wuerfel:die.augenzahl=7-die.augenzahl
        env.rng.seed(999)
        self.assertEqual(first,plan_ability_round(env.view(),env.action_mask(),beam=12))
        self.assertTrue(first)

    def test_do_not_manufacture_a_bonus_by_refilling_a_green_switch(self):
        _,root=self.view()
        root.update(own_dice=[1,0,0,0],partner_remaining=0,coffee=2)
        root['gear']=[True]*3;root['flaps']=[True]*4
        for i in (0,1,2,3):root['board'][i]={'value':3 if i<2 else 1,'owner':('pilot','kopilot')[i%2]}
        root['board'][10]={'value':1,'owner':'kopilot'}
        for cell in root['track']:cell['planes']=0
        allowed=[False]*len(MODULE_ACTIONS)
        refill=IDS[Action('place',die=0,slot=7)]
        coffee=IDS[Action('place',die=0,slot=17)]
        allowed[refill]=allowed[coffee]=True
        ranks=plan_ability_round(root,allowed,beam=12)
        self.assertEqual(coffee,max(ranks,key=ranks.get))

    def test_matching_a_fresh_partner_switch_is_the_first_move_of_a_full_hand(self):
        for role, own, slot in (('pilot',0,7),('kopilot',1,10)):
            _,root=self.view()
            root.update(role=role,own_dice=[1,3,4,6],partner_remaining=2,coffee=0)
            other=1-own
            for i in (other,other+2):root['board'][i]={'value':3,'owner':('pilot','kopilot')[other]}
            partner_slot=10 if role=='pilot' else 7
            root['board'][partner_slot]={'value':1,'owner':('pilot','kopilot')[other]}
            root['flaps' if role=='pilot' else 'gear'][0]=True
            root['aero_orange' if role=='pilot' else 'aero_blue']+=1
            for cell in root['track']:cell['planes']=0
            allowed=[False]*len(MODULE_ACTIONS)
            match=IDS[Action('place',die=0,slot=slot)]
            announce=IDS[Action('place',die=1,slot=own)]
            allowed[match]=allowed[announce]=True
            ranks=plan_ability_round(root,allowed,beam=24)
            self.assertEqual(match,max(ranks,key=ranks.get),(role,ranks))
