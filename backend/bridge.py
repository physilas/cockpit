"""
Dünne Schicht zwischen der Spiel-Engine und einem JS-Frontend (Pyodide).

Alles hier gibt nur JSON-taugliche Python-Grundtypen (dict/list/str/int/
bool/None) zurück, nie Wuerfel-/Ergebnis-Objekte direkt - das macht die
Übergabe an JavaScript (`result.to_py()` / `pyodide.toJs`) unkompliziert
und hält die Spielregeln komplett in Python (kein Regel-Code in JS).
"""
from .spielplan import Spielplan
from .cockpit import Ergebnis
from .regeln import grund_text as _grund_text
from .landung import flughafen_liste as _flughafen_liste
from .ui_schema import feld_layout as _feld_layout

_spiel = None


def grund_text(code):
    return _grund_text(code)


def flughaefen_liste():
    """Für die Flughafen-Auswahl im Frontend (siehe landung.py:
    flughafen_liste()) - jede YAML-Datei unter backend/landungen/ taucht
    hier automatisch auf, ohne dass das Frontend angepasst werden muss."""
    return _flughafen_liste()


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


def _kein_spiel():
    return {"ergebnis": _ergebnis_zu_dict(Ergebnis(False, "kein_spiel_aktiv")), "zustand": None}


def zustand():
    if _spiel is None:
        return None
    return _spiel.zustand()


def platziere(besitzer, wuerfel_index, ziel, index=None, funk_feld=0):
    if _spiel is None:
        return _kein_spiel()
    kwargs = {}
    if index is not None:
        kwargs["index"] = index
    if ziel == "funk":
        kwargs["funk_feld"] = funk_feld
    ergebnis = _spiel.platziere(besitzer, wuerfel_index, ziel, **kwargs)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def trinke_kaffee(besitzer, wuerfel_index, delta):
    if _spiel is None:
        return _kein_spiel()
    ergebnis = _spiel.trinke_kaffee(besitzer, wuerfel_index, delta)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def moegliche_kaffee_deltas(besitzer, wuerfel_index):
    if _spiel is None:
        return []
    return _spiel.moegliche_kaffee_deltas(besitzer, wuerfel_index)


def benutze_neuwurf(pilot_indizes, kopilot_indizes):
    if _spiel is None:
        return _kein_spiel()
    try:
        pilot_indizes = list(pilot_indizes)
        kopilot_indizes = list(kopilot_indizes)
    except TypeError:
        ergebnis = Ergebnis(False, "ungueltige_neuwurf_auswahl")
        return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}
    ergebnis = _spiel.benutze_neuwurf(pilot_indizes, kopilot_indizes)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def rundenende():
    if _spiel is None:
        return _kein_spiel()
    ergebnis = _spiel.rundenende()
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def wuerfeln_fuer_runde():
    if _spiel is None:
        return None
    _spiel.wuerfeln_fuer_runde()
    return zustand()


# Statische Feld-Beschreibung fürs Frontend: welche Ziele/Slots es gibt,
# wer sie benutzen darf, und welche Zahlen dort erlaubt sind. So muss das
# JS keine Regeln kennen, nur diese Liste rendern und `platziere(...)` je
# nach Auswahl aufrufen.
def feld_layout():
    return _feld_layout()
