"""Synthetic PUBLIC counterexamples for the unchanged profiles10--12.

These are technical decision fixtures, not sampled games or win-rate evidence.
All faces below are explicitly scripted fixture values. No random engine hand
or future roll is read to choose an action. The fixtures document the existing
soft-reference gap so a future, separately versioned planner can be compared.
"""
from copy import deepcopy
import random
import unittest

from backend.regeln import AERODYNAMIK_BLAU_START, AERODYNAMIK_ORANGE_START
from backend.spielplan import Spielplan
from ai.module_physics import predict_thrust
from ai.modules import ModuleEnv, MODULE_ACTIONS, MODULE_SLOTS


def _place(game, role, die, target, index=None):
    result = game.platziere(role, die, target, index=index)
    if not result.erfolg or result.verloren:
        raise AssertionError((role, die, target, index, result))


def _action(die, target, owner=None, index=None):
    return next(number for number, action in enumerate(MODULE_ACTIONS)
                if action.kind == 'place' and action.die == die
                and MODULE_SLOTS[action.slot].target == target
                and (owner is None or MODULE_SLOTS[action.slot].owner == owner)
                and (index is None or MODULE_SLOTS[action.slot].index == index))


def _base_fixture(airport, pilot, kopilot):
    # Constructor does not roll; both route/card combinations are official.
    env = ModuleEnv(airport, abilities=['adaptation'], assistance_version=10)
    env.game = Spielplan(airport, faehigkeitskarten=['adaptation'])
    game = env.game
    game.phase = 'platzieren'
    game._vorbereitete_runde = game.aktuelle_runde
    game.landung.flugzeuge[:] = [0] * len(game.landung.flugzeuge)
    for dice, faces in ((game.pilot_wuerfel, pilot), (game.kopilot_wuerfel, kopilot)):
        for die, face in zip(dice, faces):
            die.augenzahl = face
    return env


def ice_final_pair_fixture():
    """One remaining public5 must finish ice pair4; coffee loses a won landing."""
    env = _base_fixture('LOG_KEF_YELLOW', (1, 1, 5, 3), (1, 1, 2, 5))
    game, cockpit = env.game, env.game.cockpit
    game.landung.hoehe = game.landung.entfernung = 0
    game.letzte_runde = True
    game.aktuelle_runde = game._vorbereitete_runde = 7
    cockpit.fahrwerk_ausgefahren[:] = [True] * 3
    cockpit.landeklappen_ausgefahren[:] = [True] * 4
    cockpit.aerodynamik_blau = AERODYNAMIK_BLAU_START + 3
    cockpit.aerodynamik_orange = AERODYNAMIK_ORANGE_START + 4
    cockpit.eis_fortschritt = 3
    for role in ('pilot', 'kopilot'):
        _place(game, role, 0, 'ruder')
    for role in ('pilot', 'kopilot'):
        _place(game, role, 1, 'triebwerk')
    _place(game, 'pilot', 2, 'eisbremse', 6)
    _place(game, 'kopilot', 2, 'konzentration', 0)
    _place(game, 'pilot', 3, 'konzentration', 1)
    return env


def wind_public_thrust_fixture():
    """Public tailwind+3 changes base-sum8 from one move to two at distance1."""
    env = _base_fixture('LOG_GIG_YELLOW', (3, 6, 2, 4), (3, 2, 1, 1))
    game = env.game
    game.landung.hoehe = 1000
    game.landung.entfernung = 1
    game.cockpit.wind_position = 0
    _place(game, 'pilot', 0, 'ruder')
    _place(game, 'kopilot', 0, 'ruder')
    _place(game, 'pilot', 3, 'konzentration', 0)
    _place(game, 'kopilot', 1, 'triebwerk')
    return env


class WindIceDecisionCounterexamples(unittest.TestCase):
    def test_final_ice_pair_is_win_vs_coffee_loss_but_profiles_offer_both(self):
        original = ice_final_pair_fixture()
        before = original.view()
        self.assertEqual(before['role'], 'kopilot')
        self.assertEqual(before['own_dice'], [0, 0, 0, 5])
        self.assertEqual(before['partner_remaining'], 0)
        self.assertEqual(before['modules_state']['ice_progress'], 3)
        self.assertEqual(before['modules_state']['cards'], ['adaptation'])
        good = _action(3, 'eisbremse', index=7)
        bad = _action(3, 'konzentration', index=2)
        for profile in (10, 11, 12):
            env = deepcopy(original)
            env.assistance_version = profile
            mask = env.action_mask()
            reference = env.info()['reference_action_mask']
            self.assertTrue(mask[good] and mask[bad])
            self.assertTrue(reference[good] and reference[bad])
        winning, losing = deepcopy(original), deepcopy(original)
        _place(winning.game, 'kopilot', 3, 'eisbremse', 7)
        _place(losing.game, 'kopilot', 3, 'konzentration', 2)
        self.assertTrue(winning.game.alle_wuerfel_platziert())
        self.assertTrue(losing.game.alle_wuerfel_platziert())
        win = winning.game.rundenende()
        loss = losing.game.rundenende()
        self.assertTrue(win.gewonnen)
        self.assertEqual(winning.game.status, 'gewonnen')
        self.assertTrue(loss.verloren)
        self.assertEqual(loss.grund, 'eisbremsen_unvollstaendig')
        self.assertEqual(losing.game.status, 'verloren')

    def test_public_tailwind_safe_and_overshoot_thrust_are_unranked_by_all_three_profiles(self):
        original = wind_public_thrust_fixture()
        before = original.view()
        self.assertEqual(before['own_dice'], [0, 6, 2, 0])
        self.assertEqual(before['board'][3]['value'], 2)
        self.assertEqual(before['modules_state']['wind_value'], 3)
        safe = predict_thrust(before, 2, 2)
        bad = predict_thrust(before, 6, 2)
        self.assertEqual((safe['speed'], safe['movement'], safe['reason']), (7, 1, ''))
        self.assertEqual((bad['speed'], bad['reason']), (11, 'uebers_ziel_hinaus'))
        good_action = _action(2, 'triebwerk', owner='pilot')
        bad_action = _action(1, 'triebwerk', owner='pilot')
        for profile in (10, 11, 12):
            env = deepcopy(original)
            env.assistance_version = profile
            mask = env.action_mask()
            reference = env.info()['reference_action_mask']
            self.assertTrue(mask[good_action] and mask[bad_action])
            self.assertTrue(reference[good_action] and reference[bad_action])
        for die, reason, movement in ((2, '', 1), (1, 'uebers_ziel_hinaus', 0)):
            env = deepcopy(original)
            _place(env.game, 'pilot', die, 'triebwerk')
            result = env.game.cockpit.loese_triebwerke_auf()
            self.assertEqual(result.grund, reason)
            self.assertEqual(1 - env.game.landung.entfernung, movement)

    def test_unused_partner_faces_and_real_rng_cannot_change_public_case_advice(self):
        env = wind_public_thrust_fixture()
        before = env.view()
        mask = env.action_mask()
        reference = env.info()['reference_action_mask']
        rng_before = random.getstate()
        # These are scripted, unobserved free fixture dice; do not inspect
        # their old values or use them as a search input.
        env.game.kopilot_wuerfel[2].augenzahl = 6
        env.game.kopilot_wuerfel[3].augenzahl = 5
        self.assertEqual(env.view(), before)
        self.assertEqual(env.action_mask(), mask)
        self.assertEqual(env.info()['reference_action_mask'], reference)
        self.assertEqual(random.getstate(), rng_before)


if __name__ == '__main__':
    unittest.main()
