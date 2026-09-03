import random

from .regeln import WUERFEL_MIN, WUERFEL_MAX

BESITZER = ("pilot", "kopilot")


class Wuerfel:
    """
    Ein einzelner Würfel eines Spielers.

    besitzer: "pilot" (blau) oder "kopilot" (orange)
    augenzahl: aktueller Wert (1-6) oder None, solange nicht gewürfelt
    platziert: ob der Würfel gerade auf einem Feld im Cockpit liegt
    """

    def __init__(self, besitzer):
        if besitzer not in BESITZER:
            raise ValueError('Besitzer muss "pilot" oder "kopilot" sein.')
        self.besitzer = besitzer
        self.augenzahl = None
        self.platziert = False

    def get_augenzahl(self):
        return self.augenzahl

    def get_besitzer(self):
        return self.besitzer

    def ist_platziert(self):
        return self.platziert

    def ist_verfuegbar(self):
        """Verfügbar = gewürfelt, aber noch nicht auf einem Feld platziert."""
        return self.augenzahl is not None and not self.platziert

    def werfen(self):
        """Würfelt neu (Rundenbeginn oder Neuwurf-Plättchen, S.4)."""
        self.augenzahl = random.randint(1, 6)
        self.platziert = False
        return self.augenzahl

    def veraendere(self, delta):
        """
        Verändert die Augenzahl um `delta` (per Kaffee, S.8).
        Wird bei 1 bzw. 6 gekappt statt "umzuklappen" ("Aus einer 1 kann
        keine 6 gemacht werden - oder umgekehrt").
        Gibt den tatsächlich angewendeten Delta zurück (kann kleiner
        als angefragt sein, wenn die Grenze erreicht wird).
        """
        if self.augenzahl is None:
            raise ValueError("Würfel wurde noch nicht geworfen.")
        neu = max(WUERFEL_MIN, min(WUERFEL_MAX, self.augenzahl + delta))
        tatsaechlich = neu - self.augenzahl
        self.augenzahl = neu
        return tatsaechlich

    def __repr__(self):
        return f"Wuerfel({self.besitzer}, {self.augenzahl})"
