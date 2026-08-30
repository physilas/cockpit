from pathlib import Path

import yaml

_LANDUNGEN_DIR = Path(__file__).resolve().parent / "landungen"


def load_yaml(flughafen):
    yaml_file = _LANDUNGEN_DIR / f"{flughafen}.yaml"
    with open(yaml_file, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data


class Landung:
    """
    Der flughafenspezifische Teil des Spielplans: Entfernungsleiste
    (S.3/S.6) und Höhenleiste (S.3/S.9).

    ANNAHME / OFFENE FRAGE (siehe README):
        Das YAML-Feld "flugzeugwuerfel" sowie "kurven_min"/"kurven_max"
        kommen im Basis-Regelheft NICHT vor. Ich vermute, dass sie für
        die fortgeschrittenen Szenarien (Schachteleinsatz, S.3 Hinweis)
        gedacht sind, die dieses Handbuch nicht abdeckt. Sie werden hier
        geladen und über Getter bereitgestellt, aber vom Basis-Regelwerk
        (cockpit.py / spiel.py) nicht verwendet. Bitte prüfen, ob das so
        gewünscht ist, oder ob sie etwas anderes bedeuten sollen.
    """

    def __init__(self, flughafen):
        data = load_yaml(flughafen)

        # PRIVATE (FIXED) VARIABLES
        self._flughafen_code = flughafen
        self._code = data.get("code")
        self._bezeichnung = data.get("bezeichnung")

        self._module = data.get("module")
        self._faehigkeitskarten = data.get("faehigkeitskarten")

        self._schwierigkeit = data.get("schwierigkeit")
        self._laenge = data.get("laenge")

        rohdaten = [
            [int(x) for x in item.split(" ")]
            for item in data.get("flugzeuge_wuerfel_kurven_min_max")
        ]
        # Index 0 = am weitesten vom Flughafen entfernt (Entfernung == laenge),
        # letzter Index = unmittelbar vor dem Flughafen (Entfernung == 1).
        self._initiale_flugzeuge = [row[0] for row in rohdaten]
        self._flugzeugwuerfel = [row[1] for row in rohdaten]  # siehe Hinweis oben
        self._kurven_min = [row[2] for row in rohdaten]  # siehe Hinweis oben
        self._kurven_max = [row[3] for row in rohdaten]  # siehe Hinweis oben

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
        if index is None or index >= len(self.flugzeuge) or self.flugzeuge[index] == 0:
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
    landung = Landung("YUL")
    print(landung.get_bezeichnung(), landung.get_flugzeuge())
