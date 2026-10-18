# Fly Team

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
   beim Bewegen geprüft; `flugzeugwuerfel` steuert inzwischen die
   schwarzen Verkehrswürfel vor Rundenbeginn (siehe FRA weiter unten).
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

### FRA und schwarze Verkehrswürfel

`backend/landungen/FRA.yaml` enthält eine eigene Frankfurt-Strecke mit
milden Kurven, vier initialen Flugzeugen und schwarzen Verkehrswürfeln.
Die zweite Zahl jeder Distanzzeile gibt die Anzahl der schwarzen Würfel
an; mehrere Symbole auf einem Feld bedeuten entsprechend mehrere Würfe.
Diese Spalte entspricht „Number of traffic dice“ im
[Streckengenerator](https://skyteam.fly.dev/).

Vor **jeder Runde** werden die schwarzen Würfel des aktuellen Felds
geworfen, auch beim Stehenbleiben. Die sechs gleich wahrscheinlichen
Seiten sind **2, 3, 3, 4, 4, 5**. Wie beim Funk zählt das aktuelle Feld
als 1: Eine 2 platziert ein Flugzeug ein Feld voraus, eine 3 zwei Felder
voraus. Auch auf einem bereits belegten Feld kommt ein weiteres Flugzeug
hinzu. Liegt das Ziel hinter dem Flughafen, entfällt das neue Flugzeug.
Überflogene Felder lösen keinen zusätzlichen Wurf aus.

In beiden Web-Spielmodi öffnet sich bei fälligen Würfen automatisch ein
kompakter Dialog mit schwarzem Zahlenwürfel und Wurfbutton, ohne
Erklärungstexte. Weißer Nebel sperrt das Cockpit und blendet erst unterhalb
der vollständigen Entfernungsleiste weich ein. Ein neu hinzugekommenes
Flugzeug wird kurz auf seinem Zielfeld eingeblendet, auch bei
Mehrfachbelegung; wiederholtes Rendern spielt die Animation nicht erneut.
Bei reduzierter Bewegung blitzt nur das Zielfeld auf. „Strecke ansehen“
schließt nur den Dialog, nicht die Wurfphase. Mehrere Würfe werden einzeln
abgearbeitet. Eine Sekunde nach dem letzten Ergebnis beginnt die Runde
automatisch: Der Dialog schließt, der Nebel verschwindet und erst jetzt
werden die acht Spielerwürfel geworfen (bzw. die Echtzeituhr gestartet).
Kurven stehen klein am oberen Feldrand, Verkehrswürfel rechts und
Flugzeuge dazwischen. Jedes Flugzeug erscheint als eigenes Symbol ohne
Zähler, leicht zufällig versetzt und gedreht. Die Verteilung bleibt pro
Feld stabil; reservierte Randbereiche und die gedrehte Hüllfläche verhindern
Überlappungen mit Kurven, Entfernungszahlen und Verkehrswürfeln.
Im Multiplayer würfelt die Person, die die Runde beginnt; beide Geräte
sehen denselben Verkehr und dieselben Ergebnisse.

Die Browser-Regressionsprüfung für Dialog, Nebel, Flugzeuganimation, Sperre, Mehrfachwürfe und
Rollenwechsel läuft ohne zusätzliche Pakete: lokalen Webserver starten,
`tests/traffic-ui.html` öffnen und „UI-Tests starten“ anklicken.

Engine-Snapshots enthalten dazu `phase`, `flugzeugwuerfel`,
`verkehrswuerfel_offen` und `verkehrswuerfe`. Die gemeinsame Aktion heißt
`wirf_verkehrswuerfel`; sie kann nach Abschluss der Wurfphase keine
zusätzlichen Flugzeuge erzeugen. Nach Änderungen wie bisher `make build`
ausführen, damit Flughafen, Engine und PWA-Cache aktualisiert werden.

Die Regeln bleiben in `Spielplan`/`Cockpit`, ohne Browser- oder Transport-
Abhängigkeiten. Das ist die Grenze für einen künftigen KI-Partner und einen
Cloud-Session-Service: Beide sollen dieselben validierten Aktionen an einer
eigenen `Spielplan`-Instanz ausführen. Neue Flughäfen sind reine YAML-
Szenarien; die Konfiguration wird beim Laden geprüft und erscheint
automatisch in der Browser-Auswahl.

## Landungsauswahl und Logbuch (15.10.2026)

Zwischen Menü und Spiel liegt jetzt eine gemeinsame Auswahlseite für Pass & Play
und Multiplayer: 21 Logbuch-Varianten an 11 Flughäfen mit frei lizenzierten Stadtpanoramen,
Schwierigkeitsfiltern, Suche, Streckenvorschau und verbindlicher Fähigkeitskarten-Auswahl.
Der Multiplayer-Host wählt vor dem Einladungscode; später kann er über „Landung“
eine neue Strecke auswählen. Die bisherigen Strecken stehen unter „Eigene Strecken“.

Alle 21 Originalstrecken sind aus den nachgereichten Flughafenfotos übernommen,
einschließlich beider Höhenleisten. Sämtliche Zusatzmodule und alle sechs
Fähigkeitskarten sind aktiv: Kerosin, Kerosinleck, Wind, Eisbremsen, Praktikant,
Echtzeit sowie Kontrolle, Anpassung, Voraussicht, Meisterschaft, Zusammenarbeit
und Synchronisation. Vor dem Start muss die vorgesehene Zahl unterschiedlicher
Karten ausgewählt werden. Alte Übungserfolge bleiben getrennt von vollständigen
Landungen. Die erfundenen Mock-Strecken bleiben für Modultests über
`MOCK_<CODE>_<FARBE>` verfügbar, stehen aber nicht im Katalog.
Zu große Verkehrswürfe verfallen auf allen Strecken; sie setzen kein Flugzeug
auf das letzte sichtbare Feld. Bei Originalstrecken umfasst der Vorrat
12 Flugzeuge. HND rot benötigt nach Foto und Dized
Kerosin plus Praktikant; das englische PDF zeigt nur den Praktikanten.

Datenquelle: `backend/landekatalog.json`; native Streckenkonfigurationen:
`backend/katalog.py`; gemeinsame Browserauswahl: `frontend/web/js/landings.js`.
Nach Änderungen `make build` ausführen. Der ausführliche, nach Aufwand sortierte
[Implementierungsplan](docs/IMPLEMENTIERUNGSPLAN.md) enthält Reihenfolge,
Umsetzungsstand, alle Szenariovorgaben und Dized-Regelreferenzen.
Die gemeinsame Moduloberfläche liegt in `frontend/web/js/modules.js`, die Regeln
in `backend/zusatzregeln.py`. `make test` prüft die Engine einschließlich der
Modulkombinationen und exakter Kartensets. Echtzeit verwendet eine Host-Deadline;
nach automatischem Rundenende kann vor dem nächsten Wurf besprochen werden.

Browser-Regressionen: Mit lokalem HTTP-Server und installiertem Playwright
`node tests/landings-ui.cjs` ausführen. Optional geben `COCKPIT_TEST_URL`,
`COCKPIT_CHROME` und `COCKPIT_SCREENSHOTS` Server, Browserpfad und Screenshotordner
vor. Die Prüfung nutzt echtes Pyodide und einen simulierten PeerJS-Transport;
eine Verbindung über zwei reale Geräte wird damit nicht geprüft.

### Frei lizenzierte Stadtpanoramen

Die aus dem Logbuch extrahierten Illustrationen wurden durch 13 recherchierte
Stadt- und Landschaftspanoramen der Reiseziele ersetzt, einschließlich München und Frankfurt. Autor und Lizenz
stehen auf den Karten sowie mit Links in den Details. „Bildnachweise und Lizenzen“
öffnet die vollständigen Nachweise. Quelle ist `backend/bildnachweise.json`;
`make build` erzeugt daraus `frontend/web/bildnachweise.html`. Verwendete Lizenzen:
CC0, CC BY und CC BY-SA; die jeweilige Bildfassung behält die angegebene Lizenz.

Die Zusatzinstrumente sind in das Cockpit integriert: Treibstoff rechts mit Würfelfeld unter den Klappen, Eisbremsen im Bremsbereich und ein vergrößerbares Windrad neben dem Schub. Praktikant und ausgewählte Fähigkeitskarten nutzen schmale Leisten darunter. Flughafeninfos stehen platzsparend im 42 px hohen Kopfbereich. Ein einzelner Neuwurfknopf zeigt die verfügbare Anzahl. Die UI-Prüfung dafür läuft unter `tests/modules-ui.html` über „Instrumente prüfen“.

Praktikantenplättchen und Synchronisationswürfel werden direkt auf hervorgehobene Cockpitfelder gelegt. Bei Synchronisation würfelt die Person gegenüber dem auslösenden Zug zuerst im schwarzen Würfeldialog; danach werden die erlaubten Ziele freigegeben. Eine Anzeige im fixierten Kopfbereich zeigt weiterhin den schwarzen Zahlenwürfel, die zuständige Rolle und die offene Aufgabe. Die regulären Spielerwürfel werden dabei nicht verbraucht.

### Rückgängig

Der ↶-Button im Kopfbereich stellt den letzten Spielschritt vollständig
wieder her, einschließlich Würfeln, Ressourcen, Zugfolge, Zusatzaktionen
und Rundenwechseln. Bis zu 200 Schritte sind verfügbar; eine neue Partie
leert den Verlauf. Ungültige Aktionen werden nicht mitgezählt. Auch in
den schwarzen Würfeldialogen ist Rückgängig verfügbar.
Im Multiplayer können beide Crewmitglieder den letzten gemeinsamen
Schritt zurücknehmen; der Host verteilt den wiederhergestellten Stand
mit derselben Würfel-Privatsphäre wie sonst. Veraltete doppelte Anfragen
werden abgewiesen. Die Echtzeituhr wird dabei nicht angehalten oder
zurückgedreht.

### Gemeinsames Neuwurf-Popup (16.10.2026)

Der Neuwurfknopf öffnet in beiden Spielmodi ein Popup mit beiden Würfelpools.
Im Multiplayer kann jede Person unabhängig ihre eigenen freien Würfel auswählen
und bestätigen; in Pass & Play stehen beide Bestätigungen auf demselben Gerät.
Bestätigte Auswahlen können bis zur zweiten Bestätigung wieder geändert werden.
Bereits gelegte Würfel bleiben gesperrt. Nach beiden Bestätigungen wird genau
ein Plättchen verbraucht und automatisch neu gewürfelt. Leuchtende Rahmen und
die Anzeige „vorher → nachher“ markieren die geworfenen Würfel auch bei gleichem
Ergebnis. Nach 2,4 Sekunden schließt sich das Popup automatisch. Außerhalb des
Popups bleiben die Würfel des Partners im Multiplayer verdeckt. Abbrechen oder
zwei leere Auswahlen verbrauchen kein Plättchen; der ursprüngliche Zug bleibt erhalten.

`node tests/multiplayer-actions.cjs` prüft den Hostablauf einschließlich
veralteter/doppelter Nachrichten und Fehlerfällen. `node tests/landings-ui.cjs`
prüft das Popup mit echter Engine auf Desktop und Handy sowie die Synchronisierung
zwischen zwei Browseransichten mit simuliertem PeerJS-Transport.

## Singleplayer und KI-Lernmodi

Unter **Singleplayer** stehen **Mit KI spielen**, **KI-ndergartenbetreuung**
(Feedback von −2 bis +2) und **KI-no** (Beispielpartien per Pass & Play) bereit.
Die KI übernimmt eine Rolle mit denselben eigenen Würfeln und öffentlichen
Informationen wie beim Training. Die beiden Lernmodi fragen vor dem Start nach
Zustimmung zur Datennutzung. Aufzeichnungen werden lokal gesichert und bei
konfiguriertem Cloudflare-Endpunkt automatisch zentral hochgeladen.

Modelle für die statische Webseite bereitstellen:

```bash
.venv/bin/python -m ai.export_browser
.venv/bin/python build.py
```

Der Export erfasst kompatible `best.pt` und `latest.pt` aus `runs/`. Die generierten
Dateien unter `frontend/web/models/` sowie der Modellkatalog müssen mit GitHub Pages
veröffentlicht werden. Modelle werden bei Auswahl geladen und im Browser ausgeführt.
Feedback und Demonstrationen sind zunächst Trainingsdaten; sie verändern die
Gewichte noch nicht automatisch. Die Einrichtung mit einer privaten D1-Datenbank und
einem Cloudflare Worker ist in [docs/KI-CLOUD.md](docs/KI-CLOUD.md) beschrieben.
