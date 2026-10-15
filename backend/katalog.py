"""Logbook metadata and explicit training fixtures, independent of transport/UI."""
import json
from pathlib import Path


def logbuch_katalog():
    return json.loads(Path(__file__).with_name("landekatalog.json").read_text(encoding="utf-8"))


def szenario_konfiguration(code):
    """Photo-based routes and retained mock fixtures share the same rule engine."""
    katalog = logbuch_katalog()
    for s in katalog["scenarios"]:
        mock = code == f'MOCK_{s["code"]}_{s["difficulty"].upper()}'
        if s["engine_code"] == code or mock:
            uebung = mock
            track = s["mock_track"] if mock else s["track"]
            return {
                "code": code, "bezeichnung": f'{s["code"]} {s["name"]}' + (" (Übungsregeln)" if uebung else ""),
                "sichtbar": False, "szenario_id": s["id"], "mock": mock, "uebung": uebung,
                "verkehr_regel": "eigene" if mock else "offiziell",
                "geplante_module": s["modules"], "faehigkeitskarten": s["ability_count"], "module": s["modules"],
                "schwierigkeit": [d["id"] for d in katalog["difficulties"]].index(s["difficulty"]),
                "laenge": len(track), "neuwurf_hoehen": s["neuwurf_hoehen"],
                "flugzeuge_wuerfel_kurven_min_max": track,
            }
    raise ValueError(f"Unbekannte Logbuch-Strecke: {code}")


def landekatalog():
    from .landung import flughafen_liste, load_yaml

    katalog = logbuch_katalog()
    katalog["photos"] = json.loads(Path(__file__).with_name("bildnachweise.json").read_text(encoding="utf-8"))
    for f in flughafen_liste():
        data = load_yaml(f["code"])
        katalog["scenarios"].append({
            "id": f'custom-{f["code"]}', "code": f["code"], "name": f["bezeichnung"],
            "city": f["bezeichnung"], "country": "Eigene Strecke", "kind": "custom",
            "difficulty": "custom", "description": "Bisherige Strecke aus der App. Die Streckendaten sind eigene Vorgaben und keine verifizierte Logbuch-Landung.",
            "image": katalog["photos"].get(f["code"], {}).get("path"),
            "modules": [], "ability_count": 0, "engine_code": f["code"], "mock": False, "practice": False,
            "track": data["flugzeuge_wuerfel_kurven_min_max"], "route_verified": False,
        })
    return katalog
