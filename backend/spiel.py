from .spielplan import Spielplan
from .wuerfel import Wuerfel

ANDERE_FARBE = {"pilot": "kopilot", "kopilot": "pilot"}


class Spiel():
    """Verwaltet den Rundenablauf rund um ein Spielplan-Objekt: Wuerfel
    werfen, wer ist dran, Platzieren, Rundenende (Sinkflug + Ankunfts-
    pruefung), bis das Spiel gewonnen oder verloren ist.

    Nicht Teil des Handbuchs, sondern die Orchestrierung, die es fuer ein
    tatsaechlich spielbares Programm zusaetzlich braucht.
    """

    def __init__(self, flughafen):
        self.spielplan = Spielplan(flughafen)
        self.wuerfel = {
            "pilot": [Wuerfel("pilot") for _ in range(4)],
            "kopilot": [Wuerfel("kopilot") for _ in range(4)],
        }
        self.runde = 1
        self.zuege_diese_runde = 0

        self.vorbei = False
        self.gewonnen = False
        self.grund = None

    ### PHASE 1: ABSPRACHE UND WUERFEL WERFEN ###

    def wuerfeln(self):
        """Wirft alle Wuerfel neu - zu Beginn einer Runde."""
        for w in self.wuerfel["pilot"] + self.wuerfel["kopilot"]:
            w.werfen()

    def neuwurf(self):
        """Gibt (falls vorhanden) einen Neuwurf-Marker aus: BEIDE Spieler
        duerfen dann beliebig viele ihrer noch nicht platzierten Wuerfel
        einmal neu werfen (Handbuch S.4). Gibt True zurueck, falls
        tatsaechlich ein Marker ausgegeben wurde."""
        if not self.spielplan.benutze_neuwurf():
            return False
        for farbe in ("pilot", "kopilot"):
            for w in self.wuerfel[farbe]:
                if w.ist_verfuegbar():
                    w.werfen()
        return True

    ### PHASE 2: WUERFEL PLATZIEREN ###

    def wer_ist_dran(self):
        """Wechselt strikt innerhalb der Runde ab. Wer beginnt, wechselt
        von Runde zu Runde (Handbuch S.4: 'Der Pfeil auf eurer Aktuellen
        Hoehe gibt an, wer zuerst am Zug ist').

        ANNAHME: hier einfach nach Rundenzahl alterniert (Runde 1 = Pilot).
        Falls die echte Hoehenleiste keine reine Alternierung zeigt,
        muesste das hier an die echten Pfeile angepasst werden."""
        start = "pilot" if self.runde % 2 == 1 else "kopilot"
        return start if self.zuege_diese_runde % 2 == 0 else ANDERE_FARBE[start]

    def verfuegbare_wuerfel(self, farbe=None):
        farben = [farbe] if farbe else ["pilot", "kopilot"]
        return [w for f in farben for w in self.wuerfel[f] if w.ist_verfuegbar()]

    def platziere(self, wuerfel, feldname):
        """Platziert `wuerfel` (ein Objekt aus self.wuerfel[...]) auf
        `feldname`. Lehnt ab, falls das Spiel vorbei ist oder gerade eine
        andere Farbe am Zug ist. Wertet danach sofort etwaige
        Verlustbedingungen aus (Trudeln, Kollision, Uebers-Ziel-hinaus,
        zu schnell fuer die Landung)."""
        if self.vorbei:
            return False
        if wuerfel.get_besitzer() != self.wer_ist_dran():
            return False

        erfolg = self.spielplan.platziere_wuerfel(wuerfel, feldname)
        if not erfolg:
            return False

        self.zuege_diese_runde += 1

        if self.spielplan.ist_verloren():
            self._beende(gewonnen=False, grund=self.spielplan.get_verlust_grund())

        return True

    def alle_wuerfel_platziert(self):
        return all(not w.ist_verfuegbar()
                   for liste in self.wuerfel.values() for w in liste)

    ### PHASE 3: RUNDENENDE ###

    def rundenende(self):
        """Sinkflug + Ankunftspruefung (Handbuch S.9-10). Aufrufen, sobald
        alle_wuerfel_platziert() True ist. Macht nichts, falls das Spiel
        schon vorbei ist."""
        if self.vorbei:
            return

        landung = self.spielplan.landung
        war_letzte_runde = self.spielplan.ist_letzte_runde()

        # Sinkflug: 1000ft runter, alle Wuerfel zurueck an die Spieler.
        landung.reduce_hoehe(1000)
        for feld in self.spielplan.wuerfelfelder.alle_felder().values():
            feld.zuruecksetzen()
        for liste in self.wuerfel.values():
            for w in liste:
                w.verfuegbar = True
                w.augenzahl = None

        if war_letzte_runde:
            self._beende(gewonnen=self.spielplan.pruefe_sieg(),
                          grund=None if self.spielplan.pruefe_sieg() else "landebedingungen_nicht_erfuellt")
            return

        am_flughafen = landung.ist_am_flughafen()
        am_boden = landung.ist_am_boden()

        if am_flughafen and am_boden:
            # Flughafen genau im richtigen Moment erreicht -> naechste
            # Runde ist die letzte.
            self.spielplan.setze_letzte_runde(True)
            self.spielplan.setze_warteschleife(False)
        elif am_flughafen and not am_boden:
            # Zu frueh am Flughafen -> Warteschleife, Entfernung einfrieren.
            self.spielplan.setze_warteschleife(True)
        elif am_boden and not am_flughafen:
            # Zu frueh auf dem Boden -> sofortiger Verlust.
            self._beende(gewonnen=False, grund="zu_frueh_am_boden")
            return
        else:
            self.spielplan.setze_warteschleife(False)

        self.runde += 1
        self.zuege_diese_runde = 0

    def _beende(self, gewonnen, grund):
        if self.vorbei:
            return
        self.vorbei = True
        self.gewonnen = gewonnen
        self.grund = grund

    ### STATUS ###

    def status(self):
        return {
            "runde": self.runde,
            "am_zug": None if self.vorbei else self.wer_ist_dran(),
            "warteschleife": self.spielplan.warteschleife,
            "letzte_runde": self.spielplan.letzte_runde,
            "vorbei": self.vorbei,
            "gewonnen": self.gewonnen,
            "grund": self.grund,
        }
