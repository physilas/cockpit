import json
import unittest
from unittest.mock import patch
from backend import bridge
from play_options import neues_spiel


class PlayOptionsTests(unittest.TestCase):
    cards = json.dumps(['synchronisation', 'control'])

    def prepare(self):
        while bridge.zustand()["phase"] == "verkehr":
            bridge.wirf_verkehrswuerfel()
        bridge.wuerfeln_fuer_runde()

    def test_clock_runs_by_default(self):
        with patch('time.time', return_value=1000):
            state = neues_spiel('LOG_PBH_RED', self.cards)
            self.prepare()
        self.assertIn('realtime', state['module'])
        self.assertEqual(1060, bridge._spiel.zusatz.deadline)

    def test_untimed_survives_future_rolls_save_resume_and_undo(self):
        state = neues_spiel('LOG_PBH_RED', self.cards, False)
        self.prepare()
        self.assertNotIn('realtime', state['module'])
        self.assertIn('kerosene', state['module'])
        self.assertEqual({'synchronisation', 'control'}, set(bridge._spiel.zusatz.karten))
        bridge._spiel.zusatz.wuerfel_geworfen()
        self.assertIsNone(bridge._spiel.zusatz.deadline)
        saved = bridge.spiel_speichern()
        bridge.spiel_laden(saved)
        with patch('time.time', return_value=10**12):
            self.assertFalse(bridge.tick()['ergebnis']['erfolg'])
        self.assertNotIn('realtime', bridge.zustand()['module'])
        # The native placement/undo path copies the disabled module as well.
        role = bridge._spiel.am_zug
        bridge.platziere(role, 0, 'konzentration', 0)
        self.assertTrue(bridge.rueckgaengig()['ergebnis']['erfolg'])
        self.assertNotIn('realtime', bridge.zustand()['module'])

    def test_invalid_option_does_not_replace_a_game(self):
        neues_spiel('LOG_YUL_GREEN')
        previous = bridge._spiel
        with self.assertRaises(ValueError):
            neues_spiel('LOG_PBH_RED', self.cards, 0)
        self.assertIs(previous, bridge._spiel)
