class Wuerfelfeld():

    def __init__(self, access, allowed_values=None):
        """
        Args:
            access (str/list): access level of the field, e.g. "pilot", "kopilot", ["pilot", "kopilot"]
            allowed_values (list[int] | None): which die values (1-6) may be placed
                here. None means any value is allowed (Ruder, Triebwerke, Funk,
                Konzentration all have no number restriction per the manual).
        """
        # Define internal variables using __dict__ to bypass __setattr__ during init
        self.__dict__['value'] = 0

        # If access is a string like "pilot", wrapping it in list("pilot") makes ['p', 'i', 'l', 'o', 't'].
        # Let's ensure it handles both single strings and lists properly:
        self.__dict__['access'] = [access] if isinstance(access, str) else list(access)
        self.__dict__['allowed_values'] = list(allowed_values) if allowed_values is not None else None

    ### Attribute Access and Delegation ###

    def __getattr__(self, name):
        # Delegates all unknown attribute and method access to the inner data
        return getattr(self.value, name)
    def __setattr__(self, name, new_value):
        # Allow modifying 'value'/'access'/'allowed_values' on the wrapper itself
        if name in ('value', 'access', 'allowed_values'):
            self.__dict__[name] = new_value
        else:
            # Forward everything else to the inner object
            setattr(self.value, name, new_value)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return f"Wuerfelfeld(value={self.value}, access={self.access}, allowed_values={self.allowed_values})"
    def __eq__(self, other):
        if isinstance(other, Wuerfelfeld):
            return self.value == other.value
        return self.value == other

    ### Math Operators for Integer Behavior ###

    def __add__(self, other):
        # Returns a new value or wrapper depending on your architecture.
        # Normally, 'a + b' should return the result without modifying 'a' in place.
        if isinstance(other, Wuerfelfeld):
            return self.value + other.value
        return self.value + other
    def __radd__(self, other):
        # Handles reverse addition (e.g., 5 + wrapper)
        return self.__add__(other)
    def __iadd__(self, other):
        # Handles in-place addition (e.g., field += 5)
        if isinstance(other, Wuerfelfeld):
            self.value += other.value
        else:
            self.value += other
        return self

    ### GETTERS ###

    def get_access(self):
        return self.access

    def get_allowed_values(self):
        return self.allowed_values

    ### METHODS ###

    def ist_frei(self):
        """True, wenn noch kein Wuerfel auf diesem Feld liegt."""
        return self.value == 0

    def erlaubt(self, besitzer, augenzahl):
        """Prueft Farb- UND Zahlvorgabe fuer einen Wuerfel mit gegebenem
        Besitzer ("pilot"/"kopilot") und Augenzahl (1-6)."""
        if besitzer not in self.access:
            return False
        if self.allowed_values is not None and augenzahl not in self.allowed_values:
            return False
        return True

    def zuruecksetzen(self):
        """Nimmt den Wuerfel wieder vom Feld (Rundenende / Sinkflug)."""
        self.__dict__['value'] = 0


class Wuerfelfelder():

    def __init__(self):

        # Pflichtfelder (je 1 blauer + 1 oranger Wuerfel pro Runde erforderlich).
        # Keine Zahlvorgabe.
        self.ruder_pilot = Wuerfelfeld("pilot")
        self.ruder_kopilot = Wuerfelfeld("kopilot")
        self.schub_pilot = Wuerfelfeld("pilot")
        self.schub_kopilot = Wuerfelfeld("kopilot")

        # Fahrwerk: nur Pilot, beliebige Reihenfolge, je eigene Zahlvorgabe.
        self.fahrwerk_12 = Wuerfelfeld("pilot", [1, 2])
        self.fahrwerk_34 = Wuerfelfeld("pilot", [3, 4])
        self.fahrwerk_56 = Wuerfelfeld("pilot", [5, 6])

        # Bremsen: nur Pilot, MUSS von links nach rechts aktiviert werden.
        self.bremse_2 = Wuerfelfeld("pilot", [2])
        self.bremse_4 = Wuerfelfeld("pilot", [4])
        self.bremse_6 = Wuerfelfeld("pilot", [6])

        # Funk: Farbvorgabe, aber keine Zahlvorgabe. Pilot hat 1 Feld, Co-Pilot 2.
        self.funken_pilot = Wuerfelfeld("pilot")
        self.funken_1_kopilot = Wuerfelfeld("kopilot")
        self.funken_2_kopilot = Wuerfelfeld("kopilot")

        # Landeklappen: nur Co-Pilot, MUSS von oben nach unten aktiviert werden.
        self.klappen_12 = Wuerfelfeld("kopilot", [1, 2])
        self.klappen_23 = Wuerfelfeld("kopilot", [2, 3])
        self.klappen_45 = Wuerfelfeld("kopilot", [4, 5])
        self.klappen_56 = Wuerfelfeld("kopilot", [5, 6])

        # Konzentration: keine Vorgabe ueberhaupt (Farbe oder Zahl).
        self.kaffee_1 = Wuerfelfeld(["pilot", "kopilot"])
        self.kaffee_2 = Wuerfelfeld(["pilot", "kopilot"])
        self.kaffee_3 = Wuerfelfeld(["pilot", "kopilot"])

    def alle_felder(self):
        """Gibt ein dict {feldname: Wuerfelfeld} zurueck - praktisch fuer
        generische Iteration (Anzeige, Rundenende-Reset, etc.)."""
        return {name: feld for name, feld in vars(self).items()
                if isinstance(feld, Wuerfelfeld)}
