from backend.spielplan import Spielplan


def _schalter(zustand):
    return "".join("*" if s else "." for s in zustand)


class Displayer:

    def __init__(self, spielplan: Spielplan):
        self.spielplan = spielplan

    def display_spielplan(self):
        sp = self.spielplan
        landung = sp.landung

        print("=" * 62)
        print(f" {landung.get_bezeichnung()} ({landung.get_code()})"
              f"   Hoehe: {landung.get_hoehe():>5} ft"
              f"   Position: {landung.aktuelle_position_index()}/{landung.get_laenge() - 1}")
        if sp.warteschleife:
            print(" [WARTESCHLEIFE - zu frueh am Flughafen, Entfernung eingefroren]")
        if sp.letzte_runde:
            print(" [LETZTE RUNDE - Bremsen statt Aerodynamik bei Triebwerke!]")
        print("-" * 62)
        trudeln_hinweis = "  !!! GETRUDELT !!!" if sp.ruder_im_trudeln() else ""
        print(f" Ruder (Fluglage): {sp.get_ruder():+d}   "
              f"(Trudeln bei <= -3 oder >= +3){trudeln_hinweis}")
        print(f" Fahrwerk  [1/2,3/4,5/6]: {_schalter(sp.get_fahrwerke())}   "
              f"Schub-Schwellen [blau,orange]: {sp.get_schub_min()}")
        print(f" Klappen [1/2,2/3,4/5,5/6]: {_schalter(sp.get_klappen())}")
        print(f" Bremsen [2,4,6]: {_schalter(sp.get_bremsen())}   "
              f"max. Landegeschwindigkeit: {sp.get_bremsen_max()}")
        print(f" Kaffeetassen: {sp.get_kaffees()}   Neuwurf-Marker: {sp.get_anzahl_neuwurf()}")
        print(f" Flugzeuge auf der Leiste: {landung.get_flugzeuge()}"
              f"  (aktuelle Position = Index {landung.aktuelle_position_index()})")
        print("=" * 62)
