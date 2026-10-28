from copy import deepcopy
import unittest
from ai.modules import ModuleEnv,MODULE_ACTIONS
from ai.actions import Action
from ai.briefing_planner_v2 import ability_value,progress_value,unpaired_task_cost,plan_briefed_round,synchronisation_value,wind_pair_values


class BriefingV2SynchronizationTests(unittest.TestCase):
    def root(self,paired=0,focus='tasks',coordination='synchronisation'):
        env=ModuleEnv('LOG_KUL_YELLOW',abilities=['synchronisation'],clock=lambda:0.)
        env.reset(seed='public-anytime-extra-flap');root=env.view('kopilot')
        root.update(height=4000,last_round=False,partner_remaining=0)
        root['gear']=[i<paired for i in range(3)];root['flaps']=[i<paired for i in range(4)]
        root['_briefing']={'movement_preference':1,'focus':focus,'coordination':coordination}
        return root

    def flap(self,view):
        child=deepcopy(view);i=child['flaps'].index(False)
        child['flaps'][i]=True;child['board'][10+i]={'value':(1,2,4,5)[i],'owner':'kopilot'}
        return child

    def test_one_extra_flap_is_useful_before_between_or_after_the_three_pairs(self):
        for paired in range(4):
            for focus in ('radio','tasks','coffee','fuel'):
                for coordination in ('synchronisation','level','brakes'):
                    with self.subTest(paired=paired,focus=focus,coordination=coordination):
                        root=self.root(paired,focus,coordination);one=self.flap(root)
                        utility=lambda v:progress_value(root,v)+ability_value(root,v)
                        self.assertGreater(utility(one),utility(root))
                        self.assertEqual(0.,unpaired_task_cost(root,one,synchronisation_value(root,one)))
                        if paired<3:
                            two=self.flap(one)
                            self.assertLess(utility(two),utility(one),'Task focus must not reward sacrificing another future pair when the partner cannot follow.')

    def test_an_actual_current_pair_is_not_penalized_as_unmatched_work(self):
        root=self.root();root['modules_state']['sync_triggered']=False
        child=self.flap(root);child['gear'][0]=True
        child['board'][7]={'value':1,'owner':'pilot'}
        for exact in (False,True):
            self.assertEqual(0.,unpaired_task_cost(root,child,synchronisation_value(root,child,exact=exact),exact=exact))

    def test_survival_in_the_final_round_still_allows_unpaired_completion(self):
        root=self.root();root['last_round']=True;root['height']=0
        child=self.flap(self.flap(root))
        self.assertEqual(0.,unpaired_task_cost(root,child,synchronisation_value(root,child)))

    def test_extra_flap_can_follow_an_already_earned_bonus_in_the_same_round(self):
        root=self.root(1);root['modules_state']['sync_triggered']=True
        one=self.flap(root);two=self.flap(one)
        utility=lambda v:progress_value(root,v)+ability_value(root,v)
        self.assertGreater(utility(one),utility(root))
        self.assertLess(utility(two),utility(one))

    def test_using_the_extra_flap_early_does_not_reset_its_budget_next_round(self):
        root=self.flap(self.root());root['board']=[None]*len(root['board'])
        root['modules_state']['sync_triggered']=False
        later=self.flap(root)
        utility=lambda v:progress_value(root,v)+ability_value(root,v)
        self.assertLess(utility(later),utility(root))

    def test_sync_partner_forecast_uses_the_agreed_engine_target(self):
        root=self.root();root.update(partner_remaining=3,coffee=0)
        root['board'][1]={'value':3,'owner':'kopilot'}
        root['board'][3]={'value':6,'owner':'kopilot'}
        for cell in root['track']:cell['planes']=0
        values=[]
        for movement in (0,2):
            start=deepcopy(root);start['_briefing']['movement_preference']=movement
            child=self.flap(start)
            values.append(synchronisation_value(start,child,exact=True))
        self.assertEqual(135.,values[0],'With an own engine 6, stationary flight is impossible without wind.')
        self.assertGreater(values[1],values[0])

    def test_wind_forecast_uses_the_agreed_distance_for_this_round(self):
        env=ModuleEnv('LOG_GIG_YELLOW',abilities=['control'],clock=lambda:0.)
        env.reset(seed='accepted-flight-wind');root=env.view()
        root.update(height=1000,distance=2,last_round=False)
        root['board'][0]={'value':2,'owner':'pilot'}
        root['board'][2]={'value':2,'owner':'pilot'}
        root['_briefing']={'movement_preference':0,'focus':'tasks','coordination':'wind'}
        self.assertEqual(0.,max(wind_pair_values(root,root)))
        root['_briefing']['movement_preference']=2
        self.assertGreater(max(wind_pair_values(root,root)),0.)

    def test_following_the_partner_beats_coffee_for_both_roles(self):
        ids={action:i for i,action in enumerate(MODULE_ACTIONS)}
        for role,slot,partner_slot in [('pilot',7,10),('kopilot',10,7)]:
            root=self.root();root.update(role=role,own_dice=[2,0,0,0],coffee=0,partner_remaining=0)
            for i in range(4):root['board'][i]={'value':3 if i<2 else 1,'owner':('pilot','kopilot')[i%2]}
            root['board'][partner_slot]={'value':2,'owner':'kopilot' if role=='pilot' else 'pilot'}
            root['flaps' if role=='pilot' else 'gear'][0]=True
            task=ids[Action('place',die=0,slot=slot)];coffee=ids[Action('place',die=0,slot=17)]
            mask=[i in (task,coffee) for i in range(len(MODULE_ACTIONS))]
            ranks=plan_briefed_round(root,mask,beam=12)
            self.assertEqual(task,max(ranks,key=ranks.get))



class BriefingOpeningTests(unittest.TestCase):
    def test_opening_keeps_blueprint_convention_without_breaking_agreed_distance(self):
        import json
        from unittest.mock import patch
        from backend import bridge
        from ai.briefing_browser_v2 import decision
        env=ModuleEnv('LOG_YUL_GREEN',clock=lambda:0.);env.reset(seed='opening-feasible-before-partner')
        for die,face in zip(env.game.pilot_wuerfel,(6,1,1,2)):die.augenzahl=face
        plan={'version':1,'round':1,'movement_preference':0,'focus':'tasks','coordination':'brakes'}
        ids={a:i for i,a in enumerate(MODULE_ACTIONS)}
        high_engine=ids[Action('place',die=0,slot=2)]
        self.assertTrue(env.action_mask()[high_engine])
        with patch.object(bridge,'_spiel',env.game):
            result=decision(assistance_version=15,schema_version=3,plan_json=json.dumps(plan))
            public=result['public_plan']
            self.assertEqual('briefing_v2_await_public_partner_control',public['planning_mode'])
            self.assertEqual({},public['scores']);self.assertIsNone(public['best_action'])
            self.assertFalse(public['baseline_mask'][high_engine],'An engine 6 cannot keep a stationary contract from this hand, even with two possible gear upgrades.')
            self.assertTrue(any(public['baseline_mask']))
            self.assertTrue(all(not prior or allowed for prior,allowed in zip(result['reference_action_mask'],public['baseline_mask'])))
            env.step(ids[Action('place',die=1,slot=0)])
            later=decision(assistance_version=15,schema_version=3,plan_json=json.dumps(plan))
            self.assertNotEqual('briefing_v2_await_public_partner_control',later['public_plan']['planning_mode'])


if __name__=='__main__':unittest.main()
