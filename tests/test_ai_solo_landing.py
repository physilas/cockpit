"""Independent public reconstruction and engine-proven terminal exercises."""
from copy import deepcopy
import random
import unittest
from unittest.mock import patch

from ai.actions import Action, ROLES
from ai.modules import ModuleEnv, MODULE_ACTIONS
from ai.solo_landing import eligible, prove_landing, reconstruct
from backend.wuerfel import Wuerfel
from backend.spielplan import Spielplan
from tests.test_ai_wind_ice_counterexamples import _base_fixture, _place, _action, ice_final_pair_fixture


def terminal_fixture(airport='LOG_GIG_YELLOW', card='adaptation', *, role='kopilot'):
    env = _base_fixture(airport, (1,1,2,2), (1,1,2,2))
    env.assistance_version = 0
    game, c = env.game, env.game.cockpit
    game.zusatz.karten = [card]
    game.landung.hoehe = game.landung.entfernung = 0
    game.letzte_runde = True
    game.aktuelle_runde = game._vorbereitete_runde = 7
    game._genutzte_neuwurf_hoehen = set(game.landung.get_neuwurf_hoehen())
    c.fahrwerk_ausgefahren[:] = [True]*3
    c.landeklappen_ausgefahren[:] = [True]*4
    c.bremsen_aktiviert[:] = [True]*3
    c.eis_fortschritt = 4 if 'ice' in c.module else 0
    c.aerodynamik_blau += 3; c.aerodynamik_orange += 4
    first = 'pilot' if role == 'kopilot' else 'kopilot'
    game.am_zug = game.startspieler = first
    for target, die in (('ruder',0), ('triebwerk',1), ('konzentration',2)):
        for r in (first,role):
            _place(game,r,die,target,0 if target=='konzentration' and r==first else 1 if target=='konzentration' else None)
    _place(game,first,3,'konzentration',2)
    # Constructor's adaptation flags and visited-height state match real play.
    return env


def black_fixture():
    env = terminal_fixture('LOG_KEF_YELLOW','synchronisation',role='pilot')
    game, c = env.game, env.game.cockpit
    # Publicly issued and rolled black5 plus the remaining pilot5 must finish
    # the two ice fields. The bonus can fill either colour but is counted once.
    c.eis_fortschritt = 3
    game.pilot_wuerfel[3].augenzahl = 5
    token = Wuerfel('pilot'); token.quelle = 'synchronisation'; token.augenzahl = 5
    game.zusatz.ausgeloest.add('synchronisation')
    game.zusatz.offen = [dict(rolle='pilot',wuerfel=token)]
    return env


def public(env):
    view = env.view(); view.pop('steps_remaining')
    return view


class SoloLandingTests(unittest.TestCase):
    def test_reconstruction_all_native_first_actions_both_roles_modules_cards(self):
        checked = 0
        for airport in ('LOG_GIG_YELLOW','LOG_KEF_YELLOW','LOG_ATL_YELLOW'):
            for role in ROLES:
                for card in ('adaptation','anticipation','control','mastery','synchronisation','working-together'):
                    source = terminal_fixture(airport,card,role=role)
                    rebuilt = reconstruct(source.view(),airport)
                    self.assertEqual(public(rebuilt),public(source))
                    mask = source.action_mask()
                    self.assertEqual(rebuilt.action_mask(),mask)
                    for i, legal in enumerate(mask):
                        if not legal or MODULE_ACTIONS[i].kind not in ('place','coffee','adaptation'):continue
                        real, simulation = deepcopy(source),deepcopy(rebuilt)
                        real.step(i);simulation.step(i)
                        self.assertEqual(public(simulation),public(real),(airport,role,card,i))
                        self.assertEqual(simulation.game.status,real.game.status)
                        self.assertEqual(simulation.game.verlust_grund,real.game.verlust_grund)
                        self.assertEqual(simulation.action_mask(),real.action_mask())
                        checked+=1
        self.assertGreater(checked,250)

    def test_ice_final_pair_has_actual_winning_sequence_and_no_mutation(self):
        env = ice_final_pair_fixture(); env.assistance_version=0
        before, rng = deepcopy(env.view()),random.getstate()
        proof = prove_landing(before,'LOG_KEF_YELLOW',allowed=env.action_mask())
        self.assertTrue(proof.eligible)
        self.assertEqual(proof.actions,(_action(3,'eisbremse',index=7),))
        self.assertEqual(before,env.view())
        self.assertEqual(random.getstate(),rng)
        for action in proof.actions:env.step(action)
        self.assertEqual(env.game.status,'gewonnen')

    def test_joint_rudder_and_radio_needs_two_resources_not_one(self):
        env = terminal_fixture()
        game = env.game
        # The last own die must fill the missing rudder AND remove a plane.
        # An extra copy of that same die cannot be silently assigned to radio.
        game.cockpit.ruder_kopilot.wuerfel = None
        game.landung.flugzeuge[-1] = 1
        game.kopilot_wuerfel[3].augenzahl = 1
        proof = prove_landing(env.view(),'LOG_GIG_YELLOW')
        self.assertFalse(proof.actions)
        self.assertFalse(proof.exhausted)
        self.assertFalse(proof.unknown_roll)
        self.assertEqual(game.status,'laeuft')

    def test_radio_gear_flap_fuel_and_speed_are_checked_by_actual_engine(self):
        for problem in ('radio','gear','flap','speed'):
            env = terminal_fixture('LOG_GIG_YELLOW',
                                   role='pilot' if problem=='gear' else 'kopilot')
            c, game = env.game.cockpit,env.game
            if problem=='radio':game.landung.flugzeuge[-1]=1;game.kopilot_wuerfel[3].augenzahl=1
            if problem=='gear':c.fahrwerk_ausgefahren[0]=False;game.pilot_wuerfel[3].augenzahl=1
            if problem=='flap':c.landeklappen_ausgefahren[3]=False;game.kopilot_wuerfel[3].augenzahl=6
            if problem=='speed':c.wind_position=0;c.bremsen_aktiviert[:]=[True,False,False]
            proof=prove_landing(env.view(),env.airport)
            if problem=='speed':
                self.assertFalse(proof.actions)
            else:
                self.assertTrue(proof.actions,problem)
                for action in proof.actions:env.step(action)
                self.assertEqual(game.status,'gewonnen',problem)

    def test_adaptation_coffee_helpers_and_budget_failure_abstain(self):
        env=ice_final_pair_fixture();env.assistance_version=0
        env.game.kopilot_wuerfel[3].augenzahl=2
        env.game.cockpit.kaffeetassen=0
        proof=prove_landing(env.view(),'LOG_KEF_YELLOW')
        self.assertEqual([MODULE_ACTIONS[i].kind for i in proof.actions],['adaptation','place'])
        # First-action masks and remaining action budget are real constraints.
        forbidden=list(env.action_mask())
        forbidden[proof.actions[0]]=False
        self.assertFalse(prove_landing(env.view(),'LOG_KEF_YELLOW',allowed=forbidden).actions)
        self.assertFalse(prove_landing(env.view(),'LOG_KEF_YELLOW',max_actions=1).actions)
        short=prove_landing(env.view(),'LOG_KEF_YELLOW',max_nodes=1)
        self.assertTrue(short.exhausted);self.assertFalse(short.actions)
        # Actual coffee instead of adaptation.
        env.game.zusatz.anpassung['kopilot']=True
        env.game.kopilot_wuerfel[3].augenzahl=4;env.game.cockpit.kaffeetassen=1
        proof=prove_landing(env.view(),'LOG_KEF_YELLOW')
        self.assertEqual([MODULE_ACTIONS[i].kind for i in proof.actions],['coffee','place'])
        for action in proof.actions:env.step(action)
        self.assertEqual(env.game.status,'gewonnen')

    def test_current_control_gain_and_already_paid_leak_preserve_transition(self):
        for airport,card in (('LOG_GIG_YELLOW','control'),('LOG_ATL_YELLOW','mastery')):
            env=terminal_fixture(airport,card)
            game,c=env.game,env.game.cockpit
            if card=='control':
                c.ruder_kopilot.wuerfel=None
                game.zusatz.ausgeloest.remove('ruder')
                c.kaffeetassen=0;game.kopilot_wuerfel[3].augenzahl=1
                action=_action(3,'ruder',owner='kopilot')
            else:
                # Both thrusts already paid their immediate leak cost.
                c.kerosin=1;action=_action(3,'konzentration',index=2)
                # Need an actually free concentration field.
                c.konzentration[2].wuerfel=None
            simulated=reconstruct(env.view(),airport)
            env.step(action);simulated.step(action)
            self.assertEqual(public(env),public(simulated))
            self.assertEqual(game.status,simulated.game.status)
            if card=='control':self.assertEqual(c.kaffeetassen,1)
            else:self.assertEqual(c.kerosin,1)

    def test_kerosene_final_payment_occupancy_and_actual_winning_fuel_allocation(self):
        env=terminal_fixture('LOG_ATL_YELLOW')
        # Reuse only the scripted PUBLIC board for an official kerosene route;
        # constructor/track metadata come from that route, not the leak route.
        fuel=ModuleEnv('LOG_OSL_GREEN',abilities=[],assistance_version=0)
        fuel.game=Spielplan('LOG_OSL_GREEN')
        fuel.game.phase='platzieren';fuel.game.letzte_runde=True
        fuel.game.landung.hoehe=fuel.game.landung.entfernung=0
        fuel.game._vorbereitete_runde=fuel.game.aktuelle_runde=7
        fuel.game.cockpit=deepcopy(env.game.cockpit)
        fuel.game.cockpit.module={'kerosene'}
        fuel.game.cockpit.landung=fuel.game.landung
        fuel.game.cockpit.kerosin=6
        fuel.game.zusatz.c=fuel.game.cockpit
        fuel.game.pilot_wuerfel=deepcopy(env.game.pilot_wuerfel)
        fuel.game.kopilot_wuerfel=deepcopy(env.game.kopilot_wuerfel)
        fuel.game.am_zug='kopilot';fuel.game.landung.flugzeuge[:]=[0]*len(fuel.game.landung.flugzeuge)
        proof=prove_landing(fuel.view(),'LOG_OSL_GREEN')
        self.assertTrue(proof.actions)
        for action in proof.actions:fuel.step(action)
        self.assertEqual(fuel.game.status,'gewonnen')
        self.assertEqual(fuel.game.cockpit.kerosin,4)

    def test_issued_black_die_is_shared_once_and_no_future_roll_is_used(self):
        env=black_fixture()
        rebuilt=reconstruct(env.view(),'LOG_KEF_YELLOW')
        self.assertEqual(public(rebuilt),public(env))
        proof=prove_landing(env.view(),'LOG_KEF_YELLOW')
        self.assertTrue(proof.actions)
        self.assertEqual([MODULE_ACTIONS[i].kind for i in proof.actions],['bonus_place','place'])
        for action in proof.actions:env.step(action)
        self.assertEqual(env.game.status,'gewonnen')
        # With no issued bonus, a card alone cannot provide the second die.
        env=black_fixture();env.game.zusatz.offen=[]
        self.assertFalse(prove_landing(env.view(),'LOG_KEF_YELLOW').actions)
        env=black_fixture();env.game.zusatz.offen[0]['wuerfel'].augenzahl=None
        self.assertFalse(eligible(env.view()))
        self.assertFalse(prove_landing(env.view(),'LOG_KEF_YELLOW').actions)

    def test_unsupported_hidden_future_realtime_intern_and_route_mismatch(self):
        env=terminal_fixture();view=env.view()
        for key,value in (('partner_remaining',1),('height',1000),('last_round',False)):
            changed=deepcopy(view);changed[key]=value
            self.assertFalse(eligible(changed))
        for module in ('intern','realtime'):
            changed=deepcopy(view);changed['modules_state']['modules'].append(module)
            self.assertFalse(eligible(changed))
        with self.assertRaises(ValueError):reconstruct(view,'LOG_KEF_YELLOW')

    def test_new_unrolled_synchronization_branch_abstains_without_randomness(self):
        env=terminal_fixture('LOG_GIG_YELLOW','synchronisation',role='pilot')
        c=env.game.cockpit
        # A visible current-round flap lets a gear placement trigger the bonus.
        # There is not a bonus yet and its face is not available to this solver.
        token=Wuerfel('kopilot');token.augenzahl=6;token.platziert=True
        c.landeklappen[3].wuerfel=token
        c.fahrwerk_ausgefahren[0]=False
        env.game.pilot_wuerfel[3].augenzahl=1
        with patch('backend.zusatzregeln.wirf_verkehrswuerfel',side_effect=AssertionError('Never roll future bonus')):
            proof=prove_landing(env.view(),'LOG_GIG_YELLOW')
        self.assertTrue(proof.unknown_roll)
        self.assertFalse(proof.actions)

    def test_privacy_spent_tokens_rng_and_cpu_pacing_preserve_proof(self):
        env=terminal_fixture();view=env.view();snapshot=deepcopy(view)
        state=random.getstate();policy_rng=env.rng.getstate()
        expected=prove_landing(view,env.airport)
        # Old private faces and private gameRNG cannot enter reconstruction.
        # Spent tokens in this engine alias public fields. Replace the private
        # list entries; poisoning the same objects would change PUBLIC faces.
        for i in range(4):
            die=Wuerfel('pilot');die.augenzahl=6;die.platziert=True
            env.game.pilot_wuerfel[i]=die
        env.rng.seed(123456)
        self.assertEqual(env.view(),view)
        with patch('ai.solo_landing.CpuBudget.pause') as pause, patch.object(Wuerfel,'werfen',side_effect=AssertionError('No hypothetical roll')):
            actual=prove_landing(env.view(),env.airport,cpu_duty_cycle=.7)
            self.assertTrue(pause.called)
        self.assertEqual(expected,actual)
        self.assertEqual(view,snapshot)
        self.assertEqual(random.getstate(),state)
        self.assertNotEqual(env.rng.getstate(),policy_rng)


if __name__=='__main__':unittest.main()
