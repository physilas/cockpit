import random
from wuerfelfelder import Wuerfelfeld

class Wuerfel():

    def __init__(self, besitzer):

        self.augenzahl = None
        self.verfuegbar = True

        if besitzer not in ["pilot", "kopilot"]:
            raise ValueError("Besitzer muss entweder \"pilot\" oder \"kopilot\" sein.")
        self.besitzer = besitzer

    def get_augenzahl(self):
        return self.augenzahl
    def get_besitzer(self):
        return self.besitzer

    def werfen(self):
        self.augenzahl = random.randint(1, 6)

    def platzieren(self, wuerfelfeld: Wuerfelfeld):
        if wuerfelfeld > 0:
            return False
        self.verfuegbar = False
        wuerfelfeld = self.augenzahl


    

    

