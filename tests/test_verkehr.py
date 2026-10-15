import unittest
from collections import Counter
from unittest.mock import patch

from backend import bridge
from backend.landung import flughafen_liste
from backend.spielplan import Spielplan
from backend.wuerfel import wirf_verkehrswuerfel


def platziere_runde(spiel, schub=2):
    """Eine komplette gültige Runde: gerade Fluglage, Funk und Konzentration."""
    aktionen = {
        "pilot": iter([(0, "ruder", {}), (1, "triebwerk", {}),
                       (2, "funk", {}), (3, "konzentration", {"index": 1})]),
        "kopilot": iter([(0, "ruder", {}), (1, "triebwerk", {}),
                         (2, "konzentration", {"index": 0}), (3, "konzentration", {"index": 2})]),
    }
    for wuerfel in (spiel.pilot_wuerfel, spiel.kopilot_wuerfel):
        for w, wert in zip(wuerfel, [3, schub, 1, 1]):
            w.augenzahl = wert
    for _ in range(8):
        besitzer = spiel.am_zug
        index, ziel, kwargs = next(aktionen[besitzer])
        ergebnis = spiel.platziere(besitzer, index, ziel, **kwargs)
        assert ergebnis.erfolg, ergebnis.grund
    return spiel.rundenende()


class VerkehrTest(unittest.TestCase):
    def test_fra_ist_sichtbar_und_enthaelt_mehrfachwuerfel(self):
        self.assertIn({"code": "FRA", "bezeichnung": "Frankfurt"}, flughafen_liste())
        z = Spielplan("FRA").zustand()
        self.assertEqual(len(z["flugzeugwuerfel"]), z["laenge"])
        self.assertIn(2, z["flugzeugwuerfel"])
        self.assertGreater(sum(z["flugzeuge"]), 0)
        self.assertTrue(any(minimum > -2 for minimum in z["kurven_min"]))

    def test_wuerfel_hat_sechs_seiten_mit_doppelter_drei_und_vier(self):
        with patch("backend.wuerfel.random.choice", side_effect=lambda seiten: seiten) as choice:
            seiten = wirf_verkehrswuerfel()
        choice.assert_called_once()
        self.assertEqual(Counter(seiten), {2: 1, 3: 2, 4: 2, 5: 1})

    def test_verkehr_blockiert_alle_spieleraktionen_und_spielerwuerfel(self):
        spiel = Spielplan("FRA")
        spiel.starte_spiel()
        vorher = spiel.zustand()
        self.assertEqual(vorher["phase"], "verkehr")
        self.assertEqual(vorher["verkehrswuerfel_offen"], 1)
        self.assertEqual(vorher["pilot_wuerfel"], [None] * 4)
        self.assertEqual(vorher["kopilot_wuerfel"], [None] * 4)
        self.assertFalse(spiel.wuerfeln_fuer_runde())
        for ergebnis in (spiel.platziere("pilot", 0, "ruder"),
                         spiel.trinke_kaffee("pilot", 0, 1),
                         spiel.benutze_neuwurf([0], []), spiel.rundenende()):
            self.assertFalse(ergebnis.erfolg)
            self.assertEqual(ergebnis.grund, "runde_nicht_bereit")
        self.assertEqual(spiel.moegliche_kaffee_deltas("pilot", 0), [])
        self.assertEqual(spiel.zustand(), vorher)

    def test_mehrere_wuerfe_stapeln_flugzeuge_und_geben_dann_spielerwuerfel_frei(self):
        spiel = Spielplan("FRA")
        spiel.landung.entfernung = 4  # Feld mit zwei Symbolen.
        spiel.starte_spiel()
        ziel_index = spiel.landung._index_fuer_entfernung(2)
        vorher = spiel.landung.flugzeuge[ziel_index]
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=3) as werfen:
            self.assertTrue(spiel.wirf_verkehrswuerfel().erfolg)
            self.assertEqual(spiel.phase, "verkehr")
            self.assertIsNone(spiel.pilot_wuerfel[0].augenzahl)
            self.assertTrue(spiel.wirf_verkehrswuerfel().erfolg)
            self.assertEqual(spiel.landung.flugzeuge[ziel_index], vorher + 2)
            self.assertEqual(spiel.phase, "platzieren")
            z = spiel.zustand()
            self.assertTrue(all(z["pilot_wuerfel_frei"] + z["kopilot_wuerfel_frei"]))
            self.assertEqual(z["verkehrswuerfe"], [{"wert": 3, "ziel_entfernung": 2}] * 2)
            self.assertFalse(spiel.wirf_verkehrswuerfel().erfolg)
            self.assertFalse(spiel.wuerfeln_fuer_runde())
            spiel.starte_spiel()  # Wiederholtes Setup darf keine zusätzlichen Würfe auslösen.
            self.assertEqual(spiel.zustand(), z)
            self.assertEqual(werfen.call_count, 2)

    def test_flughafen_ist_gueltiges_ziel_dahinter_entfaellt_der_flugverkehr(self):
        for wert, ziel in [(2, 1), (3, 0), (4, None), (5, None)]:
            with self.subTest(wert=wert):
                spiel = Spielplan("FRA")
                spiel.landung.entfernung = 2
                spiel.starte_spiel()
                vorher = spiel.landung.flugzeuge.copy()
                with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=wert):
                    ergebnis = spiel.wirf_verkehrswuerfel()
                self.assertTrue(ergebnis.erfolg)
                self.assertEqual(spiel.verkehrswuerfe, [{"wert": wert, "ziel_entfernung": ziel}])
                if ziel is None:
                    self.assertEqual(spiel.landung.flugzeuge, vorher)
                    self.assertIn("Glück gehabt", ergebnis.meldung)
                else:
                    vorher[spiel.landung._index_fuer_entfernung(ziel)] += 1
                    self.assertEqual(spiel.landung.flugzeuge, vorher)

    def test_stehenbleiben_loest_vor_naechster_runde_erneut_aus(self):
        spiel = Spielplan("FRA")
        spiel.starte_spiel()
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            spiel.wirf_verkehrswuerfel()
            self.assertTrue(platziere_runde(spiel).erfolg)
            self.assertEqual(spiel.landung.entfernung, 6)
            self.assertEqual(spiel.aktuelle_runde, 2)
            self.assertEqual(spiel.am_zug, "kopilot")
            self.assertEqual(spiel.verkehrswuerfel_offen, 1)
            self.assertEqual(spiel.verkehrswuerfe, [])
            self.assertFalse(spiel.wuerfeln_fuer_runde())
            vorher = sum(spiel.landung.flugzeuge)
            self.assertTrue(spiel.wirf_verkehrswuerfel("kopilot").erfolg)
            self.assertEqual(sum(spiel.landung.flugzeuge), vorher + 1)

    def test_bewegung_zaehlt_nur_symbole_des_neuen_aktuellen_felds(self):
        spiel = Spielplan("FRA")
        spiel.landung._flugzeugwuerfel[1] = 3  # Wird bei Bewegung 2 nur überflogen.
        spiel.starte_spiel()
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            spiel.wirf_verkehrswuerfel()
        self.assertTrue(platziere_runde(spiel, schub=5).erfolg)
        self.assertEqual(spiel.landung.entfernung, 4)
        self.assertEqual(spiel.verkehrswuerfel_offen, 2)
        self.assertEqual(spiel.phase, "verkehr")
        self.assertEqual(spiel.verkehrswuerfe, [])

    def test_multiplayer_rolle_und_bridge_synchronisieren_offene_wuerfe(self):
        with patch.object(bridge, "_spiel", None):
            self.assertEqual(bridge.wirf_verkehrswuerfel()["ergebnis"]["grund"], "kein_spiel_aktiv")
            vorher = bridge.neues_spiel("FRA")
            self.assertFalse(bridge.wirf_verkehrswuerfel("kopilot")["ergebnis"]["erfolg"])
            self.assertEqual(bridge.zustand(), vorher)
            with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
                antwort = bridge.wirf_verkehrswuerfel("pilot")
            self.assertTrue(antwort["ergebnis"]["erfolg"])
            self.assertEqual(antwort["zustand"]["phase"], "platzieren")
            self.assertEqual(antwort["zustand"]["verkehrswuerfe"], [{"wert": 2, "ziel_entfernung": 5}])

    def test_verkehr_auch_in_warteschleife_und_landerunde_aber_nicht_nach_spielende(self):
        spiel = Spielplan("FRA")
        spiel.landung.entfernung = 1
        spiel.landung.hoehe = 2000
        spiel.landung.flugzeuge = [0] * spiel.landung.get_laenge()
        spiel.landung._flugzeugwuerfel[-1] = 1
        spiel.starte_spiel()
        self.assertTrue(platziere_runde(spiel, schub=3).erfolg)
        self.assertTrue(spiel.warteschleife)
        self.assertEqual(spiel.verkehrswuerfel_offen, 1)
        with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
            spiel.wirf_verkehrswuerfel()
            self.assertTrue(platziere_runde(spiel).erfolg)
            self.assertTrue(spiel.letzte_runde)
            self.assertEqual(spiel.verkehrswuerfel_offen, 1)
            spiel.wirf_verkehrswuerfel()
        self.assertEqual(sum(spiel.landung.flugzeuge), 0)
        self.assertTrue(platziere_runde(spiel).verloren)  # Keine Bremsen: Spiel beendet.
        vorher = spiel.zustand()
        self.assertEqual(spiel.wirf_verkehrswuerfel().grund, "spiel_beendet")
        self.assertFalse(spiel.wuerfeln_fuer_runde())
        self.assertEqual(spiel.zustand(), vorher)

    def test_bisherige_flughaefen_starten_ohne_verkehrsphase(self):
        for code in ("MUC", "LHR", "TEST"):
            with self.subTest(code=code):
                spiel = Spielplan(code)
                spiel.starte_spiel()
                self.assertEqual(spiel.phase, "platzieren")
                self.assertTrue(all(spiel.zustand()["pilot_wuerfel_frei"]))
                self.assertFalse(spiel.wirf_verkehrswuerfel().erfolg)


if __name__ == "__main__":
    unittest.main()
