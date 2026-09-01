"""
Kein klassisches Unit-Test-File mit einzelnen, isolierten Assertions,
sondern ein "Fuzzer": spielt viele komplette Partien mit einem simplen,
regelkonformen Zufalls-Agenten durch, um Abstürze und Endlosschleifen
in der Spiel-Engine aufzudecken. Führe es aus mit:

    python3 -m tests.test_engine
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.spielplan import Spielplan  # noqa: E402

MAX_RUNDEN_SICHERHEITSNETZ = 40


def _versuche(spiel, besitzer, wuerfel_index, ziel, **kwargs):
    return spiel.platziere(besitzer, wuerfel_index, ziel, **kwargs)


def kluger_zug(spiel):
    """
    Kein optimaler Spieler, aber einer mit Grundstrategie (im Unterschied
    zu simuliere_zug's Brute-Force-Zufall), um öfter tatsächlich bis zur
    Landung zu kommen und damit auch Endspiel-Code (letzte Runde,
    Bremsen, Waagerecht-Check, Sieg) zu testen:
      - Ruder: versucht, per Kaffee den zweiten Würfel an den ersten
        anzugleichen (Differenz 0).
      - Triebwerk: zielt auf eine Summe zwischen den Aerodynamik-Markern.
      - Fahrwerk/Landeklappen/Bremsen: so früh wie möglich ausfahren.
      - Funk: räumt das nächste Hindernis vor der aktuellen Position.
    """
    besitzer = spiel.am_zug
    wuerfel_liste = spiel._wuerfel_liste(besitzer)
    verfuegbar = [i for i, w in enumerate(wuerfel_liste) if w.ist_verfuegbar()]
    if not verfuegbar:
        return False
    cockpit = spiel.cockpit

    eigenes_ruder = cockpit.ruder_pilot if besitzer == "pilot" else cockpit.ruder_kopilot
    anderes_ruder = cockpit.ruder_kopilot if besitzer == "pilot" else cockpit.ruder_pilot
    eigenes_schub = cockpit.schub_pilot if besitzer == "pilot" else cockpit.schub_kopilot

    # 0) Sicherheitsnetz: mit den verbleibenden Würfeln müssen Ruder UND
    # Triebwerk noch erreichbar sein (S.5 Pflichtfelder), sonst Verlust.
    noch_offene_pflicht = sum([eigenes_ruder.ist_frei(), eigenes_schub.ist_frei()])
    if len(verfuegbar) <= noch_offene_pflicht:
        if eigenes_ruder.ist_frei():
            ziel_wert = anderes_ruder.wuerfel.get_augenzahl() if not anderes_ruder.ist_frei() else None
            for i in verfuegbar:
                if ziel_wert is not None:
                    w = wuerfel_liste[i]
                    delta = ziel_wert - w.get_augenzahl()
                    if delta != 0 and abs(delta) <= cockpit.kaffee_verfuegbar():
                        spiel.trinke_kaffee(besitzer, i, delta)
                if _versuche(spiel, besitzer, i, "ruder"):
                    return True
        if eigenes_schub.ist_frei():
            for i in verfuegbar:
                if _versuche(spiel, besitzer, i, "triebwerk"):
                    return True

    # 1) Ruder, falls der Partner schon liegt: Wert angleichen (Differenz 0).
    if eigenes_ruder.ist_frei() and not anderes_ruder.ist_frei():
        ziel_wert = anderes_ruder.wuerfel.get_augenzahl()
        for i in verfuegbar:
            w = wuerfel_liste[i]
            delta = ziel_wert - w.get_augenzahl()
            if delta != 0 and abs(delta) <= cockpit.kaffee_verfuegbar():
                spiel.trinke_kaffee(besitzer, i, delta)
            if w.get_augenzahl() == ziel_wert:
                if _versuche(spiel, besitzer, i, "ruder"):
                    return True

    # 2) Fahrwerk/Landeklappen so früh wie möglich ausfahren (aber die
    # unter 0) reservierten Pflicht-Würfel bleiben unangetastet, da wir
    # hier nur ankommen, wenn noch genug Würfel übrig sind).
    gruppe = "fahrwerk" if besitzer == "pilot" else "landeklappe"
    status = cockpit.fahrwerk_ausgefahren if besitzer == "pilot" else cockpit.landeklappen_ausgefahren
    naechster = _erster_freier(status)
    if naechster < len(status):
        for i in verfuegbar:
            if _versuche(spiel, besitzer, i, gruppe, index=naechster):
                return True

    # 4) Bremsen (nur Pilot).
    if besitzer == "pilot":
        naechste_bremse = _erster_freier(cockpit.bremsen_aktiviert)
        if naechste_bremse < len(cockpit.bremsen_aktiviert):
            for i in verfuegbar:
                if _versuche(spiel, besitzer, i, "bremse", index=naechste_bremse):
                    return True

    # 5) Funk: nächstes Hindernis räumen.
    entfernung = spiel.landung.get_entfernung()
    for i in verfuegbar:
        wert = wuerfel_liste[i].get_augenzahl()
        ziel_e = entfernung + (wert - 1)
        idx = spiel.landung._index_fuer_entfernung(ziel_e)
        if idx is not None and spiel.landung.flugzeuge[idx] > 0:
            feld = 0 if besitzer == "pilot" else 0
            if _versuche(spiel, besitzer, i, "funk", funk_feld=0):
                return True

    # 6) Triebwerk, Ziel: Summe zwischen den Markern (moderate Geschwindigkeit).
    eigenes_schub = cockpit.schub_pilot if besitzer == "pilot" else cockpit.schub_kopilot
    anderes_schub = cockpit.schub_kopilot if besitzer == "pilot" else cockpit.schub_pilot
    if eigenes_schub.ist_frei():
        ziel_summe = (cockpit.aerodynamik_blau + cockpit.aerodynamik_orange) / 2
        if not anderes_schub.ist_frei():
            ziel_wert = round(ziel_summe - anderes_schub.wuerfel.get_augenzahl())
            ziel_wert = max(1, min(6, ziel_wert))
            for i in verfuegbar:
                w = wuerfel_liste[i]
                delta = ziel_wert - w.get_augenzahl()
                if delta != 0 and abs(delta) <= cockpit.kaffee_verfuegbar():
                    spiel.trinke_kaffee(besitzer, i, delta)
        for i in verfuegbar:
            if _versuche(spiel, besitzer, i, "triebwerk"):
                return True

    # 7) Rest: Konzentration (Kaffee sammeln) oder irgendein Pflichtfeld.
    for i in verfuegbar:
        for k in range(3):
            if _versuche(spiel, besitzer, i, "konzentration", index=k):
                return True
    for i in verfuegbar:
        if _versuche(spiel, besitzer, i, "ruder"):
            return True
        if _versuche(spiel, besitzer, i, "triebwerk"):
            return True

    return False


def _erster_freier(status_liste):
    for i, erledigt in enumerate(status_liste):
        if not erledigt:
            return i
    return len(status_liste)


def spiele_kluge_partie(flughafen="MUC"):
    spiel = Spielplan(flughafen)
    spiel.starte_spiel()
    sicherheitsnetz = 0
    while spiel.status == "laeuft" and sicherheitsnetz < MAX_RUNDEN_SICHERHEITSNETZ * 8 * 2:
        sicherheitsnetz += 1
        if not kluger_zug(spiel):
            break
        if spiel.alle_wuerfel_platziert():
            spiel.rundenende()
            if spiel.status == "laeuft":
                spiel.wuerfeln_fuer_runde()
    return spiel


def moegliche_ziele(spiel, besitzer):
    """Erzeugt alle aktuell (feld-technisch) legalen (ziel, kwargs)-Paare
    für IRGENDEINEN verfügbaren Würfel des Spielers - die konkrete
    Würfelwahl passiert danach in simuliere_zug()."""
    cockpit = spiel.cockpit
    ziele = []

    ziele.append(("ruder", {}))
    ziele.append(("triebwerk", {}))
    if besitzer == "pilot":
        ziele.append(("funk", {}))
        for i in range(3):
            ziele.append(("fahrwerk", {"index": i}))
        for i in range(3):
            ziele.append(("bremse", {"index": i}))
    else:
        ziele.append(("funk", {"funk_feld": 0}))
        ziele.append(("funk", {"funk_feld": 1}))
        for i in range(4):
            ziele.append(("landeklappe", {"index": i}))
    for i in range(3):
        ziele.append(("konzentration", {"index": i}))
    return ziele


def simuliere_zug(spiel):
    besitzer = spiel.am_zug
    wuerfel = spiel.verfuegbare_wuerfel(besitzer)
    if not wuerfel:
        return False

    random.shuffle(wuerfel)
    kandidaten = moegliche_ziele(spiel, besitzer)
    random.shuffle(kandidaten)

    wuerfel_liste = spiel._wuerfel_liste(besitzer)
    for w in wuerfel:
        idx = wuerfel_liste.index(w)
        for ziel, kwargs in kandidaten:
            ergebnis = spiel.platziere(besitzer, idx, ziel, **kwargs)
            if ergebnis.erfolg:
                return True
    return False


def spiele_eine_partie(flughafen="MUC", verbose=False):
    spiel = Spielplan(flughafen)
    spiel.starte_spiel()

    sicherheitsnetz = 0
    while spiel.status == "laeuft" and sicherheitsnetz < MAX_RUNDEN_SICHERHEITSNETZ * 8 * 2:
        sicherheitsnetz += 1
        fortschritt = simuliere_zug(spiel)
        if not fortschritt:
            # Niemand kann mehr legal platzieren (z.B. weil die übrigen
            # Würfel auf keinem freien Feld mehr passen) -> Simulation
            # bricht hier ab, um Endlosschleifen zu vermeiden. Das ist ein
            # Artefakt des simplen Zufalls-Agenten, kein Engine-Bug.
            break
        if spiel.alle_wuerfel_platziert():
            ergebnis = spiel.rundenende()
            if verbose:
                print(spiel.aktuelle_runde, ergebnis.meldung)
            if spiel.status == "laeuft":
                spiel.wuerfeln_fuer_runde()

    return spiel


def test_viele_zufallspartien():
    ausgaenge = {"gewonnen": 0, "verloren": 0, "unentschieden_abgebrochen": 0}
    for _ in range(200):
        spiel = spiele_eine_partie()
        if spiel.status == "laeuft":
            ausgaenge["unentschieden_abgebrochen"] += 1
        else:
            ausgaenge[spiel.status] += 1

    print("Ergebnisse über 200 simulierte Partien:", ausgaenge)
    # Kernaussage dieses Tests: es darf NICHT abstürzen, und praktisch
    # jede Partie muss zu einem klaren Sieg/Niederlage-Status kommen.
    assert ausgaenge["unentschieden_abgebrochen"] < 10, (
        "Zu viele Partien haben nicht sauber terminiert - "
        "vermutlich ein Deadlock in der Platzierungslogik."
    )


def test_gewinn_pfad_deterministisch():
    """
    Skriptet eine exakte Partie auf der hindernisfreien TEST-Strecke durch
    (Fahrwerk/Landeklappen/Bremsen komplett, Ruder immer ausgeglichen,
    Triebwerke passend zu den wandernden Aerodynamik-/Brems-Schwellen)
    und prüft, dass die Engine tatsächlich bis zum Sieg kommt. Das ist der
    wichtigste Test hier: er beweist, dass ein Sieg mit der aktuellen
    Implementierung überhaupt erreichbar ist (Warteschleife, Übergang zur
    letzten Runde, Bremsen-statt-Aerodynamik-Vergleich, Waagerecht-Check).
    """
    import math

    spiel = Spielplan("TEST")
    spiel.starte_spiel()

    def setze(besitzer, werte):
        for w, v in zip(spiel._wuerfel_liste(besitzer), werte):
            w.werfen()
            w.augenzahl = v
            w.platziert = False

    def split(summe):
        summe = max(2, min(12, summe))
        a = max(1, min(6, summe - 1))
        b = summe - a
        if b < 1:
            b, a = 1, summe - 1
        return a, b

    fahrwerk_werte = [1, 3, 5]
    bremse_werte = [2, 4, 6]

    runde = 0
    while spiel.status == "laeuft" and runde < 12:
        runde += 1
        i = min(runde - 1, 2)
        if runde == 1:
            k0, k0v, k1, k1v = 0, 1, 1, 2
        elif runde == 2:
            k0, k0v, k1, k1v = 2, 4, 3, 5
        else:
            k0, k0v, k1, k1v = 0, 1, 1, 2  # bereits erledigt, erneutes Platzieren ist wirkungslos aber gültig

        if spiel.letzte_runde:
            p_schub, k_schub = 3, 3  # <= Bremsstärke, siehe cockpit.bremsstaerke()
        else:
            ziel_summe = math.floor(spiel.cockpit.aerodynamik_blau) + 1
            p_schub, k_schub = split(ziel_summe)

        setze("pilot", [3, p_schub, fahrwerk_werte[i], bremse_werte[i]])
        setze("kopilot", [3, k_schub, k0v, k1v])

        queues = {
            "pilot": [(0, "ruder", {}), (1, "triebwerk", {}),
                      (2, "fahrwerk", {"index": i}), (3, "bremse", {"index": i})],
            "kopilot": [(0, "ruder", {}), (1, "triebwerk", {}),
                        (2, "landeklappe", {"index": k0}), (3, "landeklappe", {"index": k1})],
        }
        for _ in range(8):
            besitzer = spiel.am_zug
            idx, ziel, kwargs = queues[besitzer].pop(0)
            ergebnis = spiel.platziere(besitzer, idx, ziel, **kwargs)
            assert ergebnis.erfolg, (besitzer, idx, ziel, kwargs, ergebnis)

        spiel.rundenende()
        if spiel.status == "laeuft":
            spiel.wuerfeln_fuer_runde()

    assert spiel.status == "gewonnen", f"Erwarteter Sieg, aber Status ist {spiel.status} ({spiel.verlust_grund})"


def test_ruder_vorzeichen():
    """Bug #1: Pilot 5 / Kopilot 4 -> -1. Pilot 3 / Kopilot 5 -> +2."""
    from backend.spielplan import Spielplan

    spiel = Spielplan("TEST")
    spiel.starte_spiel()

    def lege_ruder(pilot_wert, kopilot_wert):
        spiel.pilot_wuerfel[0].werfen()
        spiel.pilot_wuerfel[0].augenzahl = pilot_wert
        spiel.pilot_wuerfel[0].platziert = False
        spiel.kopilot_wuerfel[0].werfen()
        spiel.kopilot_wuerfel[0].augenzahl = kopilot_wert
        spiel.kopilot_wuerfel[0].platziert = False
        erster, zweiter = ("pilot", "kopilot") if spiel.am_zug == "pilot" else ("kopilot", "pilot")
        spiel.platziere(erster, 0, "ruder")
        spiel.platziere(zweiter, 0, "ruder")

    lege_ruder(5, 4)
    assert spiel.cockpit.fluglage == -1, spiel.cockpit.fluglage

    spiel.cockpit.ruder_pilot.leere()
    spiel.cockpit.ruder_kopilot.leere()
    spiel.am_zug = "pilot"
    lege_ruder(3, 5)
    assert spiel.cockpit.fluglage == -1 + 2 == 1, spiel.cockpit.fluglage


def test_triebwerk_wartet_bis_alle_wuerfel_liegen():
    """
    Bugs #2/#3: eine Kollision, die spät in der Runde per Funk noch
    geräumt wird, darf NICHT vorzeitig zum Verlust führen - und Funk
    muss unabhängig davon funktionieren, ob die Triebwerke schon
    platziert wurden oder nicht.
    """
    from backend.spielplan import Spielplan

    spiel = Spielplan("MUC")
    spiel.starte_spiel()
    # Ein Flugzeug direkt vor die aktuelle Position setzen, das die
    # Triebwerke ohne Funk garantiert rammen würden.
    entfernung = spiel.landung.get_entfernung()
    idx = spiel.landung._index_fuer_entfernung(entfernung)
    spiel.landung.flugzeuge[idx] = 1

    def setze(besitzer, werte):
        for w, v in zip(spiel._wuerfel_liste(besitzer), werte):
            w.werfen()
            w.augenzahl = v
            w.platziert = False

    # Engine-Summe erzwingt eine Bewegung (>= Bewegung 1), OBWOHL das
    # Hindernis noch auf dem aktuellen Feld steht - das wird erst am
    # Rundenende ausgewertet, NACHDEM Funk das Feld geräumt hat.
    setze("pilot", [3, 4, 1, 2])       # ruder, triebwerk, fahrwerk, bremse
    setze("kopilot", [3, 4, 1, 2])     # ruder, triebwerk, funk(wert 1 -> aktuelle Position), landeklappe

    queues = {
        "pilot": [(0, "ruder", {}), (1, "triebwerk", {}), (2, "fahrwerk", {"index": 0}), (3, "bremse", {"index": 0})],
        "kopilot": [(0, "ruder", {}), (1, "triebwerk", {}), (2, "funk", {"funk_feld": 0}), (3, "landeklappe", {"index": 0})],
    }
    for _ in range(8):
        besitzer = spiel.am_zug
        idx2, ziel, kwargs = queues[besitzer].pop(0)
        ergebnis = spiel.platziere(besitzer, idx2, ziel, **kwargs)
        assert ergebnis.erfolg, (besitzer, idx2, ziel, kwargs, ergebnis)
        # Zentrale Behauptung von Bug #2: während der Runde darf NIE ein
        # Sieg/Verlust ausgelöst werden (außer durch Trudeln, hier nicht der Fall).
        assert spiel.status == "laeuft", f"Vorzeitige Auswertung während der Runde: {ergebnis}"

    ergebnis = spiel.rundenende()
    assert spiel.status == "laeuft", f"Fälschlich verloren, obwohl Funk das Hindernis geräumt hat: {ergebnis}"


def test_funk_zielt_richtig_unabhaengig_von_reihenfolge():
    """Bug #3 direkt: Funk zählt Richtung Flughafen (sinkende Entfernung,
    siehe S.7-Beispiel/Foto), und das bleibt korrekt unabhängig davon, ob
    Triebwerke in derselben Runde schon platziert wurden."""
    from backend.spielplan import Spielplan

    spiel = Spielplan("MUC")
    spiel.starte_spiel()
    spiel.landung.entfernung = 3  # wie im gemeldeten Bug: "an Position 3"
    start_entfernung = spiel.landung.get_entfernung()
    ziel_entfernung = start_entfernung - 2  # mit einer 3 erreichbar: current - (3-1) = 1
    idx = spiel.landung._index_fuer_entfernung(ziel_entfernung)
    spiel.landung.flugzeuge[idx] = 1

    wuerfel = spiel._wuerfel_liste(spiel.am_zug)
    besitzer = spiel.am_zug
    for w in wuerfel:
        w.werfen()
    wuerfel[0].augenzahl = 3
    ergebnis = spiel.platziere(besitzer, 0, "funk", funk_feld=0)
    assert ergebnis.erfolg
    assert "entfernt" in ergebnis.meldung, ergebnis.meldung
    assert spiel.landung.flugzeuge[idx] == 0


def test_funk_am_rundenstart_kann_ueber_gesamte_verbleibende_strecke_zielen():
    """
    Regressionstest für den konkret gemeldeten Bug: in Runde 1 (Entfernung
    == laenge, also der denkbar ungünstigste Fall) muss ein Würfel > 1
    trotzdem ein Flugzeug entfernen können, wenn eines im Zielbereich
    liegt - vorher (falsche Zählrichtung) ging dort NUR die 1.
    """
    from backend.spielplan import Spielplan

    spiel = Spielplan("MUC")
    spiel.starte_spiel()
    entfernung = spiel.landung.get_entfernung()  # == laenge (7) in Runde 1
    ziel_entfernung = entfernung - 2  # mit einer 3 erreichbar
    idx = spiel.landung._index_fuer_entfernung(ziel_entfernung)
    spiel.landung.flugzeuge[idx] = 1

    besitzer = spiel.am_zug
    wuerfel = spiel._wuerfel_liste(besitzer)
    for w in wuerfel:
        w.werfen()
    wuerfel[0].augenzahl = 3
    ergebnis = spiel.platziere(besitzer, 0, "funk", funk_feld=0)
    assert ergebnis.erfolg and "entfernt" in ergebnis.meldung, ergebnis.meldung
    assert spiel.landung.flugzeuge[idx] == 0


if __name__ == "__main__":
    test_viele_zufallspartien()
    test_gewinn_pfad_deterministisch()
    test_ruder_vorzeichen()
    test_triebwerk_wartet_bis_alle_wuerfel_liegen()
    test_funk_zielt_richtig_unabhaengig_von_reihenfolge()
    test_funk_am_rundenstart_kann_ueber_gesamte_verbleibende_strecke_zielen()
    print("Alle Regressionstests: OK")
