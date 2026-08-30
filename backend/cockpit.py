from .wuerfelfeld import Wuerfelfeld
from .regeln import (
    AERODYNAMIK_BLAU_START,
    AERODYNAMIK_ORANGE_START,
    AERODYNAMIK_SCHRITT,
    BREMSSTAERKE_PRO_AKTIVIERUNG,
    MAX_KAFFEETASSEN,
    RUDER_STALL_SCHWELLE,
)


def _erster_freier_index(status_liste):
    """Index des ersten noch nicht erledigten Eintrags, oder len() falls alle fertig."""
    for i, erledigt in enumerate(status_liste):
        if not erledigt:
            return i
    return len(status_liste)


class Ergebnis:
    """Rückgabewert einer Cockpit-Aktion: Erfolg/Misserfolg + evtl. sofortiger Spielausgang."""

    def __init__(self, erfolg, grund="", verloren=False, gewonnen=False, meldung=""):
        self.erfolg = erfolg
        self.grund = grund
        self.verloren = verloren
        self.gewonnen = gewonnen
        self.meldung = meldung

    def __bool__(self):
        return self.erfolg

    def __repr__(self):
        return f"Ergebnis(erfolg={self.erfolg}, grund={self.grund!r}, verloren={self.verloren})"


class Cockpit:
    """
    Alles, was NICHT auf der Entfernungs-/Höhenleiste passiert: die
    Würfelfelder und ihre Aktionen (S.4-S.9).

    `landung` wird gebraucht, weil Triebwerke und Funk die
    Entfernungsleiste (in `landung`) verändern.
    """

    def __init__(self, landung):
        self.landung = landung

        # PFLICHTFELDER (S.5/S.6) - je 1 pro Farbe, jede Runde neu zu besetzen
        self.ruder_pilot = Wuerfelfeld("pilot")
        self.ruder_kopilot = Wuerfelfeld("kopilot")
        self.schub_pilot = Wuerfelfeld("pilot")
        self.schub_kopilot = Wuerfelfeld("kopilot")

        # FAHRWERK (S.7) - nur Pilotin, beliebige Reihenfolge
        self.fahrwerk = [
            Wuerfelfeld("pilot", zahlen={1, 2}),
            Wuerfelfeld("pilot", zahlen={3, 4}),
            Wuerfelfeld("pilot", zahlen={5, 6}),
        ]
        self.fahrwerk_ausgefahren = [False, False, False]

        # LANDEKLAPPEN (S.8) - nur Co-Pilot, STRIKTE Reihenfolge oben->unten
        self.landeklappen = [
            Wuerfelfeld("kopilot", zahlen={1, 2}),
            Wuerfelfeld("kopilot", zahlen={2, 3}),
            Wuerfelfeld("kopilot", zahlen={4, 5}),
            Wuerfelfeld("kopilot", zahlen={5, 6}),
        ]
        self.landeklappen_ausgefahren = [False, False, False, False]

        # BREMSEN (S.9) - nur Pilotin, STRIKTE Reihenfolge links->rechts
        self.bremsen = [
            Wuerfelfeld("pilot", zahlen={2}),
            Wuerfelfeld("pilot", zahlen={4}),
            Wuerfelfeld("pilot", zahlen={6}),
        ]
        self.bremsen_aktiviert = [False, False, False]

        # FUNK (S.7) - Pilotin 1 Feld, Co-Pilot 2 Felder, keine Zahlvorgabe
        self.funk_pilot = Wuerfelfeld("pilot")
        self.funk_kopilot = [Wuerfelfeld("kopilot"), Wuerfelfeld("kopilot")]

        # KONZENTRATION (S.8) - beide, keine Vorgabe, erzeugt Kaffee
        self.konzentration = [
            Wuerfelfeld(("pilot", "kopilot")),
            Wuerfelfeld(("pilot", "kopilot")),
            Wuerfelfeld(("pilot", "kopilot")),
        ]

        # AERODYNAMIK & BREMS-MARKER (S.3/S.7-S.9)
        self.aerodynamik_blau = AERODYNAMIK_BLAU_START
        self.aerodynamik_orange = AERODYNAMIK_ORANGE_START

        # FLUGLAGE-ANZEIGER (Ruder-Dial, S.5). 0 = waagerecht/level.
        # Positiv = Richtung Pilot (blau/links), negativ = Richtung Co-Pilot.
        self.fluglage = 0

        # KAFFEE (S.8)
        self.kaffeetassen = 0

    ### ALLGEMEINE HILFEN ###

    def alle_felder(self):
        """Alle Wuerfelfeld-Objekte, für UI/Statusabfragen."""
        felder = [
            self.ruder_pilot, self.ruder_kopilot,
            self.schub_pilot, self.schub_kopilot,
            self.funk_pilot, *self.funk_kopilot,
            *self.konzentration,
        ]
        felder += self.fahrwerk + self.landeklappen + self.bremsen
        return felder

    def leere_alle_felder(self):
        """Rundenende (S.9): alle Würfel zurücknehmen. Schalter/Marker bleiben stehen."""
        for feld in self.alle_felder():
            feld.leere()

    def pflichtfelder_erfuellt(self):
        """
        Verlierbedingung S.5: am Rundenende muss je 1 Würfel jeder Farbe
        auf Ruder UND je 1 Würfel jeder Farbe auf Triebwerken liegen.
        Muss VOR leere_alle_felder() aufgerufen werden!
        """
        return not any(
            feld.ist_frei()
            for feld in (self.ruder_pilot, self.ruder_kopilot, self.schub_pilot, self.schub_kopilot)
        )

    def ist_im_trudeln(self):
        return abs(self.fluglage) >= RUDER_STALL_SCHWELLE

    def ist_waagerecht(self):
        """Siegbedingung C (S.11)."""
        return self.fluglage == 0

    def fahrwerk_komplett(self):
        return all(self.fahrwerk_ausgefahren)

    def landeklappen_komplett(self):
        return all(self.landeklappen_ausgefahren)

    def bremsstaerke(self):
        """
        S.9-S.11: Bremsmarker beginnt links der 2 und rückt pro
        aktivierter Bremse ein Feld vor. Anhand des Beispiels auf S.11
        (Bremsen 2+4 aktiv, Geschwindigkeit 4 erfüllt "kleiner als
        Bremsstärke") modelliere ich die Stärke als
        2 * Anzahl aktivierter Bremsen und prüfe Geschwindigkeit <=
        Stärke (siehe cockpit.py Kommentar bei `pruefe_bremsen`).
        """
        return BREMSSTAERKE_PRO_AKTIVIERUNG * sum(self.bremsen_aktiviert)

    ### RUDER (S.5) ###

    def platziere_ruder(self, wuerfel):
        feld = self.ruder_pilot if wuerfel.get_besitzer() == "pilot" else self.ruder_kopilot
        anderes = self.ruder_kopilot if wuerfel.get_besitzer() == "pilot" else self.ruder_pilot

        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        if anderes.ist_frei():
            # Erster der beiden Ruder-Würfel - noch kein Effekt (S.5).
            return Ergebnis(True)

        # Zweiter Würfel liegt jetzt - vergleichen (S.5).
        blau = self.ruder_pilot.wuerfel.get_augenzahl()
        orange = self.ruder_kopilot.wuerfel.get_augenzahl()
        differenz = blau - orange
        if differenz != 0:
            richtung = 1 if differenz > 0 else -1
            self.fluglage += richtung * abs(differenz)

        if self.ist_im_trudeln():
            return Ergebnis(True, verloren=True, grund="trudeln",
                             meldung="Ins Trudeln geraten - der Fluglage-Anzeiger hat das X erreicht.")
        return Ergebnis(True)

    ### TRIEBWERKE (S.6, S.10 für die letzte Runde) ###

    def platziere_triebwerk(self, wuerfel, letzte_runde=False, warteschleife=False):
        feld = self.schub_pilot if wuerfel.get_besitzer() == "pilot" else self.schub_kopilot
        anderes = self.schub_kopilot if wuerfel.get_besitzer() == "pilot" else self.schub_pilot

        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        if anderes.ist_frei():
            return Ergebnis(True)

        geschwindigkeit = self.schub_pilot.wuerfel.get_augenzahl() + self.schub_kopilot.wuerfel.get_augenzahl()

        if warteschleife and not letzte_runde:
            # S.10 Sonderfall "Zu früh am Flughafen": Entfernungsleiste darf
            # nicht weiter bewegt werden, solange die Warteschleife läuft.
            return Ergebnis(True, meldung=f"Warteschleife: Geschwindigkeit {geschwindigkeit}, keine Bewegung.")

        if letzte_runde:
            # S.10: WICHTIG - Bremsen statt Aerodynamik in der letzten Runde.
            if geschwindigkeit > self.bremsstaerke():
                return Ergebnis(True, verloren=True, grund="zu_schnell_gelandet",
                                 meldung=f"Geschwindigkeit {geschwindigkeit} überschreitet die Bremsstärke "
                                         f"({self.bremsstaerke()}) - über die Landebahn hinausgeschossen.")
            return Ergebnis(True, meldung=f"Geschwindigkeit {geschwindigkeit}, Bremsstärke {self.bremsstaerke()}.")

        # Normale Runde: Bewegung anhand der Aerodynamik-Marker (S.6).
        if geschwindigkeit < self.aerodynamik_blau:
            bewegung = 0
        elif geschwindigkeit < self.aerodynamik_orange:
            bewegung = 1
        else:
            bewegung = 2

        if bewegung > 0:
            entfernung = self.landung.get_entfernung()
            if bewegung > entfernung:
                return Ergebnis(True, verloren=True, grund="uebers_ziel_hinaus",
                                 meldung="Über den Flughafen hinausgeschossen.")
            if self.landung.flugzeuge_an_aktueller_position() > 0:
                return Ergebnis(True, verloren=True, grund="kollision",
                                 meldung="Kollision mit einem Flugzeug auf der Entfernungsleiste.")
            self.landung.reduce_entfernung(bewegung)

        return Ergebnis(True, meldung=f"Geschwindigkeit {geschwindigkeit}, Entfernungsleiste um {bewegung} bewegt.")

    ### FUNK (S.7) ###

    def platziere_funk(self, wuerfel, feld_index=0):
        feld = self.funk_pilot if wuerfel.get_besitzer() == "pilot" else self.funk_kopilot[feld_index]
        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        wert = wuerfel.get_augenzahl()
        ziel_entfernung = self.landung.get_entfernung() + (wert - 1)
        entfernt = self.landung.remove_flugzeug_bei_entfernung(ziel_entfernung)
        meldung = (
            f"Flugzeug bei Entfernung {ziel_entfernung} entfernt."
            if entfernt
            else "Kein Flugzeug auf dem abgezählten Feld (oder Würfelwert zu hoch) - kein Effekt."
        )
        return Ergebnis(True, meldung=meldung)

    ### FAHRWERK (S.7, beliebige Reihenfolge) ###

    def platziere_fahrwerk(self, wuerfel, index):
        if index < 0 or index >= len(self.fahrwerk):
            return Ergebnis(False, "ungueltiger_index")
        feld = self.fahrwerk[index]
        if self.fahrwerk_ausgefahren[index]:
            # Bereits grünes Licht - Platzieren ist erlaubt, aber wirkungslos.
            if not feld.ist_frei() or not feld.erlaubt(wuerfel.get_besitzer(), wuerfel.get_augenzahl()):
                return Ergebnis(False, "feld_ungueltig")
            feld.platziere(wuerfel)
            return Ergebnis(True, meldung="Fahrwerksteil bereits ausgefahren - kein Effekt.")

        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        self.fahrwerk_ausgefahren[index] = True
        self.aerodynamik_blau += AERODYNAMIK_SCHRITT
        return Ergebnis(True, meldung="Fahrwerksteil ausgefahren.")

    ### LANDEKLAPPEN (S.8, strikte Reihenfolge) ###

    def platziere_landeklappe(self, wuerfel, index):
        if index < 0 or index >= len(self.landeklappen):
            return Ergebnis(False, "ungueltiger_index")
        naechste_faellige = _erster_freier_index(self.landeklappen_ausgefahren)
        feld = self.landeklappen[index]

        if self.landeklappen_ausgefahren[index]:
            if not feld.ist_frei() or not feld.erlaubt(wuerfel.get_besitzer(), wuerfel.get_augenzahl()):
                return Ergebnis(False, "feld_ungueltig")
            feld.platziere(wuerfel)
            return Ergebnis(True, meldung="Landeklappe bereits ausgefahren - kein Effekt.")

        if index != naechste_faellige:
            return Ergebnis(False, "falsche_reihenfolge")

        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        self.landeklappen_ausgefahren[index] = True
        self.aerodynamik_orange += AERODYNAMIK_SCHRITT
        return Ergebnis(True, meldung="Landeklappe ausgefahren.")

    ### BREMSEN (S.9, strikte Reihenfolge) ###

    def platziere_bremse(self, wuerfel, index):
        if index < 0 or index >= len(self.bremsen):
            return Ergebnis(False, "ungueltiger_index")
        naechste_faellige = _erster_freier_index(self.bremsen_aktiviert)
        feld = self.bremsen[index]

        if self.bremsen_aktiviert[index]:
            if not feld.ist_frei() or not feld.erlaubt(wuerfel.get_besitzer(), wuerfel.get_augenzahl()):
                return Ergebnis(False, "feld_ungueltig")
            feld.platziere(wuerfel)
            return Ergebnis(True, meldung="Bremse bereits aktiviert - kein Effekt.")

        if index != naechste_faellige:
            return Ergebnis(False, "falsche_reihenfolge")

        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        self.bremsen_aktiviert[index] = True
        return Ergebnis(True, meldung=f"Bremse aktiviert, Bremsstärke jetzt {self.bremsstaerke()}.")

    ### KONZENTRATION / KAFFEE (S.8) ###

    def platziere_konzentration(self, wuerfel, index):
        if index < 0 or index >= len(self.konzentration):
            return Ergebnis(False, "ungueltiger_index")
        feld = self.konzentration[index]
        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")

        if self.kaffeetassen < MAX_KAFFEETASSEN:
            self.kaffeetassen += 1
            return Ergebnis(True, meldung="Kaffee gekocht.")
        return Ergebnis(True, meldung="Kaffeevorrat bereits voll (3) - kein Effekt.")

    def kaffee_verfuegbar(self):
        return self.kaffeetassen

    def trinke_kaffee(self, wuerfel, delta):
        """
        Verändert die Augenzahl eines noch NICHT platzierten Würfels um
        `delta` (positiv oder negativ), sofern genug Tassen im Vorrat
        sind. Verbraucht abs(delta) Tassen. (S.8)
        """
        kosten = abs(delta)
        if kosten == 0:
            return Ergebnis(True)
        if wuerfel.ist_platziert():
            return Ergebnis(False, "wuerfel_bereits_platziert")
        if kosten > self.kaffeetassen:
            return Ergebnis(False, "nicht_genug_kaffee")
        tatsaechlich = wuerfel.veraendere(delta)
        self.kaffeetassen -= abs(tatsaechlich)
        return Ergebnis(True, meldung=f"Würfel um {tatsaechlich} verändert.")
