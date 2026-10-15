"""Logbook modules and abilities. All decisions, including deadlines, live in Python."""
import random
import time
from .cockpit import Ergebnis
from .wuerfel import Wuerfel, BESITZER, wirf_verkehrswuerfel
from .regeln import MAX_NEUWURF_PLAETTCHEN

KARTEN = {"working-together", "synchronisation", "mastery", "control", "anticipation", "adaptation"}


class Zusatzregeln:
    def __init__(self, spiel, karten, clock=None):
        self.spiel = spiel
        self.c = spiel.cockpit
        self.clock = clock or time.time
        self.karten = list(karten)
        self.praktikant = random.sample(range(1, 7), 6) if "intern" in self.c.module else []
        self.anpassung = {r: False for r in BESITZER}
        self.deadline = None
        self.neue_runde()

    def neue_runde(self):
        self.offen = []
        self.kooperation = None
        self.kooperation_erste_wahl = None
        self.kooperation_genutzt = False
        self.voraussicht_genutzt = False
        self.ausgeloest = set()
        self.platzierungen = 0
        self.deadline = None

    def wuerfel_geworfen(self):
        if "realtime" in self.c.module:
            self.deadline = self.clock() + 60

    def tick(self):
        s = self.spiel
        if s.status == "laeuft" and self.deadline is not None and self.clock() >= self.deadline:
            self.deadline = None
            self.offen = []
            self.kooperation = None
            result = s.rundenende(zeit_abgelaufen=True)
            result.meldung = "Zeit abgelaufen. " + result.meldung
            s.letzte_meldung = result.meldung
            return result
        return Ergebnis(False, "zeit_noch_nicht_abgelaufen")

    def pruefe(self, zusatz=False):
        if self.tick().erfolg:
            return Ergebnis(False, "zeit_abgelaufen")
        if not zusatz and (self.offen or self.kooperation):
            return Ergebnis(False, "zusatzaktion_offen")
        return None

    def trainiere(self, w):
        r = w.besitzer
        if "intern" not in self.c.module or not self.praktikant:
            return Ergebnis(False, "praktikant_fertig")
        wert = self.praktikant[0 if r == "pilot" else -1]
        if wert == w.augenzahl:
            return Ergebnis(False, "praktikant_gleiche_zahl")
        token = Wuerfel(r)
        token.augenzahl = wert
        token.quelle = "intern"
        pending = {"rolle": r, "wuerfel": token}
        if not self.platzierziele(pending):
            return Ergebnis(False, "praktikant_kein_ziel")
        if not self.c.training[r].platziere(w):
            return Ergebnis(False, "feld_ungueltig")
        self.praktikant.pop(0 if r == "pilot" else -1)
        self.offen.append(pending)
        return Ergebnis(True, meldung=f"Praktikant {wert}: jetzt auf ein Cockpit-Feld legen.")

    def nach_platzierung(self, ziel):
        c, s = self.c, self.spiel
        self.platzierungen += 1
        if ziel == "ruder" and not c.ruder_pilot.ist_frei() and not c.ruder_kopilot.ist_frei() and "ruder" not in self.ausgeloest:
            self.ausgeloest.add("ruder")
            if "wind" in c.module:
                c.wind_position = (c.wind_position + c.fluglage) % len(c.WIND_RING)
            if "control" in self.karten and c.ruder_pilot.wuerfel.augenzahl == c.ruder_kopilot.wuerfel.augenzahl:
                c.kaffeetassen = min(3, c.kaffeetassen + 1)
        if ziel == "triebwerk" and not c.schub_pilot.ist_frei() and not c.schub_kopilot.ist_frei() and "triebwerk" not in self.ausgeloest:
            self.ausgeloest.add("triebwerk")
            a, b = c.schub_pilot.wuerfel.augenzahl, c.schub_kopilot.wuerfel.augenzahl
            if "mastery" in self.karten and a == b:
                auf_leiste = len(set(s.landung.get_neuwurf_hoehen()) - s._genutzte_neuwurf_hoehen)
                if s.neuwurf_plaettchen + auf_leiste < MAX_NEUWURF_PLAETTCHEN:
                    s.neuwurf_plaettchen += 1
            if "leak" in c.module:
                result = c.verbrauche_kerosin(abs(a - b) + 1)
                if result.verloren:
                    return result
        if "synchronisation" in self.karten and "synchronisation" not in self.ausgeloest and any(not f.ist_frei() for f in c.fahrwerk) and any(not f.ist_frei() for f in c.landeklappen):
            self.ausgeloest.add("synchronisation")
            w = Wuerfel("kopilot")
            w.augenzahl = wirf_verkehrswuerfel()
            w.quelle = "synchronisation"
            self.offen.append({"rolle": "kopilot", "wuerfel": w})
        return None

    def rundenverbrauch(self):
        if "kerosene" in self.c.module and "leak" not in self.c.module and self.c.kerosin_feld.ist_frei():
            return self.c.verbrauche_kerosin(6)
        return None

    def platzierziele(self, pending=None):
        """Legal destinations for the mandatory token/die, including target colour."""
        if pending is None and not self.offen:
            return []
        p = pending if pending is not None else self.offen[0]
        w = p["wuerfel"]
        bonus = w.quelle == "synchronisation"
        roles = BESITZER if bonus else [p["rolle"]]
        c = self.c
        result = []
        def add(ziel, index, feld, rolle, label, erlaubt=True, funk_feld=0):
            if erlaubt and feld.ist_frei() and feld.erlaubt(rolle, w.augenzahl):
                result.append({"ziel": ziel, "index": index, "funk_feld": funk_feld, "ziel_besitzer": rolle, "label": label})
        for r in roles:
            suffix = "Pilotin" if r == "pilot" else "Co-Pilot"
            add("ruder", None, c.ruder_pilot if r == "pilot" else c.ruder_kopilot, r, f"Ruder · {suffix}")
            add("triebwerk", None, c.schub_pilot if r == "pilot" else c.schub_kopilot, r, f"Triebwerk · {suffix}")
            for i, f in enumerate([c.funk_pilot] if r == "pilot" else c.funk_kopilot):
                add("funk", None, f, r, f"Funk {i + 1} · {suffix}", funk_feld=i)
            for z, fields, status, label in [("fahrwerk", c.fahrwerk, c.fahrwerk_ausgefahren, "Fahrwerk"), ("landeklappe", c.landeklappen, c.landeklappen_ausgefahren, "Klappe"), ("bremse", c.bremsen, c.bremsen_aktiviert, "Bremse")]:
                next_index = next((i for i, done in enumerate(status) if not done), len(status))
                for i, f in enumerate(fields):
                    valid = z == "fahrwerk" or status[i] or i == next_index
                    add(z, i, f, r, f"{label} {i + 1} · {suffix}", valid and not (z == "bremse" and "ice" in c.module))
            for i, f in enumerate(c.konzentration):
                add("konzentration", i, f, r, f"Konzentration {i + 1}", bonus)
            add("kerosin", None, c.kerosin_feld, r, "Kerosin", "kerosene" in c.module and "leak" not in c.module)
            for i, f in enumerate(c.eisbremsen):
                add("eisbremse", i, f, r, f"Eisbremse {2 + i // 2} · {'oben' if i % 2 == 0 else 'unten'}", "ice" in c.module and i // 2 == c.eis_fortschritt)
        # Shared spaces need only one entry even if the traffic die can use both colours.
        seen, unique = set(), []
        for target in result:
            shared = target["ziel"] in ("kerosin", "konzentration") or (target["ziel"] == "eisbremse" and target["index"] % 2 == 1)
            key = (target["ziel"], target["index"], target["funk_feld"], None if shared else target["ziel_besitzer"])
            if key not in seen:
                unique.append(target)
                seen.add(key)
        return unique

    def aktion(self, rolle, aktion, params):
        s = self.spiel
        error = self.pruefe(zusatz=True)
        if error is not None:
            return error
        if rolle not in BESITZER:
            return Ergebnis(False, "ungueltiger_besitzer")
        if s.status != "laeuft":
            return Ergebnis(False, "spiel_beendet")
        if aktion == "wuerfeln" and s.phase == "vorbereitung":
            if rolle != s.am_zug:
                return Ergebnis(False, "nicht_am_zug")
            s.wuerfeln_fuer_runde()
            return Ergebnis(True, meldung="Würfel geworfen; die Runde beginnt.")
        if s.phase != "platzieren":
            return Ergebnis(False, "runde_nicht_bereit")
        if aktion == "bonus_kaffee":
            if not self.offen or self.offen[0]["rolle"] != rolle or self.offen[0]["wuerfel"].quelle != "synchronisation":
                return Ergebnis(False, "karte_nicht_verfuegbar")
            return self.c.trinke_kaffee(self.offen[0]["wuerfel"], params.get("delta"))
        if aktion == "zusatz_platzieren":
            if not self.offen or rolle != self.offen[0]["rolle"]:
                return Ergebnis(False, "nicht_am_zug")
            keys = ("ziel", "index", "funk_feld", "ziel_besitzer")
            target = next((x for x in self.platzierziele() if all(x[k] == params.get(k) for k in keys)), None)
            if target is None:
                return Ergebnis(False, "feld_ungueltig")
            p = self.offen.pop(0)
            w = p["wuerfel"]
            w.besitzer = target["ziel_besitzer"]
            result = s._lege_wuerfel(w, target["ziel"], target["index"], target["funk_feld"])
            if not result.erfolg:
                self.offen.insert(0, p)
                return result
            return s._nach_platzierung(result, target["ziel"], wechsel=False)
        if self.offen:
            return Ergebnis(False, "zusatzaktion_offen")
        if aktion == "kooperation_start":
            if "working-together" not in self.karten or self.kooperation_genutzt or self.kooperation or any(not s.verfuegbare_wuerfel(r) for r in BESITZER):
                return Ergebnis(False, "karte_nicht_verfuegbar")
            self.kooperation = {"wartet_auf": rolle}
            return Ergebnis(True, meldung="Zusammenarbeit: beide wählen nacheinander einen freien Würfel.")
        if aktion == "kooperation_wahl" and self.kooperation:
            if self.kooperation["wartet_auf"] != rolle:
                return Ergebnis(False, "nicht_am_zug")
            i = params.get("wuerfel_index")
            if not s._gueltiger_wuerfel_index(i) or not s._wuerfel_liste(rolle)[i].ist_verfuegbar():
                return Ergebnis(False, "wuerfel_nicht_verfuegbar")
            if self.kooperation_erste_wahl is None:
                self.kooperation_erste_wahl = (rolle, i)
                self.kooperation["wartet_auf"] = "kopilot" if rolle == "pilot" else "pilot"
                return Ergebnis(True, meldung="Gerät weitergeben: Partner wählt seinen Würfel.")
            first, index = self.kooperation_erste_wahl
            a, b = s._wuerfel_liste(first)[index], s._wuerfel_liste(rolle)[i]
            a.augenzahl, b.augenzahl = b.augenzahl, a.augenzahl
            self.kooperation = self.kooperation_erste_wahl = None
            self.kooperation_genutzt = True
            return Ergebnis(True, meldung="Würfelwerte getauscht. Der reguläre Zug bleibt bestehen.")
        if self.kooperation:
            return Ergebnis(False, "zusatzaktion_offen")
        if aktion not in ("adaptation", "anticipation") or aktion not in self.karten:
            return Ergebnis(False, "karte_nicht_verfuegbar")
        i = params.get("wuerfel_index")
        if not s._gueltiger_wuerfel_index(i) or not s._wuerfel_liste(rolle)[i].ist_verfuegbar():
            return Ergebnis(False, "wuerfel_nicht_verfuegbar")
        w = s._wuerfel_liste(rolle)[i]
        if aktion == "adaptation":
            if self.anpassung[rolle]:
                return Ergebnis(False, "karte_nicht_verfuegbar")
            w.augenzahl = 7 - w.augenzahl
            self.anpassung[rolle] = True
        else:
            if rolle != s.startspieler or self.platzierungen or self.voraussicht_genutzt:
                return Ergebnis(False, "karte_nicht_verfuegbar")
            w.werfen()
            self.voraussicht_genutzt = True
        return Ergebnis(True, meldung="Anpassung: Würfel gedreht." if aktion == "adaptation" else "Voraussicht: Würfel neu geworfen.")

    def snapshot(self):
        s, c = self.spiel, self.c
        return {
            "module": sorted(c.module), "faehigkeitskarten": self.karten.copy(),
            "kerosin": c.kerosin, "kerosin_faellig": (0 if not c.kerosin_feld.ist_frei() else 6) if "kerosene" in c.module and "leak" not in c.module else None,
            "wind_position": c.wind_position, "wind_ring": list(c.WIND_RING), "wind_wert": c.wind_wert(),
            "eis_fortschritt": c.eis_fortschritt, "praktikant": self.praktikant.copy(),
            "zusatzaktion": {"rolle": self.offen[0]["rolle"], "quelle": self.offen[0]["wuerfel"].quelle, "wert": self.offen[0]["wuerfel"].augenzahl, "ziele": self.platzierziele(), "kaffee_deltas": c.moegliche_kaffee_deltas(self.offen[0]["wuerfel"].augenzahl) if self.offen[0]["wuerfel"].quelle == "synchronisation" else []} if self.offen else None,
            "kooperation": dict(self.kooperation) if self.kooperation else None,
            "kooperation_verfuegbar": "working-together" in self.karten and not self.kooperation_genutzt and all(s.verfuegbare_wuerfel(r) for r in BESITZER),
            "anpassung_verfuegbar": {r: "adaptation" in self.karten and not self.anpassung[r] for r in BESITZER},
            "voraussicht_verfuegbar": "anticipation" in self.karten and not self.voraussicht_genutzt and not self.platzierungen,
            "timer_deadline_ms": int(self.deadline * 1000) if self.deadline is not None else None,
            "server_time_ms": int(self.clock() * 1000) if "realtime" in c.module else 0,
            "geschwindigkeit": c.triebwerk_geschwindigkeit(),
        }
