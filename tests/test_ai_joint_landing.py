"""Static joint assignment math and authoritative terminal module exercises."""
from copy import deepcopy
from itertools import permutations,product
from math import inf
import random
import unittest
from unittest.mock import patch

from ai.actions import Action
from ai.joint_landing_prior import control_task_costs,fair_task_value,own_options
from ai.joint_landing_advice import (eligible,task_allocations,joint_landing_plans,joint_landing_reference)
from ai.module_physics import WIND_RING
from ai.modules import MODULE_ACTIONS
from tests.test_ai_wind_ice_counterexamples import _base_fixture,_place,_action


def final_fixture(airport,pilot,kopilot):
    env=_base_fixture(airport,pilot,kopilot)
    env.assistance_version=12
    game,c=env.game,env.game.cockpit
    game.landung.hoehe=game.landung.entfernung=0
    game.letzte_runde=True;game.aktuelle_runde=game._vorbereitete_runde=7
    c.fahrwerk_ausgefahren[:]=[True]*3;c.landeklappen_ausgefahren[:]=[True]*4
    c.aerodynamik_blau+=3;c.aerodynamik_orange+=4
    return env


def ice_fixture():
    env=final_fixture('LOG_KEF_YELLOW',(1,1,5,2),(1,1,5,2))
    env.game.cockpit.eis_fortschritt=3
    return env


def brake_fixture():
    env=final_fixture('LOG_GIG_YELLOW',(1,1,2,4),(1,1,6,2))
    env.game.cockpit.wind_position=WIND_RING.index(0)
    env.game.cockpit.landeklappen_ausgefahren[3]=False
    return env


def radio_fixture():
    env=final_fixture('LOG_GIG_YELLOW',(2,1,1,2),(1,1,1,5))
    c=env.game.cockpit
    c.wind_position=WIND_RING.index(0);c.bremsen_aktiviert[:]=[True]*3
    c.landeklappen_ausgefahren[3]=False
    env.game.landung.flugzeuge[-1]=1
    _place(env.game,'pilot',0,'funk')  # Occupied pilot radio cannot clear face1 later.
    return env


class JointLandingPriorTests(unittest.TestCase):
    def test_tasks_and_two_controls_use_three_distinct_dice(self):
        pairs=tuple(r==t==1 for r in range(1,7) for t in range(1,7))
        self.assertEqual(fair_task_value(pairs,2,0,[(5,)]),0.)
        self.assertAlmostEqual(fair_task_value(pairs,3,0,[(5,)]),10000*3/216)
        self.assertEqual(dict(control_task_costs((1,5),2,((5,),)))[(1,1)],inf)

    def test_shared_coffee_exact_probability_matches_independent_ordered_hands(self):
        pairs=tuple(r==1 and t<=2 for r in range(1,7) for t in range(1,7))
        total=0.
        for hand in product(range(1,7),repeat=3):
            best=0.
            for assignment in permutations(range(3)):
                for r,t in product(range(1,7),repeat=2):
                    cost=abs(hand[assignment[0]]-r)+abs(hand[assignment[1]]-t)+abs(hand[assignment[2]]-5)
                    if pairs[(r-1)*6+t-1] and cost<=1:best=max(best,10000+1.5*(1-cost))
            total+=best
        self.assertAlmostEqual(fair_task_value(pairs,3,1,[(5,)]),total/216)

    def test_published_controls_consume_no_private_die_and_fixed_own_plan_precedes_expectation(self):
        all_valid=(True,)*36
        self.assertAlmostEqual(fair_task_value(all_valid,1,0,[(5,)],rudder=1,thrust=1),10000/6)
        self.assertEqual(fair_task_value(all_valid,0,3,[(5,)],rudder=1,thrust=1),0.)
        plans=[tuple(r==face for r in range(1,7) for t in range(1,7)) for face in (1,2)]
        self.assertAlmostEqual(max(fair_task_value(p,1,0,thrust=1) for p in plans),10000/6)
        self.assertAlmostEqual(fair_task_value(tuple(a or b for a,b in zip(*plans)),1,0,thrust=1),10000/3)
        self.assertEqual(own_options((1,),rudder=1,thrust=1,tasks=[(5,)]),((1,1,4),))

    def test_invalid_inputs_and_no_rng(self):
        state=random.getstate()
        for args,kwargs in ((([True]*35,2,0),{}),(([True]*36,5,0),{}),
                (([True]*36,2,4),{}),(([True]*36,2,0),dict(rudder=True)),
                (([True]*36,2,0,[(7,)]),{})):
            with self.assertRaises(ValueError):fair_task_value(*args,**kwargs)
        self.assertEqual(random.getstate(),state)


class JointLandingAdviceTests(unittest.TestCase):
    def test_ice_reservation_excludes_sacrificing_the_only_upper_five_to_rudder(self):
        env=ice_fixture();view=env.view();allowed=env.action_mask()
        with patch('ai.joint_landing_advice.CpuBudget.pause'):
            plans=joint_landing_plans(view,allowed)
        good=_action(2,'eisbremse',index=6);bad=_action(2,'ruder',owner='pilot')
        self.assertGreater(plans[good],0.)
        self.assertEqual(plans[bad],0.)
        reference=joint_landing_reference(view,allowed,allowed)
        self.assertFalse(reference[bad])
        # An ordered real-engine completion exists with the reserved resources.
        for role,die,target,index in (('pilot',2,'eisbremse',6),('kopilot',0,'ruder',None),
                ('pilot',0,'ruder',None),('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),
                ('kopilot',2,'eisbremse',7),('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1)):
            _place(env.game,role,die,target,index)
        self.assertTrue(env.game.rundenende().gewonnen)

    def test_regular_brake_activation_uses_a_reserved_actual_die(self):
        env=brake_fixture();allowed=env.action_mask()
        plans=joint_landing_plans(env.view(),allowed)
        good=_action(2,'bremse',index=0);bad=_action(2,'ruder',owner='pilot')
        self.assertGreater(plans[good],0.)
        self.assertEqual(plans[bad],0.)
        for role,die,target,index in (('pilot',2,'bremse',0),('kopilot',0,'ruder',None),
                ('pilot',0,'ruder',None),('kopilot',1,'triebwerk',None),('pilot',1,'triebwerk',None),
                ('kopilot',2,'landeklappe',3),('pilot',3,'konzentration',0),('kopilot',3,'konzentration',1)):
            _place(env.game,role,die,target,index)
        self.assertTrue(env.game.rundenende().gewonnen)
        # Tailwind+3 requires three brakes, which cannot fit with two pilot
        # controls into this remaining four-die pilot hand.
        env=brake_fixture();env.game.cockpit.wind_position=0
        self.assertEqual(max(joint_landing_plans(env.view(),env.action_mask()).values()),0.)

    def test_radio_and_flap_share_controls_capacity_and_allocation_is_engine_checked(self):
        env=radio_fixture();view=env.view();allowed=env.action_mask()
        plans=joint_landing_plans(view,allowed)
        bad=_action(0,'konzentration',index=0);good=_action(0,'funk',owner='kopilot')
        self.assertGreater(plans[good],0.);self.assertEqual(plans[bad],0.)
        for role,die,target,index in (('kopilot',0,'funk',None),('pilot',1,'ruder',None),
                ('kopilot',1,'ruder',None),('pilot',2,'triebwerk',None),('kopilot',2,'triebwerk',None),
                ('pilot',3,'konzentration',0),('kopilot',3,'landeklappe',3)):
            _place(env.game,role,die,target,index)
        self.assertTrue(env.game.rundenende().gewonnen)

    def test_unreachable_planes_capacity_and_no_future_black_die_are_not_invented(self):
        env=ice_fixture();view=env.view()
        # Card possession alone cannot add a fifth regular die or a second
        # allocation of any shared lower ice cell.
        view['modules_state']['cards']=['synchronisation']
        allocations=task_allocations(view)
        self.assertTrue(allocations)
        self.assertTrue(all(sum(req==(5,) for req in p+c)==2 for p,c,_ in allocations))
        view['track'][0]['planes']=1
        self.assertEqual(task_allocations(view),())
        self.assertEqual(max(joint_landing_plans(view,env.action_mask()).values()),0.)

    def test_privacy_pacing_no_mutation_and_unsupported_fallback(self):
        env=ice_fixture();view=env.view();snapshot=deepcopy(view)
        mask=env.action_mask();rng=random.getstate()
        expected=joint_landing_reference(view,mask,mask)
        for die in env.game.kopilot_wuerfel:die.augenzahl=6
        self.assertEqual(env.view(),view)
        with patch('ai.joint_landing_advice.CpuBudget.pause') as pause:
            self.assertEqual(joint_landing_reference(env.view(),mask,mask,cpu_duty_cycle=.7),expected)
            self.assertTrue(pause.called)
        self.assertEqual(view,snapshot);self.assertEqual(random.getstate(),rng)
        for change in ('last_round','pending'):
            altered=deepcopy(view)
            if change=='last_round':altered['last_round']=False
            else:altered['modules_state']['pending']=dict(role='pilot',source='synchronisation',value=5)
            self.assertFalse(eligible(altered))
            self.assertEqual(joint_landing_reference(altered,mask,mask),mask)


if __name__=='__main__':unittest.main()
