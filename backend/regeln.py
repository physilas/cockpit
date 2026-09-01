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

# S.4: 2 Neuwurf-Plättchen, platziert auf den Neuwurf-Symbolen der
# Höhenleiste (die Positionen hängen vom Flughafen/Szenario ab und
# stehen daher in der jeweiligen landungen/<code>.yaml).
ANZAHL_NEUWURF_PLAETTCHEN = 2

# S.8 Konzentration: nie mehr als 3 Kaffeetassen gleichzeitig im Vorrat.
MAX_KAFFEETASSEN = 3

# Würfelwerte sind immer 1-6, Kaffee darf nur innerhalb dieses Bereichs
# verschieben (aus einer 1 wird durch Verringern keine 6, S.8).
WUERFEL_MIN = 1
WUERFEL_MAX = 6

# Menschlich lesbare (großgeschriebene) Anzeige-Texte für die internen
# grund-Codes von Ergebnis - sowohl Verlust-Gründe als auch abgelehnte
# Aktionen (Bug #6: "kollision" -> "Kollision" usw.). Zentral hier
# gepflegt, damit Terminal- und Web-Frontend denselben Text zeigen.
GRUND_TEXT = {
    # Verlust-/Siegauswertung
    "trudeln": "Trudeln",
    "kollision": "Kollision",
    "uebers_ziel_hinaus": "Übers Ziel hinaus",
    "zu_schnell_gelandet": "Zu schnell gelandet",
    "notlandung": "Notlandung",
    "pflichtfelder_nicht_erfuellt": "Pflichtfelder nicht erfüllt",
    "flugzeuge_uebrig": "Flugzeuge übrig",
    "fahrwerk_unvollstaendig": "Fahrwerk unvollständig",
    "landeklappen_unvollstaendig": "Landeklappen unvollständig",
    "nicht_waagerecht": "Nicht waagerecht",
    # Abgelehnte Aktionen (Ergebnis.erfolg == False)
    "feld_ungueltig": "Feld ungültig",
    "ungueltiger_index": "Ungültiger Index",
    "falsche_reihenfolge": "Falsche Reihenfolge",
    "triebwerke_nicht_platziert": "Triebwerke noch nicht platziert",
    "wuerfel_bereits_platziert": "Würfel bereits platziert",
    "nicht_genug_kaffee": "Nicht genug Kaffee",
    "kein_neuwurf_plaettchen": "Kein Neuwurf-Plättchen verfügbar",
    "spiel_beendet": "Spiel beendet",
    "nicht_am_zug": "Nicht am Zug",
    "ungueltiger_wuerfel_index": "Ungültiger Würfel-Index",
    "wuerfel_nicht_verfuegbar": "Würfel nicht verfügbar",
    "unbekanntes_ziel": "Unbekanntes Ziel",
    "noch_nicht_alle_wuerfel_platziert": "Noch nicht alle Würfel platziert",
}


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
