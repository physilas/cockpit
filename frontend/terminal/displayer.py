from backend.spielplan import Spielplan
from backend.regeln import RUDER_STALL_SCHWELLE, grund_text


def _balken(werte, aktiv_symbol="●", offen_symbol="○"):
    return "".join(aktiv_symbol if v else offen_symbol for v in werte)


def _wuerfel_zeile(werte, frei):
    teile = []
    for i, (wert, ist_frei) in enumerate(zip(werte, frei)):
        anzeige = str(wert) if wert is not None else "-"
        markierung = "" if ist_frei else "(gelegt)"
        teile.append(f"[{i}:{anzeige}{markierung}]")
    return " ".join(teile)


class Displayer:
    """
    Einfache, aber vollständig funktionale Textdarstellung des
    Spielplans - kein Nachbau der Cockpit-Grafik (siehe
    templates/spielplan.txt für das spätere Layout-Ziel), aber genug,
    um über die Konsole tatsächlich Cockpit zu spielen.
    """

    def __init__(self, spielplan: Spielplan):
        self.spielplan = spielplan

    def display_spielplan(self):
        s = self.spielplan
        z = s.zustand()
        cockpit = s.cockpit

        print("=" * 60)
        print(f" COCKPIT - {s.landung.get_bezeichnung()} ({s.landung.get_code()})")
        print(f" Runde {z['runde']}" + (" (LETZTE RUNDE)" if z['letzte_runde'] else "")
              + (" [WARTESCHLEIFE]" if z['warteschleife'] else ""))
        print("=" * 60)
        print(f" Hoehe: {z['hoehe']:>5} ft   Entfernung: {z['entfernung']}   "
              f"Flugzeuge voraus: {z['flugzeuge']}")
        print(f" Fluglage: {z['fluglage']:+d}  (Trudeln bei |x| >= {RUDER_STALL_SCHWELLE})")
        print(f" Aerodynamik blau/orange: {z['aerodynamik_blau']} / {z['aerodynamik_orange']}"
              f"   Bremsstaerke: {z['bremsstaerke']}")
        print(f" Fahrwerk:      {_balken(z['fahrwerk_ausgefahren'])}")
        print(f" Landeklappen:  {_balken(z['landeklappen_ausgefahren'])}")
        print(f" Bremsen:       {_balken(z['bremsen_aktiviert'])}")
        print(f" Kaffeetassen: {z['kaffeetassen']}   Neuwurf-Plaettchen: {z['neuwurf_plaettchen']}")
        print("-" * 60)
        print(f" Pilot   (blau)  Wuerfel: {_wuerfel_zeile(z['pilot_wuerfel'], z['pilot_wuerfel_frei'])}")
        print(f" Kopilot (orange) Wuerfel: {_wuerfel_zeile(z['kopilot_wuerfel'], z['kopilot_wuerfel_frei'])}")
        print("-" * 60)
        if z["letzte_meldung"]:
            print(f" > {z['letzte_meldung']}")
        if z["status"] == "laeuft":
            print(f" Am Zug: {z['am_zug'].upper()}")
        else:
            print(f" SPIELENDE: {z['status'].upper()} ({grund_text(z['verlust_grund']) or 'Sieg!'})")
        print("=" * 60)
