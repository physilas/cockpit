from .cockpit import Cockpit, Ergebnis
from .landung import Landung
from .wuerfel import Wuerfel

# S.4: "Legt 1 Neuwurf-Plättchen auf jedes Neuwurf-Symbol der Höhenleiste."
# ANNAHME: Die Höhenleiste ist (anders als die Entfernungsleiste) für alle
# Flughäfen gleich, daher hier als globale Konstante. Das Beispiel auf S.4
# nennt "wie in Runde 1 bei 6000 Fuß" als einen der beiden Symbolplätze -
# den zweiten Wert (2000 Fuß) konnte ich auf den Fotos nicht zuverlässig
# erkennen. Bitte am echten Höhenleiste-Bauteil prüfen und ggf. anpassen!
NEUWURF_HOEHEN = [6000, 2000]


class Spielplan:
    """
    Orchestriert eine komplette Partie Cockpit: Würfelpools,
    Zugreihenfolge, Neuwurf-Plättchen, Rundenablauf (S.4-S.11) und
    Sieg-/Verlustauswertung.

    Name/Modul bewusst "spielplan.py"/"Spielplan" belassen, damit
    bestehende Importe (frontend/terminal/displayer.py) weiter
    funktionieren.
    """

    def __init__(self, flughafen="MUC", startspieler="pilot"):
        self.landung = Landung(flughafen)
        self.cockpit = Cockpit(self.landung)

        self.pilot_wuerfel = [Wuerfel("pilot") for _ in range(4)]
        self.kopilot_wuerfel = [Wuerfel("kopilot") for _ in range(4)]

        self.aktuelle_runde = 1
        self.status = "laeuft"  # "laeuft" | "gewonnen" | "verloren"
        self.verlust_grund = None
        self.letzte_meldung = ""

        self.letzte_runde = False
        self.warteschleife = False

        # ANNAHME: Startspieler alterniert jede Runde (S.4 sagt nur, dass
        # ein Pfeil auf der Höhenleiste dies anzeigt und Runde 1 mit der
        # Pilotin beginnt). Bitte am Bauteil prüfen, ob das Muster wirklich
        # eine einfache Alternierung ist.
        self.startspieler = startspieler
        self.am_zug = startspieler

        self._genutzte_neuwurf_hoehen = set()
        self.neuwurf_plaettchen = 0

    ### SETUP / RUNDENABLAUF ###

    def starte_spiel(self):
        """Vor Runde 1: evtl. Neuwurf-Plättchen bei Starthöhe einsammeln, würfeln."""
        self._sammle_neuwurf_plaettchen()
        self.wuerfeln_fuer_runde()

    def wuerfeln_fuer_runde(self):
        """Phase 1 (S.4): alle 8 Würfel neu werfen."""
        for w in self.pilot_wuerfel + self.kopilot_wuerfel:
            w.werfen()

    def _sammle_neuwurf_plaettchen(self):
        hoehe = self.landung.get_hoehe()
        if hoehe in NEUWURF_HOEHEN and hoehe not in self._genutzte_neuwurf_hoehen:
            self._genutzte_neuwurf_hoehen.add(hoehe)
            self.neuwurf_plaettchen += 1

    def benutze_neuwurf(self, pilot_indizes=(), kopilot_indizes=()):
        """
        S.4: gibt ein Neuwurf-Plättchen aus, damit BEIDE Spieler beliebig
        viele ihrer noch nicht platzierten Würfel einmal neu werfen dürfen.
        `pilot_indizes`/`kopilot_indizes`: Indizes (0-3) der Würfel, die
        neu geworfen werden sollen.
        """
        if self.neuwurf_plaettchen <= 0:
            return Ergebnis(False, "kein_neuwurf_plaettchen")
        for i in pilot_indizes:
            w = self.pilot_wuerfel[i]
            if w.ist_verfuegbar():
                w.werfen()
        for i in kopilot_indizes:
            w = self.kopilot_wuerfel[i]
            if w.ist_verfuegbar():
                w.werfen()
        self.neuwurf_plaettchen -= 1
        return Ergebnis(True, meldung="Neuwurf-Plättchen eingelöst.")

    ### WÜRFEL PLATZIEREN (S.4-S.9) ###

    def _wuerfel_liste(self, besitzer):
        return self.pilot_wuerfel if besitzer == "pilot" else self.kopilot_wuerfel

    def verfuegbare_wuerfel(self, besitzer):
        return [w for w in self._wuerfel_liste(besitzer) if w.ist_verfuegbar()]

    def alle_wuerfel_platziert(self):
        """S.9: 'Sobald ihr alle 8 Würfel platziert habt' - über die Würfel
        selbst geprüft, nicht über die (viel zahlreicheren) Felder."""
        return all(w.ist_platziert() for w in self.pilot_wuerfel + self.kopilot_wuerfel)

    def trinke_kaffee(self, besitzer, wuerfel_index, delta):
        """Kaffee auf einen eigenen, noch nicht platzierten Würfel anwenden (S.8)."""
        wuerfel = self._wuerfel_liste(besitzer)[wuerfel_index]
        return self.cockpit.trinke_kaffee(wuerfel, delta)

    def moegliche_kaffee_deltas(self, besitzer, wuerfel_index):
        wuerfel = self._wuerfel_liste(besitzer)[wuerfel_index]
        return self.cockpit.moegliche_kaffee_deltas(wuerfel.get_augenzahl())

    def platziere(self, besitzer, wuerfel_index, ziel, index=None, funk_feld=0):
        """
        Zentrale Aktion: `besitzer` platziert seinen Würfel Nr.
        `wuerfel_index` (0-3) auf `ziel` in {"ruder", "triebwerk", "funk",
        "fahrwerk", "landeklappe", "bremse", "konzentration"}.
        `index` wird für die Mehrfach-Felder (Fahrwerk/Landeklappen/
        Bremsen/Konzentration) gebraucht, `funk_feld` (0/1) wählt beim
        Co-Piloten zwischen dessen zwei Funk-Feldern.

        Gibt ein Ergebnis zurück und wechselt bei Erfolg den Zug (S.4 A).
        """
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if besitzer != self.am_zug:
            return Ergebnis(False, "nicht_am_zug")
        wuerfel_liste = self._wuerfel_liste(besitzer)
        if wuerfel_index < 0 or wuerfel_index >= len(wuerfel_liste):
            return Ergebnis(False, "ungueltiger_wuerfel_index")
        wuerfel = wuerfel_liste[wuerfel_index]
        if not wuerfel.ist_verfuegbar():
            return Ergebnis(False, "wuerfel_nicht_verfuegbar")

        if ziel == "ruder":
            ergebnis = self.cockpit.platziere_ruder(wuerfel)
        elif ziel == "triebwerk":
            ergebnis = self.cockpit.platziere_triebwerk(wuerfel)
        elif ziel == "funk":
            feld_index = funk_feld if besitzer == "kopilot" else 0
            ergebnis = self.cockpit.platziere_funk(wuerfel, feld_index)
        elif ziel == "fahrwerk":
            ergebnis = self.cockpit.platziere_fahrwerk(wuerfel, index)
        elif ziel == "landeklappe":
            ergebnis = self.cockpit.platziere_landeklappe(wuerfel, index)
        elif ziel == "bremse":
            ergebnis = self.cockpit.platziere_bremse(wuerfel, index)
        elif ziel == "konzentration":
            ergebnis = self.cockpit.platziere_konzentration(wuerfel, index)
        else:
            return Ergebnis(False, "unbekanntes_ziel")

        if not ergebnis.erfolg:
            return ergebnis

        self.letzte_meldung = ergebnis.meldung
        if ergebnis.verloren:
            self.status = "verloren"
            self.verlust_grund = ergebnis.grund
            return ergebnis

        self.am_zug = "kopilot" if besitzer == "pilot" else "pilot"
        return ergebnis

    ### RUNDENENDE (S.9-S.11) ###

    def rundenende(self):
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if not self.alle_wuerfel_platziert():
            return Ergebnis(False, "noch_nicht_alle_wuerfel_platziert")

        # Verlierbedingung S.5: Pflichtfelder müssen VOR dem Leeren geprüft werden.
        if not self.cockpit.pflichtfelder_erfuellt():
            self.status = "verloren"
            self.verlust_grund = "pflichtfelder_nicht_erfuellt"
            return Ergebnis(True, verloren=True, grund=self.verlust_grund,
                             meldung="Nicht auf jeder Pflichtfeld-Farbe lag ein Würfel - Absturz.")

        # Triebwerke werden erst JETZT ausgewertet - nicht mehr sofort beim
        # Platzieren des 2. Würfels. So kann ein Funk-Würfel, der später in
        # derselben Runde gelegt wird, ein Hindernis noch rechtzeitig
        # räumen, bevor auf Kollision geprüft wird. Einzige Ausnahme bleibt
        # das Ruder/Trudeln (sofort beim 2. Würfel, siehe cockpit.py).
        triebwerk_ergebnis = self.cockpit.loese_triebwerke_auf(
            letzte_runde=self.letzte_runde, warteschleife=self.warteschleife
        )
        self.letzte_meldung = triebwerk_ergebnis.meldung
        if triebwerk_ergebnis.verloren:
            self.status = "verloren"
            self.verlust_grund = triebwerk_ergebnis.grund
            return triebwerk_ergebnis

        if self.letzte_runde:
            return self._werte_spielende_aus()

        # Sinkflug (S.9): 1 Feld runter, alle Würfel zurücknehmen.
        self.landung.reduce_hoehe(1)
        self.cockpit.leere_alle_felder()
        self.aktuelle_runde += 1
        self._sammle_neuwurf_plaettchen()

        am_flughafen = self.landung.ist_am_flughafen()
        auf_hoehe_null = self.landung.ist_auf_hoehe_null()

        if am_flughafen and auf_hoehe_null:
            self.letzte_runde = True
            self.warteschleife = False
            self.am_zug = self._naechster_startspieler()
            return Ergebnis(True, meldung="Perfektes Timing - die letzte Runde beginnt!")

        if am_flughafen and not auf_hoehe_null:
            self.warteschleife = True
            self.am_zug = self._naechster_startspieler()
            return Ergebnis(True, meldung="Zu früh am Flughafen - ihr fliegt eine Warteschleife.")

        if auf_hoehe_null and not am_flughafen:
            self.status = "verloren"
            self.verlust_grund = "notlandung"
            return Ergebnis(True, verloren=True, grund="notlandung",
                             meldung="Boden erreicht, bevor der Flughafen erreicht wurde - Notlandung!")

        self.am_zug = self._naechster_startspieler()
        return Ergebnis(True, meldung=f"Runde {self.aktuelle_runde} beginnt.")

    def _naechster_startspieler(self):
        self.startspieler = "kopilot" if self.startspieler == "pilot" else "pilot"
        return self.startspieler

    def _werte_spielende_aus(self):
        gruende = []
        if not self.landung.ist_frei_von_flugzeugen():
            gruende.append("flugzeuge_uebrig")
        if not self.cockpit.fahrwerk_komplett():
            gruende.append("fahrwerk_unvollstaendig")
        if not self.cockpit.landeklappen_komplett():
            gruende.append("landeklappen_unvollstaendig")
        if not self.cockpit.ist_waagerecht():
            gruende.append("nicht_waagerecht")

        if gruende:
            self.status = "verloren"
            self.verlust_grund = ",".join(gruende)
            return Ergebnis(True, verloren=True, grund=self.verlust_grund,
                             meldung="Landung nicht sauber genug.")

        self.status = "gewonnen"
        return Ergebnis(True, gewonnen=True, meldung="Sicher gelandet - ihr habt gewonnen!")

    ### STATUS FÜR EIN FRONTEND ###

    def zustand(self):
        """Kompakter Snapshot für UI/Displayer - keine Spiellogik."""
        return {
            "status": self.status,
            "verlust_grund": self.verlust_grund,
            "letzte_meldung": self.letzte_meldung,
            "runde": self.aktuelle_runde,
            "letzte_runde": self.letzte_runde,
            "warteschleife": self.warteschleife,
            "am_zug": self.am_zug,
            "hoehe": self.landung.get_hoehe(),
            "entfernung": self.landung.get_entfernung(),
            "laenge": self.landung.get_laenge(),
            "flugzeuge": list(self.landung.get_flugzeuge()),
            "neuwurf_plaettchen": self.neuwurf_plaettchen,
            "kaffeetassen": self.cockpit.kaffeetassen,
            "fluglage": self.cockpit.fluglage,
            "aerodynamik_blau": self.cockpit.aerodynamik_blau,
            "aerodynamik_orange": self.cockpit.aerodynamik_orange,
            "bremsstaerke": self.cockpit.bremsstaerke(),
            "fahrwerk_ausgefahren": list(self.cockpit.fahrwerk_ausgefahren),
            "landeklappen_ausgefahren": list(self.cockpit.landeklappen_ausgefahren),
            "bremsen_aktiviert": list(self.cockpit.bremsen_aktiviert),
            "pilot_wuerfel": [w.get_augenzahl() for w in self.pilot_wuerfel],
            "kopilot_wuerfel": [w.get_augenzahl() for w in self.kopilot_wuerfel],
            "pilot_wuerfel_frei": [w.ist_verfuegbar() for w in self.pilot_wuerfel],
            "kopilot_wuerfel_frei": [w.ist_verfuegbar() for w in self.kopilot_wuerfel],
            "felder": self.cockpit.felder_snapshot(),
        }


if __name__ == "__main__":
    spiel = Spielplan("MUC")
    spiel.starte_spiel()
    print(spiel.zustand())
