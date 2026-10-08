"""
Zentrale Spielkonstanten für Cockpit.

Alle Werte sind mit der Seite des Original-Regelhefts referenziert,
auf der sie stehen.
"""

ANZAHL_RUNDEN = 7  # S.4: "Eine Partie verläuft über 7 Runden"

# S.5 RUDER: Trudeln, sobald der Anzeiger das X erreicht/überschreitet.
# Bestätigt am physischen Board: Trudeln bei |Fluglage| > 2, d.h. ab 3.
RUDER_STALL_SCHWELLE = 3

# S.3 Aufbau: Aerodynamik-Marker starten zwischen 4/5 (blau) und 8/9 (orange).
AERODYNAMIK_BLAU_START = 4.5
AERODYNAMIK_ORANGE_START = 8.5

# S.7 Fahrwerk: jedes ausgefahrene Teil verschiebt den blauen Marker um 1.
# S.8 Landeklappen: jede ausgefahrene Klappe verschiebt den orangen Marker um 1.
AERODYNAMIK_SCHRITT = 1

# S.9 Bremsen: Marker beginnt links vor der 2, jede Bremse schiebt ihn 1
# Feld weiter. Wirksam lässt sich die Bremsstärke als 2 * (Anzahl
# aktivierter Bremsen) modellieren (siehe Kommentar in cockpit.py für
# die Herleitung anhand des Beispiels auf S.11: Bremsen 2+4 aktiviert,
# Geschwindigkeit 4 erfüllt die Siegbedingung).
BREMSSTAERKE_PRO_AKTIVIERUNG = 2

# S.8 Konzentration: nie mehr als 3 Kaffeetassen gleichzeitig im Vorrat.
MAX_KAFFEETASSEN = 3

# Würfelwerte sind immer 1-6, Kaffee darf nur innerhalb dieses Bereichs
# verschieben (aus einer 1 wird durch Verringern keine 6, S.8).
WUERFEL_MIN = 1
WUERFEL_MAX = 6

from .ui_schema import frontend_schema

# Also exported by build.py for both browser clients.
GRUND_TEXT = frontend_schema()["grund_texte"]


def grund_text(code):
    """
    Wandelt einen (evtl. kommagetrennten, siehe _werte_spielende_aus)
    verlust_grund-Code in lesbaren, korrekt großgeschriebenen deutschen
    Text um. Unbekannte Codes werden unverändert durchgereicht, statt
    einen Fehler zu werfen.
    """
    if not code:
        return ""
    return ", ".join(GRUND_TEXT.get(teil, teil) for teil in code.split(","))
