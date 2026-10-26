"""Logbook identities, mock separation and native/browser data contract."""
import json
import unittest
from collections import Counter
from unittest.mock import patch

from backend.katalog import landekatalog, logbuch_katalog
from backend.landung import FlughafenKonfigurationsfehler, Landung, flughafen_liste
from backend.spielplan import Spielplan


class KatalogTest(unittest.TestCase):
    def test_alle_21_varianten_eindeutig_mit_richtigen_modulen(self):
        scenarios = logbuch_katalog()["scenarios"]
        self.assertEqual(len(scenarios), 21)
        self.assertEqual(len({s["id"] for s in scenarios}), 21)
        self.assertEqual(len({s["code"] for s in scenarios}), 11)
        self.assertEqual(Counter(s["difficulty"] for s in scenarios), {"green": 6, "yellow": 7, "red": 5, "black": 3})
        by_id = {s["id"]: s for s in scenarios}
        self.assertEqual(by_id["PRG-green"]["modules"], ["kerosene"])
        self.assertEqual(by_id["PRG-green"]["ability_count"], 2)
        self.assertEqual(by_id["OSL-red"]["modules"], ["leak", "ice"])
        self.assertEqual(by_id["PBH-black"]["modules"], ["kerosene", "realtime"])

    def test_jede_originalstrecke_startet_mit_grenzen_und_ehrlichen_metadaten(self):
        for s in logbuch_katalog()["scenarios"]:
            with self.subTest(scenario=s["id"]):
                spiel = Spielplan(s["engine_code"], faehigkeitskarten=["control", "adaptation"][:s["ability_count"]])
                spiel.starte_spiel()
                z = spiel.zustand()
                self.assertEqual(z["szenario_id"], s["id"])
                self.assertFalse(z["mock"])
                self.assertFalse(z["uebung"])
                self.assertEqual(z["geplante_module"], s["modules"])
                self.assertEqual(spiel.landung.get_module(), s["modules"])
                self.assertEqual(spiel.landung.get_faehigkeitskarten(), s["ability_count"])
                self.assertEqual(z["entfernung"], len(s["track"]) - 1)
                self.assertEqual(z["flugzeuge"][0], int(s["track"][0].split()[0]))
                self.assertLessEqual(sum(z["flugzeuge"]), 12)
                self.assertTrue(all(-2 <= lo <= hi <= 2 for lo,hi in zip(z["kurven_min"],z["kurven_max"])))
                with patch("backend.spielplan.wirf_verkehrswuerfel", return_value=2):
                    while spiel.verkehrswuerfel_offen:
                        self.assertTrue(spiel.wirf_verkehrswuerfel().erfolg)
                self.assertEqual(spiel.phase, "platzieren")
                self.assertTrue(all(v is not None for v in spiel.zustand()["pilot_wuerfel"]))

    def test_varianten_sind_unterschiedlich_und_eigene_strecken_bleiben_erhalten(self):
        scenarios = landekatalog()["scenarios"]
        by_id = {s["id"]: s for s in scenarios}
        self.assertNotEqual(by_id["LHR-green"]["track"], by_id["LHR-yellow"]["track"])
        self.assertNotEqual(by_id["HND-green"]["track"], by_id["HND-red"]["track"])
        self.assertIn("custom-LHR", by_id)
        self.assertEqual(by_id["custom-LHR"]["engine_code"], "LHR")
        self.assertNotEqual(by_id["LHR-green"]["engine_code"], "LHR")
        self.assertEqual({s["engine_code"] for s in scenarios if s["kind"] == "custom"}, {s["code"] for s in flughafen_liste()})
        self.assertFalse(Spielplan("LHR").zustand()["mock"])

    def test_fotos_liefern_die_echten_laengen_verteilungen_und_hoehen(self):
        self.assertEqual(Landung("LOG_YUL_GREEN").get_initial_flugzeuge(), [0, 0, 1, 2, 1, 3, 2])
        self.assertEqual(Landung("LOG_LHR_GREEN").get_laenge(), 6)
        self.assertEqual(Landung("LOG_HND_GREEN").get_laenge(), 8)
        self.assertEqual(Landung("LOG_TGU_YELLOW").get_laenge(), 5)
        self.assertEqual(Landung("LOG_ATL_GREEN").get_flugzeugwuerfel()[0], 4)
        self.assertEqual(Landung("LOG_PRG_YELLOW").get_initial_flugzeuge(), [0, 0, 1, 3, 0, 3, 2, 3])
        self.assertEqual(Landung("LOG_HND_GREEN").get_neuwurf_hoehen(), [6000, 2000])
        self.assertEqual(Landung("LOG_HND_RED").get_neuwurf_hoehen(), [])
        self.assertEqual(Landung("LOG_HND_RED").geplante_module, ["kerosene", "intern"])
        self.assertEqual(Landung("LOG_KUL_BLACK").get_kurven_min()[3], -2)
        self.assertEqual(Landung("LOG_KUL_BLACK").get_kurven_max()[3], -2)
        self.assertEqual(Landung("LOG_PBH_BLACK").get_kurven_min()[4], 2)
        self.assertEqual(Landung("LOG_PBH_BLACK").get_kurven_max()[4], 2)

    def test_original_verkehr_verwirft_zu_grosse_wuerfe_und_begrenzt_vorrat(self):
        landung = Landung("LOG_LHR_GREEN")
        landung.entfernung = 1
        vorher = landung.flugzeuge.copy()
        self.assertIsNone(landung.add_flugzeug_fuer_verkehrswurf(5))
        self.assertEqual(landung.flugzeuge, vorher)
        self.assertEqual(landung.add_flugzeug_fuer_verkehrswurf(2), 0)
        self.assertEqual(landung.flugzeuge[-1], 3)
        voll = Landung("LOG_PRG_YELLOW")
        vorher = voll.flugzeuge.copy()
        self.assertIsNone(voll.add_flugzeug_fuer_verkehrswurf(2))
        self.assertEqual(voll.letzter_verkehr_grund, "vorrat_leer")
        self.assertEqual(voll.flugzeuge, vorher)
        self.assertTrue(voll.remove_flugzeug(2))
        self.assertEqual(voll.add_flugzeug_fuer_verkehrswurf(2), 6)
        self.assertEqual(sum(voll.flugzeuge), 12)
        spiel = Spielplan("LOG_PRG_YELLOW", faehigkeitskarten=["control", "adaptation"])
        spiel.landung.entfernung = 4
        spiel.starte_spiel()
        self.assertIn("vorrat", spiel.wirf_verkehrswuerfel().meldung.lower())

    def test_mock_strecken_bleiben_isoliert_fuer_modultests_verfuegbar(self):
        for s in logbuch_katalog()["scenarios"]:
            mock = Spielplan(f'MOCK_{s["code"]}_{s["difficulty"].upper()}', faehigkeitskarten=["control", "adaptation"][:s["ability_count"]])
            self.assertTrue(mock.zustand()["mock"])
            self.assertTrue(mock.zustand()["uebung"])
            self.assertEqual(mock.landung.get_laenge(), len(s["mock_track"]))
            self.assertEqual(mock.landung.verkehr_regel, "eigene")

    def test_unbekannte_mocks_und_pfade_werden_abgewiesen(self):
        for code in ["MOCK_NOPE_GREEN", "MOCK_YUL_PURPLE", "../MUC"]:
            with self.assertRaises(FlughafenKonfigurationsfehler):
                Landung(code)

    def test_browser_catalogue_matches_python(self):
        from pathlib import Path
        text = (Path(__file__).resolve().parents[1] / "frontend/web/js/landing-catalog.js").read_text()
        bundled = json.loads(text.split("window.LANDING_CATALOG = ", 1)[1].removesuffix(";\n"))
        expected = landekatalog()
        expected["scenarios"] = [s for s in expected["scenarios"] if s["kind"] == "logbook"]
        self.assertEqual(bundled, expected)
        self.assertEqual(len(bundled["scenarios"]), 21)
        self.assertFalse(any(s["id"].startswith("custom-") for s in bundled["scenarios"]))


if __name__ == "__main__":
    unittest.main()
