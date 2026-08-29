from ..backend.spielplan import Spielplan

class Displayer:

    def __init__(self, spielplan: Spielplan):
        self.spielplan = spielplan

    def display_spielplan(self):
        