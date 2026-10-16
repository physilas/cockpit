"""Bridge history: full rule state, round boundaries and shared revisions."""
import json
import unittest
from unittest.mock import patch

from backend import bridge
from backend.spielplan import Spielplan


def game_state():
    return {k: v for k, v in bridge.zustand().items()
            if not k.startswith("rueckgaengig_") and k != "server_time_ms"}


class UndoTest(unittest.TestCase):
    def setUp(self):
        bridge.neues_spiel("TEST")

    def assert_success(self, answer):
        self.assertTrue(answer["ergebnis"]["erfolg"], answer["ergebnis"])

    def undo(self):
        self.assert_success(bridge.rueckgaengig())

    def resolve_initial_traffic(self):
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            while bridge._spiel.phase == "verkehr":
                bridge._spiel.wirf_verkehrswuerfel()

    def test_empty_history_and_invalid_actions_are_not_recorded(self):
        with patch.object(bridge, "_spiel", None):
            self.assertEqual(bridge.rueckgaengig()["ergebnis"]["grund"], "kein_spiel_aktiv")
        before = bridge.zustand()
        self.assertEqual(bridge.rueckgaengig()["ergebnis"]["grund"], "kein_rueckgaengig")
        self.assertFalse(bridge.platziere("kopilot", 0, "ruder")["ergebnis"]["erfolg"])
        self.assertFalse(bridge.modul_aktion("pilot", "unknown")["ergebnis"]["erfolg"])
        self.assertFalse(bridge.tick()["ergebnis"]["erfolg"])
        self.assertEqual(bridge.zustand(), before)

    def test_placement_restores_turn_effects_and_shared_die_references(self):
        bridge._spiel.pilot_wuerfel[0].augenzahl = 3
        bridge._spiel.kopilot_wuerfel[0].augenzahl = 4
        self.assert_success(bridge.platziere("pilot", 0, "ruder"))
        before = game_state()
        self.assert_success(bridge.platziere("kopilot", 0, "ruder"))
        self.undo()
        self.assertEqual(game_state(), before)
        g = bridge._spiel
        self.assertIs(g.cockpit.ruder_pilot.wuerfel, g.pilot_wuerfel[0])
        self.assertIs(g.zusatz.spiel, g)
        self.assertIs(g.zusatz.c, g.cockpit)
        self.assertIs(g.cockpit.landung, g.landung)
        self.assert_success(bridge.platziere("kopilot", 0, "ruder"))

    def test_resources_coffee_and_radio_obstacles_are_restored(self):
        g = bridge._spiel
        g.pilot_wuerfel[0].augenzahl = 2
        g.cockpit.kaffeetassen = 2
        before = game_state()
        self.assert_success(bridge.trinke_kaffee("pilot", 0, 1))
        self.undo()
        self.assertEqual(game_state(), before)
        g = bridge._spiel
        g.pilot_wuerfel[0].augenzahl = 1
        i = g.landung._index_fuer_entfernung(g.landung.entfernung)
        g.landung.flugzeuge[i] = 2
        before = game_state()
        self.assert_success(bridge.platziere("pilot", 0, "funk"))
        self.undo()
        self.assertEqual(game_state(), before)

    def test_reroll_restores_exact_values_and_token(self):
        bridge._spiel.neuwurf_plaettchen = 1
        before = game_state()
        self.assert_success(bridge.benutze_neuwurf([0, 2], [1, 3]))
        self.undo()
        self.assertEqual(game_state(), before)

    def test_black_die_undo_before_and_after_automatic_round_start(self):
        for start_round in (False, True):
            with self.subTest(start_round=start_round):
                bridge.neues_spiel("FRA")
                before = game_state()
                with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=3):
                    self.assert_success(bridge.wirf_verkehrswuerfel("pilot"))
                self.assertEqual(bridge.zustand()["phase"], "vorbereitung")
                self.assertEqual(bridge.zustand()["pilot_wuerfel"], [None] * 4)
                self.assertFalse(bridge.platziere("pilot", 0, "ruder")["ergebnis"]["erfolg"])
                if start_round:
                    self.assertEqual(bridge.wuerfeln_fuer_runde()["phase"], "platzieren")
                self.undo()
                self.assertEqual(game_state(), before)
                self.assertFalse(bridge.zustand()["rueckgaengig_moeglich"])

    def test_multiple_black_dice_undo_only_the_latest_roll(self):
        bridge.neues_spiel("FRA")
        g = bridge._spiel
        g.verkehrswuerfel_offen = 2
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            self.assert_success(bridge.wirf_verkehrswuerfel())
            before = game_state()
            self.assert_success(bridge.wirf_verkehrswuerfel())
        self.undo()
        self.assertEqual(game_state(), before)
        self.assertEqual(bridge.zustand()["verkehrswuerfel_offen"], 1)

    def complete_round(self):
        g = bridge._spiel
        g.landung.flugzeuge = [0] * g.landung.get_laenge()
        actions = {
            "pilot": iter([(0, "ruder", None), (1, "triebwerk", None),
                           (2, "funk", None), (3, "konzentration", 1)]),
            "kopilot": iter([(0, "ruder", None), (1, "triebwerk", None),
                             (2, "konzentration", 0), (3, "konzentration", 2)]),
        }
        for dice in (g.pilot_wuerfel, g.kopilot_wuerfel):
            for die, value in zip(dice, [3, 2, 1, 1]):
                die.augenzahl = value
        for _ in range(8):
            role = g.am_zug
            i, target, index = next(actions[role])
            self.assert_success(bridge.platziere(role, i, target, index))

    def test_round_end_and_automatic_white_roll_are_one_undo_step(self):
        self.complete_round()
        before = game_state()
        self.assert_success(bridge.rundenende())
        self.assertEqual(bridge.wuerfeln_fuer_runde()["runde"], 2)
        self.undo()
        self.assertEqual(game_state(), before)
        self.undo()
        self.assertFalse(bridge._spiel.kopilot_wuerfel[3].platziert)

    def test_loss_can_be_undone(self):
        bridge._spiel.pilot_wuerfel[0].augenzahl = 1
        bridge._spiel.kopilot_wuerfel[0].augenzahl = 6
        self.assert_success(bridge.platziere("pilot", 0, "ruder"))
        before = game_state()
        answer = bridge.platziere("kopilot", 0, "ruder")
        self.assertTrue(answer["ergebnis"]["verloren"])
        self.assertEqual(bridge.zustand()["status"], "verloren")
        self.undo()
        self.assertEqual(game_state(), before)

    def test_synchronisation_trigger_roll_coffee_and_placement_are_reversible(self):
        bridge.neues_spiel("LOG_PRG_GREEN", '["synchronisation","control"]')
        self.resolve_initial_traffic()
        g = bridge._spiel
        g.cockpit.kaffeetassen = 1
        g.pilot_wuerfel[0].augenzahl = 1
        g.kopilot_wuerfel[0].augenzahl = 2
        self.assert_success(bridge.platziere("pilot", 0, "fahrwerk", 0))
        before_trigger = game_state()
        self.assert_success(bridge.platziere("kopilot", 0, "landeklappe", 0))
        before_roll = game_state()
        with patch("backend.zusatzregeln.wirf_verkehrswuerfel", return_value=4):
            self.assert_success(bridge.modul_aktion("pilot", "synchronisation_wuerfeln"))
        before_coffee = game_state()
        self.assert_success(bridge.modul_aktion("pilot", "bonus_kaffee", '{"delta":1}'))
        before_placement = game_state()
        target = next(t for t in bridge.zustand()["zusatzaktion"]["ziele"]
                      if t["ziel"] == "ruder" and t["ziel_besitzer"] == "kopilot")
        self.assert_success(bridge.modul_aktion("pilot", "zusatz_platzieren", json.dumps(target)))
        for before in (before_placement, before_coffee, before_roll, before_trigger):
            self.undo()
            self.assertEqual(game_state(), before)

    def test_shared_undo_rejects_stale_or_invalid_role_requests(self):
        self.assert_success(bridge.platziere("pilot", 0, "ruder"))
        revision = bridge.zustand()["rueckgaengig_version"]
        self.assertEqual(bridge.rueckgaengig("observer", revision)["ergebnis"]["grund"], "ungueltiger_besitzer")
        self.assert_success(bridge.rueckgaengig("kopilot", revision))
        before = bridge.zustand()
        for stale in (revision, str(revision), True):
            self.assertEqual(bridge.rueckgaengig("pilot", stale)["ergebnis"]["grund"], "spielstand_geaendert")
        self.assertEqual(bridge.zustand(), before)
        self.assertNotIn("verlauf", json.dumps(bridge.zustand()))

    def test_new_game_clears_history_but_invalid_new_game_keeps_it(self):
        self.assert_success(bridge.platziere("pilot", 0, "ruder"))
        before = bridge.zustand()
        with self.assertRaises(ValueError):
            bridge.neues_spiel("LOG_PRG_GREEN")
        self.assertEqual(bridge.zustand(), before)
        after = bridge.neues_spiel("MUC")
        self.assertFalse(after["rueckgaengig_moeglich"])
        self.assertGreater(after["rueckgaengig_id"], before["rueckgaengig_id"])

    def test_realtime_deadline_is_not_rewound_and_idle_ticks_do_not_add_history(self):
        now = [100.0]
        bridge._spiel = Spielplan("LOG_PBH_RED", faehigkeitskarten=["control", "adaptation"], clock=lambda: now[0])
        bridge._spiel.starte_spiel()
        self.resolve_initial_traffic()
        before = game_state()
        deadline = before["timer_deadline_ms"]
        self.assert_success(bridge.platziere("pilot", 0, "ruder"))
        revision = bridge.zustand()["rueckgaengig_version"]
        for _ in range(10):
            bridge.tick()
        self.assertEqual(bridge.zustand()["rueckgaengig_version"], revision)
        now[0] += 20
        self.undo()
        self.assertEqual(game_state(), before)
        self.assertEqual(bridge.zustand()["timer_deadline_ms"], deadline)
        now[0] = deadline / 1000
        # A rejected late move still changes the game (timeout); it is undoable.
        self.assertFalse(bridge.platziere("pilot", 0, "ruder")["ergebnis"]["erfolg"])
        self.assertEqual(bridge.zustand()["status"], "verloren")
        self.undo()
        self.assertEqual(game_state(), before)
        bridge.tick()
        self.assertEqual(bridge.zustand()["status"], "verloren")

    def test_realtime_clock_stays_stopped_during_black_die_cooldown(self):
        bridge.neues_spiel("LOG_PBH_RED", '["control","adaptation"]')
        now = [100.0]
        bridge._spiel.zusatz.clock = lambda: now[0]
        self.assertEqual(bridge._spiel.phase, "verkehr")
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=3):
            while bridge._spiel.verkehrswuerfel_offen:
                self.assert_success(bridge.wirf_verkehrswuerfel())
        self.assertIsNone(bridge.zustand()["timer_deadline_ms"])
        now[0] += 1
        self.assertEqual(bridge.wuerfeln_fuer_runde()["timer_deadline_ms"], 161000)
        self.undo()
        self.assertIsNone(bridge.zustand()["timer_deadline_ms"])

    def test_history_retains_at_most_200_steps(self):
        bridge._spiel.pilot_wuerfel[0].augenzahl = 3
        for i in range(205):
            bridge._spiel.cockpit.kaffeetassen = 3
            self.assert_success(bridge.trinke_kaffee("pilot", 0, 1 if i % 2 == 0 else -1))
        self.assertEqual(len(bridge._verlauf), 200)
        for _ in range(200):
            self.undo()
        self.assertFalse(bridge.zustand()["rueckgaengig_moeglich"])


if __name__ == "__main__":
    unittest.main()
