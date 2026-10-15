# Sky Team: Landungen und Zusatzfunktionen

Stand: 16. Oktober 2026. Grundlage: das bereitgestellte **Sky Team Flight Log**, die acht Fotos der Strecken und die [vom Verlag gepflegten Regeln bei Dized](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/sky-team).

## Umgesetzt

**Menü → Landung auswählen → Kartenset auswählen → Spiel.** Alle 21 Originalvarianten sind mit ihren vorgesehenen Zusatzmodulen aktiv, sowohl in Pass & Play als auch im Multiplayer. Die Engine verlangt genau die angegebene Zahl unterschiedlicher Fähigkeiten; ein unvollständiges oder unbekanntes Set wird beim Start abgewiesen.

| Ursprüngliche Aufwandsreihenfolge | Funktion | Stand |
| --- | --- | --- |
| 1–3 · gering | Erfolgsmarkierungen, Kurven, Streckenlängen und Verkehrswürfel | Aktiv; Originalstrecken aus den Fotos, Vorrat von 12 Flugzeugen |
| 4 · gering bis mittel | Kerosin | Vorrat 20, gemeinsames Würfelfeld, sofortiger Verbrauch, sonst 6 am Rundenende; leerer Tank verliert auch bei der Landung |
| 5 · gering | Kerosinleck | Ersetzt normalen Verbrauch durch Triebwerksdifferenz plus 1; Kerosinfeld gesperrt |
| 6 · gering bis mittel | Kontrolle, Anpassung, Voraussicht, Meisterschaft | Kaffee bei gleichen Rudern; einmaliges Drehen je Person; Neuwurf vor dem ersten Zug des Startspielers; begrenzter Plättchenvorrat |
| 7 · mittel | Wind | Persistenter Ring mit 18 Positionen, Start bei +3; Drehen um die aktuelle Fluglage nach Ruderauflösung; Modifikator auch beim Landen |
| 8 · mittel | Eisbremsen | Vier Paare 2/3/4/5, oben Pilotin, unten beide; gleiche Runde und feste Reihenfolge; alle Paare als zusätzliche Siegbedingung |
| 9 · mittel bis hoch | Zusammenarbeit | Zwei private Auswahlen, anschließend atomarer Werttausch; einmal pro Runde, regulärer Zug bleibt bestehen |
| 10 · hoch | Praktikant | Sechs zufällig angeordnete Plättchen 1–6, Zugriff von beiden Enden, je ein Trainingsfeld; verpflichtende Zusatzplatzierung ohne Kaffee/Konzentration; vollständige Ausbildung als Siegbedingung |
| 11 · hoch | Synchronisation | Ein zusätzlicher schwarzer Würfel pro Runde nach Fahrwerk und Klappen; Co-Pilot platziert auch auf Pilotenfeldern; Kaffee möglich |
| 12 · hoch | Echtzeit | 60 Sekunden ab den Spielerwürfen, Host prüft Deadline vor Aktionen und wertet automatisch aus; danach Besprechung vor dem nächsten Wurf |

### Bedienung und Anzeigen

`frontend/web/js/modules.js` zeigt gemeinsame Instrumente und Fähigkeiten. Zusätzliche Plättchen/Würfel bieten ausschließlich von Python gelieferte erlaubte Ziele an. Praktikantenplättchen erscheinen grün, Synchronisationswürfel dunkel. Die Treibstoffanzeige sitzt als schmale Leiste am rechten Cockpitrand, das gemeinsame Kerosinfeld unter den Klappen. Bei einem Leck erscheint dort nur die Verbrauchsanzeige. Eisbremsen ersetzen die normale Bremsreihe; der rote Marker sitzt auch bei halben Bremswerten zwischen den Zahlen. Das kleine Windrad neben dem Schub öffnet den vollständigen Ring, der aktuelle Modifikator steht unter „Schub“. Der Praktikant nutzt eine horizontale Trainingsleiste unter dem Cockpit. Ausgewählte Fähigkeiten erscheinen als kompakte Kartenknöpfe mit Details und Aktionen per Tipp. Flughafen, Schwierigkeit und Modulsymbole stehen im verkleinerten Kopfbereich.

Die Verkehrsflugzeuge verwenden über alle sichtbaren Felder dieselbe Größe und feste Zellenabstände. Ihre kleinen Drehungen sind stabil; die Hüllflächen überlagern sich nicht. Der Mittelmarker zwischen Höhen- und Entfernungsleiste entfällt. Beide Leisten stehen enger zusammen; Kaffeeplätze sind quadratisch und die Symbole darin zentriert.

### Engine und Transport

`backend/zusatzregeln.py` verwaltet Karten, Zusatzaktionen und die Uhr. `Cockpit` enthält Wind, Kerosin und Eisbremsen; `Spielplan` verbindet die Regeln mit Platzierung und Rundenende. `backend/bridge.py` bietet JSON-basierte Aktionen an. Der Multiplayer-Host weist die Rolle über die Verbindung zu und verteilt ausschließlich rollengefilterte Zustände. Die erste Tauschwahl wird nicht übertragen. Würfelwerte des Partners bleiben verdeckt, solange sie nicht platziert sind.

Die Uhr verwendet eine feste Host-Deadline. Das Öffnen eines Dialogs und Hintergrundtabs verlängern sie nicht. Wenn der Browser eingefroren ist, erfolgt die Auswertung beim nächsten Host-Tick oder spätestens vor der nächsten Aktion. Der Client zeigt die verbleibende Zeit relativ zur Host-Messung an. Nach Ablauf werden ungespielte Würfel ignoriert; fehlende Pflichtfelder verlieren. Verkehr bleibt vor dem Wurf der Spielerwürfel eine eigene Phase.

Neuwurfmaterial: zwei Grundspiel-Plättchen plus ein zusätzliches Plättchen aus den erweiterten Komponenten, insgesamt drei. Bei Meisterschaft zählen Plättchen auf der Höhenleiste und im Cockpit als belegt. Quelle: [Dized-Materialliste](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/YbDJ5NU7QQW9eZ3_rM3WDg/contents).

### Prüfung

53 native Tests einschließlich aller 21 Varianten mit sämtlichen zulässigen Kartensets, Verbrauchsgrenzen, Ringumlauf, Eis-Paaren, Zusatzaktionen, verdeckten Tauschzuständen, Ressourcenlimits, kombinierten Landebedingungen und verspäteten Aktionen. Zusätzlich 12 DOM-Regressionen für Verkehr, Größen, Abstände und Hüllflächen bei 80–200 px Leistenbreite sowie 21 Instrumentenprüfungen für beide Web-UIs: Rollenrechte, Platzierungsargumente, Privatheit, Markerpositionen, Dialoge, Kopfbereich und 320–600 px breite Spielpläne.

Manuell mit echtem Pyodide geprüft: Kerosinaktion und Praktikantenplatzierung in Pass & Play, automatischer Echtzeitabschluss sowie Zusammenarbeit und Synchronisation zwischen zwei über PeerJS verbundenen Browser-Clients. Das ersetzt keine Erprobung auf zwei unterschiedlichen physischen Geräten.

## Vollständiger Szenariokatalog

Module und Kartenanzahlen sind aus den Symbolen der PDF-Seiten 6–8 übernommen und mit den Fotos abgeglichen. HND rot wurde nach Foto und Dized um Kerosin ergänzt. Verkehr und Kurven sind Streckeneffekte und stehen nicht in der Modulspalte; ihre konkrete Verteilung ist in [STRECKENDATEN.md](STRECKENDATEN.md) dokumentiert.

| Seite | Farbe | Flughafen | Zusatzmodule | Karten |
| --- | --- | --- | --- | ---: |
| 6 | Grün | YUL Montréal-Trudeau | Keine | 0 |
| 6 | Grün | LHR Heathrow | Keine | 0 |
| 6 | Grün | HND Haneda | Keine | 0 |
| 6 | Grün | OSL Gardermoen | Kerosin | 0 |
| 6 | Grün | ATL Hartsfield-Jackson | Praktikant | 0 |
| 6 | Grün | PRG Václav Havel | Kerosin | 2 |
| 7 | Gelb | LHR Heathrow | Praktikant | 0 |
| 7 | Gelb | TGU Toncontín | Kerosin | 2 |
| 7 | Gelb | GIG Galeão | Wind | 1 |
| 7 | Gelb | KEF Keflavík | Eisbremsen | 1 |
| 7 | Gelb | PRG Václav Havel | Kerosinleck | 2 |
| 7 | Gelb | KUL Kuala Lumpur | Kerosin | 1 |
| 7 | Gelb | ATL Hartsfield-Jackson | Kerosinleck | 1 |
| 8 | Rot | PBH Paro | Kerosin, Echtzeit | 2 |
| 8 | Rot | HND Haneda | Kerosin, Praktikant | 1 |
| 8 | Rot | GIG Galeão | Wind, Kerosinleck | 2 |
| 8 | Rot | OSL Gardermoen | Kerosinleck, Eisbremsen | 2 |
| 8 | Rot | TGU Toncontín | Kerosin, Wind | 2 |
| 8 | Schwarz | KEF Keflavík | Wind, Eisbremsen | 2 |
| 8 | Schwarz | KUL Kuala Lumpur | Kerosin, Echtzeit | 2 |
| 8 | Schwarz | PBH Paro | Kerosin, Echtzeit | 2 |

## Daten und Build

`backend/landekatalog.json` enthält die Originalstrecken, Modulvorgaben und Kartenanzahlen; `backend/katalog.py` erzeugt die Startkonfigurationen. `make build` bündelt die Python-Engine und den Browserkatalog. Eigene YAML-Strecken MUC, FRA und LHR bleiben separat verfügbar. `MOCK_<CODE>_<FARBE>` bleibt für künstliche Streckentests erhalten und wird als Übung gekennzeichnet; seine Module sind ebenfalls aktiv. Frühere Übungserfolge werden nicht in Originalerfolge umgewandelt.

## Regelreferenzen

- [Verkehrswürfel](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/_WPce283SP63APWmCnFSPA/traffic-die-approach-track-effect)
- [Kerosin](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/PWqgL6m9SFiIlQRuIMrtFQ/module-kerosene) und [Kerosinleck](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/cqr_4ZwOQ461R5wnZgU6WA/module-kerosene-leak)
- [Wind](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/JNNK7ICVTFGUv5cFhJLVyw/module-wind) und [Eisbremsen](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/RbvY4rs7T5SsHdlAY_VGQw/module-ice-breaks)
- [Praktikant](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/CZdwSo0GSFKGRTWk4dFXug/module-intern) und [Echtzeit](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/Uf2D_8IwSQSruNWqIQtaew/module-real-time)
