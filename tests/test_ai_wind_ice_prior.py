"""The new prior remains public and leaves the earlier research phase intact."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from backend.regeln import AERODYNAMIK_BLAU_START, AERODYNAMIK_ORANGE_START
from backend.spielplan import Spielplan
from ai.actions import Action
from ai.modules import MODULE_ACTIONS, ModuleEnv
from ai.public_hand_prior import fair_control_value
from ai.wind_ice_advice import _after_placement, wind_ice_plans
from ai.wind_ice_compare import comparison_fingerprint
from ai.wind_ice_environment import WindIceEnv
from ai.wind_ice_prior_advice import pair_scores, prior_plans, radio_capacity
from ai.wind_ice_prior_environment import PriorWindIceEnv
from tests.test_ai_wind_ice_counterexamples import ice_final_pair_fixture, wind_public_thrust_fixture, _action, _place


def paired(source):
    source.assistance_version = 12
    env = PriorWindIceEnv(source.airport, abilities=list(source.abilities))
    env.__dict__.update(deepcopy(source.__dict__))
    env._source_reference_mask = env._research_cache = env._prior_cache = None
    return source, env


class WindIcePriorTests(unittest.TestCase):
    def test_earlier_research_code_fingerprint_stays_exact(self):
        report = json.loads(Path('ai/experiments/wind-ice-2026-10-25/microplans-development-v1.json').read_text())
        self.assertEqual(comparison_fingerprint(), report['comparison_sha256'])

    def test_fully_public_controls_retain_exact_old_technical_rankings(self):
        for fixture in (ice_final_pair_fixture, wind_public_thrust_fixture):
            env = fixture(); view, allowed = env.view(), env.action_mask()
            self.assertEqual(prior_plans(view, allowed), wind_ice_plans(view, allowed))

    def test_new_reference_still_closes_the_actual_winning_ice_pair(self):
        source, env = paired(ice_final_pair_fixture())
        study, native = env.info(), source.info()
        good = _action(3, 'eisbremse', index=7)
        self.assertEqual([i for i, yes in enumerate(study['reference_action_mask']) if yes], [good])
        self.assertEqual(study['action_mask'], native['action_mask'])
        self.assertEqual(study['source_reference_action_mask'], native['reference_action_mask'])
        self.assertEqual(study['microplans_reference_action_mask'][good], True)
        _place(env.game, 'kopilot', 3, 'eisbremse', 7)
        self.assertTrue(env.game.rundenende().gewonnen)

    def test_fair_rudder_risk_prefers_a_central_face_without_reading_partner(self):
        view = ice_final_pair_fixture().view()
        view['board'][0] = view['board'][1] = None
        view['board'][2] = {'value': 1, 'owner': 'pilot'}
        view['board'][3] = None
        view['partner_remaining'] = 2
        center = pair_scores(view, view, own_r=3, own_t=2)
        extreme = pair_scores(view, view, own_r=6, own_t=2)
        self.assertGreater(fair_control_value(center, 2, 0, thrust=1),
                           fair_control_value(extreme, 2, 0, thrust=1))

    def test_certain_current_control_card_gain_can_fund_the_remaining_thrust(self):
        env = ModuleEnv('LOG_GIG_YELLOW', abilities=['control'], assistance_version=12)
        env.game = Spielplan('LOG_GIG_YELLOW', faehigkeitskarten=['control'])
        game, cockpit = env.game, env.game.cockpit
        game.phase = 'platzieren'
        game._vorbereitete_runde = game.aktuelle_runde
        game.landung.hoehe, game.landung.entfernung = 1000, 1
        game.landung.flugzeuge[:] = [0] * len(game.landung.flugzeuge)
        cockpit.wind_position = 8  # Public headwind-3.
        cockpit.fahrwerk_ausgefahren[:] = [True] * 3
        cockpit.landeklappen_ausgefahren[:] = [True] * 4
        cockpit.bremsen_aktiviert[:] = [True] * 3
        cockpit.aerodynamik_blau = AERODYNAMIK_BLAU_START + 3
        cockpit.aerodynamik_orange = AERODYNAMIK_ORANGE_START + 4
        for dice, faces in ((game.pilot_wuerfel, (3, 4, 1, 1)), (game.kopilot_wuerfel, (3, 6, 1, 1))):
            for die, face in zip(dice, faces): die.augenzahl = face
        _place(game, 'pilot', 2, 'funk')
        _place(game, 'kopilot', 0, 'ruder')
        _place(game, 'pilot', 3, 'konzentration', 0)
        _place(game, 'kopilot', 1, 'triebwerk')
        cockpit.kaffeetassen = 0  # Explicit public technical starting budget.
        view, allowed = env.view(), env.action_mask()
        ranked = prior_plans(view, allowed)
        good = _action(0, 'ruder', owner='pilot')
        early_thrust = _action(1, 'triebwerk', owner='pilot')
        self.assertGreater(ranked[good], ranked[early_thrust] + 1000)
        self.assertEqual(view['coffee'], 0)
        _place(game, 'pilot', 0, 'ruder')
        self.assertEqual(cockpit.kaffeetassen, 1)
        _place(game, 'kopilot', 2, 'funk')
        self.assertTrue(game.trinke_kaffee('pilot', 1, 1).erfolg)
        _place(game, 'pilot', 1, 'triebwerk')
        self.assertEqual(cockpit.triebwerk_geschwindigkeit(), 8)
        result = cockpit.loese_triebwerke_auf()
        self.assertTrue(result.erfolg)
        self.assertFalse(result.verloren)
        self.assertEqual(game.landung.entfernung, 0)

    def test_radio_bound_reserves_controls_and_never_credits_future_bonus(self):
        view = wind_public_thrust_fixture().view()
        capacity = radio_capacity(view, view)
        self.assertEqual(capacity, 3)
        changed = deepcopy(view)
        changed['partner_remaining'] = 0
        self.assertEqual(radio_capacity(changed, changed), 1)
        changed['modules_state']['cards'] = ['synchronisation']
        self.assertEqual(radio_capacity(changed, changed), 1)

    def test_public_partner_poisoning_and_pacing_never_change_advice(self):
        source, env = paired(wind_public_thrust_fixture())
        # Remove one PUBLIC partner control in both scripted fixtures to
        # activate the declared hypothetical fair-hand prior.
        for fixture in (source, env):
            fixture.game.cockpit.schub_kopilot.leere()
        view, info, rng = env.view(), env.info(), random.getstate()
        env.game.kopilot_wuerfel[1].augenzahl = 6
        env.game.kopilot_wuerfel[2].augenzahl = 5
        self.assertEqual(env.view(), view)
        self.assertEqual(env.info()['reference_action_mask'], info['reference_action_mask'])
        snapshot = deepcopy(view)
        with patch('ai.wind_ice_prior_advice.CpuBudget.pause') as pause:
            ranked = prior_plans(view, info['action_mask'], cpu_duty_cycle=.7)
            self.assertTrue(pause.called)
        self.assertEqual(ranked, prior_plans(view, info['action_mask']))
        self.assertEqual(view, snapshot)
        self.assertEqual(random.getstate(), rng)

    def test_unassisted_role_and_other_modules_are_exact_fallbacks(self):
        source, env = paired(ice_final_pair_fixture())
        env.assisted_roles = source.assisted_roles = ('pilot',)
        self.assertEqual(env.current_role, 'kopilot')
        self.assertEqual(env.info()['reference_action_mask'], source.info()['action_mask'])
        for airport, cards in (('MUC', []), ('LOG_ATL_YELLOW', ['adaptation']), ('LOG_ATL_GREEN', [])):
            ordinary = ModuleEnv(airport, abilities=cards, assistance_version=12)
            candidate = PriorWindIceEnv(airport, abilities=cards)
            seed = 'train:wind-ice-prior-fallback:' + airport
            ordinary.reset(seed=seed); candidate.reset(seed=seed)
            self.assertEqual(ordinary.view(), candidate.view())
            self.assertEqual(ordinary.observation(), candidate.observation())
            self.assertEqual(ordinary.info()['reference_action_mask'], candidate.info()['reference_action_mask'])
            self.assertEqual(ordinary.rng.getstate(), candidate.rng.getstate())
            self.assertIsNone(candidate.clock)


if __name__ == '__main__':
    unittest.main()
