import os
import yaml

def load_yaml(flughafen):
    # Relativ zum Ort DIESER Datei, nicht zum aktuellen Arbeitsverzeichnis -
    # sonst bricht es, sobald man das Skript nicht mehr aus backend/ heraus startet.
    verzeichnis = os.path.dirname(os.path.abspath(__file__))
    yaml_file = os.path.join(verzeichnis, "landungen", f"{flughafen}.yaml")
    with open(yaml_file, 'r') as file:
        data = yaml.safe_load(file)
    return data

class Landung():

    def __init__(self, flughafen):

        # PRIVATE (FIXED) VARIABLES

        data = load_yaml(flughafen)

        self._code = data.get('code')
        self._bezeichnung = data.get('bezeichnung')

        self._module = data.get('module')
        self._faehigkeitskarten = data.get('faehigkeitskarten')

        self._schwierigkeit = data.get('schwierigkeit')
        self._laenge = data.get('laenge')

        flugzeuge_wuerfel_kurven_min_max = [[int(x) 
                                             for x in item.split(" ")] 
                                             for item in data.get('flugzeuge_wuerfel_kurven_min_max')]
        self._initiale_flugzeuge = [flugzeuge_wuerfel_kurven_min_max[i][0] for i in range(len(flugzeuge_wuerfel_kurven_min_max))]
        self._flugzeugwuerfel = [flugzeuge_wuerfel_kurven_min_max[i][1] for i in range(len(flugzeuge_wuerfel_kurven_min_max))]   
        self._kurven_min = [flugzeuge_wuerfel_kurven_min_max[i][2] for i in range(len(flugzeuge_wuerfel_kurven_min_max))]
        self._kurven_max = [flugzeuge_wuerfel_kurven_min_max[i][3] for i in range(len(flugzeuge_wuerfel_kurven_min_max))]

        # DYNAMIC VARIABLES

        self.hoehe = 6000
        self.entfernung = self._laenge

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

    ### METHODS ###

    def reduce_hoehe(self, N=1):
        self.hoehe -= N

    def reduce_entfernung(self, N):
        self.entfernung -= N

    def add_flugzeug(self, index):
        self.flugzeuge[index] += 1

    def remove_flugzeug(self, index):
        if index >= len(self.flugzeuge) or self.flugzeuge[index] == 0:
            return False
        self.flugzeuge[index] -= 1
        return True

    ### ENTFERNUNGSLEISTE: INDEXIERUNG ###
    # Konvention (User-Vorgabe): Index 0 = ganz am Anfang, weit weg vom
    # Flughafen. Der LETZTE Index (laenge-1, bzw. -1) = der Flughafen
    # selbst. self.entfernung startet bei self._laenge und zaehlt bei jeder
    # Bewegung Richtung Flughafen runter.

    def aktuelle_position_index(self):
        """Index in `flugzeuge`, der der aktuellen Position entspricht."""
        return self._laenge - self.entfernung

    def ist_am_flughafen(self):
        """True, wenn die aktuelle Position genau der Flughafen ist
        (letztes Feld der Entfernungsleiste)."""
        return self.aktuelle_position_index() == self._laenge - 1

    def flugzeug_an_aktueller_position(self):
        index = self.aktuelle_position_index()
        if 0 <= index < len(self.flugzeuge):
            return self.flugzeuge[index] > 0
        return False

    def bewege_entfernung(self, felder):
        """Bewegt die Entfernungsleiste `felder` Felder Richtung Flughafen
        (ausgeloest durch Triebwerke, Handbuch S.6). Bewegt sich ein Feld
        nach dem anderen; VOR jedem Schritt wird geprueft:
          - ist die aktuelle Position schon der Flughafen? -> Uebers-Ziel-
            hinaus (kann nicht mehr weiter Richtung Flughafen fliegen).
          - steht noch ein Flugzeug auf der aktuellen (zu verlassenden)
            Position? -> Kollision.
        Gibt (ok: bool, grund: str|None) zurueck. grund ist "kollision"
        oder "uebers_ziel_hinaus" falls ok=False; in dem Fall wurde nicht
        mehr weiterbewegt als bis zu diesem Fehler (das Spiel ist verloren).
        """
        for _ in range(felder):
            if self.ist_am_flughafen():
                return False, "uebers_ziel_hinaus"
            if self.flugzeug_an_aktueller_position():
                return False, "kollision"
            self.reduce_entfernung(1)
        return True, None

    def entferne_flugzeug_per_funk(self, augenzahl):
        """Zaehlt von der aktuellen Position `augenzahl` Felder Richtung
        Flughafen (augenzahl=1 heisst: die aktuelle Position selbst) und
        entfernt dort SOFORT ein Flugzeug, falls eins da ist (Handbuch
        S.7). Gibt True zurueck, wenn tatsaechlich eins entfernt wurde."""
        ziel_index = self.aktuelle_position_index() + (augenzahl - 1)
        if ziel_index < 0 or ziel_index >= len(self.flugzeuge):
            return False
        return self.remove_flugzeug(ziel_index)

    def keine_flugzeuge_mehr(self):
        """Siegbedingung A (Handbuch S.11)."""
        return sum(self.flugzeuge) == 0

    def ist_am_boden(self):
        """Das Flugzeug-Bild auf der Hoehenleiste ist erreicht (0 Fuss).
        HINWEIS/Annahme: die Hoehenleiste zeigt 6000,5000,...,1000,0 -
        d.h. das Flugzeug-Symbol sitzt beim letzten (0 ft) Feld. Bitte am
        echten Brett gegenpruefen, falls es dort abweicht."""
        return self.hoehe <= 0

if __name__=='__main__':
    landung = Landung("YUL")
