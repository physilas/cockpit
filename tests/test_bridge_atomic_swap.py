"""One typed exchange choice has one bridge revision, including its confirmation."""
from copy import deepcopy
from unittest.mock import patch
import unittest

from backend import bridge
from backend.cockpit import Ergebnis
from backend.spielplan import Spielplan
from backend.zusatzregeln import Zusatzregeln


class AtomicSwapBridgeTests(unittest.TestCase):
    def setUp(self):
        self.previous = (bridge._spiel, bridge._verlauf, bridge._revision, bridge._undo_id)
        bridge._verlauf = []
        bridge.neues_spiel('LOG_ATL_YELLOW', '["working-together"]')
        while bridge._spiel.phase == 'verkehr':
            bridge._spiel.wirf_verkehrswuerfel()
        self.assertTrue(bridge.modul_aktion('pilot', 'kooperation_start')['ergebnis']['erfolg'])
        self.identity = bridge._spiel.zusatz.kooperation['id']

    def tearDown(self):
        bridge._spiel, bridge._verlauf, bridge._revision, bridge._undo_id = self.previous

    def test_matches_two_native_steps_and_is_exactly_one_undo_entry(self):
        for role, index in (('pilot', 2), ('kopilot', 1)):
            before = deepcopy(bridge._spiel)
            native = deepcopy(before)
            self.assertTrue(native.zusatz.aktion(role, 'kooperation_wahl', {'wuerfel_index': index}))
            expected = native.zusatz.aktion(role, 'kooperation_bestaetigen', {})
            revision, history = bridge._revision, len(bridge._verlauf)
            answer = bridge.kooperation_waehlen_bestaetigen(role, index, self.identity)
            self.assertEqual(answer['ergebnis'], bridge._ergebnis_zu_dict(expected))
            self.assertEqual(bridge._spiel.zustand(), native.zustand())
            self.assertEqual(bridge._revision, revision + 1)
            self.assertEqual(len(bridge._verlauf), history + 1)
            after = deepcopy(bridge._spiel)
            self.assertTrue(bridge.rueckgaengig(version=bridge._revision)['ergebnis']['erfolg'])
            self.assertEqual(bridge._spiel.zustand(), before.zustand())
            bridge._spiel = after
        result = bridge._spiel.zusatz.kooperation_ergebnis
        self.assertIsNotNone(result)
        self.assertEqual(result['nachher']['pilot'], result['vorher']['kopilot'])
        self.assertEqual(result['nachher']['kopilot'], result['vorher']['pilot'])

    def test_invalid_stale_or_confirmed_choices_do_not_mutate_or_add_history(self):
        for role, index, identity in [('hacker', 0, self.identity), ('pilot', True, self.identity),
                                      ('pilot', -1, self.identity), ('pilot', 4, self.identity),
                                      ('pilot', 0, self.identity + 1), ('pilot', 0, True)]:
            with self.subTest(role=role, index=index, identity=identity):
                before, revision, history = bridge._spiel.zustand(), bridge._revision, len(bridge._verlauf)
                self.assertFalse(bridge.kooperation_waehlen_bestaetigen(role, index, identity)['ergebnis']['erfolg'])
                self.assertEqual(bridge._spiel.zustand(), before)
                self.assertEqual((bridge._revision, len(bridge._verlauf)), (revision, history))
        self.assertTrue(bridge.kooperation_waehlen_bestaetigen('pilot', 0)['ergebnis']['erfolg'])
        before, revision = bridge._spiel.zustand(), bridge._revision
        self.assertFalse(bridge.kooperation_waehlen_bestaetigen('pilot', 1)['ergebnis']['erfolg'])
        self.assertEqual(bridge._spiel.zustand(), before)
        self.assertEqual(bridge._revision, revision)

    def test_confirmation_failure_rolls_back_the_selection(self):
        original = Zusatzregeln.aktion
        def rejected_confirmation(instance, role, action, params):
            return Ergebnis(False, 'fixture_rejected') if action == 'kooperation_bestaetigen' else original(instance, role, action, params)
        before, revision, history = bridge._spiel.zustand(), bridge._revision, len(bridge._verlauf)
        with patch.object(Zusatzregeln, 'aktion', rejected_confirmation):
            answer = bridge.kooperation_waehlen_bestaetigen('pilot', 3, self.identity)
        self.assertEqual(answer['ergebnis']['grund'], 'fixture_rejected')
        self.assertEqual(bridge._spiel.zustand(), before)
        self.assertEqual((bridge._revision, len(bridge._verlauf)), (revision, history))

    def test_no_game_uses_the_regular_bridge_error(self):
        bridge._spiel = None
        self.assertEqual(bridge.kooperation_waehlen_bestaetigen('pilot', 0)['ergebnis']['grund'], 'kein_spiel_aktiv')

    def test_real_clock_expiry_during_confirmation_is_preserved(self):
        now = [0.]
        game = Spielplan('LOG_PBH_RED', faehigkeitskarten=['working-together', 'control'], clock=lambda: now[0])
        game.starte_spiel()
        while game.phase == 'verkehr':
            game.wirf_verkehrswuerfel()
        self.assertTrue(game.zusatz.aktion('pilot', 'kooperation_start', {}))
        bridge._spiel, bridge._verlauf = game, []
        revision = bridge._revision
        original = Zusatzregeln.aktion
        def expire_before_confirmation(instance, role, action, params):
            if action == 'kooperation_bestaetigen':
                now[0] = 61.
            return original(instance, role, action, params)
        with patch.object(Zusatzregeln, 'aktion', expire_before_confirmation):
            answer = bridge.kooperation_waehlen_bestaetigen('pilot', 0)
        self.assertFalse(answer['ergebnis']['erfolg'])
        self.assertEqual(answer['zustand']['status'], 'verloren')
        self.assertEqual(bridge._revision, revision + 1)
        self.assertEqual(len(bridge._verlauf), 1)


if __name__ == '__main__':
    unittest.main()
