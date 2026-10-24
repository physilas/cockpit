from copy import deepcopy
from itertools import product
from pathlib import Path
import unittest

from ai.environment import CrewEnv
from ai.partners import FrozenPartner, partner_specs
from ai.tactics import joint_control_probability, expected_best_face


class PartnerPlanningTests(unittest.TestCase):
    def test_partner_fraction_and_roles_remain_balanced_for_arbitrary_fractions(self):
        from collections import Counter
        from ai.parallel import partner_assignment
        for fraction in (.25,.5,.75,1):
            counts=Counter(partner_assignment(i,fraction,3) for i in range(240))
            self.assertEqual(counts[None,None],int(240*(1-fraction)))
            paired=[n for (partner,role),n in counts.items() if partner is not None]
            self.assertEqual(len(paired),6)
            self.assertEqual(min(paired),max(paired))

    def test_joint_control_prior_matches_exhaustive_distinct_dice(self):
        for a,b in [({2},{2}),({1,2},{2,3}),({1,2,3},{4,5,6}),(set(),{1})]:
            for count in (1,2,3,4):
                wins=sum(any(i!=j and hand[i] in a and hand[j] in b
                    for i in range(count) for j in range(count)) for hand in product(range(1,7),repeat=count))
                self.assertAlmostEqual(joint_control_probability(a,b,count),wins/6**count)

    def test_expected_best_includes_bad_outcomes(self):
        scores=[-100,-20,0,0,5,10]
        for count in (1,2,3):
            actual=sum(max(hand) for hand in product(scores,repeat=count))/6**count
            self.assertAlmostEqual(expected_best_face(scores,count),actual)

    def test_joint_prior_spends_shared_coffee_only_once(self):
        for a,b in [({2},{2}),({1,2},{4,5})]:
            for coffee in (1,2,3):
                for count in (2,3):
                    wins=sum(any(i!=j and min(abs(x-t) for t in a)+min(abs(y-t) for t in b)<=coffee
                        for i,x in enumerate(hand) for j,y in enumerate(hand))
                        for hand in product(range(1,7),repeat=count))
                    self.assertAlmostEqual(joint_control_probability(a,b,count,coffee),wins/6**count)

    def test_new_profile_does_not_read_partner_hand(self):
        env=CrewEnv('LOG_HND_GREEN',assistance_version=4)
        env.reset(seed=5100001)
        old=deepcopy((env.view(),env.action_mask()))
        for die in env.game._wuerfel_liste(env.other_role(env.current_role)):
            die.augenzahl=7-die.augenzahl
        self.assertEqual(old,(env.view(),env.action_mask()))

    def test_unseen_partner_risk_alone_does_not_spend_reroll(self):
        from ai.actions import ACTION_IDS,Action
        env=CrewEnv('MUC',assistance_version=4);env.reset(seed=7)
        g,c=env.game,env.game.cockpit
        g.am_zug='pilot';g.letzte_runde=True;g.landung.hoehe=0
        c.fahrwerk_ausgefahren[:]=[True]*3;c.landeklappen_ausgefahren[:]=[True]*4
        c.bremsen_aktiviert[:]=[True,False,False]
        for d,v in zip(g.pilot_wuerfel,(3,1,5,6)):
            d.augenzahl=v
        g.kopilot_wuerfel[0].augenzahl=3;c.ruder_kopilot.platziere(g.kopilot_wuerfel[0])
        for d in g.kopilot_wuerfel[1:3]:
            d.platziert=True
        self.assertFalse(env.action_mask()[ACTION_IDS[Action('reroll_start')]])

    def test_frozen_partner_applies_its_own_profile_and_does_not_mutate_view(self):
        env=CrewEnv('MUC');env.reset(seed=5100002)
        path=Path(__file__).resolve().parents[1]/'ai/releases/crew-basegame-v1/best.pt'
        partner=FrozenPartner(path)
        view=deepcopy(env.view())
        action=partner.select(view,env.action_mask())
        self.assertTrue(env.action_mask()[action])
        self.assertEqual(view,env.view())
        self.assertEqual(len(partner_specs([path])),3)
