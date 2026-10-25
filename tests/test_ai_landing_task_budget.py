"""Optimistic necessary count bounds, with no policy or private-face input."""
from copy import deepcopy
import random
import unittest

from ai.landing_task_budget import task_budget
from ai.module_physics import WIND_RING
from ai.wind_ice_advice import _after_placement
from tests.test_ai_joint_landing import ice_fixture,brake_fixture,radio_fixture
from tests.test_ai_solo_landing import black_fixture
from tests.test_ai_wind_ice_counterexamples import _place


class LandingTaskBudgetTests(unittest.TestCase):
    def test_last_two_rounds_exact_capacity_concentration_loses_one_necessary_slot(self):
        env=ice_fixture();view=env.view()
        view['height']=1000;view['last_round']=False
        view['gear']=[False]*3;view['flaps']=[True,False,False,False]
        before=task_budget(view)
        self.assertTrue(before['possible']);self.assertEqual(before['available_total'],16)
        self.assertEqual(before['minimum_total_need'],16)
        after,_=_after_placement(view,3,17,2,0)  # Concentration consumes a regular die.
        self.assertFalse(task_budget(after)['possible'])
        good,_=_after_placement(view,2,29,5,0)  # Upper ice5 completes one actual task.
        self.assertTrue(task_budget(good)['possible'])
        self.assertEqual(task_budget(good)['minimum_total_need'],15)

    def test_radio_needs_die_and_free_role_slot_even_when_controls_fit(self):
        env=radio_fixture();view=env.view()
        self.assertTrue(task_budget(view)['possible'])
        after,_=_after_placement(view,0,17,1,0)
        self.assertFalse(task_budget(after)['possible'])
        view['track'][-1]['planes']=3
        self.assertFalse(task_budget(view)['possible'])

    def test_issued_bonus_once_future_card_abstains_without_adding_capacity(self):
        env=black_fixture();view=env.view()
        budget=task_budget(view)
        self.assertTrue(budget['possible']);self.assertEqual(budget['issued_shared_bonus'],1)
        self.assertEqual(budget['available_total'],2)
        view['modules_state']['pending']=None
        self.assertFalse(task_budget(view)['possible'])
        view['modules_state']['sync_triggered']=False
        budget=task_budget(view)
        self.assertIsNone(budget['possible']);self.assertEqual(budget['available_total'],1)
        view['height']=1000;view['last_round']=False
        view['modules_state']['pending']=dict(role='pilot',source='synchronisation',value=None)
        self.assertIsNone(task_budget(view)['possible'])
        self.assertEqual(task_budget(view)['issued_shared_bonus'],1)

    def test_all_prefixes_of_ordered_successful_engine_drills_pass_the_bound(self):
        exercises=[(ice_fixture(),(('pilot',2,'eisbremse',6),('kopilot',0,'ruder',None),
            ('pilot',0,'ruder',None),('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),
            ('kopilot',2,'eisbremse',7),('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1))),
            (brake_fixture(),(('pilot',2,'bremse',0),('kopilot',0,'ruder',None),('pilot',0,'ruder',None),
            ('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),('kopilot',2,'landeklappe',3),
            ('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1)))]
        for env,sequence in exercises:
            for step in sequence:
                self.assertTrue(task_budget(env.view())['possible'])
                _place(env.game,*step)
            self.assertTrue(env.game.rundenende().gewonnen)

    def test_headwind_can_land_without_regular_brake_and_bound_does_not_invent_a_need(self):
        env=brake_fixture();game,c=env.game,env.game.cockpit
        c.wind_position=WIND_RING.index(-3);c.landeklappen_ausgefahren[:]=[True]*4
        self.assertEqual(task_budget(env.view())['minimum_brake_upgrades'],0)
        self.assertTrue(task_budget(env.view())['possible'])
        for role,die,target,index in (('pilot',0,'ruder',None),('kopilot',0,'ruder',None),
                ('pilot',1,'triebwerk',None),('kopilot',1,'triebwerk',None),
                ('pilot',2,'konzentration',0),('kopilot',2,'landeklappe',3),
                ('pilot',3,'konzentration',1),('kopilot',3,'konzentration',2)):
            _place(game,role,die,target,index)
        self.assertTrue(game.rundenende().gewonnen)

    def test_only_public_counts_no_rng_no_mutation_unsupported_tokens_abstain(self):
        env=ice_fixture();view=env.view();snapshot=deepcopy(view);rng=random.getstate()
        expected=task_budget(view)
        for die in env.game.kopilot_wuerfel:die.augenzahl=6
        self.assertEqual(task_budget(env.view()),expected)
        self.assertEqual(view,snapshot);self.assertEqual(random.getstate(),rng)
        for module in ('intern','realtime'):
            bad=deepcopy(view);bad['modules_state']['modules'].append(module)
            self.assertIsNone(task_budget(bad)['possible'])
        view['modules_state']['pending']=dict(role='pilot',source='intern',value=5)
        self.assertIsNone(task_budget(view)['possible'])


if __name__=='__main__':unittest.main()
