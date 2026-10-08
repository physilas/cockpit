from pathlib import Path
import re

import yaml

_LANDUNGEN_DIR = Path(__file__).resolve().parent / "landungen"
_CODE_RE = re.compile(r"^[A-Z0-9_-]+$")


class FlughafenKonfigurationsfehler(ValueError):
    """A scenario file is missing or structurally invalid."""


def load_yaml(flughafen):
    if not isinstance(flughafen, str) or not _CODE_RE.fullmatch(flughafen.upper()):
        raise FlughafenKonfigurationsfehler("Ungültiger Flughafen-Code.")
    yaml_file = _LANDUNGEN_DIR / f"{flughafen.upper()}.yaml"
    try:
        with open(yaml_file, "r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except FileNotFoundError as exc:
        raise FlughafenKonfigurationsfehler(f"Unbekannter Flughafen: {flughafen!r}") from exc
    except yaml.YAMLError as exc:
        raise FlughafenKonfigurationsfehler(f"Ungültiges YAML in {yaml_file.name}.") from exc
    if not isinstance(data, dict):
        raise FlughafenKonfigurationsfehler(f"{yaml_file.name}: erwartet ein YAML-Objekt.")
    _pruefe_konfiguration(data, yaml_file.name)
    return data


def _pruefe_konfiguration(data, dateiname):
    """Fail early with a useful error before a malformed airport starts a game."""
    for key in ("code", "bezeichnung", "laenge", "flugzeuge_wuerfel_kurven_min_max"):
        if key not in data:
            raise FlughafenKonfigurationsfehler(f"{dateiname}: Pflichtfeld {key!r} fehlt.")
    laenge = data["laenge"]
    if isinstance(laenge, bool) or not isinstance(laenge, int) or laenge < 1:
        raise FlughafenKonfigurationsfehler(f"{dateiname}: 'laenge' muss eine positive ganze Zahl sein.")
    zeilen = data["flugzeuge_wuerfel_kurven_min_max"]
    if not isinstance(zeilen, list) or len(zeilen) != laenge:
        raise FlughafenKonfigurationsfehler(
            f"{dateiname}: erwartet genau {laenge} Distanzzeilen, erhalten: "
            f"{len(zeilen) if isinstance(zeilen, list) else 'kein Array'}."
        )
    for nummer, zeile in enumerate(zeilen, start=1):
        try:
            werte = [int(x) for x in zeile.split()]
        except (AttributeError, ValueError) as exc:
            raise FlughafenKonfigurationsfehler(f"{dateiname}: ungültige Distanzzeile {nummer}.") from exc
        if len(werte) != 4 or werte[0] < 0 or werte[1] < 0 or werte[2] > werte[3]:
            raise FlughafenKonfigurationsfehler(f"{dateiname}: ungültige Distanzzeile {nummer}.")
    hoehen = data.get("neuwurf_hoehen", [])
    if not isinstance(hoehen, list) or any(
        isinstance(h, bool) or not isinstance(h, int) or h < 0 or h % 1000 for h in hoehen
    ):
        raise FlughafenKonfigurationsfehler(
            f"{dateiname}: 'neuwurf_hoehen' muss eine Liste nichtnegativer 1000-ft-Werte sein."
        )


def flughafen_liste():
    """
    Liste aller Flughäfen, die in backend/landungen/*.yaml liegen - fürs
    Frontend, damit die Flughafen-Auswahl nicht mehr hart codiert werden
    muss, sondern jede neu hinzugefügte YAML-Datei automatisch auftaucht.

    Eine YAML-Datei kann sich mit `sichtbar: false` aus dieser Liste
    ausblenden (z.B. die reine Engine-Test-Strecke TEST.yaml), taucht
    dann aber weiterhin ganz normal auf, wenn man sie über ihren Code
    direkt anfordert (Landung(code) liest sie unabhängig davon).
    """
    ergebnisse = []
    for pfad in sorted(_LANDUNGEN_DIR.glob("*.yaml")):
        try:
            data = load_yaml(pfad.stem)
        except FlughafenKonfigurationsfehler:
            continue
        if data.get("sichtbar", True) is False:
            continue
        ergebnisse.append({
            "code": data.get("code", pfad.stem),
            "bezeichnung": data.get("bezeichnung", pfad.stem),
        })
    ergebnisse.sort(key=lambda eintrag: eintrag["bezeichnung"])
    return ergebnisse


class Landung:
    """
    Der flughafenspezifische Teil des Spielplans: Entfernungsleiste
    (S.3/S.6) und Höhenleiste (S.3/S.9).

    "kurven_min"/"kurven_max" (bestätigt): je Entfernungsfeld die erlaubte
        Ruderstellung (Fluglage) beim Überfliegen dieses Feldes, wie auf
        den Distanz-Modulen (z.B. aus dem skyteam.fly.dev-Generator)
        aufgedruckt: -2/+2 = keine Einschränkung. Die Engine erzwingt diese
        Korridore beim Bewegen (Cockpit.loese_triebwerke_auf()).

    OFFENE FRAGE: "flugzeugwuerfel" (Würfel-Symbol auf dem Modul) wird
        geladen, aber weder angezeigt noch ausgewertet.
    """

    def __init__(self, flughafen):
        data = load_yaml(flughafen)

        # PRIVATE (FIXED) VARIABLES
        self._flughafen_code = flughafen.upper()
        self._code = data.get("code")
        self._bezeichnung = data.get("bezeichnung")

        self._module = data.get("module")
        self._faehigkeitskarten = data.get("faehigkeitskarten")

        self._schwierigkeit = data.get("schwierigkeit")
        self._laenge = data.get("laenge")

        rohdaten = [
            [int(x) for x in item.split()]
            for item in data.get("flugzeuge_wuerfel_kurven_min_max")
        ]
        # Index 0 = am weitesten vom Flughafen entfernt (Entfernung == laenge),
        # letzter Index = unmittelbar vor dem Flughafen (Entfernung == 1).
        self._initiale_flugzeuge = [row[0] for row in rohdaten]
        self._flugzeugwuerfel = [row[1] for row in rohdaten]  # siehe Hinweis oben
        self._kurven_min = [row[2] for row in rohdaten]  # siehe Hinweis oben
        self._kurven_max = [row[3] for row in rohdaten]  # siehe Hinweis oben
        self._neuwurf_hoehen = list(data.get("neuwurf_hoehen", []))

        # DYNAMIC VARIABLES
        self.hoehe = 6000  # S.3 Schritt 5
        self.entfernung = self._laenge  # S.3 Schritt 6
        self.flugzeuge = self._initiale_flugzeuge.copy()

    ### GETTERS ###

    def get_code(self):
        return self._code

    def get_bezeichnung(self):
        return self._bezeichnung

    def get_module(self):
        return self._module

    def get_faehigkeitskarten(self):
        return self._faehigkeitskarten

    def get_schwierigkeit(self):
        return self._schwierigkeit

    def get_laenge(self):
        return self._laenge

    def get_initial_flugzeuge(self):
        return self._initiale_flugzeuge

    def get_flugzeugwuerfel(self):
        return self._flugzeugwuerfel

    def get_kurven_min(self):
        return self._kurven_min

    def get_kurven_max(self):
        return self._kurven_max

    def get_neuwurf_hoehen(self):
        return self._neuwurf_hoehen.copy()

    def get_hoehe(self):
        return self.hoehe

    def get_entfernung(self):
        return self.entfernung

    def get_flugzeuge(self):
        return self.flugzeuge

    ### INDEX-HILFEN ###

    def _index_fuer_entfernung(self, entfernung):
        """Wandelt eine Entfernung (1..laenge) in einen Index in `flugzeuge` um."""
        if entfernung < 1 or entfernung > self._laenge:
            return None
        return self._laenge - entfernung

    def verbotenes_feld_fuer_ruder(self, fluglage, bewegung):
        """
        Prüft die Ruder-Korridore (kurven_min/kurven_max) aller Felder, die
        bei einer Bewegung um `bewegung` Felder überflogen werden: das
        aktuelle Feld sowie (bei Bewegung 2) das nächste. Gibt die Entfernung
        des ersten Feldes zurück, dessen Korridor `fluglage` verbietet,
        sonst None.
        """
        aktuell = self._laenge - self.entfernung
        for idx in range(aktuell, min(aktuell + bewegung, self._laenge)):
            if idx < 0:
                continue
            if not (self._kurven_min[idx] <= fluglage <= self._kurven_max[idx]):
                return self._laenge - idx
        return None

    def flugzeuge_an_aktueller_position(self):
        idx = self._index_fuer_entfernung(self.entfernung)
        if idx is None:
            return 0
        return self.flugzeuge[idx]

    ### METHODS ###

    def reduce_hoehe(self, N=1):
        self.hoehe -= 1000 * N

    def reduce_entfernung(self, N):
        self.entfernung -= N

    def add_flugzeug(self, index):
        self.flugzeuge[index] += 1

    def remove_flugzeug(self, index):
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(self.flugzeuge):
            return False
        if self.flugzeuge[index] == 0:
            return False
        self.flugzeuge[index] -= 1
        return True

    def remove_flugzeug_bei_entfernung(self, entfernung):
        """Entfernt ein Flugzeug beim angegebenen Entfernungswert (Funk, S.7)."""
        return self.remove_flugzeug(self._index_fuer_entfernung(entfernung))

    ### ZUSTANDSPRÜFUNGEN (S.9/S.10) ###

    def ist_am_flughafen(self):
        """'Flughafen-Bild auf Aktueller Position' - S.9."""
        return self.entfernung <= 0

    def ist_auf_hoehe_null(self):
        """'Flugzeug-Bild auf Aktueller Höhe' - S.9 (Boden erreicht)."""
        return self.hoehe <= 0

    def ist_frei_von_flugzeugen(self):
        """Siegbedingung A (S.11): kein Flugzeug mehr auf der Entfernungsleiste."""
        return sum(self.flugzeuge) == 0


if __name__ == "__main__":
    landung = Landung("MUC")
    print(landung.get_bezeichnung(), landung.get_flugzeuge())
