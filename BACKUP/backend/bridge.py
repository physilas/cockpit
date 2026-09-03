"""
Dünne Schicht zwischen der Spiel-Engine und einem JS-Frontend (Pyodide).

Alles hier gibt nur JSON-taugliche Python-Grundtypen (dict/list/str/int/
bool/None) zurück, nie Wuerfel-/Ergebnis-Objekte direkt - das macht die
Übergabe an JavaScript (`result.to_py()` / `pyodide.toJs`) unkompliziert
und hält die Spielregeln komplett in Python (kein Regel-Code in JS).
"""
from .spielplan import Spielplan
from .regeln import grund_text as _grund_text

_spiel = None


def grund_text(code):
    return _grund_text(code)


def neues_spiel(flughafen="MUC"):
    global _spiel
    _spiel = Spielplan(flughafen)
    _spiel.starte_spiel()
    return zustand()


def _ergebnis_zu_dict(ergebnis):
    return {
        "erfolg": ergebnis.erfolg,
        "grund": ergebnis.grund,
        "verloren": ergebnis.verloren,
        "gewonnen": ergebnis.gewonnen,
        "meldung": ergebnis.meldung,
    }


def zustand():
    if _spiel is None:
        return None
    return _spiel.zustand()


def platziere(besitzer, wuerfel_index, ziel, index=None, funk_feld=0):
    kwargs = {}
    if index is not None:
        kwargs["index"] = index
    if ziel == "funk":
        kwargs["funk_feld"] = funk_feld
    ergebnis = _spiel.platziere(besitzer, wuerfel_index, ziel, **kwargs)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def trinke_kaffee(besitzer, wuerfel_index, delta):
    ergebnis = _spiel.trinke_kaffee(besitzer, wuerfel_index, delta)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def moegliche_kaffee_deltas(besitzer, wuerfel_index):
    return _spiel.moegliche_kaffee_deltas(besitzer, wuerfel_index)


def benutze_neuwurf(pilot_indizes, kopilot_indizes):
    ergebnis = _spiel.benutze_neuwurf(list(pilot_indizes), list(kopilot_indizes))
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def rundenende():
    ergebnis = _spiel.rundenende()
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def wuerfeln_fuer_runde():
    _spiel.wuerfeln_fuer_runde()
    return zustand()


# Statische Feld-Beschreibung fürs Frontend: welche Ziele/Slots es gibt,
# wer sie benutzen darf, und welche Zahlen dort erlaubt sind. So muss das
# JS keine Regeln kennen, nur diese Liste rendern und `platziere(...)` je
# nach Auswahl aufrufen.
def feld_layout():
    return [
        {"ziel": "ruder", "snapshot_key": "ruder", "zugriff": ["pilot", "kopilot"], "pflicht": True, "art": "farbpaar"},
        {"ziel": "triebwerk", "snapshot_key": "triebwerk", "zugriff": ["pilot", "kopilot"], "pflicht": True, "art": "farbpaar"},
        {"ziel": "funk", "snapshot_key": "funk_pilot", "zugriff": ["pilot"], "slots": 1, "funk_feld_basis": 0},
        {"ziel": "funk", "snapshot_key": "funk_kopilot", "zugriff": ["kopilot"], "slots": 2, "funk_feld_basis": 0},
        {"ziel": "fahrwerk", "snapshot_key": "fahrwerk", "zugriff": ["pilot"], "slots": 3, "zahlen": [[1, 2], [3, 4], [5, 6]]},
        {"ziel": "landeklappe", "snapshot_key": "landeklappe", "zugriff": ["kopilot"], "slots": 4,
         "zahlen": [[1, 2], [2, 3], [4, 5], [5, 6]]},
        {"ziel": "bremse", "snapshot_key": "bremse", "zugriff": ["pilot"], "slots": 3, "zahlen": [[2], [4], [6]]},
        {"ziel": "konzentration", "snapshot_key": "konzentration", "zugriff": ["pilot", "kopilot"], "slots": 3},
    ]
