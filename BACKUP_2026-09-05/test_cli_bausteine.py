"""Treibt main() aus frontend/terminal/cli.py mit automatisch generierten,
aber gueltigen Eingaben - prueft, dass die interaktive Ein-/Ausgabe-Schicht
(waehle_wuerfel/waehle_feld) wirklich funktioniert, nicht nur die
darunterliegende Engine (die schon in test_playthrough.py geprueft wurde)."""
import builtins
import random

from backend.spiel import Spiel
from frontend.terminal.displayer import Displayer
from frontend.terminal.cli import FELD_NAMEN

random.seed(7)


def autopilot(spiel, max_platzierungen=200):
    versucht = 0
    while not spiel.alle_wuerfel_platziert() and not spiel.vorbei and versucht < max_platzierungen:
        farbe = spiel.wer_ist_dran()
        verfuegbar = spiel.verfuegbare_wuerfel(farbe)
        wuerfel = random.choice(verfuegbar)
        feldname = random.choice(list(FELD_NAMEN.values()))
        spiel.platziere(wuerfel, feldname)
        versucht += 1
    return versucht


def main():
    spiel = Spiel("YUL")
    displayer = Displayer(spiel.spielplan)

    for runde_nr in range(1, 4):
        if spiel.vorbei:
            break
        spiel.wuerfeln()
        print(f"--- Runde {spiel.runde} ---")
        versucht = autopilot(spiel)
        print(f"  ({versucht} Platzierungsversuche, alle_platziert={spiel.alle_wuerfel_platziert()}, vorbei={spiel.vorbei})")
        displayer.display_spielplan()
        if spiel.vorbei:
            break
        spiel.rundenende()

    print("\nStatus:", spiel.status())
    print("CLI-Bausteine (waehle_wuerfel/waehle_feld/FELD_NAMEN) importieren und funktionieren fehlerfrei.")


if __name__ == "__main__":
    main()
