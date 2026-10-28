import unittest

from ai.coherent_safety import coherent_safe_actions, closing_rescue_possible
from ai.modules import ModuleEnv, MODULE_ACTIONS


def closing_game(thrust,last,coffee,rerolls):
    env=ModuleEnv('MUC')
    env.reset(seed=14000300)
    g=env.game;c=g.cockpit
    g.landung.hoehe=0;g.landung.entfernung=0;g.landung.flugzeuge=[0]*len(g.landung.flugzeuge)
    g.letzte_runde=True;g.warteschleife=False;g.am_zug='pilot';g.neuwurf_plaettchen=rerolls
    c.fahrwerk_ausgefahren=[True]*3;c.landeklappen_ausgefahren=[True]*4
    c.aerodynamik_blau=7.5;c.aerodynamik_orange=12.5;c.kaffeetassen=coffee
    for role in ('pilot','kopilot'):
        dice=g._wuerfel_liste(role)
        for die in dice:
            die.platziert=True
        dice[0].augenzahl=1;dice[1].augenzahl=thrust
        (c.ruder_pilot if role=='pilot' else c.ruder_kopilot).wuerfel=dice[0]
        (c.schub_pilot if role=='pilot' else c.schub_kopilot).wuerfel=dice[1]
    g.pilot_wuerfel[3].platziert=False;g.pilot_wuerfel[3].augenzahl=last
    return env


class CoherentSafetyTests(unittest.TestCase):
    def test_futile_coffee_and_rerolls_are_not_forced_before_a_proven_closing_loss(self):
        env=closing_game(6,6,3,3)
        raw=env.action_mask()
        self.assertFalse(closing_rescue_possible('MUC',env.view(),raw))
        allowed,meta=coherent_safe_actions('MUC',env.view(),raw)
        self.assertTrue(meta['unavoidable_closing_loss'])
        self.assertTrue(any(allowed))
        self.assertTrue(all(not ok or action.kind=='place' for ok,action in zip(allowed,MODULE_ACTIONS)))
        self.assertEqual(3,env.game.cockpit.kaffeetassen)
        self.assertEqual('laeuft',env.game.status)

    def test_possible_reroll_rescue_is_preserved(self):
        env=closing_game(1,6,0,1)
        raw=env.action_mask()
        self.assertTrue(closing_rescue_possible('MUC',env.view(),raw))
        _,meta=coherent_safe_actions('MUC',env.view(),raw)
        self.assertFalse(meta['unavoidable_closing_loss'])

    def test_shared_coffee_budget_distinguishes_reachable_from_unreachable_brake(self):
        for last,coffee,possible in ((3,1,True),(6,3,False)):
            env=closing_game(1,last,coffee,0)
            self.assertEqual(possible,closing_rescue_possible('MUC',env.view(),env.action_mask()))
