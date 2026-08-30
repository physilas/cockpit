# Sky Team – digitaler Zwilling

Digitale Umsetzung von **Sky Team** (Luc Rémond, KOSMOS 2024), Basis-
Regelwerk laut `Sky-Team-Spieleanleitung.pdf`. Dieses README dokumentiert,
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
  landungen/YUL.yaml  Flughafendaten
frontend/
  terminal/          Text-UI (funktional, kein Pixel-Nachbau des Boards)
  web/               Browser-UI, lädt die Python-Engine per Pyodide
tests/
  test_engine.py     Simulations-"Fuzzer" + ein deterministischer,
                      durchgeskripteter Gewinn-Durchlauf
```

Spielen im Terminal:
```
cd skyteam
python3 main.py YUL
```

Tests laufen lassen:
```
cd skyteam
python3 -m tests.test_engine
```

Web-Version lokal testen (Fetch von `.py`-Dateien braucht `http(s)://`,
nicht `file://`):
```
cd skyteam
python3 -m http.server 8000
# dann im Browser: http://localhost:8000/frontend/web/
```
Auf GitHub Pages funktioniert das genauso, sobald das Repo dort gehostet
wird (Pages-Quelle = Repo-Root reicht; `index.html` im Root leitet
automatisch zu `frontend/web/index.html` weiter).

## Annahmen, die ich treffen musste (bitte am echten Spiel prüfen!)

Ich hatte nur die Fotos aus der PDF, kein physisches Exemplar. Alle
folgenden Werte sind in `backend/regeln.py` bzw. `backend/spielplan.py`
mit Kommentar versehen, falls sie angepasst werden müssen:

1. **`RUDER_STALL_SCHWELLE = 5`** - das Regelheft sagt nur "sobald der
   Fluglage-Anzeiger ein X erreicht", ohne Zahl. Ich konnte die
   Schrittzahl bis zum X-Symbol auf dem Foto nicht zuverlässig
   auszählen. Bitte am Cockpit-Board nachzählen.
2. **`NEUWURF_HOEHEN = [6000, 2000]`** - S.4 nennt nur 6000 als Beispiel
   für eine der beiden Neuwurf-Positionen auf der Höhenleiste; die
   zweite Höhe ist geraten.
3. **Startspieler-Wechsel**: Ich lasse Pilot/Co-Pilot pro Runde
   alternieren. Das Regelheft sagt nur, dass ein Pfeil auf der
   Höhenleiste dies anzeigt (S.4) - ob es wirklich eine einfache
   Alternierung ist, weiß ich nicht sicher.
4. **Flugzeug-Verteilung auf der YUL-Entfernungsleiste**
   (`backend/landungen/YUL.yaml`) - im Regelheft nur als Gesamtzahl
   ("12 Flugzeuge, 9 auf der Leiste") genannt, nicht pro Feld. Meine
   Verteilung `[2,1,2,1,1,1,1]` ist geraten und sollte durch die echten
   Werte von der YUL-Karte ersetzt werden.
5. Die YAML-Felder `flugzeugwuerfel`, `kurven_min`, `kurven_max` aus der
   ursprünglichen Datei kommen im Basis-Regelheft gar nicht vor - ich
   vermute, sie gehören zu den fortgeschrittenen Szenarien unter dem
   Schachteleinsatz (S.3-Hinweis). Sie werden geladen, aber von der
   Engine nicht verwendet. Wenn du weißt, was sie bedeuten sollen, sag
   Bescheid, dann baue ich sie ein.
6. Deine `Arrivals.pdf` scheint ein separates Erweiterungsmodul mit
   weiteren Flughäfen zu sein (LHR, SFO, SYD, MUC, ...). Noch nicht
   ausgewertet/integriert - aktuell ist nur YUL spielbar.

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
