from .wuerfelfeld import Wuerfelfeld
from .regeln import (
    AERODYNAMIK_BLAU_START,
    AERODYNAMIK_ORANGE_START,
    AERODYNAMIK_SCHRITT,
    BREMSSTAERKE_PRO_AKTIVIERUNG,
    MAX_KAFFEETASSEN,
    RUDER_STALL_SCHWELLE,
    WUERFEL_MAX,
    WUERFEL_MIN,
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
        # Vorzeichen: (orange - blau) beim 2. Ruder-Würfel, siehe
        # platziere_ruder() - bestätigt am physischen Board.
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
        # Vorzeichen wie am physischen Board bestätigt: Pilot 5 / Kopilot 4
        # -> -1, Pilot 3 / Kopilot 5 -> +2. Das ist (orange - blau).
        differenz = orange - blau
        if differenz != 0:
            self.fluglage += differenz

        if self.ist_im_trudeln():
            return Ergebnis(True, verloren=True, grund="trudeln",
                             meldung="Ins Trudeln geraten - der Fluglage-Anzeiger hat das X erreicht.")
        return Ergebnis(True)

    ### TRIEBWERKE (S.6, S.10 für die letzte Runde) ###
    #
    # WICHTIG: Das Platzieren selbst hat KEINEN sofortigen Effekt mehr.
    # Die Auswertung (Bewegung/Kollision/"übers Ziel hinaus" bzw. der
    # Bremsen-Vergleich in der letzten Runde) passiert erst am
    # Rundenende, siehe loese_triebwerke_auf(). Das verhindert, dass
    # eine Kollision erkannt wird, obwohl ein Funk-Würfel später in
    # derselben Runde das Hindernis noch geräumt hätte - und ist die
    # einzige "echte" Gewinn-/Verlustauswertung, die NICHT sofort beim
    # Platzieren passiert (Ausnahme: Ruder/Trudeln, s.o.).

    def platziere_triebwerk(self, wuerfel):
        feld = self.schub_pilot if wuerfel.get_besitzer() == "pilot" else self.schub_kopilot
        if not feld.platziere(wuerfel):
            return Ergebnis(False, "feld_ungueltig")
        return Ergebnis(True)

    def triebwerk_geschwindigkeit(self):
        """Summe beider Triebwerk-Würfel, oder None falls noch nicht beide liegen."""
        if self.schub_pilot.ist_frei() or self.schub_kopilot.ist_frei():
            return None
        return self.schub_pilot.wuerfel.get_augenzahl() + self.schub_kopilot.wuerfel.get_augenzahl()

    def loese_triebwerke_auf(self, letzte_runde=False, warteschleife=False):
        """
        Wird von Spielplan.rundenende() aufgerufen, NACHDEM alle 8 Würfel
        der Runde platziert sind (siehe Kommentar oben).
        """
        geschwindigkeit = self.triebwerk_geschwindigkeit()
        if geschwindigkeit is None:
            # Sollte nie passieren, pflichtfelder_erfuellt() wird vorher geprüft.
            return Ergebnis(False, "triebwerke_nicht_platziert")

        if letzte_runde:
            # S.10: WICHTIG - Bremsen statt Aerodynamik in der letzten Runde.
            if geschwindigkeit > self.bremsstaerke():
                return Ergebnis(True, verloren=True, grund="zu_schnell_gelandet",
                                 meldung=f"Geschwindigkeit {geschwindigkeit} überschreitet die Bremsstärke "
                                         f"({self.bremsstaerke()}) - über die Landebahn hinausgeschossen.")
            return Ergebnis(True, meldung=f"Geschwindigkeit {geschwindigkeit}, Bremsstärke {self.bremsstaerke()}.")

        if warteschleife:
            # S.10 Sonderfall "Zu früh am Flughafen": Entfernungsleiste darf
            # nicht weiter bewegt werden, solange die Warteschleife läuft.
            return Ergebnis(True, meldung=f"Warteschleife: Geschwindigkeit {geschwindigkeit}, keine Bewegung.")

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

    def moegliche_kaffee_deltas(self, augenzahl):
        """
        Für die UI (Bug #5): alle Delta-Werte, die mit dem aktuellen
        Kaffeevorrat auf `augenzahl` angewendet werden dürfen (Ergebnis
        bleibt 1-6, |delta| <= Vorrat, delta != 0).
        """
        n = self.kaffeetassen
        return [
            d for d in range(-n, n + 1)
            if d != 0 and WUERFEL_MIN <= augenzahl + d <= WUERFEL_MAX
        ]

    ### SNAPSHOT FÜR DIE UI ###

    @staticmethod
    def _feld_wert(feld):
        if feld is None or feld.ist_frei():
            return None
        return {"wert": feld.wuerfel.get_augenzahl(), "besitzer": feld.wuerfel.get_besitzer()}

    def felder_snapshot(self):
        """
        Für die UI: der tatsächlich abgelegte Würfel (Wert + Besitzer)
        auf jedem einzelnen Feld, oder None wenn leer. Damit lässt sich
        JEDER Würfel, den der Partner gelegt hat, direkt anzeigen (Bug
        #4) - es gibt kein "verstecktes" Feld, nur die eigenen noch
        nicht gelegten Würfel bleiben unsichtbar (das übernimmt die
        Sichtschirm-Logik im Frontend, nicht das Cockpit).
        """
        fw = self._feld_wert
        return {
            "ruder": {"pilot": fw(self.ruder_pilot), "kopilot": fw(self.ruder_kopilot)},
            "triebwerk": {"pilot": fw(self.schub_pilot), "kopilot": fw(self.schub_kopilot)},
            "funk_pilot": [fw(self.funk_pilot)],
            "funk_kopilot": [fw(f) for f in self.funk_kopilot],
            "fahrwerk": [fw(f) for f in self.fahrwerk],
            "landeklappe": [fw(f) for f in self.landeklappen],
            "bremse": [fw(f) for f in self.bremsen],
            "konzentration": [fw(f) for f in self.konzentration],
        }

    ### KAFFEE (S.8) ###

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
