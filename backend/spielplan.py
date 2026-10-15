from .cockpit import Cockpit, Ergebnis
from .landung import Landung
from .wuerfel import Wuerfel, BESITZER, wirf_verkehrswuerfel
from .zusatzregeln import Zusatzregeln, KARTEN


class Spielplan:
    """
    Orchestriert eine komplette Partie Cockpit: Würfelpools,
    Zugreihenfolge, Neuwurf-Plättchen, Rundenablauf (S.4-S.11) und
    Sieg-/Verlustauswertung.

    Name/Modul bewusst "spielplan.py"/"Spielplan" belassen, damit
    bestehende Importe (frontend/terminal/displayer.py) weiter
    funktionieren.
    """

    def __init__(self, flughafen="MUC", startspieler="pilot", faehigkeitskarten=None, clock=None):
        self.landung = Landung(flughafen)
        karten = [] if faehigkeitskarten is None else faehigkeitskarten
        if not isinstance(karten, (list, tuple)) or any(not isinstance(k, str) or k not in KARTEN for k in karten) or len(set(karten)) != len(karten):
            raise ValueError("Ungültiges Fähigkeitskarten-Set.")
        if len(karten) != (self.landung.get_faehigkeitskarten() or 0):
            raise ValueError(f"Für diese Landung sind genau {self.landung.get_faehigkeitskarten() or 0} Fähigkeitskarten erforderlich.")
        if startspieler not in BESITZER:
            raise ValueError("Ungültiger Startspieler.")
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
        self.phase = "vorbereitung"  # "vorbereitung" | "verkehr" | "platzieren"
        self.verkehrswuerfel_offen = 0
        self.verkehrswuerfe = []
        self._vorbereitete_runde = None
        self.zusatz = Zusatzregeln(self, karten, clock)

    ### SETUP / RUNDENABLAUF ###

    def starte_spiel(self):
        """Vor Runde 1: Neuwurf-Plättchen sammeln, zuerst Verkehr, dann Spielerwürfel."""
        self._sammle_neuwurf_plaettchen()
        self._bereite_runde_vor()
        self.wuerfeln_fuer_runde()

    def _bereite_runde_vor(self):
        if self._vorbereitete_runde == self.aktuelle_runde:
            return
        self._vorbereitete_runde = self.aktuelle_runde
        self.zusatz.neue_runde()
        self.verkehrswuerfel_offen = self.landung.verkehrswuerfel_an_aktueller_position()
        self.verkehrswuerfe = []
        self.phase = "verkehr" if self.verkehrswuerfel_offen else "vorbereitung"
        for w in self.pilot_wuerfel + self.kopilot_wuerfel:
            w.augenzahl = None
            w.platziert = False

    def wuerfeln_fuer_runde(self):
        """Alle 8 Spielerwürfel einmal pro Runde werfen, sobald der Verkehr geklärt ist."""
        if self.status != "laeuft" or self.phase != "vorbereitung":
            return False
        for w in self.pilot_wuerfel + self.kopilot_wuerfel:
            w.werfen()
        self.phase = "platzieren"
        self.zusatz.wuerfel_geworfen()
        return True

    def wirf_verkehrswuerfel(self, besitzer=None):
        """Ein Symbol auflösen. Nach dem letzten Wurf beginnt die Platzierphase."""
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if besitzer is not None:
            if besitzer not in BESITZER:
                return Ergebnis(False, "ungueltiger_besitzer")
            if besitzer != self.am_zug:
                return Ergebnis(False, "nicht_am_zug")
        if self.phase != "verkehr" or self.verkehrswuerfel_offen <= 0:
            return Ergebnis(False, "kein_verkehrswuerfel_offen")
        wert = wirf_verkehrswuerfel()
        ziel = self.landung.add_flugzeug_fuer_verkehrswurf(wert)
        self.verkehrswuerfe.append({"wert": wert, "ziel_entfernung": ziel})
        self.verkehrswuerfel_offen -= 1
        meldung = f"Schwarzer Würfel: {wert}. "
        if self.landung.letzter_verkehr_grund == "vorrat_leer":
            meldung += "Der Flugzeugvorrat ist leer – kein neues Flugzeug."
        elif ziel is None:
            meldung += "Die Entfernung reicht nicht aus – kein neues Flugzeug. Glück gehabt!"
        else:
            meldung += f"Ein weiteres Flugzeug auf Entfernung {ziel}."
        if self.verkehrswuerfel_offen == 0:
            self.phase = "vorbereitung"
            self.wuerfeln_fuer_runde()
            meldung += f" Runde {self.aktuelle_runde} ist bereit."
        self.letzte_meldung = meldung
        return Ergebnis(True, meldung=meldung)

    def _sammle_neuwurf_plaettchen(self):
        hoehe = self.landung.get_hoehe()
        if hoehe in self.landung.get_neuwurf_hoehen() and hoehe not in self._genutzte_neuwurf_hoehen:
            self._genutzte_neuwurf_hoehen.add(hoehe)
            self.neuwurf_plaettchen += 1

    def benutze_neuwurf(self, pilot_indizes=(), kopilot_indizes=()):
        """
        S.4: gibt ein Neuwurf-Plättchen aus, damit BEIDE Spieler beliebig
        viele ihrer noch nicht platzierten Würfel einmal neu werfen dürfen.
        `pilot_indizes`/`kopilot_indizes`: Indizes (0-3) der Würfel, die
        neu geworfen werden sollen.
        """
        pruefung = self.zusatz.pruefe()
        if pruefung is not None:
            return pruefung
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if self.phase != "platzieren":
            return Ergebnis(False, "runde_nicht_bereit")
        if self.neuwurf_plaettchen <= 0:
            return Ergebnis(False, "kein_neuwurf_plaettchen")
        pruefung = self._pruefe_neuwurf_auswahl(pilot_indizes, self.pilot_wuerfel)
        if pruefung is None:
            pruefung = self._pruefe_neuwurf_auswahl(kopilot_indizes, self.kopilot_wuerfel)
        if pruefung is not None:
            return pruefung
        for i in pilot_indizes:
            self.pilot_wuerfel[i].werfen()
        for i in kopilot_indizes:
            self.kopilot_wuerfel[i].werfen()
        self.neuwurf_plaettchen -= 1
        return Ergebnis(True, meldung="Neuwurf-Plättchen eingelöst.")

    @staticmethod
    def _pruefe_neuwurf_auswahl(indizes, wuerfel_liste):
        if not isinstance(indizes, (list, tuple, set)):
            return Ergebnis(False, "ungueltige_neuwurf_auswahl")
        gesehen = set()
        for index in indizes:
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(wuerfel_liste):
                return Ergebnis(False, "ungueltige_neuwurf_auswahl")
            if index in gesehen:
                return Ergebnis(False, "ungueltige_neuwurf_auswahl")
            gesehen.add(index)
            if not wuerfel_liste[index].ist_verfuegbar():
                return Ergebnis(False, "wuerfel_nicht_verfuegbar")
        return None

    ### WÜRFEL PLATZIEREN (S.4-S.9) ###

    def _wuerfel_liste(self, besitzer):
        if besitzer == "pilot":
            return self.pilot_wuerfel
        if besitzer == "kopilot":
            return self.kopilot_wuerfel
        raise ValueError(f"Ungültiger Besitzer: {besitzer!r}")

    def verfuegbare_wuerfel(self, besitzer):
        return [w for w in self._wuerfel_liste(besitzer) if w.ist_verfuegbar()]

    def alle_wuerfel_platziert(self):
        """S.9: 'Sobald ihr alle 8 Würfel platziert habt' - über die Würfel
        selbst geprüft, nicht über die (viel zahlreicheren) Felder."""
        return all(w.ist_platziert() for w in self.pilot_wuerfel + self.kopilot_wuerfel)

    def trinke_kaffee(self, besitzer, wuerfel_index, delta):
        """Kaffee auf einen eigenen, noch nicht platzierten Würfel anwenden (S.8)."""
        pruefung = self.zusatz.pruefe()
        if pruefung is not None:
            return pruefung
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if self.phase != "platzieren":
            return Ergebnis(False, "runde_nicht_bereit")
        if besitzer not in BESITZER:
            return Ergebnis(False, "ungueltiger_besitzer")
        if besitzer != self.am_zug:
            return Ergebnis(False, "nicht_am_zug")
        if not self._gueltiger_wuerfel_index(wuerfel_index):
            return Ergebnis(False, "ungueltiger_wuerfel_index")
        if not isinstance(delta, int) or isinstance(delta, bool) or delta == 0:
            return Ergebnis(False, "ungueltiger_delta")
        wuerfel = self._wuerfel_liste(besitzer)[wuerfel_index]
        return self.cockpit.trinke_kaffee(wuerfel, delta)

    def moegliche_kaffee_deltas(self, besitzer, wuerfel_index):
        if self.phase != "platzieren" or besitzer not in BESITZER or not self._gueltiger_wuerfel_index(wuerfel_index):
            return []
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
        pruefung = self.zusatz.pruefe()
        if pruefung is not None:
            return pruefung
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if self.phase != "platzieren":
            return Ergebnis(False, "runde_nicht_bereit")
        if besitzer not in BESITZER:
            return Ergebnis(False, "ungueltiger_besitzer")
        if besitzer != self.am_zug:
            return Ergebnis(False, "nicht_am_zug")
        if not self._gueltiger_wuerfel_index(wuerfel_index):
            return Ergebnis(False, "ungueltiger_wuerfel_index")
        wuerfel_liste = self._wuerfel_liste(besitzer)
        wuerfel = wuerfel_liste[wuerfel_index]
        if not wuerfel.ist_verfuegbar():
            return Ergebnis(False, "wuerfel_nicht_verfuegbar")

        ergebnis = self._lege_wuerfel(wuerfel, ziel, index, funk_feld)
        return self._nach_platzierung(ergebnis, ziel, wechsel=True, rolle=besitzer)

    def _lege_wuerfel(self, wuerfel, ziel, index=None, funk_feld=0):
        besitzer = wuerfel.besitzer
        if not isinstance(ziel, str):
            return Ergebnis(False, "unbekanntes_ziel")
        felder_mit_index = {"fahrwerk", "landeklappe", "bremse", "konzentration", "eisbremse"}
        if ziel in felder_mit_index and (not isinstance(index, int) or isinstance(index, bool)):
            return Ergebnis(False, "ungueltiger_index")
        if ziel == "funk":
            if not isinstance(funk_feld, int) or isinstance(funk_feld, bool):
                return Ergebnis(False, "ungueltiger_funk_index")
            if besitzer == "pilot" and funk_feld != 0:
                return Ergebnis(False, "ungueltiger_funk_index")
            if besitzer == "kopilot" and funk_feld not in (0, 1):
                return Ergebnis(False, "ungueltiger_funk_index")

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
        elif ziel == "kerosin":
            ergebnis = self.cockpit.platziere_kerosin(wuerfel)
        elif ziel == "eisbremse":
            ergebnis = self.cockpit.platziere_eisbremse(wuerfel, index)
        elif ziel == "training":
            ergebnis = self.zusatz.trainiere(wuerfel)
        else:
            return Ergebnis(False, "unbekanntes_ziel")
        return ergebnis

    def _nach_platzierung(self, ergebnis, ziel, wechsel=False, rolle=None):
        if not ergebnis.erfolg:
            return ergebnis

        if not ergebnis.verloren:
            zusatz = self.zusatz.nach_platzierung(ziel, rolle)
            if zusatz is not None:
                ergebnis = zusatz
        self.letzte_meldung = ergebnis.meldung
        if ergebnis.verloren:
            self.status = "verloren"
            self.zusatz.deadline = None
            self.verlust_grund = ergebnis.grund
            return ergebnis

        if wechsel:
            self.am_zug = "kopilot" if self.am_zug == "pilot" else "pilot"
        return ergebnis

    @staticmethod
    def _gueltiger_wuerfel_index(index):
        return isinstance(index, int) and not isinstance(index, bool) and 0 <= index < 4

    ### RUNDENENDE (S.9-S.11) ###

    def rundenende(self, zeit_abgelaufen=False):
        if not zeit_abgelaufen:
            pruefung = self.zusatz.pruefe()
            if pruefung is not None:
                return pruefung
        if self.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if self.phase != "platzieren":
            return Ergebnis(False, "runde_nicht_bereit")
        if not zeit_abgelaufen and not self.alle_wuerfel_platziert():
            return Ergebnis(False, "noch_nicht_alle_wuerfel_platziert")

        self.zusatz.deadline = None
        verbrauch = self.zusatz.rundenverbrauch()
        if verbrauch is not None and verbrauch.verloren:
            self.status, self.verlust_grund = "verloren", verbrauch.grund
            return verbrauch

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
            self._bereite_runde_vor()
            return Ergebnis(True, meldung="Perfektes Timing - die letzte Runde beginnt!")

        if am_flughafen and not auf_hoehe_null:
            self.warteschleife = True
            self.am_zug = self._naechster_startspieler()
            self._bereite_runde_vor()
            return Ergebnis(True, meldung="Zu früh am Flughafen - ihr fliegt eine Warteschleife.")

        if auf_hoehe_null and not am_flughafen:
            self.status = "verloren"
            self.verlust_grund = "notlandung"
            return Ergebnis(True, verloren=True, grund="notlandung",
                             meldung="Boden erreicht, bevor der Flughafen erreicht wurde - Notlandung!")

        self.am_zug = self._naechster_startspieler()
        self._bereite_runde_vor()
        return Ergebnis(True, meldung=f"Runde {self.aktuelle_runde} beginnt.")

    def _naechster_startspieler(self):
        self.startspieler = "kopilot" if self.startspieler == "pilot" else "pilot"
        return self.startspieler

    def _werte_spielende_aus(self):
        gruende = []
        if "intern" in self.cockpit.module and self.zusatz.praktikant:
            gruende.append("praktikant_unvollstaendig")
        if "ice" in self.cockpit.module and self.cockpit.eis_fortschritt != 4:
            gruende.append("eisbremsen_unvollstaendig")
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
            **self.zusatz.snapshot(),
            "status": self.status,
            "flughafen_code": self.landung.get_code(),
            "flughafen_name": self.landung.get_bezeichnung(),
            "szenario_id": self.landung.szenario_id,
            "mock": self.landung.mock,
            "uebung": self.landung.uebung,
            "verkehr_regel": self.landung.verkehr_regel,
            "flugzeug_vorrat": max(0, 12 - sum(self.landung.flugzeuge)) if self.landung.verkehr_regel == "offiziell" else None,
            "geplante_module": self.landung.geplante_module.copy(),
            "verlust_grund": self.verlust_grund,
            "letzte_meldung": self.letzte_meldung,
            "runde": self.aktuelle_runde,
            "phase": self.phase,
            "verkehrswuerfel_offen": self.verkehrswuerfel_offen,
            "verkehrswuerfe": [dict(wurf) for wurf in self.verkehrswuerfe],
            "letzte_runde": self.letzte_runde,
            "warteschleife": self.warteschleife,
            "am_zug": self.am_zug,
            "hoehe": self.landung.get_hoehe(),
            "entfernung": self.landung.get_entfernung(),
            "laenge": self.landung.get_laenge(),
            "entfernungswerte": self.landung.get_entfernungswerte(),
            "flugzeuge": list(self.landung.get_flugzeuge()),
            "flugzeugwuerfel": self.landung.get_flugzeugwuerfel(),
            # Erlaubte Ruderstellung je Entfernungsfeld (gleiche Indizierung
            # wie "flugzeuge": Index 0 = am weitesten vom Flughafen weg).
            "kurven_min": list(self.landung.get_kurven_min()),
            "kurven_max": list(self.landung.get_kurven_max()),
            "neuwurf_plaettchen": self.neuwurf_plaettchen,
            "neuwurf_hoehen": self.landung.get_neuwurf_hoehen(),
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
