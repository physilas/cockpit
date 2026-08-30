"""
Minimaler, aber spielbarer Terminal-Client für Cockpit.

Start (aus dem Ordner `skyteam/` heraus):
    python3 main.py [FLUGHAFEN-CODE]

Hinweis: Bewusst kein "Sichtschirm" zwischen den Spielern - beide Seiten
sehen hier denselben Bildschirm, ideal zum Testen der Engine. Für ein
echtes Koop-Erlebnis bräuchte es getrennte Ein-/Ausgaben (z.B. das
Web-Frontend mit zwei Browserfenstern, oder ein Hot-Seat-Modus mit
Bildschirm-Löschen zwischen den Zügen).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backend.spielplan import Spielplan  # noqa: E402
from frontend.terminal.displayer import Displayer  # noqa: E402

ZIELE_MIT_INDEX = {
    "fahrwerk": 3,
    "landeklappe": 4,
    "bremse": 3,
    "konzentration": 3,
}


def frage_int(prompt, minimum, maximum):
    while True:
        roh = input(prompt).strip()
        if roh.lower() in ("q", "quit", "exit"):
            raise KeyboardInterrupt
        try:
            wert = int(roh)
        except ValueError:
            print(f"Bitte eine Zahl zwischen {minimum} und {maximum} eingeben (oder 'q' zum Beenden).")
            continue
        if minimum <= wert <= maximum:
            return wert
        print(f"Bitte eine Zahl zwischen {minimum} und {maximum} eingeben.")


def spielzug(spiel):
    besitzer = spiel.am_zug
    verfuegbar = spiel.verfuegbare_wuerfel(besitzer)
    if not verfuegbar:
        print(f"{besitzer} hat keine verfügbaren Würfel mehr.")
        return

    liste = spiel._wuerfel_liste(besitzer)
    print(f"\n{besitzer.upper()} ist am Zug.")
    print("Verfügbare Würfel: " + ", ".join(
        f"{liste.index(w)}={w.get_augenzahl()}" for w in verfuegbar))

    if spiel.cockpit.kaffee_verfuegbar() > 0:
        kaffee = input("Kaffee einsetzen? Format '<wuerfel_index> <delta>' oder Enter zum Überspringen: ").strip()
        if kaffee:
            try:
                idx_str, delta_str = kaffee.split()
                spiel.trinke_kaffee(besitzer, int(idx_str), int(delta_str))
            except (ValueError, IndexError):
                print("Ungültiges Format, kein Kaffee eingesetzt.")

    wuerfel_index = frage_int("Welchen Würfel platzieren (Index)? ", 0, len(liste) - 1)

    ziele = ["ruder", "triebwerk", "funk", "konzentration"]
    if besitzer == "pilot":
        ziele += ["fahrwerk", "bremse"]
    else:
        ziele += ["landeklappe"]

    print("Ziele: " + ", ".join(f"{i}={z}" for i, z in enumerate(ziele)))
    ziel = ziele[frage_int("Auf welches Ziel platzieren (Index)? ", 0, len(ziele) - 1)]

    kwargs = {}
    if ziel in ZIELE_MIT_INDEX:
        kwargs["index"] = frage_int(f"Welcher Slot (0-{ZIELE_MIT_INDEX[ziel] - 1})? ", 0, ZIELE_MIT_INDEX[ziel] - 1)
    if ziel == "funk" and besitzer == "kopilot":
        kwargs["funk_feld"] = frage_int("Welches Funk-Feld (0 oder 1)? ", 0, 1)

    ergebnis = spiel.platziere(besitzer, wuerfel_index, ziel, **kwargs)
    if not ergebnis.erfolg:
        print(f"Nicht möglich: {ergebnis.grund}")
    elif ergebnis.meldung:
        print(ergebnis.meldung)


def main():
    flughafen = sys.argv[1] if len(sys.argv) > 1 else "MUC"
    spiel = Spielplan(flughafen)
    spiel.starte_spiel()
    displayer = Displayer(spiel)

    try:
        while spiel.status == "laeuft":
            displayer.display_spielplan()
            spielzug(spiel)

            if spiel.alle_wuerfel_platziert() and spiel.status == "laeuft":
                ergebnis = spiel.rundenende()
                print(f"\n--- Rundenende: {ergebnis.meldung} ---")
                if spiel.status == "laeuft":
                    input("Enter zum Würfeln der nächsten Runde...")
                    spiel.wuerfeln_fuer_runde()
    except KeyboardInterrupt:
        print("\nSpiel abgebrochen.")
        return

    displayer.display_spielplan()


if __name__ == "__main__":
    main()
