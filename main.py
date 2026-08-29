"""Kleiner Rauchtest fuer die Backend-Engine.

Das ist noch kein richtiges Spiel (keine Rundenschleife, keine Sieg-/
Verlustpruefung) - nur ein Nachweis, dass Spielplan.platziere_wuerfel() jetzt
tatsaechlich funktioniert: Farbe/Zahl werden geprueft, Fahrwerk/Landeklappen/
Bremsen-Schalter springen um, der Fluglage-Anzeiger dreht sich, Kaffee wird
gekocht. Einfach ausfuehren mit:

    python main.py

(von diesem Verzeichnis aus, damit die Paket-Imports funktionieren).
"""

from backend.wuerfel import Wuerfel
from backend.spielplan import Spielplan


def wuerfel_werfen(anzahl, besitzer):
    wuerfel = [Wuerfel(besitzer) for _ in range(anzahl)]
    for w in wuerfel:
        w.werfen()
    return wuerfel


def naechster_freier(wuerfel_liste):
    return next((w for w in wuerfel_liste if w.ist_verfuegbar()), None)


def versuch(spielplan, wuerfel, feld, hinweis=""):
    if wuerfel is None:
        print(f"{feld}: kein Wuerfel mehr uebrig")
        return
    erfolg = spielplan.platziere_wuerfel(wuerfel, feld)
    status = "OK" if erfolg else "ABGELEHNT"
    zusatz = f"  ({hinweis})" if hinweis else ""
    print(f"{feld}: Wuerfel={wuerfel.get_augenzahl()} [{wuerfel.get_besitzer()}] -> {status}{zusatz}")


def main():
    spielplan = Spielplan("YUL")

    pilot = wuerfel_werfen(4, "pilot")
    kopilot = wuerfel_werfen(4, "kopilot")
    print("Geworfen:")
    print("  Pilot:   ", [w.get_augenzahl() for w in pilot])
    print("  Co-Pilot:", [w.get_augenzahl() for w in kopilot])
    print()

    # Pflichtfelder: je 1 Wuerfel jeder Farbe auf Ruder und Triebwerke.
    print("-- Pflichtfelder --")
    versuch(spielplan, naechster_freier(pilot), "ruder_pilot")
    versuch(spielplan, naechster_freier(kopilot), "ruder_kopilot")
    print(f"  Fluglage-Anzeiger: {spielplan.get_ruder()} "
          f"(getrudelt: {spielplan.ruder_im_trudeln()})")
    versuch(spielplan, naechster_freier(pilot), "schub_pilot")
    versuch(spielplan, naechster_freier(kopilot), "schub_kopilot")
    print()

    # Falscher Versuch: irgendein Co-Pilot-Wuerfel auf einem Pilot-Feld.
    print("-- Farbvorgabe testen (sollte ABGELEHNT sein) --")
    versuch(spielplan, naechster_freier(kopilot), "bremse_2", "falsche Farbe")
    print()

    # Fahrwerk: beliebige Reihenfolge, aber Zahlvorgabe pro Feld.
    print("-- Fahrwerk (nur Pilot, beliebige Reihenfolge) --")
    rest_pilot = naechster_freier(pilot)
    versuch(spielplan, rest_pilot, "fahrwerk_34", "passt nur bei 3 oder 4")
    print(f"  Fahrwerk-Schalter: {spielplan.get_fahrwerke()}  |  "
          f"Schub-Schwellen [blau, orange]: {spielplan.get_schub_min()}")
    print()

    # Konzentration: letzter Pilot-Wuerfel kocht Kaffee.
    print("-- Konzentration / Kaffee --")
    letzter_pilot = naechster_freier(pilot)
    versuch(spielplan, letzter_pilot, "kaffee_1")
    print(f"  Kaffeevorrat: {spielplan.get_kaffees()}")

    # Kaffee einsetzen, um einen Co-Pilot-Wuerfel zu veraendern.
    ziel = naechster_freier(kopilot)
    if ziel is not None:
        vorher = ziel.get_augenzahl()
        geschafft = spielplan.trinke_kaffee(ziel, +2)
        print(f"  Kaffee trinken: Wuerfel {vorher} -> {ziel.get_augenzahl()} "
              f"(gewuenscht +2, angewendet {geschafft:+d}); "
              f"Kaffeevorrat jetzt {spielplan.get_kaffees()}")

    print()
    print("Rauchtest fertig - keine Exceptions, Engine steht.")


if __name__ == "__main__":
    main()
