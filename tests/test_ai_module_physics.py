"""Synthetic public module projections compared with authoritative engine rules."""
from copy import deepcopy
import json
from pathlib import Path
import random
import unittest

from backend.spielplan import Spielplan
from backend.wuerfel import Wuerfel
from ai.modules import ModuleEnv
from ai.module_physics import (active_modules, fuel_budget, ice_brake_bound,
    landing_speed_bound, movement_projection, predict_rudder, predict_thrust, wind_value)


MATRIX = json.loads((Path(__file__).resolve().parents[1] /
                    'ai/experiments/modules-50pct-2026-10-25/matrix.json').read_text())


def fixture(modules=()):
    case = next(case for case in MATRIX['cases'] if set(case['modules']) == set(modules))
    game = Spielplan(case['airport'], faehigkeitskarten=case['abilities'])
    game.phase = 'platzieren'
    game._vorbereitete_runde = 1
    game.landung.flugzeuge[:] = [0]*len(game.landung.flugzeuge)
    for role in ('pilot', 'kopilot'):
        for die in game._wuerfel_liste(role): die.augenzahl = 3
    env = ModuleEnv(); env.game = game
    return env


def place_pair(game, target, pilot, kopilot):
    game.am_zug = 'pilot'
    game.pilot_wuerfel[0].augenzahl = pilot
    game.kopilot_wuerfel[0].augenzahl = kopilot
    first = game.platziere('pilot', 0, target)
    second = game.platziere('kopilot', 0, target)
    if not first.erfolg or not second.erfolg:
        raise AssertionError((first, second))
    return second


class ModulePhysicsTests(unittest.TestCase):
    def test_wind_rudder_projection_matches_engine_including_stall_hook_order(self):
        base = fixture(['wind']).game
        for attitude in (-2, 0, 2):
            for position in (0, 5, 9, 14, 17):
                for pilot in range(1, 7):
                    for kopilot in range(1, 7):
                        env = ModuleEnv(); env.game = deepcopy(base)
                        env.game.cockpit.fluglage = attitude
                        env.game.cockpit.wind_position = position
                        expected = predict_rudder(env.view('pilot'), pilot, kopilot)
                        result = place_pair(env.game, 'ruder', pilot, kopilot)
                        self.assertEqual(expected['attitude'], env.game.cockpit.fluglage)
                        self.assertEqual(expected['wind_position'], env.game.cockpit.wind_position)
                        self.assertEqual(expected['wind_value'], env.game.cockpit.wind_wert())
                        self.assertEqual(expected['reason'], result.grund)
                        repeated = predict_rudder(env.view('pilot'))
                        self.assertEqual(repeated['wind_position'], expected['wind_position'])
                        self.assertEqual(repeated['attitude'], expected['attitude'])

    def test_leak_cost_matches_engine_and_is_not_paid_twice(self):
        base = fixture(['leak']).game
        for remaining in (1, 5, 20):
            for pilot in range(1, 7):
                for kopilot in range(1, 7):
                    env = ModuleEnv(); env.game = deepcopy(base)
                    env.game.cockpit.kerosin = remaining
                    expected = fuel_budget(env.view('pilot'), pilot, kopilot)
                    result = place_pair(env.game, 'triebwerk', pilot, kopilot)
                    self.assertEqual(expected['after_current'], env.game.cockpit.kerosin)
                    self.assertEqual(expected['reason'], result.grund)
                    repeated = fuel_budget(env.view('pilot'))
                    self.assertEqual(repeated['current_cost'], 0)
                    self.assertEqual(repeated['after_current'], env.game.cockpit.kerosin)

    def test_control_card_coffee_and_nonzero_existing_bank_match_engine(self):
        for coffee in (0, 2, 3):
            env = fixture(['wind'])
            env.game.zusatz.karten = ['control']
            env.game.cockpit.kaffeetassen = coffee
            env.game.cockpit.fluglage = 1
            env.game.cockpit.wind_position = 5
            expected = predict_rudder(env.view('pilot'), 4, 4)
            place_pair(env.game, 'ruder', 4, 4)
            self.assertEqual(expected['coffee'], env.game.cockpit.kaffeetassen)
            self.assertEqual(expected['wind_position'], 6)
            self.assertEqual(expected['wind_value'], env.game.cockpit.wind_wert())
            self.assertEqual(predict_rudder(env.view('pilot'))['coffee_gain'], 0)

    def test_wind_ice_dynamic_speed_and_every_landing_bound_match_engine(self):
        env = fixture(['wind', 'ice'])
        view = env.view('pilot')
        with self.assertRaisesRegex(ValueError, 'rudder outcome'):
            predict_thrust(view, 1, 1)
        for progress in range(5):
            env.game.cockpit.eis_fortschritt = progress
            view = env.view('pilot')
            bound = ice_brake_bound(view)
            self.assertTrue(bound['strict'])
            self.assertEqual(bound['strength'], env.game.cockpit.bremsstaerke())
            for position in range(18):
                env.game.cockpit.wind_position = position
                view = env.view('pilot')
                rudder = predict_rudder(view, 3, 3)
                for pilot, kopilot in ((1, 1), (1, 2), (2, 2), (3, 3), (6, 6)):
                    forecast = predict_thrust(view, pilot, kopilot, rudder=rudder)
                    # Synthetic public control fields isolate the engine's
                    # authoritative speed/braking evaluation from final tasks.
                    for field, owner, value in ((env.game.cockpit.schub_pilot, 'pilot', pilot),
                                                 (env.game.cockpit.schub_kopilot, 'kopilot', kopilot)):
                        die = Wuerfel(owner); die.augenzahl = value
                        field.wuerfel = die
                    env.game.cockpit.wind_position = rudder['wind_position']
                    self.assertEqual(forecast['speed'], env.game.cockpit.triebwerk_geschwindigkeit())
                    direct = env.game.cockpit.loese_triebwerke_auf(letzte_runde=True)
                    landing_view = {**view, 'last_round': True}
                    self.assertEqual(movement_projection(landing_view, forecast['speed'])['reason'], direct.grund)
                    env.game.cockpit.schub_pilot.wuerfel = None
                    env.game.cockpit.schub_kopilot.wuerfel = None
                    env.game.cockpit.wind_position = position

    def test_prospective_wind_changes_ice_landing_result_before_second_rudder(self):
        env = fixture(['wind', 'ice'])
        env.game.cockpit.wind_position = 5  # Current wind0; bank-1 moves to wind+1.
        env.game.cockpit.eis_fortschritt = 2
        env.game.letzte_runde = True
        env.game.landung.hoehe = 0
        env.game.landung.entfernung = 0
        before = env.view('pilot')
        rudder = predict_rudder(before, 4, 3)
        forecast = predict_thrust(before, 1, 2, rudder=rudder)
        self.assertEqual(forecast['speed'], 4)
        self.assertEqual(forecast['reason'], 'zu_schnell_gelandet')
        self.assertEqual(1+2+before['modules_state']['wind_value'], 3)
        self.assertEqual(movement_projection(before, 3)['reason'], '')
        place_pair(env.game, 'ruder', 4, 3)
        env.game.pilot_wuerfel[1].augenzahl = 1
        env.game.kopilot_wuerfel[1].augenzahl = 2
        self.assertTrue(env.game.platziere('pilot', 1, 'triebwerk').erfolg)
        self.assertTrue(env.game.platziere('kopilot', 1, 'triebwerk').erfolg)
        actual = env.game.cockpit.loese_triebwerke_auf(letzte_runde=True)
        self.assertEqual(forecast['reason'], actual.grund)
        self.assertEqual(forecast['speed'], env.game.cockpit.triebwerk_geschwindigkeit())

    def test_ice_pair_upgrades_match_actual_field_completion(self):
        env = fixture(['ice'])
        for progress in range(4):
            before = env.view('pilot')
            expected = ice_brake_bound(before, additional_pairs=1)
            for row, owner in enumerate(('pilot', 'kopilot')):
                die = Wuerfel(owner); die.augenzahl = 2+progress
                result = env.game.cockpit.platziere_eisbremse(die, progress*2+row)
                self.assertTrue(result.erfolg)
            self.assertEqual(env.game.cockpit.bremsstaerke(), expected['strength'])
            self.assertEqual(env.game.cockpit.eis_fortschritt, progress+1)

    def test_public_movement_failure_priority_and_motion_match_engine(self):
        base = fixture().game
        for distance in (1, 2, 3):
            for attitude in (-2, 0, 2):
                for planes in (0, 1):
                    for speed in (2, 7, 12):
                        game = deepcopy(base)
                        game.landung.entfernung = distance
                        game.cockpit.fluglage = attitude
                        index = game.landung._index_fuer_entfernung(distance)
                        game.landung.flugzeuge[index] = planes
                        game.landung._kurven_min[index] = 0
                        game.landung._kurven_max[index] = 1
                        env = ModuleEnv(); env.game = game
                        expected = movement_projection(env.view('pilot'), speed)
                        pilot = min(6, speed-1)
                        for field, owner, value in ((game.cockpit.schub_pilot, 'pilot', pilot),
                                                    (game.cockpit.schub_kopilot, 'kopilot', speed-pilot)):
                            die = Wuerfel(owner); die.augenzahl = value; field.wuerfel = die
                        answer = game.cockpit.loese_triebwerke_auf()
                        self.assertEqual(expected['reason'], answer.grund)
                        self.assertEqual(expected['movement'], distance-game.landung.entfernung)

    def test_kerosene_payment_holding_and_necessary_future_budget(self):
        env = fixture(['kerosene'])
        env.game.cockpit.kerosin = 10
        view = env.view('pilot')
        empty = fuel_budget(view)
        planned = fuel_budget(view, kerosene_payment=1)
        self.assertEqual(empty['after_current'], 4)
        self.assertFalse(empty['necessary_survival'])
        self.assertEqual(planned['after_current'], 9)
        self.assertTrue(planned['necessary_survival'])
        env.game.pilot_wuerfel[0].augenzahl = 1
        self.assertTrue(env.game.platziere('pilot', 0, 'kerosin').erfolg)
        paid = fuel_budget(env.view('pilot'))
        self.assertEqual(paid['after_current'], planned['after_current'])
        self.assertEqual(paid['current_cost'], 0)
        with self.assertRaises(ValueError): fuel_budget(env.view('pilot'), kerosene_payment=1)
        holding = {**view, 'holding': True, 'distance': 0}
        self.assertEqual(movement_projection(holding, 12)['movement'], 0)
        self.assertEqual(movement_projection(holding, 12)['reason'], '')
        landing = {**view, 'last_round': True, 'height': 0}
        self.assertEqual(fuel_budget(landing, kerosene_payment=1)['future_rounds'], 0)

    def test_public_pair_cannot_be_replaced_and_partner_faces_do_not_affect_projection(self):
        env = fixture(['wind'])
        before = env.view('pilot')
        rng = random.getstate()
        first = predict_thrust(before, 2, 3, rudder=predict_rudder(before, 4, 3))
        for die in env.game.kopilot_wuerfel: die.augenzahl = 6
        self.assertEqual(before, env.view('pilot'))
        self.assertEqual(first, predict_thrust(env.view('pilot'), 2, 3,
            rudder=predict_rudder(env.view('pilot'), 4, 3)))
        self.assertEqual(rng, random.getstate())
        place_pair(env.game, 'ruder', 4, 3)
        with self.assertRaises(ValueError): predict_rudder(env.view('pilot'), 5, 3)
        with self.assertRaises(ValueError): wind_value(18)
        with self.assertRaises(ValueError): ice_brake_bound(env.view('pilot'))
        self.assertEqual(active_modules(fixture().view('pilot')), frozenset())
        self.assertFalse(landing_speed_bound(fixture().view('pilot'))['strict'])


if __name__ == '__main__':
    unittest.main()
