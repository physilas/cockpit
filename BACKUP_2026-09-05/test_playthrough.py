"""Nicht Teil des Spiels - ein Testskript, das viele Partien mit
zufaelligen (aber legalen) Zuegen durchspielt, um Abstuerze/Logikfehler in
der Engine aufzudecken, bevor wir das CLI draufsetzen."""
import random
import sys

sys.path.insert(0, ".")
from backend.spiel import Spiel

ALLE_FELDER = [
    "ruder_pilot", "ruder_kopilot", "schub_pilot", "schub_kopilot",
    "fahrwerk_12", "fahrwerk_34", "fahrwerk_56",
    "bremse_2", "bremse_4", "bremse_6",
    "funken_pilot", "funken_1_kopilot", "funken_2_kopilot",
    "klappen_12", "klappen_23", "klappen_45", "klappen_56",
    "kaffee_1", "kaffee_2", "kaffee_3",
]


def spiele_eine_partie(seed):
    random.seed(seed)
    spiel = Spiel("YUL")
    max_runden = 30  # Sicherheitsnetz gegen Endlosschleifen bei einem Bug

    while not spiel.vorbei and spiel.runde <= max_runden:
        spiel.wuerfeln()
        versuche_ohne_erfolg = 0
        while not spiel.alle_wuerfel_platziert() and not spiel.vorbei:
            farbe = spiel.wer_ist_dran()
            verfuegbar = spiel.verfuegbare_wuerfel(farbe)
            if not verfuegbar:
                break
            wuerfel = random.choice(verfuegbar)
            feld = random.choice(ALLE_FELDER)
            erfolg = spiel.platziere(wuerfel, feld)
            if not erfolg:
                versuche_ohne_erfolg += 1
                if versuche_ohne_erfolg > 500:
                    # Zufallsagent findet kein legales Feld mehr - kein
                    # Engine-Bug, einfach abbrechen und naechste Partie.
                    return "STUCK", spiel
                continue
            versuche_ohne_erfolg = 0
        if spiel.vorbei:
            break
        spiel.rundenende()

    ergebnis = "GEWONNEN" if spiel.gewonnen else ("VERLOREN(%s)" % spiel.grund)
    if not spiel.vorbei:
        ergebnis = "ABGEBROCHEN(max_runden)"
    return ergebnis, spiel


if __name__ == "__main__":
    ergebnisse = {}
    for seed in range(200):
        try:
            ergebnis, spiel = spiele_eine_partie(seed)
        except Exception as e:
            print(f"!!! CRASH bei seed={seed}: {type(e).__name__}: {e}")
            raise
        schluessel = ergebnis.split("(")[0]
        ergebnisse[schluessel] = ergebnisse.get(schluessel, 0) + 1

    print("Ergebnisse ueber 200 zufaellige Partien (keine Strategie, nur Legalitaet):")
    for k, v in sorted(ergebnisse.items()):
        print(f"  {k}: {v}")
    print("\nKeine Exceptions aufgetreten -> Engine ist strukturell stabil.")
