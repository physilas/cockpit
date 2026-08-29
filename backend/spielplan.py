from .landung import Landung
from .wuerfelfelder import Wuerfelfelder


def _activate(task, index, sequential):
    if sequential and index > 0 and task[index - 1] == 0:
        return False
    if task[index] == 1:
        return False
    task[index] = 1
    return True


class Spielplan():

    # Benannte Cockpit-Felder, die einen Fahrwerk-/Landeklappen-/Bremsen-Schalter
    # ansteuern -> (Name der Aktivierungsliste, Index darin). Nur diese Felder
    # brauchen einen Eintrag hier; Ruder/Triebwerke werden gesondert behandelt
    # (siehe platziere_wuerfel), Funk/Konzentration brauchen keine Reihenfolge.
    FIELD_GROUPS = {
        'fahrwerk_12': ('fahrwerke', 0),
        'fahrwerk_34': ('fahrwerke', 1),
        'fahrwerk_56': ('fahrwerke', 2),
        'klappen_12': ('klappen', 0),
        'klappen_23': ('klappen', 1),
        'klappen_45': ('klappen', 2),
        'klappen_56': ('klappen', 3),
        'bremse_2': ('bremsen', 0),
        'bremse_4': ('bremsen', 1),
        'bremse_6': ('bremsen', 2),
    }
    RUDER_FELDER = ('ruder_pilot', 'ruder_kopilot')
    KAFFEE_FELDER = ('kaffee_1', 'kaffee_2', 'kaffee_3')

    def __init__(self, flughafen):

        self.landung = Landung(flughafen)
        self.wuerfelfelder = Wuerfelfelder()

        self.fahrwerke = [0, 0, 0]
        self.klappen = [0, 0, 0, 0]
        self.bremsen = [0, 0, 0]
        self.kaffees = 0
        self.ruder = 0

        if self.landung.get_schwierigkeit() <= 1:
            self.anzahl_neuwurf = 1
        else:
            self.anzahl_neuwurf = 0

        self.schub_min = self.compute_schub_min()
        self.bremsen_max = self.compute_bremsen_max()

    ### GETTERS ###

    def get_fahrwerke(self):
        return self.fahrwerke
    def get_klappen(self):
        return self.klappen
    def get_bremsen(self):
        return self.bremsen
    def get_ruder(self):
        return self.ruder
    def get_kaffees(self):
        return self.kaffees
    def get_anzahl_neuwurf(self):
        return self.anzahl_neuwurf
    def get_schub_min(self):
        return self.schub_min
    def get_bremsen_max(self):
        return self.bremsen_max

    ### METHODS ###

    def activate_fahrwerk(self, index):
        erfolg = _activate(self.fahrwerke, index, sequential=False)
        # WICHTIG: das Ergebnis muss zurueckgeschrieben werden, sonst bleiben
        # get_schub_min()-Aufrufe nach der ersten Aktivierung auf einem
        # veralteten Stand stehen (das war vorher ein stiller Bug).
        self.schub_min = self.compute_schub_min()
        return erfolg

    def activate_klappen(self, index):
        erfolg = _activate(self.klappen, index, sequential=True)
        self.schub_min = self.compute_schub_min()
        return erfolg

    def activate_bremsen(self, index):
        erfolg = _activate(self.bremsen, index, sequential=True)
        self.bremsen_max = self.compute_bremsen_max()
        return erfolg

    def compute_schub_min(self):
        return [5 + sum(self.fahrwerke), 9 + sum(self.klappen)]

    def compute_bremsen_max(self):
        return 2 * sum(self.bremsen)

    def koche_kaffee(self):
        if self.kaffees < 3:
            self.kaffees += 1

    def trinke_kaffee(self, wuerfel, delta):
        """Gibt Kaffeetassen aus, um den Wert von `wuerfel` um `delta`
        Schritte zu veraendern (delta>0: erhoehen, delta<0: verringern).
        Pro Tasse genau 1 Schritt; hoert vorzeitig auf, wenn entweder der
        Vorrat leer ist oder der Wuerfel an die 1/6-Grenze stoesst (kein
        Wraparound). Gibt zurueck, wie viele Schritte tatsaechlich
        angewendet wurden."""
        richtung = 1 if delta > 0 else -1
        angewendet = 0
        for _ in range(abs(delta)):
            if self.kaffees == 0:
                break
            if not wuerfel.veraendere_augenzahl(richtung):
                break
            self.kaffees -= 1
            angewendet += richtung
        return angewendet

    def bewege_ruder(self, N):
        self.ruder += N
        if self.ruder < -2 or self.ruder > 2:
            return False
        return True

    def ruder_im_trudeln(self):
        """True, sobald der Fluglage-Anzeiger ausserhalb von [-2, 2] steht
        (= sofortiger Verlust, siehe Handbuch S.5)."""
        return self.ruder < -2 or self.ruder > 2

    def benutze_neuwurf(self):
        if self.anzahl_neuwurf == 0:
            return False
        self.anzahl_neuwurf -= 1
        return True

    def platziere_wuerfel(self, wuerfel, feldname):
        """Versucht, `wuerfel` auf dem Cockpit-Feld `feldname` zu platzieren.

        Prueft Verfuegbarkeit, Farb- und Zahlvorgabe. Bei Fahrwerk-/
        Landeklappen-/Bremsen-Feldern wird sofort die Reihenfolge-Pruefung
        samt Schalter-/Aerodynamik-Marker-Update ausgeloest (ueber die
        bestehenden activate_*-Methoden). Bei Ruder-Feldern wird - sobald
        BEIDE Farben liegen - sofort die Differenz gebildet und der
        Fluglage-Anzeiger gedreht. Bei Konzentrations-Feldern wird sofort
        eine Kaffeetasse gekocht.

        Gibt True zurueck bei Erfolg, sonst False (dann wurde NICHTS
        veraendert - weder der Wuerfel noch das Feld noch irgendein
        Zaehler).
        """
        feld = getattr(self.wuerfelfelder, feldname, None)
        if feld is None:
            raise ValueError(f"Unbekanntes Feld: {feldname}")

        # Vorab-Pruefung, BEVOR irgendein Zustand veraendert wird - so bleibt
        # bei einer Ablehnung garantiert alles unveraendert (u.a. wichtig,
        # weil activate_fahrwerk/klappen/bremsen sonst schon den Schalter
        # umgelegt haetten, bevor wir merken, dass der Wuerfel gar nicht
        # verfuegbar war).
        if not wuerfel.verfuegbar or not feld.ist_frei():
            return False
        if not feld.erlaubt(wuerfel.get_besitzer(), wuerfel.get_augenzahl()):
            return False

        if feldname in self.FIELD_GROUPS:
            gruppe, index = self.FIELD_GROUPS[feldname]
            aktivieren = {
                'fahrwerke': self.activate_fahrwerk,
                'klappen': self.activate_klappen,
                'bremsen': self.activate_bremsen,
            }[gruppe]
            if not aktivieren(index):
                return False  # falsche Reihenfolge oder Feld schon aktiv

        if not wuerfel.platzieren(feld):
            # sollte nach den obigen Pruefungen nicht mehr vorkommen,
            # aber sicherheitshalber sauber abbrechen statt inkonsistent
            # weiterzumachen
            return False

        if feldname in self.KAFFEE_FELDER:
            self.koche_kaffee()

        if feldname in self.RUDER_FELDER:
            pilot_feld = self.wuerfelfelder.ruder_pilot
            kopilot_feld = self.wuerfelfelder.ruder_kopilot
            # Erst wenn BEIDE Felder belegt sind (= gerade eben der zweite
            # Wuerfel platziert wurde) wird verglichen - siehe Handbuch S.5.
            if not pilot_feld.ist_frei() and not kopilot_feld.ist_frei():
                diff = pilot_feld.value - kopilot_feld.value
                # Vorzeichen-Konvention: positiv = Richtung Pilot (blau),
                # negativ = Richtung Co-Pilot (orange). Wer den hoeheren
                # Wuerfel platziert hat, "gewinnt" die Drehrichtung.
                self.bewege_ruder(diff)

        return True
