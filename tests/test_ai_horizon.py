from copy import deepcopy
from itertools import combinations_with_replacement
from math import factorial,prod
import unittest

from ai.actions import SLOTS
from ai.environment import CrewEnv
from ai.horizon import control_prior,make_forecast
from ai.tactics import assisted_mask


class HorizonTests(unittest.TestCase):
    def view(self):
        env=CrewEnv();env.reset(seed=5100200)
        v=env.view()
        v.update(height=2000,distance=2,last_round=False,holding=False,
            gear=[True]*3,flaps=[True]*4,brakes=6,brake_progress=[True]*3,
            aero_blue=7.5,aero_orange=12.5,coffee=0)
        for c in v['track']:
            c.update(planes=0,traffic=0,min=-2,max=2)
        return v

    def test_control_prior_uses_distinct_dice_for_rudder_and_minimum_thrust(self):
        hands=[]
        for hand in combinations_with_replacement(range(1,7),4):
            if 1 not in hand:
                continue
            remaining=list(hand);remaining.remove(1)
            weight=factorial(4)//prod(factorial(hand.count(n)) for n in set(hand))
            hands.append((set(remaining),weight))
        expected=sum(a_weight*b_weight for a,a_weight in hands for b,b_weight in hands if a&b)/6**8
        self.assertAlmostEqual(control_prior(0,2,2,0),expected)
        self.assertLess(expected,(1-(5/6)**4)**2)

    def test_more_shared_coffee_can_only_help_and_impossible_speed_is_zero(self):
        probabilities=[control_prior(-2,9,10,c) for c in range(4)]
        self.assertEqual(probabilities,sorted(probabilities))
        self.assertTrue(all(0<=p<=1 for p in probabilities))
        self.assertEqual(control_prior(0,13,14,3),0)
        self.assertEqual(control_prior(6,2,12,3),0)

    def test_forecast_requires_enough_future_movement_before_landing(self):
        view=self.view();before=deepcopy(view)
        forecast=make_forecast(view);traffic=tuple(c['planes'] for c in view['track'])
        self.assertEqual(forecast(0,0,7,15,7,0,traffic),0)
        self.assertGreater(forecast(1,0,7,15,7,0,traffic),0)
        self.assertEqual(view,before)

    def test_forecast_prepares_the_bank_for_a_required_next_round_curve(self):
        view=self.view();view['distance']=1
        for c in view['track']:
            if c['distance']==1:
                c.update(min=-2,max=-1)
        forecast=make_forecast(view);traffic=tuple(c['planes'] for c in view['track'])
        self.assertGreater(forecast(0,-1,7,15,7,0,traffic),forecast(0,2,7,15,7,0,traffic))

    def test_early_round_choices_and_hidden_partner_boundary_are_preserved(self):
        env=CrewEnv('LOG_HND_GREEN');env.reset(seed=5100201)
        view,mask=env.view(),env.action_mask()
        self.assertEqual(assisted_mask(view,mask,version=10),assisted_mask(view,mask,version=3))
        env.game.landung.hoehe=2000
        view=env.view();before=deepcopy((view,assisted_mask(view,mask,version=10)))
        for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl=7-die.augenzahl
        self.assertEqual(before,(env.view(),assisted_mask(env.view(),mask,version=10)))

    def test_module_and_bonus_die_abilities_remain_explicitly_unsupported(self):
        env=CrewEnv(assistance_version=10);env.reset(seed=5100201)
        env.game.zusatz.karten=['synchronisation']
        with self.assertRaises(ValueError):
            env.action_mask()
