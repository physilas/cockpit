import random


class Wuerfel():

    def __init__(self, besitzer):

        self.augenzahl = None
        self.verfuegbar = True

        if besitzer not in ["pilot", "kopilot"]:
            raise ValueError("Besitzer muss entweder \"pilot\" oder \"kopilot\" sein.")
        self.besitzer = besitzer

    ### GETTERS ###

    def get_augenzahl(self):
        return self.augenzahl

    def get_besitzer(self):
        return self.besitzer

    def ist_verfuegbar(self):
        return self.verfuegbar

    ### METHODS ###

    def werfen(self):
        self.augenzahl = random.randint(1, 6)
        self.verfuegbar = True

    def veraendere_augenzahl(self, delta):
        """Kaffee-Effekt: verschiebt den Wert um `delta` (i.d.R. +-1 pro Tasse).
        Geklemmt auf 1..6, KEIN Wraparound (aus einer 1 wird durch Verringern
        keine 6, siehe Handbuch S.8). Gibt True zurueck, falls der Wert
        tatsaechlich geaendert wurde."""
        if self.augenzahl is None:
            return False
        neuer_wert = self.augenzahl + delta
        if neuer_wert < 1 or neuer_wert > 6:
            return False
        self.augenzahl = neuer_wert
        return True

    def platzieren(self, wuerfelfeld):
        """Platziert diesen Wuerfel auf `wuerfelfeld`, sofern er verfuegbar ist,
        das Feld frei ist, und Farb-/Zahlvorgabe des Feldes erfuellt sind.
        Gibt True bei Erfolg zurueck, sonst False (nichts wird veraendert)."""
        if not self.verfuegbar or self.augenzahl is None:
            return False
        if not wuerfelfeld.ist_frei():
            return False
        if not wuerfelfeld.erlaubt(self.besitzer, self.augenzahl):
            return False

        wuerfelfeld.value = self.augenzahl
        self.verfuegbar = False
        return True


if __name__ == '__main__':
    w = Wuerfel("pilot")
    w.werfen()
    print(w.get_augenzahl())
