"""Rule-level boundaries and interactions for the complete flight log."""
import json
import unittest
from unittest.mock import patch
from backend.spielplan import Spielplan
from backend import bridge


class ModuleTest(unittest.TestCase):
    def game(self, code="LOG_PRG_GREEN", cards=("control", "adaptation"), clock=None):
        with patch("backend.zusatzregeln.random.sample", return_value=[1, 2, 3, 4, 5, 6]):
            g = Spielplan(code, faehigkeitskarten=list(cards), clock=clock)
        g.starte_spiel()
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            while g.phase == "verkehr":
                g.wirf_verkehrswuerfel()
        g.landung.flugzeuge = [0] * g.landung.get_laenge()
        g.landung._flugzeugwuerfel = [0] * g.landung.get_laenge()
        return g

    def place(self, g, role, i, value, target, index=None):
        g._wuerfel_liste(role)[i].augenzahl = value
        return g.platziere(role, i, target, index)

    def mandatory(self, g, value=2):
        for r, i, target in [("pilot", 0, "ruder"), ("kopilot", 0, "ruder"), ("pilot", 1, "triebwerk"), ("kopilot", 1, "triebwerk")]:
            self.assertTrue(self.place(g, r, i, value, target).erfolg)

    def end_fixture(self, g):
        for w in g.pilot_wuerfel + g.kopilot_wuerfel:
            w.platziert = True
        return g.rundenende()

    def test_card_set_validated_and_invalid_start_keeps_existing_game(self):
        for cards in ([], ["control"], ["control", "control"], ["control", "unknown"], "control", [None, "control"]):
            with self.assertRaises(ValueError):
                Spielplan("LOG_PRG_GREEN", faehigkeitskarten=cards)
        bridge.neues_spiel("LOG_YUL_GREEN")
        before = bridge.zustand()["szenario_id"]
        with self.assertRaises(ValueError):
            bridge.neues_spiel("LOG_PRG_GREEN")
        self.assertEqual(bridge.zustand()["szenario_id"], before)

    def test_kerosene_immediate_once_and_zero_loses_in_final_round(self):
        g = self.game("LOG_OSL_GREEN", ())
        self.assertTrue(self.place(g, "pilot", 0, 3, "kerosin"))
        self.assertEqual(g.cockpit.kerosin, 17)
        g.am_zug = "pilot"
        self.assertFalse(self.place(g, "pilot", 1, 2, "kerosin"))
        self.assertEqual(g.cockpit.kerosin, 17)
        g.cockpit.leere_alle_felder(); g.cockpit.kerosin = 2; g.letzte_runde = True
        result = self.place(g, "pilot", 0, 2, "kerosin")
        self.assertTrue(result.verloren)
        self.assertEqual(g.verlust_grund, "kerosin_leer")

    def test_kerosene_without_die_costs_six_once_and_no_double_charge(self):
        g = self.game("LOG_OSL_GREEN", ())
        self.mandatory(g)
        self.assertTrue(self.end_fixture(g).erfolg)
        self.assertEqual(g.cockpit.kerosin, 14)
        g.wuerfeln_fuer_runde()
        g.am_zug = "pilot"
        self.assertTrue(self.place(g, "pilot", 2, 1, "kerosin"))
        g.am_zug = "pilot"; self.mandatory(g)
        self.end_fixture(g)
        self.assertEqual(g.cockpit.kerosin, 13)

    def test_leak_replaces_normal_consumption_and_disables_kerosene_action(self):
        g = self.game("LOG_PRG_YELLOW")
        self.assertFalse(self.place(g, "pilot", 3, 1, "kerosin"))
        self.assertTrue(self.place(g, "pilot", 0, 2, "ruder"))
        self.assertTrue(self.place(g, "kopilot", 0, 2, "ruder"))
        self.assertTrue(self.place(g, "pilot", 1, 1, "triebwerk"))
        self.assertEqual(g.cockpit.kerosin, 20)
        self.assertTrue(self.place(g, "kopilot", 1, 3, "triebwerk"))
        self.assertEqual(g.cockpit.kerosin, 17)
        self.end_fixture(g)
        self.assertEqual(g.cockpit.kerosin, 17)

    def test_leak_equal_engines_cost_one_and_can_end_game_immediately(self):
        g = self.game("LOG_PRG_YELLOW")
        g.cockpit.kerosin = 1
        self.place(g, "pilot", 0, 2, "triebwerk")
        result = self.place(g, "kopilot", 0, 2, "triebwerk")
        self.assertTrue(result.verloren)
        self.assertEqual(g.cockpit.kerosin, 0)

    def test_wind_initial_value_ring_wrap_and_persistent_axis(self):
        g = self.game("LOG_GIG_YELLOW", ("control",))
        self.assertEqual(g.cockpit.wind_wert(), 3)
        self.place(g, "pilot", 0, 3, "ruder"); self.place(g, "kopilot", 0, 5, "ruder")
        self.assertEqual((g.cockpit.fluglage, g.cockpit.wind_position, g.cockpit.wind_wert()), (2, 2, 2))
        g.cockpit.leere_alle_felder(); g.zusatz.neue_runde(); g.am_zug = "pilot"
        self.place(g, "pilot", 1, 2, "ruder"); self.place(g, "kopilot", 1, 2, "ruder")
        self.assertEqual(g.cockpit.wind_position, 4)
        g.cockpit.wind_position = 17
        g.cockpit.leere_alle_felder(); g.zusatz.neue_runde(); g.am_zug = "pilot"
        self.place(g, "pilot", 2, 2, "ruder"); self.place(g, "kopilot", 2, 2, "ruder")
        self.assertEqual(g.cockpit.wind_position, 1)
        self.place(g, "pilot", 3, 1, "triebwerk"); self.place(g, "kopilot", 3, 1, "triebwerk")
        self.assertEqual(g.cockpit.triebwerk_geschwindigkeit(), 5)
        self.assertTrue(g.cockpit.loese_triebwerke_auf(letzte_runde=True).verloren)

    def test_ice_requires_order_same_round_pairs_and_top_pilot_only(self):
        g = self.game("LOG_KEF_YELLOW", ("control",))
        self.assertFalse(self.place(g, "pilot", 0, 3, "eisbremse", 2))
        self.assertTrue(self.place(g, "pilot", 0, 2, "eisbremse", 0))
        self.assertFalse(self.place(g, "kopilot", 0, 3, "eisbremse", 1))
        self.assertTrue(self.place(g, "kopilot", 0, 2, "eisbremse", 1))
        self.assertEqual(g.cockpit.eis_fortschritt, 1)
        self.assertTrue(self.place(g, "pilot", 1, 3, "eisbremse", 2))
        g.cockpit.leere_alle_felder()
        self.assertEqual(g.cockpit.eis_fortschritt, 1)
        g.am_zug = "kopilot"
        self.assertFalse(self.place(g, "kopilot", 2, 3, "eisbremse", 2))
        self.assertTrue(self.place(g, "kopilot", 2, 3, "eisbremse", 3))
        self.assertEqual(g.cockpit.eis_fortschritt, 1)
        self.assertFalse(self.place(g, "pilot", 2, 2, "eisbremse", 0))

    def test_ice_completion_is_additional_win_condition_and_speed_boundary(self):
        g = self.game("LOG_KEF_YELLOW", ("control",))
        g.landung.flugzeuge = [0] * g.landung.get_laenge()
        g.cockpit.fahrwerk_ausgefahren = [True] * 3
        g.cockpit.landeklappen_ausgefahren = [True] * 4
        self.assertEqual(g._werte_spielende_aus().grund, "eisbremsen_unvollstaendig")
        g.cockpit.eis_fortschritt = 4
        self.assertTrue(g._werte_spielende_aus().gewonnen)
        g.cockpit.schub_pilot.wuerfel = g.pilot_wuerfel[0]; g.pilot_wuerfel[0].augenzahl = 2
        g.cockpit.schub_kopilot.wuerfel = g.kopilot_wuerfel[0]; g.kopilot_wuerfel[0].augenzahl = 3
        self.assertFalse(g.cockpit.loese_triebwerke_auf(letzte_runde=True).verloren)
        g.kopilot_wuerfel[0].augenzahl = 4
        self.assertTrue(g.cockpit.loese_triebwerke_auf(letzte_runde=True).verloren)

    def test_intern_both_ends_different_number_forced_token_and_no_coffee(self):
        g = self.game("LOG_ATL_GREEN", ())
        self.assertFalse(self.place(g, "pilot", 0, 1, "training"))
        self.assertTrue(self.place(g, "pilot", 0, 2, "training"))
        p = g.zustand()["zusatzaktion"]
        self.assertEqual((p["wert"], p["rolle"]), (1, "pilot"))
        self.assertFalse(any(t["ziel"] in ("konzentration", "training") for t in p["ziele"]))
        self.assertFalse(self.place(g, "kopilot", 0, 2, "ruder"))
        self.assertFalse(g.trinke_kaffee("pilot", 0, 1))
        target = next(t for t in p["ziele"] if t["ziel"] == "ruder")
        self.assertTrue(g.zusatz.aktion("pilot", "zusatz_platzieren", target))
        self.assertEqual(g.cockpit.ruder_pilot.wuerfel.augenzahl, 1)
        self.assertEqual(g.am_zug, "kopilot")
        self.assertTrue(self.place(g, "kopilot", 0, 4, "training"))
        self.assertEqual(g.zustand()["zusatzaktion"]["wert"], 6)
        self.assertEqual(g.zusatz.praktikant, [2, 3, 4, 5])

    def test_intern_no_legal_destination_leaves_training_and_token_unchanged(self):
        g = self.game("LOG_ATL_GREEN", ())
        g.zusatz.praktikant = [6]
        for field in (g.cockpit.ruder_pilot, g.cockpit.schub_pilot, g.cockpit.funk_pilot, g.cockpit.fahrwerk[2]):
            from backend.wuerfel import Wuerfel
            w = Wuerfel("pilot"); w.augenzahl = 6
            self.assertTrue(field.platziere(w))
        result = self.place(g, "pilot", 0, 2, "training")
        self.assertEqual(result.grund, "praktikant_kein_ziel")
        self.assertEqual(g.zusatz.praktikant, [6])
        self.assertTrue(g.cockpit.training["pilot"].ist_frei())
        self.assertTrue(g.pilot_wuerfel[0].ist_verfuegbar())
        self.assertIsNone(g.zustand()["zusatzaktion"])

    def test_intern_requires_full_training_to_win(self):
        g = self.game("LOG_ATL_GREEN", ())
        g.cockpit.fahrwerk_ausgefahren = [True] * 3; g.cockpit.landeklappen_ausgefahren = [True] * 4
        self.assertEqual(g._werte_spielende_aus().grund, "praktikant_unvollstaendig")
        g.zusatz.praktikant = []
        self.assertTrue(g._werte_spielende_aus().gewonnen)

    def test_control_coffee_cap_and_mastery_finite_token_supply(self):
        g = self.game(cards=("control", "mastery"))
        g.cockpit.kaffeetassen = 3
        self.mandatory(g)
        self.assertEqual(g.cockpit.kaffeetassen, 3)
        self.assertEqual(g.neuwurf_plaettchen, 2)  # One token remains on altitude track; the third is now gained.
        g.cockpit.leere_alle_felder(); g.zusatz.neue_runde(); g.am_zug = "pilot"
        self.assertTrue(g.benutze_neuwurf([0], []))
        self.mandatory(g)
        self.assertEqual(g.neuwurf_plaettchen, 2)
        # Trigger cannot be harvested twice in one round.
        g.zusatz.nach_platzierung("triebwerk")
        self.assertEqual(g.neuwurf_plaettchen, 2)

    def test_adaptation_once_per_person_and_anticipation_first_placement_window(self):
        g = self.game(cards=("adaptation", "anticipation"))
        g.pilot_wuerfel[0].augenzahl = 1
        self.assertTrue(g.zusatz.aktion("pilot", "adaptation", {"wuerfel_index":0}))
        self.assertEqual(g.pilot_wuerfel[0].augenzahl, 6)
        self.assertFalse(g.zusatz.aktion("pilot", "adaptation", {"wuerfel_index":1}))
        self.assertTrue(g.zusatz.aktion("kopilot", "adaptation", {"wuerfel_index":0}))
        self.assertFalse(g.zusatz.aktion("kopilot", "anticipation", {"wuerfel_index":0}))
        self.assertTrue(g.zusatz.aktion("pilot", "anticipation", {"wuerfel_index":0}))
        self.assertFalse(g.zusatz.aktion("pilot", "anticipation", {"wuerfel_index":1}))
        self.place(g, "pilot", 1, 2, "ruder")
        self.assertFalse(g.zusatz.aktion("pilot", "anticipation", {"wuerfel_index":2}))

    def test_working_together_atomic_private_choices_no_turn_consumption(self):
        g = self.game(cards=("working-together", "control"))
        g.pilot_wuerfel[0].augenzahl = 1; g.kopilot_wuerfel[1].augenzahl = 6
        g.am_zug = "kopilot"
        self.assertTrue(g.zusatz.aktion("pilot", "kooperation_start", {}))
        self.assertTrue(g.zusatz.aktion("pilot", "kooperation_wahl", {"wuerfel_index":0}))
        self.assertEqual(g.zustand()["kooperation"], {"wartet_auf":"kopilot"})
        self.assertEqual(g.pilot_wuerfel[0].augenzahl, 1)
        self.assertFalse(g.trinke_kaffee("kopilot", 1, -1))
        self.assertTrue(g.zusatz.aktion("kopilot", "kooperation_wahl", {"wuerfel_index":1}))
        self.assertEqual((g.pilot_wuerfel[0].augenzahl, g.kopilot_wuerfel[1].augenzahl), (6, 1))
        self.assertEqual(g.am_zug, "kopilot")
        self.assertFalse(g.zusatz.aktion("pilot", "kooperation_start", {}))

    def test_synchronisation_other_player_rolls_then_places_on_either_colour_once(self):
        g = self.game(cards=("synchronisation", "control"))
        with patch("backend.zusatzregeln.wirf_verkehrswuerfel", return_value=2) as roll:
            self.place(g, "pilot", 0, 1, "fahrwerk", 0)
            self.place(g, "kopilot", 0, 2, "landeklappe", 0)
            p = g.zustand()["zusatzaktion"]
            self.assertEqual((p["rolle"], p["quelle"], p["wert"]), ("pilot", "synchronisation", None))
            self.assertFalse(p["geworfen"])
            self.assertEqual(p["ziele"], [])
            self.assertEqual(p["kaffee_deltas"], [])
            roll.assert_not_called()
            self.assertFalse(g.zusatz.aktion("kopilot", "synchronisation_wuerfeln", {}))
            self.assertFalse(g.zusatz.aktion("pilot", "bonus_kaffee", {"delta":1}))
            self.assertTrue(g.zusatz.aktion("pilot", "synchronisation_wuerfeln", {}))
            self.assertFalse(g.zusatz.aktion("pilot", "synchronisation_wuerfeln", {}))
            roll.assert_called_once()
        p = g.zustand()["zusatzaktion"]
        target = next(t for t in p["ziele"] if t["ziel"] == "ruder" and t["ziel_besitzer"] == "kopilot")
        self.assertFalse(g.zusatz.aktion("kopilot", "zusatz_platzieren", target))
        self.assertTrue(g.zusatz.aktion("pilot", "zusatz_platzieren", target))
        self.assertEqual(g.am_zug, "pilot")
        self.assertEqual(g.zustand()["felder"]["ruder"]["kopilot"]["quelle"], "synchronisation")
        self.assertEqual(sum(w.platziert for w in g.pilot_wuerfel + g.kopilot_wuerfel), 2)
        g.zusatz.nach_platzierung("fahrwerk")
        self.assertIsNone(g.zustand()["zusatzaktion"])

    def test_synchronisation_pilot_trigger_hands_roll_to_copilot(self):
        g = self.game(cards=("synchronisation", "control"))
        self.assertTrue(self.place(g, "pilot", 0, 3, "ruder"))
        self.assertTrue(self.place(g, "kopilot", 0, 2, "landeklappe", 0))
        self.assertTrue(self.place(g, "pilot", 1, 1, "fahrwerk", 0))
        self.assertEqual(g.zustand()["zusatzaktion"]["rolle"], "kopilot")
        self.assertIsNone(g.zustand()["zusatzaktion"]["wert"])
        self.assertFalse(g.zusatz.aktion("kopilot", "zusatz_platzieren", {}))
        self.assertFalse(g.rundenende())

    def test_synchronisation_roll_cannot_outlive_realtime_deadline(self):
        now = [100.0]
        g = self.game("LOG_PBH_RED", ("synchronisation", "control"), clock=lambda:now[0])
        self.place(g, "pilot", 0, 1, "fahrwerk", 0)
        self.place(g, "kopilot", 0, 2, "landeklappe", 0)
        now[0] = 160
        with patch("backend.zusatzregeln.wirf_verkehrswuerfel") as roll:
            result = g.zusatz.aktion("pilot", "synchronisation_wuerfeln", {})
            self.assertFalse(result)
            self.assertEqual(result.grund, "zeit_abgelaufen")
            roll.assert_not_called()
        self.assertIsNone(g.zustand()["zusatzaktion"])

    def test_synchronisation_accepts_coffee_but_intern_token_does_not(self):
        g = self.game(cards=("synchronisation", "control"))
        g.cockpit.kaffeetassen = 1
        self.place(g, "pilot", 0, 1, "fahrwerk", 0)
        self.place(g, "kopilot", 0, 2, "landeklappe", 0)
        with patch("backend.zusatzregeln.wirf_verkehrswuerfel", return_value=4):
            self.assertTrue(g.zusatz.aktion("pilot", "synchronisation_wuerfeln", {}))
        self.assertTrue(g.zusatz.aktion("pilot", "bonus_kaffee", {"delta":-1}))
        self.assertEqual(g.zustand()["zusatzaktion"]["wert"], 3)
        self.assertEqual(g.cockpit.kaffeetassen, 0)
        self.assertFalse(g.zusatz.aktion("kopilot", "bonus_kaffee", {"delta":1}))
        intern = self.game("LOG_ATL_GREEN", ())
        self.place(intern, "pilot", 0, 2, "training")
        self.assertFalse(intern.zusatz.aktion("pilot", "bonus_kaffee", {"delta":1}))

    def test_mastery_cannot_exceed_three_physical_tokens_including_altitude(self):
        g = self.game(cards=("control", "mastery"))
        g.neuwurf_plaettchen = 2  # The third token is still on the 2000-ft space.
        self.mandatory(g)
        self.assertEqual(g.neuwurf_plaettchen, 2)

    def test_realtime_late_action_rejected_and_missing_required_dice_lose(self):
        now = [100.0]
        g = self.game("LOG_PBH_RED", clock=lambda:now[0])
        self.assertEqual(g.zustand()["timer_deadline_ms"], 160000)
        now[0] = 160
        result = self.place(g, "pilot", 0, 2, "ruder")
        self.assertEqual(result.grund, "zeit_abgelaufen")
        self.assertEqual(g.status, "verloren")
        self.assertTrue(g.cockpit.ruder_pilot.ist_frei())
        self.assertFalse(g.zusatz.tick())

    def test_realtime_unused_dice_ignored_then_discussion_before_next_roll(self):
        now = [100.0]
        g = self.game("LOG_PBH_RED", clock=lambda:now[0])
        self.mandatory(g)
        now[0] = 161
        self.assertTrue(g.zusatz.tick())
        self.assertEqual((g.aktuelle_runde, g.phase, g.cockpit.kerosin), (2, "vorbereitung", 14))
        self.assertIsNone(g.zustand()["timer_deadline_ms"])
        now[0] = 500
        self.assertFalse(g.zusatz.tick())
        self.assertTrue(g.zusatz.aktion(g.am_zug, "wuerfeln", {}))
        self.assertEqual(g.zustand()["timer_deadline_ms"], 560000)

    def test_all_official_routes_accept_every_exact_card_combination(self):
        from itertools import combinations
        from backend.katalog import logbuch_katalog
        from backend.zusatzregeln import KARTEN
        for scenario in logbuch_katalog()["scenarios"]:
            for cards in combinations(sorted(KARTEN), scenario["ability_count"]):
                with self.subTest(scenario=scenario["id"], cards=cards):
                    g = self.game(scenario["engine_code"], cards)
                    z = g.zustand()
                    self.assertEqual(set(z["module"]), set(scenario["modules"]))
                    self.assertEqual(z["faehigkeitskarten"], list(cards))
                    self.assertFalse(z["uebung"])
                    json.dumps(z)

    def test_intern_token_can_regulate_kerosene_without_second_turn(self):
        g = self.game("LOG_HND_RED", ("control",))
        self.assertTrue(self.place(g, "pilot", 0, 2, "training"))
        target = next(t for t in g.zustand()["zusatzaktion"]["ziele"] if t["ziel"] == "kerosin")
        self.assertTrue(g.zusatz.aktion("pilot", "zusatz_platzieren", target))
        self.assertEqual((g.cockpit.kerosin, g.am_zug), (19, "kopilot"))
        self.assertIsNone(g.zustand()["zusatzaktion"])
        self.assertFalse(self.place(g, "kopilot", 0, 2, "kerosin"))

    def test_wind_and_ice_combined_final_landing(self):
        for wind_position, wins in [(9, True), (0, False)]:
            g = self.game("LOG_KEF_BLACK")
            self.mandatory(g)
            g.cockpit.wind_position = wind_position
            g.cockpit.eis_fortschritt = 4
            g.cockpit.fahrwerk_ausgefahren = [True] * 3
            g.cockpit.landeklappen_ausgefahren = [True] * 4
            g.letzte_runde = True
            result = self.end_fixture(g)
            self.assertEqual(result.gewonnen, wins)
            self.assertEqual(result.verloren, not wins)

    def test_leak_and_ice_empty_fuel_loses_before_landing(self):
        g = self.game("LOG_OSL_RED")
        g.cockpit.kerosin = 6
        g.cockpit.eis_fortschritt = 4
        g.letzte_runde = True
        self.place(g, "pilot", 0, 1, "triebwerk")
        result = self.place(g, "kopilot", 0, 6, "triebwerk")
        self.assertTrue(result.verloren)
        self.assertEqual(result.grund, "kerosin_leer")

    def test_timer_cancels_pending_cooperation_and_rejects_late_partner(self):
        now = [100.0]
        g = self.game("LOG_PBH_RED", ("working-together", "control"), lambda:now[0])
        self.mandatory(g)
        self.assertTrue(g.zusatz.aktion("pilot", "kooperation_start", {}))
        self.assertTrue(g.zusatz.aktion("pilot", "kooperation_wahl", {"wuerfel_index":2}))
        now[0] = 161
        result = g.zusatz.aktion("kopilot", "kooperation_wahl", {"wuerfel_index":2})
        self.assertEqual(result.grund, "zeit_abgelaufen")
        self.assertEqual(g.kopilot_wuerfel[2].augenzahl, None)  # New round is not rolled yet.
        self.assertIsNone(g.zustand()["kooperation"])
        self.assertEqual(g.aktuelle_runde, 2)

    def test_bridge_module_boundary_rejects_invalid_parameters(self):
        bridge.neues_spiel("LOG_OSL_GREEN")
        self.assertEqual(bridge.modul_aktion("pilot", "adaptation", "[]")["ergebnis"]["grund"], "ungueltige_aktion")
        self.assertFalse(bridge.modul_aktion("hacker", "adaptation")["ergebnis"]["erfolg"])
        json.dumps(bridge.zustand())


if __name__ == '__main__':
    unittest.main()
