class Wuerfelfeld:
    """
    Ein einzelnes Würfel-Feld im Cockpit (S.4, Grundregeln B-F).

    access: wer hier platzieren darf - "pilot", "kopilot", oder beides
    zahlen: erlaubte Augenzahlen (set/tuple) oder None = jede Zahl erlaubt
            (z.B. Funk- und Konzentrationsfelder, S.4 E/F)
    wuerfel: der aktuell hier liegende Wuerfel, oder None
    """

    def __init__(self, access, zahlen=None):
        self.access = [access] if isinstance(access, str) else list(access)
        self.zahlen = set(zahlen) if zahlen is not None else None
        self.wuerfel = None

    def ist_frei(self):
        return self.wuerfel is None

    def erlaubt(self, besitzer, augenzahl):
        """Prüft Farb- und Zahlvorgabe (S.4 B/C), ohne zu platzieren."""
        if besitzer not in self.access:
            return False
        if self.zahlen is not None and augenzahl not in self.zahlen:
            return False
        return True

    def platziere(self, wuerfel):
        """
        Versucht, `wuerfel` hier abzulegen. Gibt True/False zurück.
        Prüft nur die Feld-eigenen Vorgaben (Farbe/Zahl/frei) - Regeln,
        die von der Reihenfolge anderer Felder abhängen (Fahrwerk,
        Landeklappen, Bremsen), werden im Cockpit geprüft.
        """
        if not self.ist_frei():
            return False
        if not self.erlaubt(wuerfel.get_besitzer(), wuerfel.get_augenzahl()):
            return False
        self.wuerfel = wuerfel
        wuerfel.platziert = True
        return True

    def leere(self):
        """Nimmt den Würfel vom Feld zurück (Rundenende, S.9) und gibt ihn zurück."""
        wuerfel = self.wuerfel
        if wuerfel is not None:
            wuerfel.platziert = False
        self.wuerfel = None
        return wuerfel

    def __repr__(self):
        return f"Wuerfelfeld(access={self.access}, zahlen={self.zahlen}, wuerfel={self.wuerfel})"
