# Cockpit – digitaler Zwilling

Digitale Umsetzung eines kooperativen 2-Spieler-Flugzeuglandespiels
(Würfel platzieren, gemeinsam ein Flugzeug sicher landen). Regelwerk
laut dem Original-Regelheft, auf das sich alle Seitenangaben (S.X) in
diesem Projekt beziehen. Dieses README dokumentiert,
was seit der zuletzt geteilten Version verändert wurde, welche Annahmen
ich treffen musste (bitte prüfen!), und was ich für die geplante
Web-Oberfläche noch von dir brauche.

## Kurz gesagt

- Ich konnte **keine "neue Log-Datei"** im Repo/den Anhängen finden -
  weder ein Änderungsprotokoll noch ein `CHANGELOG`. Ich bin daher davon
  ausgegangen, dass die im Chat eingefügten Dateien (`backend/*.py`,
  `frontend/*`) der aktuelle Stand sind, den es zu reparieren/vervoll-
  ständigen galt. Falls du eine andere Datei meintest: bitte nochmal
  anhängen, dann gleiche ich das ab.
- Ich habe die komplette Engine gegen das Regelheft geprüft (S.1-S.12)
  und **grundlegend neu aufgebaut** (Details unten) - die alte Version
  hatte gute Ansätze (z.B. die Reihenfolge-Logik für Fahrwerk/
  Landeklappen/Bremsen war schon korrekt!), aber keine funktionierende
  Verbindung zwischen Würfeln, Feldern und Spiellogik.
- Es gibt jetzt eine **spielbare Terminal-Version** (`main.py`) und ein
  **funktionierendes Web-Grundgerüst** (`frontend/web/`), das dieselbe
  Python-Engine per Pyodide direkt im Browser laufen lässt (kein Server
  nötig, GitHub-Pages-tauglich). Design ist bewusst noch schlicht.

## Was repariert wurde (Bugs in der vorherigen Version)

- `backend/wuerfel.py`: `platziere()` hat einen Wert auf den lokalen
  Funktionsparameter statt auf das `Wuerfelfeld`-Objekt geschrieben -
  hatte nie einen Effekt. Der Vergleich `wuerfelfeld > 0` konnte zudem
  nie funktionieren (der alte `Wuerfelfeld`-Wrapper überlädt `__gt__`
  nicht, und `__getattr__` wird für Operatoren nicht aufgerufen).
- `backend/wuerfelfelder.py`: der Int-Wrapper-Hack um `Wuerfelfeld` war
  fehleranfällig (s.o.). Ersetzt durch eine simple Klasse, die den
  platzierten `Wuerfel` direkt referenziert (`backend/wuerfelfeld.py`).
- `backend/spielplan.py`: rief `Landung()` ohne den Pflichtparameter
  `flughafen` auf. Imports waren zudem absolut (`from landung import
  ...`) statt relativ - lief nur, wenn `backend/` zufällig im
  `sys.path` lag.
- `backend/landung.py`: YAML-Pfad war relativ zum Arbeitsverzeichnis
  (`landungen/{code}.yaml`) statt zum Modul - schlug fehl, sobald man
  nicht exakt aus `backend/` heraus startete. Jetzt über
  `Path(__file__).resolve().parent`.
- Die bisherige Neuwurf-Logik (`anzahl_neuwurf` abhängig von
  `schwierigkeit`) entspricht nicht dem Regelheft (S.4): Neuwurf-
  Plättchen hängen an bestimmten Höhen der Höhenleiste, nicht an der
  Schwierigkeit. Neu implementiert (siehe Annahmen unten).
- Es fehlte komplett: Ruder-Fluglage-Mechanik inkl. Trudeln (S.5),
  Triebwerke/Aerodynamik-Marker/Entfernungsbewegung inkl. Kollision und
  "übers Ziel hinaus" (S.6), Funk (S.7), Kaffee/Konzentration inkl.
  Würfel-Manipulation (S.8), die "Bremsen-statt-Aerodynamik"-Regel für
  die letzte Runde (S.10), Warteschleife/Notlandung-Sonderfälle (S.10)
  und die komplette Sieg-/Verlustauswertung (S.11).

## Architektur jetzt

```
backend/
  regeln.py        Konstanten (mit Fundstelle im Regelheft kommentiert)
  wuerfel.py        Würfel-Klasse (inkl. Kaffee-Anpassung)
  wuerfelfeld.py     Ein einzelnes Würfelfeld (Farb-/Zahlvorgabe)
  cockpit.py         Alle Felder + Aktionslogik (Ruder, Triebwerke, ...)
  landung.py         Flughafen-/Entfernungs-/Höhen-Daten (pro Flughafen-YAML)
  spielplan.py        Orchestriert eine Partie (Würfelpools, Züge, Runden)
  bridge.py           JSON-Schnittstelle fürs Web-Frontend (Pyodide)
  ui_schema.json      Gemeinsame Texte/Feldlayout für beide Web-UIs
  landungen/MUC.yaml  Flughafendaten
frontend/
  terminal/          Text-UI (funktional, kein Pixel-Nachbau des Boards)
  web/               Browser-UI, lädt die Python-Engine per Pyodide
tests/
  test_engine.py     Simulations-"Fuzzer" + ein deterministischer,
                      durchgeskripteter Gewinn-Durchlauf
```

Einmalig Abhängigkeiten installieren:
```
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Spielen im Terminal:
```
cd skyteam
python3 main.py MUC
```

Tests laufen lassen:
```
cd skyteam
make test
# alternativ: python3 -m unittest discover -s tests -v
```

Web-Version lokal testen (Fetch von `.py`-Dateien braucht `http(s)://`,
nicht `file://`):
```
cd skyteam
python3 -m http.server 8000
# dann im Browser: http://localhost:8000/frontend/web/
```
Nach Änderungen an `backend/` oder `backend/ui_schema.json` zuerst
`python3 build.py` (oder `make build`) ausführen. Auf GitHub Pages funktioniert das genauso, sobald das Repo dort gehostet
wird (Pages-Quelle = Repo-Root reicht; `index.html` im Root leitet
automatisch zu `frontend/web/index.html` weiter).

## Annahmen, die ich treffen musste (bitte am echten Spiel prüfen!)

Ich hatte nur die Fotos aus der PDF, kein physisches Exemplar. Flughafen-
spezifische Werte liegen jeweils im passenden `backend/landungen/*.yaml`:

1. **`neuwurf_hoehen: [6000, 2000]`** - S.4 nennt nur 6000 als Beispiel
   für eine der beiden Neuwurf-Positionen auf der Höhenleiste; die
   zweite Höhe ist geraten. Die Einstellung ist jetzt pro Flughafen
   konfigurierbar und wird auch direkt im Frontend angezeigt.
2. **Startspieler-Wechsel**: Ich lasse Pilot/Co-Pilot pro Runde
   alternieren. Das Regelheft sagt nur, dass ein Pfeil auf der
   Höhenleiste dies anzeigt (S.4) - ob es wirklich eine einfache
   Alternierung ist, weiß ich nicht sicher.
3. **Flugzeug-Verteilung auf der MUC-Entfernungsleiste**
   (`backend/landungen/MUC.yaml`) - im Regelheft nur als Gesamtzahl
   ("12 Flugzeuge, 9 auf der Leiste") genannt, nicht pro Feld. Meine
   Verteilung `[2,1,2,1,1,1,1]` ist geraten und sollte durch die echten
   Werte von der MUC-Karte ersetzt werden.
4. Die YAML-Felder `flugzeugwuerfel`, `kurven_min`, `kurven_max` aus der
   ursprünglichen Datei kommen im Basis-Regelheft gar nicht vor - ich
   vermute, sie gehören zu den fortgeschrittenen Szenarien unter dem
   Schachteleinsatz (S.3-Hinweis). Die Kurven-Korridore werden bereits
   beim Bewegen geprüft; `flugzeugwuerfel` ist für die zukünftige Dynamik-
   Mechanik reserviert und wird noch nicht ausgewertet.
5. `RUDER_STALL_SCHWELLE` ist jetzt auf **3** gesetzt (Trudeln bei
   `|Fluglage| > 2`, wie von dir bestätigt).
6. Deine `Arrivals.pdf` scheint ein separates Erweiterungsmodul mit
   weiteren Flughäfen zu sein (LHR, SFO, SYD, MUC, ...) - MUC taucht
   dort also möglicherweise nochmal mit eigenen, "offiziellen" Werten
   auf. Falls ja, sag Bescheid, dann ersetze ich die geratene
   Platzhalter-Verteilung durch die echten Erweiterungsdaten.

## Bugfixes (nach deinem Feedback)

1. **Ruder-Vorzeichen gedreht**: Pilot 5 / Kopilot 4 ergibt jetzt -1
   (vorher +1), Pilot 3 / Kopilot 5 ergibt +2 - am physischen Board
   bestätigt. Formel ist jetzt `fluglage += (kopilot_wert - pilot_wert)`.
2. **Triebwerke werten erst am Rundenende aus**: Bewegung/Kollision/
   "übers Ziel hinaus" (bzw. der Bremsen-Vergleich in der letzten Runde)
   passieren jetzt NICHT mehr sofort beim Platzieren des 2. Triebwerk-
   Würfels, sondern erst in `rundenende()`, nachdem alle 8 Würfel liegen.
   Einzige Ausnahme bleibt das Ruder: Trudeln führt weiterhin sofort zum
   Verlust, sobald der 2. Ruder-Würfel liegt.
3. **Funk-Bug war ein Folgefehler von #2**: Weil Triebwerke vorher
   mitten in der Runde die Entfernung verschieben konnten, änderte sich
   die "aktuelle Position" unter der Hand, bevor Funk sein Ziel
   ausrechnete. Mit #2 behoben bleibt die Position während der ganzen
   Runde stabil - die Funk-Formel selbst war schon korrekt.
4. **Cockpit-Board zeigt jetzt jedes gelegte Würfelfeld** (Wert + Farbe
   des Besitzers), egal wer es platziert hat - `backend/cockpit.py:
   felder_snapshot()` liefert das, `frontend/web/js/app.js:
   renderCockpitBoard()` zeichnet es.
5. **Kaffee-Auswahl als Buttons** statt Texteingabe: nur noch gültige
   Deltas (Bereich 1-6, begrenzt durch verfügbare Tassen) werden
   angezeigt (`backend/cockpit.py: moegliche_kaffee_deltas()`).
6. **Flugzeugleiste "rutscht" jetzt nach links**: die UI zeigt nur noch
   den Teil der Liste ab der aktuellen Position (`flugzeuge.slice(...)`
   in app.js) - das Backend speichert weiterhin die volle Liste.
7. **Aerodynamik-Anzeige als durchgehende Skala** (`2 3 4 | 5 6 7 8 |
   9 10 11 12` statt `4.5 / 8.5`) - siehe `aeroSkalaHTML()` in app.js.

## Für das Web-Design brauche ich von dir



Die Engine und ein klickbares Grundgerüst stehen; für den Feinschliff:

- **Optischer Rahmen**: eigenes Look&Feel, oder soll es nah am
  physischen Cockpit-Board aussehen (Farben/Icons aus der Anleitung)?
  Referenzbilder/Screenshots vom echten Board helfen enorm.
- **Assets**: Habt ihr/darf ich Board-Grafiken, Flugzeug-/Wolken-Icons
  o.ä. verwenden, oder soll ich alles neu (SVG) gestalten?
- **Spielmodus**: ein gemeinsamer Bildschirm (wie aktuell), zwei Geräte
  (z.B. per Link/Session geteilt) oder Hot-Seat mit
  Bildschirm-verdecken zwischen den Zügen (näher am "Sichtschirm"-
  Gefühl des Originals)?
- **Sprache**: Deutsch beibehalten, oder zusätzlich/nur Englisch?
- **Priorität Mobile vs. Desktop**?
- **Repo-Name/Pfad**, falls die GitHub-Pages-URL nicht einfach
  `<user>.github.io/<repo>/` sein soll (wirkt sich nur auf den
  Root-Redirect aus, nicht auf die Pfade im Code).

Sag mir außerdem, ob ich Bild-Generierung (Visualizer) für erste
Mockups des Boards/Icons nutzen soll, oder ob du lieber mit echten
Fotos/Scans der Cockpit-Teile arbeitest.

## Multiplayer (zwei Geräte)

Die produktive Browser-Variante ist serverlos: `multiplayer.html` nutzt
PeerJS/WebRTC für die Verbindung und Pyodide auf dem Host-Gerät für die
Regeln. Beide Geräte brauchen Internetzugang; sie müssen nicht im selben
WLAN sein.

**Ablauf:**
1. Spieler 1 (Host) öffnet die URL im Browser → klickt **"Spiel hosten"**
   → QR-Code erscheint auf dem Bildschirm.
2. Spieler 2 öffnet `multiplayer.html` (oder scannt direkt mit der Kamera-App)
   → gibt den Code ein oder öffnet den QR-Link.
3. Verbindung steht. Jeder Spieler sieht nur seine eigenen Würfel,
   aber alle gelegten Felder sind für beide sichtbar.

`server.py` bleibt als experimenteller lokaler WebSocket-Server im Repo,
hat aber bewusst keine aktive Browser-UI. Bevor daraus eine dritte Variante
wird, sollte er entweder einen eigenen Client bekommen oder durch einen
späteren Cloud-Session-Service ersetzt werden.

## Erweiterungspunkte

Die Regeln bleiben in `Spielplan`/`Cockpit`, ohne Browser- oder Transport-
Abhängigkeiten. Das ist die Grenze für einen künftigen KI-Partner und einen
Cloud-Session-Service: Beide sollen dieselben validierten Aktionen an einer
eigenen `Spielplan`-Instanz ausführen. Neue Flughäfen sind reine YAML-
Szenarien; die Konfiguration wird beim Laden geprüft und erscheint
automatisch in der Browser-Auswahl.
