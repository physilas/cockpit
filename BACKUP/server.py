#!/usr/bin/env python3
"""
Cockpit – Lokaler Multiplayer-Server

Startet einen HTTP-Server (Port 8080) für die Spielseite und einen
WebSocket-Server (Port 8765) für die Echtzeit-Kommunikation.
Beide Geräte müssen im gleichen WLAN sein.

Starten:
    pip install websockets
    python3 server.py

Der Server zeigt dann die URLs, die die beiden Spieler öffnen müssen.
"""

import asyncio
import json
import os
import socket
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

try:
    import websockets
    import websockets.exceptions
except ImportError:
    print("Fehler: 'websockets' nicht installiert.")
    print("Bitte ausführen:  pip install websockets")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from backend.spielplan import Spielplan  # noqa: E402
from backend.regeln import grund_text    # noqa: E402

HTTP_PORT = 8080
WS_PORT   = 8765

# ---------------------------------------------------------------------------
# Spielzustand (nur im asyncio-Thread verwendet, kein Lock nötig)
# ---------------------------------------------------------------------------
spielplan: Spielplan | None = None
verbindungen: dict = {}   # rolle -> websocket


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def zustand_fuer_rolle(rolle: str) -> dict | None:
    """Spielzustand, bei dem die noch nicht gelegten Würfel des Partners
    als None übermittelt werden (der Client zeigt sie als '?' an)."""
    if spielplan is None:
        return None
    z = spielplan.zustand()
    partner = "kopilot" if rolle == "pilot" else "pilot"
    partner_frei = z[f"{partner}_wuerfel_frei"]
    # Verbirgt ungespielte Partnerwürfel – gespielte bleiben sichtbar
    z[f"{partner}_wuerfel"] = [
        None if frei else wert
        for wert, frei in zip(z[f"{partner}_wuerfel"], partner_frei)
    ]
    return z


async def broadcast_zustand():
    """Sendet den rollenspezifisch gefilterten Zustand an alle Clients."""
    for rolle, ws in list(verbindungen.items()):
        try:
            await ws.send(json.dumps({
                "typ": "zustand",
                "zustand": zustand_fuer_rolle(rolle),
            }))
        except Exception:
            pass


async def sende(ws, daten: dict):
    try:
        await ws.send(json.dumps(daten))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Aktions-Dispatcher
# ---------------------------------------------------------------------------
async def verarbeite(ws, rolle: str, msg: dict):
    global spielplan

    typ = msg.get("typ")

    if typ == "neues_spiel":
        spielplan = Spielplan(msg.get("flughafen", "MUC"))
        spielplan.starte_spiel()
        await broadcast_zustand()
        return

    if spielplan is None:
        await sende(ws, {"typ": "fehler", "meldung": "Kein Spiel aktiv."})
        return

    if typ == "platziere":
        kwargs = {}
        if msg.get("index") is not None:
            kwargs["index"] = msg["index"]
        if msg["ziel"] == "funk":
            kwargs["funk_feld"] = msg.get("funk_feld", 0)
        erg = spielplan.platziere(rolle, msg["wuerfel_index"], msg["ziel"], **kwargs)
        await sende(ws, {
            "typ": "ergebnis",
            "erfolg": erg.erfolg,
            "meldung": erg.meldung,
            "grund": grund_text(erg.grund),
        })

    elif typ == "trinke_kaffee":
        erg = spielplan.trinke_kaffee(rolle, msg["wuerfel_index"], msg["delta"])
        await sende(ws, {
            "typ": "ergebnis",
            "erfolg": erg.erfolg,
            "meldung": erg.meldung,
            "grund": grund_text(erg.grund),
        })

    elif typ == "benutze_neuwurf":
        erg = spielplan.benutze_neuwurf(
            msg.get("pilot_indizes", []),
            msg.get("kopilot_indizes", []),
        )
        await sende(ws, {
            "typ": "ergebnis",
            "erfolg": erg.erfolg,
            "meldung": erg.meldung,
            "grund": grund_text(erg.grund),
        })

    elif typ == "rundenende":
        erg = spielplan.rundenende()
        await sende(ws, {
            "typ": "ergebnis",
            "erfolg": erg.erfolg,
            "meldung": erg.meldung,
            "grund": grund_text(erg.grund),
        })
        if erg.erfolg and spielplan.status == "laeuft":
            spielplan.wuerfeln_fuer_runde()

    else:
        await sende(ws, {"typ": "fehler", "meldung": f"Unbekannter Typ: {typ}"})
        return

    await broadcast_zustand()


# ---------------------------------------------------------------------------
# WebSocket-Handler (ein Client pro Verbindung)
# ---------------------------------------------------------------------------
async def handler(ws):
    global spielplan

    # Erste Nachricht: Rollenanmeldung
    try:
        erste = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
    except Exception:
        return

    rolle = erste.get("rolle")
    if rolle not in ("pilot", "kopilot"):
        await sende(ws, {"typ": "fehler", "meldung": "Bitte rolle='pilot' oder 'kopilot' senden."})
        return

    # Rolle schon besetzt?
    if rolle in verbindungen:
        try:
            await verbindungen[rolle].ping()
            await sende(ws, {"typ": "fehler", "meldung": f"Rolle '{rolle}' ist bereits belegt."})
            return
        except Exception:
            pass  # alte Verbindung tot → übernehmen

    verbindungen[rolle] = ws
    print(f"  ✓  {rolle:10s}  verbunden  ({ws.remote_address[0]})")

    # Spiel starten, falls noch keins läuft
    if spielplan is None:
        spielplan = Spielplan("MUC")
        spielplan.starte_spiel()

    await sende(ws, {"typ": "rolle", "rolle": rolle})
    await sende(ws, {"typ": "zustand", "zustand": zustand_fuer_rolle(rolle)})

    try:
        async for raw in ws:
            try:
                await verarbeite(ws, rolle, json.loads(raw))
            except Exception as exc:
                await sende(ws, {"typ": "fehler", "meldung": str(exc)})
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if verbindungen.get(rolle) is ws:
            del verbindungen[rolle]
        print(f"  ✗  {rolle:10s}  getrennt")


# ---------------------------------------------------------------------------
# HTTP-Server (statische Dateien, separater Thread)
# ---------------------------------------------------------------------------
def starte_http():
    os.chdir(ROOT)

    class StillerHandler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass  # kein HTTP-Log-Spam

    server = HTTPServer(("", HTTP_PORT), StillerHandler)
    server.serve_forever()


# ---------------------------------------------------------------------------
# Einstiegspunkt
# ---------------------------------------------------------------------------
async def main():
    ip = get_local_ip()
    base = f"http://{ip}:{HTTP_PORT}/frontend/web"
    pilot_url   = f"{base}/multiplayer.html?rolle=pilot"
    kopilot_url = f"{base}/multiplayer.html?rolle=kopilot"

    t = threading.Thread(target=starte_http, daemon=True)
    t.start()

    breite = max(len(pilot_url), len(kopilot_url)) + 4
    rahmen = "═" * breite

    print(f"\n╔{rahmen}╗")
    print(f"║  COCKPIT – Multiplayer-Server  ".ljust(breite + 1) + "║")
    print(f"╠{rahmen}╣")
    print(f"║  Pilotin  → {pilot_url}  ║")
    print(f"║  Co-Pilot → {kopilot_url}  ║")
    print(f"╠{rahmen}╣")
    print(f"║  Beide Geräte müssen im gleichen WLAN sein.".ljust(breite + 1) + "║")
    print(f"║  Strg+C zum Beenden.".ljust(breite + 1) + "║")
    print(f"╚{rahmen}╝\n")

    async with websockets.serve(handler, "", WS_PORT):
        await asyncio.Future()   # läuft bis Strg+C


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer beendet.")
