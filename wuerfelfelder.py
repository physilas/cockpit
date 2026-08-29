class Wuerfelfeld():
    
    def __init__(self, access):
        """
        Args:
            access (str/list): access level of the field, e.g. "pilot", "kopilot", ["pilot", "kopilot"]
        """
        # Define internal variables using __dict__ to bypass __setattr__ during init
        self.__dict__['value'] = 0
        
        # If access is a string like "pilot", wrapping it in list("pilot") makes ['p', 'i', 'l', 'o', 't'].
        # Let's ensure it handles both single strings and lists properly:
        self.__dict__['access'] = [access] if isinstance(access, str) else list(access)

    ### Attribute Access and Delegation ###

    def __getattr__(self, name):
        # Delegates all unknown attribute and method access to the inner data
        return getattr(self.value, name)
    def __setattr__(self, name, new_value):
        # Allow modifying 'value' or 'access' on the wrapper itself
        if name in ('value', 'access'):
            self.__dict__[name] = new_value
        else:
            # Forward everything else to the inner object
            setattr(self.value, name, new_value)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return f"Wuerfelfeld(value={self.value}, access={self.access})"
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


class Wuerfelfelder():

    def __init__(self):

        self.ruder_pilot = Wuerfelfeld("pilot")
        self.schub_pilot = Wuerfelfeld("pilot")

        self.fahrwerk_12 = Wuerfelfeld("pilot")
        self.fahrwerk_34 = Wuerfelfeld("pilot")
        self.fahrwerk_56 = Wuerfelfeld("pilot")

        self.bremse_2 = Wuerfelfeld("pilot")
        self.bremse_4 = Wuerfelfeld("pilot")
        self.bremse_6 = Wuerfelfeld("pilot")

        self.funken_pilot = Wuerfelfeld("pilot")

        self.schub_kopilot = Wuerfelfeld("kopilot")
        self.ruder_kopilot = Wuerfelfeld("kopilot")

        self.klappen_12 = Wuerfelfeld("kopilot")
        self.klappen_23 = Wuerfelfeld("kopilot")
        self.klappen_45 = Wuerfelfeld("kopilot")
        self.klappen_56 = Wuerfelfeld("kopilot")

        self.funken_1_kopilot = Wuerfelfeld("kopilot")
        self.funken_2_kopilot = Wuerfelfeld("kopilot")

        self.kaffee_1 = Wuerfelfeld(["pilot", "kopilot"])
        self.kaffee_2 = Wuerfelfeld(["pilot", "kopilot"])
        self.kaffee_3 = Wuerfelfeld(["pilot", "kopilot"])

