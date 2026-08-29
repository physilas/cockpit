from landung import Landung
from wuerfelfelder import Wuerfelfelder


def _activate(task, index, sequential):
    if sequential and index > 0 and task[index - 1] == 0:
        return False
    if task[index] == 1:
        return False
    task[index] = 1
    return True


class Spielplan():

    def __init__(self):

        self.landung = Landung()
        self.wuerfelfelder = Wuerfelfelder()

        self.fahrwerke = [0, 0, 0]
        self.klappen = [0, 0, 0, 0]
        self.bremsen = [0, 0, 0]
        self.kaffees = 0
        self.ruder = 0

        if self.landung.get_schwierigkeit() <= 1:
            self.anzahl_neuwurf = 1
        else:
            self.anzahl_neuwurf = 0

        self.schub_min = self.compute_schub_min()
        self.bremsen_max = self.compute_bremsen_max()

    ### GETTERS ###

    def get_fahrwerke(self):
        return self.fahrwerke
    def get_klappen(self):
        return self.klappen
    def get_bremsen(self):
        return self.bremsen
    def get_ruder(self):
        return self.ruder
    def get_kaffees(self):
        return self.kaffees
    def get_anzahl_neuwurf(self):
        return self.anzahl_neuwurf
    def get_schub_min(self):
        return self.schub_min
    def get_bremsen_max(self):
        return self.bremsen_max

    ### METHODS ###

    def activate_fahrwerk(self, index):
        _activate(self.fahrwerke, index, sequential=False)
        self.compute_schub_min()

    def activate_klappen(self, index):
        _activate(self.klappen, index, sequential=True)
        self.compute_schub_min()

    def activate_bremsen(self, index):
        _activate(self.bremsen, index, sequential=True)
        self.compute_bremsen_max()

    def compute_schub_min(self):
        return [5 + sum(self.fahrwerke), 9 + sum(self.klappen)]

    def compute_bremsen_max(self):
        return 2 * sum(self.bremsen)

    def koche_kaffee(self):
        if self.kaffees < 3:
            self.kaffees += 1

    def trinke_kaffee(self):
        if self.kaffees == 0:
            return False
        self.kaffees -= 1
        return True

    def bewege_ruder(self, N):
        self.ruder += N
        if self.ruder < -2 or self.ruder > 2:
            return False
        return True

    def benutze_neuwurf(self):
        if self.anzahl_neuwurf == 0:
            return False
        self.anzahl_neuwurf -= 1
        return True
