"""Spielbares Terminal-Frontend fuer Sky Team.

Hotseat-Modus: beide Spieler teilen sich ein Terminal. Der Einfachheit
halber sind hier BEIDE Wuerfelsaetze sichtbar (keine Geheimhaltung wie am
echten Tisch mit Sichtschirmen) - das ist eine bewusste Vereinfachung fuer
diese erste spielbare Version, siehe Notizen.

Start (vom Projekt-Wurzelverzeichnis aus):
    python -m frontend.terminal.cli
"""

from backend.spiel import Spiel
from frontend.terminal.displayer import Displayer

FELD_NAMEN = {
    "1": "ruder_pilot", "2": "ruder_kopilot",
    "3": "schub_pilot", "4": "schub_kopilot",
    "5": "fahrwerk_12", "6": "fahrwerk_34", "7": "fahrwerk_56",
    "8": "bremse_2", "9": "bremse_4", "10": "bremse_6",
    "11": "funken_pilot", "12": "funken_1_kopilot", "13": "funken_2_kopilot",
    "14": "klappen_12", "15": "klappen_23", "16": "klappen_45", "17": "klappen_56",
    "18": "kaffee_1", "19": "kaffee_2", "20": "kaffee_3",
}


def zeige_feldliste():
    print("Felder:")
    for nr, name in FELD_NAMEN.items():
        print(f"   {nr:>2}: {name}")


def waehle_wuerfel(spiel, farbe):
    verfuegbar = spiel.verfuegbare_wuerfel(farbe)
    werte = [w.get_augenzahl() for w in verfuegbar]
    print(f"{farbe.capitalize()} ist dran. Deine Wuerfel: {werte}")
    while True:
        eingabe = input("  Welchen Wuerfel spielen (Wert eingeben, 'f' fuer Feldliste, 'q' zum Beenden)? ").strip()
        if eingabe.lower() == 'q':
            return None, True
        if eingabe.lower() == 'f':
            zeige_feldliste()
            continue
        if not eingabe.isdigit():
            print("  Bitte eine Zahl eingeben.")
            continue
        wert = int(eingabe)
        treffer = [w for w in verfuegbar if w.get_augenzahl() == wert]
        if not treffer:
            print(f"  Du hast keinen verfuegbaren Wuerfel mit Wert {wert}.")
            continue
        return treffer[0], False


def waehle_feld():
    while True:
        eingabe = input("  Auf welches Feld (Nummer, 'f' fuer Feldliste)? ").strip()
        if eingabe.lower() == 'f':
            zeige_feldliste()
            continue
        if eingabe in FELD_NAMEN:
            return FELD_NAMEN[eingabe]
        print("  Unbekannte Feldnummer - 'f' zeigt die Liste.")


def main():
    print("SKY TEAM - Terminal-Prototyp (YUL Montreal-Trudeau)")
    print("Hotseat: Wuerfel sind hier fuer beide sichtbar (keine Sichtschirme in dieser Version).\n")

    spiel = Spiel("YUL")
    displayer = Displayer(spiel.spielplan)

    while not spiel.vorbei:
        print(f"\n############ RUNDE {spiel.runde} ############")
        spiel.wuerfeln()
        displayer.display_spielplan()

        abgebrochen = False
        while not spiel.alle_wuerfel_platziert() and not spiel.vorbei:
            farbe = spiel.wer_ist_dran()
            wuerfel, quit_ = waehle_wuerfel(spiel, farbe)
            if quit_:
                abgebrochen = True
                break
            feldname = waehle_feld()
            erfolg = spiel.platziere(wuerfel, feldname)
            if not erfolg:
                print("  -> ABGELEHNT (falsches Feld/Farbe/Zahl oder schon belegt).")
                continue
            print(f"  -> OK: {farbe} hat {wuerfel.get_augenzahl()} auf {feldname} gelegt.")
            if spiel.vorbei:
                break
            displayer.display_spielplan()

        if abgebrochen:
            print("Abgebrochen.")
            return

        if spiel.vorbei:
            break

        input("\nAlle Wuerfel platziert - Enter fuer Sinkflug/Rundenende...")
        spiel.rundenende()

    print("\n" + "#" * 40)
    if spiel.gewonnen:
        print("GEWONNEN! Die Passagiere klatschen begeistert - sicher gelandet!")
    else:
        print(f"VERLOREN. Grund: {spiel.grund}")
    print("#" * 40)


if __name__ == "__main__":
    main()
