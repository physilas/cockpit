"""
Dünne Schicht zwischen der Spiel-Engine und einem JS-Frontend (Pyodide).

Alles hier gibt nur JSON-taugliche Python-Grundtypen (dict/list/str/int/
bool/None) zurück, nie Wuerfel-/Ergebnis-Objekte direkt - das macht die
Übergabe an JavaScript (`result.to_py()` / `pyodide.toJs`) unkompliziert
und hält die Spielregeln komplett in Python (kein Regel-Code in JS).
"""
import json
from copy import deepcopy
from functools import wraps
from .spielplan import Spielplan
from .cockpit import Ergebnis
from .regeln import grund_text as _grund_text
from .landung import flughafen_liste as _flughafen_liste
from .ui_schema import feld_layout as _feld_layout

_spiel = None
_verlauf = []
_revision = 0
_undo_id = 0


def _mit_verlauf(aktion):
    """Keep complete object graphs, including pending abilities and die references."""
    @wraps(aktion)
    def ausfuehren(*args, **kwargs):
        global _revision
        if _spiel is None:
            return aktion(*args, **kwargs)
        # The UI polls at 5 Hz; an unchanged clock must not copy or fill history.
        if aktion.__name__ == "tick" and (
            _spiel.zusatz.deadline is None or _spiel.zusatz.clock() < _spiel.zusatz.deadline
        ):
            return aktion(*args, **kwargs)
        vorher = deepcopy(_spiel)
        antwort = aktion(*args, **kwargs)
        if (antwort["ergebnis"]["erfolg"] or vorher.status != _spiel.status
                or vorher.aktuelle_runde != _spiel.aktuelle_runde):
            _verlauf.append(vorher)
            del _verlauf[:-200]
            _revision += 1
        antwort["zustand"] = zustand()
        return antwort
    return ausfuehren


def grund_text(code):
    return _grund_text(code)


def flughaefen_liste():
    """Für die Flughafen-Auswahl im Frontend (siehe landung.py:
    flughafen_liste()) - jede YAML-Datei unter backend/landungen/ taucht
    hier automatisch auf, ohne dass das Frontend angepasst werden muss."""
    return _flughafen_liste()


def neues_spiel(flughafen="MUC", karten_json="[]"):
    global _spiel, _revision, _undo_id
    spiel = Spielplan(flughafen, faehigkeitskarten=json.loads(karten_json))
    spiel.starte_spiel()
    _spiel = spiel
    _verlauf.clear()
    _revision += 1
    _undo_id += 1
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
    return {**_spiel.zustand(), "rueckgaengig_moeglich": bool(_verlauf),
            "rueckgaengig_version": _revision, "rueckgaengig_id": _undo_id}


def rueckgaengig(besitzer=None, version=None):
    """Either crew member may undo the latest shared action, never a stale version.

    Real-time deadlines retain their original absolute time: undo does not
    pause or rewind the clock. A new game intentionally clears the history.
    """
    global _spiel, _revision, _undo_id
    if _spiel is None:
        return _kein_spiel()
    if besitzer is not None and besitzer not in ("pilot", "kopilot"):
        result = Ergebnis(False, "ungueltiger_besitzer")
    elif version is not None and (type(version) is not int or version != _revision):
        result = Ergebnis(False, "spielstand_geaendert")
    elif not _verlauf:
        result = Ergebnis(False, "kein_rueckgaengig")
    else:
        _spiel = _verlauf.pop()
        _revision += 1
        _undo_id += 1
        result = Ergebnis(True, meldung="Letzter Spielschritt rückgängig.")
    return {"ergebnis": _ergebnis_zu_dict(result), "zustand": zustand()}


@_mit_verlauf
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


@_mit_verlauf
def trinke_kaffee(besitzer, wuerfel_index, delta):
    if _spiel is None:
        return _kein_spiel()
    ergebnis = _spiel.trinke_kaffee(besitzer, wuerfel_index, delta)
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


def moegliche_kaffee_deltas(besitzer, wuerfel_index):
    if _spiel is None:
        return []
    return _spiel.moegliche_kaffee_deltas(besitzer, wuerfel_index)


@_mit_verlauf
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


@_mit_verlauf
def rundenende():
    if _spiel is None:
        return _kein_spiel()
    ergebnis = _spiel.rundenende()
    return {"ergebnis": _ergebnis_zu_dict(ergebnis), "zustand": zustand()}


@_mit_verlauf
def wirf_verkehrswuerfel(besitzer=None):
    if _spiel is None:
        return _kein_spiel()
    ergebnis = _spiel.wirf_verkehrswuerfel(besitzer, runde_starten=False)
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


@_mit_verlauf
def modul_aktion(besitzer, aktion, parameter_json="{}"):
    if _spiel is None:
        return _kein_spiel()
    try:
        params = json.loads(parameter_json)
        if not isinstance(params, dict):
            raise ValueError("Parameter müssen ein Objekt sein.")
    except (ValueError, TypeError):
        result = Ergebnis(False, "ungueltige_aktion")
    else:
        result = _spiel.zusatz.aktion(besitzer, aktion, params)
    return {"ergebnis": _ergebnis_zu_dict(result), "zustand": zustand()}


@_mit_verlauf
def kooperation_waehlen_bestaetigen(besitzer, wuerfel_index, kooperation_id=None):
    """One policy choice and undo entry for selecting AND confirming a die.

    A rejected confirmation must not leave behind a partial selection. Genuine
    realtime expiry still applies, matching the engine's two-step operation.
    """
    global _spiel
    if _spiel is None:
        return _kein_spiel()
    if kooperation_id is not None and type(kooperation_id) is not int:
        return {"ergebnis": _ergebnis_zu_dict(Ergebnis(False, "ungueltige_aktion")), "zustand": zustand()}
    vorher = deepcopy(_spiel)
    lifecycle = (_spiel.status, _spiel.aktuelle_runde, _spiel.phase, _spiel.zusatz.deadline)
    params = {"wuerfel_index": wuerfel_index}
    if kooperation_id is not None:
        params["kooperation_id"] = kooperation_id
    result = _spiel.zusatz.aktion(besitzer, "kooperation_wahl", params)
    if result.erfolg:
        result = _spiel.zusatz.aktion(besitzer, "kooperation_bestaetigen", params)
    if not result.erfolg and lifecycle == (_spiel.status, _spiel.aktuelle_runde, _spiel.phase, _spiel.zusatz.deadline):
        _spiel = vorher
    return {"ergebnis": _ergebnis_zu_dict(result), "zustand": zustand()}


@_mit_verlauf
def tick():
    if _spiel is None:
        return _kein_spiel()
    result = _spiel.zusatz.tick()
    return {"ergebnis": _ergebnis_zu_dict(result), "zustand": zustand()}
