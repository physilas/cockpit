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
        
if __name__=='__main__':
    landung = Landung("YUL")
