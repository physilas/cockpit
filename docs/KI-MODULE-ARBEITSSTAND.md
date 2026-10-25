# Laufendes Ziel: alle Module, zunächst 30–40 % je Fall

Stand: 25. Oktober 2026. **Crew 2 ist für acht Grundspielstrecken zusätzlich
freigegeben. Zusätzlich besteht Crew 2 · Kerosin für Oslo mit 39,8 % unter dem
neu akzeptierten 30-%-Kriterium. Das Ziel aller Module/Karten ist nicht
abgeschlossen. Crew 1 bleibt verfügbar und vorausgewählt. Ein ausdrücklich
gewünschter Zwischenstand heißt jetzt Crew 3 · Praktikant (Test), mit Atlanta
grün und Heathrow gelb; er ist als Entwicklungsmodell sichtbar, ohne Freigabe.
Zusätzlich wird Crew 4 · Leck (Test) für Atlanta gelb mit allen sechs Einzelkarten
bereitgestellt: erst 0–5 % auf Entwicklung, ausdrücklich noch sehr schwach.**

## Verbindlicher Auftrag

Der Nutzer hat das ursprüngliche 50-%-Ziel ausdrücklich auf zunächst **30–40 %**
gelockert und einen etwa 20-minütigen Lauf mit Fokus auf sämtliche Module verlangt.
Verbindlich ist jetzt `ai/experiments/modules-30pct-2026-10-25/matrix.json`:
dieselben 21 offiziellen Routen und 186 einzelnen Route/Karten-Fälle, unveränderte
Originalregeln, aber Freigabeuntergrenze 30 % je Fall. Eine spätere Freigabe
verlangt unabhängige Einzeltests mit unterer Wilson-Grenze >=30 %. Die alte
50-%-Matrix und damalige Ergebnisse bleiben unverändert als Historie erhalten.
Es darf nicht über einfache und schwere Fälle gemittelt werden.

**Neueste ausdrückliche Nutzeranweisung:** Zwischenmodelle samt schwachen Routen
sollen schon vor Freigabe spielbar sein. Deshalb dürfen zusätzlich zu genehmigten
Modellen explizit markierte Vorschauen (`preview.enabled === true`) erscheinen.
`quality.approved` bleibt dabei `false`; Entwicklungsquoten sind separat beschriftet
und ersetzen keine unabhängige Qualifikation. Alte unqualifizierte Modelle ohne
dieses ausdrückliche Flag bleiben verborgen. Vorauswahl bleibt eine genehmigte Crew.

## Ressourcen, Stoppen und automatische Fortsetzung

Der frühere 20-Minuten-Lauf mit vorübergehend acht Workern zu 80 % ist beendet.
Für neue ausdrücklich beauftragte Modulversuche gilt wieder **acht/70 %**.
Ein Torch-Thread, `nice -n 15`, ein schwerer Lauf gleichzeitig; Metal darf
PPO-Minibatches rechnen. Die genaue Zuordnung zu Performance-Kernen steuert macOS.

Eine Nachricht im Chat **„Training und automatische Fortsetzung stoppen“** bedeutet:
aktiven eigenen Job stoppen und die 15-Minuten-Automation pausieren. Zusätzlich:

```sh
.venv/bin/python -m ai.job_control stop
```

setzt den dauerhaften Stoppschalter `runs/STOP_AI_TRAINING`. Der verwaltete Job
prüft ihn alle 0,5 Sekunden; nach SIGINT erhält der Prozess bis zu 15 Sekunden
für das geordnete Ende. Neue verwaltete Jobs bleiben blockiert. Die Automation
darf den Schalter nicht selbst löschen. Zum Wiederaufnehmen ist eine ausdrückliche
Nutzeranweisung nötig. Bereits gespeicherte Modelle bleiben erhalten.

Neue schwere Jobs laufen unter `python -m ai.job_control run -- ...`; eine
Dateisperre verhindert zwei verwaltete Läufe gleichzeitig. Vor jedem Start auch
bestehende unverwaltete Trainingsprozesse prüfen. Die wieder aktivierte Automation
`ki-schonend-weitertrainieren` prüft alle 15 Minuten; ihre Reaktivierung wurde nach
einer ersten automatischen Ablehnung ausdrücklich vom Nutzer bestätigt.
Keine E-Mail. Nur aussagekräftigen Fortschritt, Fehler, Abschluss oder benötigten
Input melden.

## Neuer Veröffentlichungsauftrag: Crew 3 mit allen positiv getesteten Fällen

Der Nutzer verlangt erneut Crew 3 mit allen Routen, auf denen sie mehr als 0 %
gewinnt. Gemeint und im Chat angekündigt ist der **aktuelle vorhandene Crew-3-
Stand**, `ai/releases/crew3-intern-preview-v1/best.pt`, Profil 10 und Abstand 4:
keine still übernommenen Leckgewichte, keine neue Trainingsbehauptung.
Vorgesehen ist eine neue Veröffentlichung `crew3-current-preview-v2` namens
**Crew 3 · Aktuell (Test)**; vorhandene Veröffentlichungen bleiben erhalten.

Alle 186 offiziellen Fälle plus sechs vorhandene Grundspielrouten
FRA/LHR/MUC/MUC_T1/MUC_T2/MUC_T3 werden einzeln mit je 20 frischen
Entwicklungspartien geprüft (192 Fälle, 3.840 Spiele). Seedfolge ab 14.960.000,
Abstand 100 je Fall, vollständig unter 15.000.000. Nur tatsächlich positive
Einzelfälle (`wins > 0`) werden angeboten; 0/20 beweist keine Unmöglichkeit.
Explizite Falllisten gelten auch für Strecken ohne Karten. Anzeige nennt
Entwicklungsquote, keine unabhängige Freigabe (`quality.approved=false`).

Neue Module/Karten werden hier zunächst **getestet, nicht nachtrainiert**.
Eine spätere Metadatenkopie für die Veröffentlichung bewahrt alle Tensoren,
ursprünglichen Trainingsfelder und Zähler. Zusätzliche Laufzeitangaben und
getestete Fälle werden als reine Preview-Erweiterung getrennt dokumentiert.
Das neue `ai.preview_matrix_eval` und gemischte Falllisten sind implementiert.
30 relevante Python-Tests in 8,58 Sekunden und der strikte Node-Fallvertrag
bestehen. Read-only-Review ohne Befund. Das Frontend prüft ganzzahlige Siege,
konsistente Quote und exakte Fallzugehörigkeit auch ohne Karten. Neue Module
werden nicht pauschal aus `supported_airports` freigeschaltet.

Die vollständige Auswertung `ai.preview_matrix_eval` ist regulär beendet,
Exit 0, 167,22 Sekunden. Log `/tmp/cockpit-crew3-current-matrix-v1.log`,
abgeschlossener Bericht `ai/experiments/crew3-current-2026-10-25/matrix-development-v1.json`.
Alle **192 Fälle / 3.840 Partien**, keine Trunkierungen, echte Engine-Uhr auch bei
Echtzeit. 51 positive Fälle auf **18 Routen** (zwölf offizielle plus sechs alte
Grundspielrouten). Alle 141 Nullfälle bleiben vollständig im Bericht. Kein
unabhängiger Test, keine neuen Trainingsentscheidungen und keine neue Policy.
Modell-, Tensor-, Planer-, Engine- und Matrixhashes vor/nach dem Lauf geprüft.

Der neue Release `ai/releases/crew3-current-preview-v2/best.pt` ist lokal
zusammengestellt, **Crew 3 · Aktuell (Test)**. Exakt dieselben Tensoren und dasselbe
Browserasset wie bisheriges Crew 3, SHA
`d68bf9e86a7c2b514cb503f6e3aea12ef703f56f7b559c13b2649ab5acba7a8c`.
Keine zusätzlichen gelernten Modulkenntnisse behauptet. Reine Metadaten-Erweiterung
samt vollständiger ursprünglicher Trainingskonfiguration ist unter
`source-lineage.json` dokumentiert; Profil 10/Abstand 4 und 120.272 Phasenentscheidungen
bleiben unverändert. Testbare Erweiterung: Praktikant/Kerosin/Echtzeit und genau
die 39 positiv getesteten Kartenkombinationen, dazu zwölf kartenlose Fälle.
Wind/Eis/Leck haben mit diesem Modell auf den geprüften Fällen 0/20 und sind
in dieser neuen Crew daher nicht auswählbar. Andere ausdrücklich gewünschte
schwache Previews, insbesondere Crew 4, bleiben unverändert verfügbar.

`preview.positive_only=true`, `preview.enabled=true`, `quality.approved=false`.
Alle 73 vorherigen Katalogeinträge exakt erhalten, genehmigte Crew bleibt
vorausgewählt. Der komplette Auswertungsbericht wurde bytegenau ins Release
kopiert; Quoten je Fall, keine Durchschnittsfreigabe. Drei abschließende echte
Browserprüfungen bestehen: neue Crew 3 auf MUC ohne Karten und PBH Schwarz mit
Control+Mastery (Kerosin/Echtzeit), tatsächliche NN-Platzierungen und gespeichertes
Feedback; technische Wind-/NoCard- und 0%-Sperrprüfungen; unverändertes Crew 4/
Profil 11 mit allen sechs Karten; Daumen-/Mobil-/Privacy-/Speicher-/Cloudretry-
Regression. Chrome und Scoped-Server geschlossen, letzter Job regulär Exit 0.
Kein schwerer Job aktiv. Geprüfter Stand bereit für Push und Pages-Byteprüfung.

## Aktueller Auftrag: weitere Module, zunächst Praktikant

Der Nutzer hat nach der Veröffentlichung ausdrücklich weitere Module beauftragt.
Nächste reale offizielle Fälle sind Atlanta-grün (`LOG_ATL_GREEN`) und
Heathrow-gelb (`LOG_LHR_YELLOW`), jeweils Praktikant ohne Karten. Die offiziellen
Wind-/Eisstrecken benötigen bereits Karten; solche Karten nicht für eine
scheinbare offizielle Freigabe entfernen.

**Der Praktikantenlauf ist regulär beendet**, Exit 0: `runs/intern-profile10-stage1/`,
Log `/tmp/cockpit-intern-profile10-stage1.log`, Bericht
`ai/experiments/intern-2026-10-25/profile10-stage1.json`.
120.272 **neue** Entscheidungen in 54 Updates und 2.935 Partien, davon Atlanta
64.428 und Heathrow 55.844. 579,17 Sekunden Rollout/PPO-Zeit, 903,78 Sekunden
Wandzeit einschließlich Entwicklungsbewertungen. Acht Worker zu .7, Torch 1,
nice 15, Metal-Minibatches. Quelle exakt `ai/releases/crew2-v1/best.pt`, Seed
251050, frischer Adam und ausdrücklich neue Phase. Nur der bestehende Detailzweig
lernte; die ursprüngliche Grundlage blieb exakt eingefroren.

Feste Entwicklung, je 80 Partien: ATL ab 14.940.000, LHR ab 14.950.000.
Vorher 0/80 und 1/80 Siege; ausgewähltes `best.pt` bei 120.272 neuen Zügen:
**Atlanta 21/80 = 26,25 %, Heathrow 19/80 = 23,75 %**. Auswahl vorab nach schwächerer
Route, dann Mittel; der letzte Stand wurde so tatsächlich ausgewählt. Diese
Partien wurden zur Auswahl benutzt und sind **keine unabhängige Qualifikation**.
Die nächste unabhängige Kohorte ab 15.400.000 bleibt unbenutzt.

Auf ausdrücklichen Wunsch wird dieser Stand bereits als
**Crew 3 · Praktikant (Test)** (`ai/releases/crew3-intern-preview-v1/best.pt`)
mit beiden Routen angeboten. Tatsächlicher Gewichts-SHA:
`d68bf9e86a7c2b514cb503f6e3aea12ef703f56f7b559c13b2649ab5acba7a8c`.
Browserasset `b101798fc398d46a28ba3c323399ae1ebe9ec85a2ff77bd5760b591b25677707.json`.
`quality.approved=false`, `preview.enabled=true`, ausdrücklich Entwicklungsdaten;
keine automatische Auswahl anstelle genehmigter Crews. Kein Karten-/Wind-/Eis-
oder weiterer Modulnachweis. Der Bericht
`profile10-preview-development-v1.json` und `development.json` im Release
enthalten dieselben tatsächlichen Einzelquoten.

Vor jedem neuen schweren Job Prozesse, `runs/ai-job.json` und STOP prüfen.
Nicht während eines aktiven Vergleichs dessen Planungs-/Trainingsquellen ändern.
Der begrenzte Vergleich `ai.intern_strength_compare` ist regulär beendet, Exit 0.
Log `/tmp/cockpit-intern-strength-v1.log`, vollständiger Bericht
`ai/experiments/intern-2026-10-25/intern-strength-v1.json`, separate gepaarte
Auswertung `intern-strength-v1-analysis.json`. 320 Partien insgesamt,
acht Worker zu .7, Torch 1, nice 15. Je 40 frische Entwicklungspartien auf
Atlanta ab 14.980.000 und Heathrow ab 14.990.000, keine Abschlusskohorte.

| Variante | Atlanta | Heathrow | Schwächere Route |
| --- | ---: | ---: | ---: |
| Ursprüngliche Quelle, Abstand 4 | 0/40 | 2/40 | 0 % |
| Trainiertes Modell, Abstand 4 | 14/40 | 13/40 | 32,5 % |
| Gleiche Tensoren, Abstand 8 | 17/40 | 12/40 | 30 % |
| Gleiche Tensoren, Abstand 12 | 17/40 | 12/40 | 30 % |

Der trainierte Spieler verbessert beide frischen Entwicklungsrouten deutlich
gegenüber der Quelle. Ein größerer Referenzabstand ist kein konsistenter Vorteil:
er verbessert Atlanta und verschlechtert Heathrow. Abstand 4 bleibt nach dem
vorab festgelegten Kriterium; **Crew 3 bleibt exakt unverändert**. Abstand 8/12
führt in allen 80 Spielen zu denselben Ausgängen, keine zusätzlichen unabhängigen
Modelle oder Partien. Diese kleine Probe ist keine unabhängige Qualifikation.

Nächster begründeter Modulschritt: Leck, zunächst offizielles Atlanta gelb mit
jeder der sechs erlaubten Einzelkarten. Das Rohschema beobachtet den tatsächlichen
Kerosinstand, aber die alte Grundspielsuche ignoriert Leckkosten. Ein Leck hat
kein Kerosinfeld; `fuel.present=true` würde eine falsche Zusatzaufgabe erzeugen.
Die Kosten `abs(Pilotschub-Kopilotschub)+1` müssen direkt mit dem hypothetischen
Schubpaar und seinen Bewegungsfolgen bewertet werden. Neue Planung separat
entwickeln, engineprüfen und ausdrücklich neue Phase/Profile deklarieren.

### Laufende Leck-Diagnose nach dem Preview-Push

Crew 4 und alle sechs Kartenfälle sind mit
`7d60ffa921cafb9cd321a93426ca0133667bf78d` nach main gepusht und live bytegenau
geprüft (Katalog, Cacheversion, Singleplayer, Enginebundle, tatsächliche Gewichte).

Der Leckvergleich `ai.leak_strength_compare` ist regulär beendet, Exit 0,
199,24 Sekunden. Log `/tmp/cockpit-leak-strength-v1.log`, vollständiger Bericht
`ai/experiments/leak-2026-10-25/leak-strength-v1.json`. Sechs Varianten:
ursprüngliche Phasenquelle und vorab gewähltes Leckmodell, jeweils endlicher
Referenzabstand 4/8/12. Identische Tensoren innerhalb einer Herkunft; keine
zusätzlichen unabhängigen Trainingslinien. Beide Kontrollen (Quelle 4 und
Kandidat 4) sind je Fall gepaart gespeichert.

Genau sechs Einzelkarten, je 20 frische Entwicklungspartien ab 14.920.000 mit
Abstand 100. 720 simulierte Partien, ein gemeinsamer Satz von 120 Fall/Seed-Paaren
unter sechs Konfigurationen, acht Worker zu .7, Torch 1, nice 15, kein Training.

| Karte | Quelle 4 / 8 / 12 | Trainierter Kandidat 4 / 8 / 12 |
| --- | ---: | ---: |
| Adaptation | 1 / 2 / 3 | 0 / 2 / 3 |
| Anticipation | 0 / 1 / 1 | 0 / 1 / 1 |
| Control | 0 / 1 / 2 | 0 / 3 / 4 |
| Mastery | 0 / 1 / 1 | 0 / 0 / 0 |
| Synchronisation | 0 / 2 / 4 | 0 / 2 / 3 |
| Working-together | 0 / 2 / 2 | 0 / 1 / 0 |

Alle Werte Siege aus je 20. Abstand 12 weicht in diesen Spielen nie von der
Referenz ab; das ist keine generelle Garantie. Stärkere Vorgabe hilft mehreren
Fällen, doch das trainierte Modell bleibt bei zwei Karten sieglos. Die Quelle
mit Abstand 12 erreicht 5–20 % je Karte; der kleine Entwicklungsvergleich ist
keine Qualifikation. **Keine bestehende Crew geändert oder Konfiguration heimlich
umgestellt.** Der Vergleich hinterließ keinen aktiven Job. Sieben gezielte Tests bestehen.

Nächster begründeter Schritt: getrenntes neues öffentliches Profil für das
belegte Anpassungsmanöver; dann neue Phase aus den ursprünglichen Gewichten mit
explizit stärkerem endlichem Planungsabstand und frischem Adam. Neue Hashes,
Anfangsgewichte und Konfigurationsänderung ehrlich festhalten. Keine 80.206
Entscheidungen der schwächeren Linie als geerbtes Lernen ausgeben.

Zusätzlicher enginegeprüfter öffentlicher Gegenfall (keine NN-Präferenzprobe):
`public-card-rescue-v1.py` und abgeschlossener Bericht `public-card-rescue-v1.json`.
Pilot hat als letzten freien Würfel 1, Partner-Ruder 4 liegt, Fluglage 0,
Kaffee/Neuwurf 0. Profil 11 empfiehlt ausschließlich Ruder 1 und trudelt sofort
mit +3. Die legale Anpassung dreht 1→6, danach Ruder 6 überlebt mit −2.
Die Quelle ist eine legale öffentliche Platzierungsfolge; kein Partnerblick,
kein zukünftiger Spiel-RNG. Das belegt ein fehlendes Kartenmakro der Referenz,
keine Verbesserung einer Modellquote. Adaptation ist einmal je Person pro Flug,
nicht jede Runde. Weitere Erweiterung separat entwickeln und engineprüfen;
Profil 11 und bestehende Releases nicht still verändern.

Der beobachtete Unterschied „Verkehr auf jedem überflogenen Feld“ gegenüber
„sofortige Kollision nur am Abflugfeld“ rechtfertigt keine pauschale Entfernung
des Strafterms: übersprungene Flugzeuge bleiben unerreichbar und verhindern
später die Landung. Kein belegter nutzbarer Regelvorteil. Ruderauflösung,
einmalige Leckzahlung und eigene Aerodynamikänderungen wurden korrekt gefunden.

### Neue öffentliche Planungsphase 12: Anpassung als geplantes Manöver

Der abgeschlossene Leckvergleich und der öffentliche Gegenfall sind mit
`78de538` gesichert und gepusht. Danach wurde ein **neues Profil 12** ergänzt;
Profil 11 und alle vorhandenen Releasegewichte bleiben unverändert. Neue
Quelldatei `ai.leak_card_advice` plant eine legale Anpassung als 1→6 bzw.
allgemein 7−Augenzahl-Manöver vor der anschließenden gewöhnlichen Handplanung.
Die virtuelle Hand hat dieselbe Würfelanzahl. Platzierungs-/Kaffeeregeln werden
für die veränderten Augen neu berechnet; keine alte Gesichtsmaske wird kopiert.

Normale Pläne und höchstens vier verschiedene Augenwert-Manöver werden gemeinsam
bewertet; ein Kartenverbrauch kostet einen weichen Punkt und muss netto einen
normalen Plan verbessern. Das ist eine begrenzte Heuristik, kein exakter
Gewinnwert oder Beweis richtiger Ressourcenbewertung. Fehlende/verwendete Karte,
andere Physik und Dialoge fallen exakt auf Profil 11 zurück. Keine Zeitlimits
oder lastabhängiges Weglassen von Kandidaten: feste Arbeit (maximal Beam 24),
CPU-Pausen etwa alle 20 ms ändern keine Referenzmaske. Native Worker übergeben
`planning_cpu_duty_cycle=.7`, Browser rechnet mit 1; Beobachtung/Maske bleiben gleich.
Gemessen etwa 20–52 ms CPU je neuer Planungsentscheidung, mit .7 etwa 33–73 ms
Wandzeit. Neun neue gezielte Tests plus sieben bestehende Lecktests bestehen,
inklusive beider Rollen, echter Rettungsfolge, Kartenverbrauch über Runden,
virtueller Legalität, Privacy, deterministischem Pacing und Browserbridge.

`ai.train_leak` kann jetzt ausdrücklich `--assistance-version 12 --guide-margin 12`
verwenden. Standard 11/4 bleibt semantisch erhalten, aber **kein exaktes Resume
alter Fingerprints**. Ein neuer Aufruf startet erneut von originalem
`ai/releases/crew2-v1/best.pt`, frischem Adam, Zählern und Replay 0; die 80.206
Entscheidungen der schwächeren Linie werden nicht geerbt. Gewichtsdatei-Fingerprint
vor Override und Anfangs-Fingerprint danach werden getrennt aufgezeichnet;
Tensorhashes stimmen exakt überein. Die endliche Vorgabe verändert ausdrücklich
die Anfangswahrscheinlichkeiten, keine Tensorwerte. Bestehender Detailzweig lernt,
ursprüngliche Grundlage bleibt eingefroren. Phasehash umfasst nun auch den
verwendeten Kopier-/Hashhelper; alte Reports bleiben unverändert.

Der technische Metal-Probelauf `runs/leak-profile12-smoke-v1` ist regulär fertig:
69 neue Entscheidungen, ein echtes Update, Grundlage exakt unverändert,
trainierbarer Detailzweig verändert. Anfangstensoren exakt originales Crew-2-
Release, Modellkonfiguration mit Abstand 12 ausdrücklich anders. Bericht
`profile12-smoke-v1.json`; Probelaufgewichte werden verworfen. Zehn fokussierte
Trainer-/Fallbewertungstests bestehen, inklusive echtem 12/12-Rollout→PPO.

**373 Python-Tests bestanden in 99,55 Sekunden**, verwalteter Job Exit 0,
Log `/tmp/cockpit-leak12-tests.log`. Drei echte Browserprüfungen bestehen:
Profil 12 mit originalen Crew-2-Tensoren und ausdrücklich Abstand 12 wählt selbst
Anpassung 1→6 und anschließend Ruder 6 des KI-Kopiloten; Fluglage +2, Flug läuft
weiter. Dies ist ein technischer öffentlicher Gegenfall, keine neue Spielquote.
Unverändertes Crew 4/Profil 11 mit allen sechs Karten sowie Daumen-/Mobil-/
Speicher-/Cloudretry-Verhalten sind ebenfalls geprüft. Chrome und scoped Server
sind geschlossen; danach wurde nur der unten genannte Lauf gestartet.
Unabhängiger Read-only-Review ohne konkreten Befund; bestehende Modellkataloge
und Releasegewichte bleiben exakt erhalten.

**Profil 12 ist regulär beendet, Exit 0**: `runs/leak-profile12-stage1/`,
Log `/tmp/cockpit-leak-profile12-stage1.log`, abgeschlossener Bericht
`ai/experiments/leak-2026-10-25/profile12-stage1.json`. 80.139 neue Entscheidungen,
1.425 Trainingspartien, 35 Updates, 386,35 Trainingssekunden und 547,17 Sekunden
Gesamtwandzeit. Grundlage exakt eingefroren; 57 Trainingssiege, erfolgreiche
Selbstnachahmung erstmals aktiv (35 von 35 Updates mit positiver demo_loss).
Alle sechs Fallzähler summieren exakt auf 80.139. Quelle erneut originales Crew 2;
keine vorherige schwache Linie geerbt. Geprüfter Code mit `f6948ad` nach main
gepusht und Pages deployed; Enginebundle und Cacheversion live bytegenau.

Entwicklung je 20 Partien/Karte, Seed 251057 und Evaluationsbasis 14.930.000,
Abstand 100. Reihenfolge Adaptation/Anticipation/Control/Mastery/Synchronisation/
Working-together: **Anfang 2/1/4/2/1/1**, bei 45.694 Zügen **1/2/4/2/3/0**,
letzter Stand **1/3/3/2/4/0** Siege aus je 20. Nach vorab festgelegtem Minimum-
Kriterium bleibt **best.pt tatsächlich der Warmstand bei 0 neuen Zügen**.
57 erfolgreiche Trainingspartien sind ein Fortschritt gegenüber der sieglosen
Profil-11-Trainingslinie, aber keine Verbesserung der schwächsten Entwicklungs-
karte. Kein unabhängiger Test und kein Profil-12-Modell veröffentlicht. Nicht
unverändert weitertrainieren oder den warmen Stand als neu gelernten Erfolg
verkaufen. Zuerst der neue Crew-3-Veröffentlichungsauftrag, danach konkrete
Working-together-Fehler bzw. erfolgreiche enginegeprüfte Kartenübungen untersuchen.
Kein schwerer Job nach Abschluss aktiv; nächste Auswertung separat prüfen.

### Abgeschlossene neue Phase: Leck auf Atlanta gelb

Implementiert und gezielt geprüft: öffentliches Modulprofil **11**, getrennt von 10. Die bestehende
Handplanung erhält einen optionalen Schub-Bewertungshook, der ohne Hook exakt
die bisherigen Rechenwege bewahrt. `ai.leak_advice` bewertet für jedes öffentliche
oder hypothetische Schubpaar die tatsächlichen Leckkosten und die notwendige
Mindestreserve für spätere Runden. Die öffentliche Partnerprior-Verteilung bleibt
eine Näherung; sie ist weder eine gelesene Partnerhand noch ein exakter
Gewinnwert. Bereits vollständig platzierter Schub hat bereits Kerosin verbraucht
und wird nicht nochmals belastet. Gemischte Wind-/Eis-/Praktikantenphysik und
Bonus-/Tauschdialoge behalten vorerst die bisherige Planungsreferenz.

`ai.train_leak` ist eine neue explizite Phase mit frischem Adam aus den originalen
Crew-2-Gewichten, ohne zusätzliche Netzschicht. Nur der vorhandene Detailzweig
lernt, die ursprüngliche Grundlage bleibt eingefroren. Der echte Lauf `runs/leak-profile11-stage1/`, Log
`/tmp/cockpit-leak-profile11-stage1.log`, ist regulär beendet, Exit 0.
**80.206 neue Entscheidungen**, 2.481 Trainingspartien und 37 Updates,
331,12 Rollout/PPO-Sekunden, 416,27 Sekunden gesamte Wandzeit. Budget war
höchstens 80.000 neue Entscheidungen oder 600 Trainingssekunden plus letzte Charge,
acht Worker zu .7, Torch 1, nice 15 und Metal-Minibatches. Alle sechs offiziellen
Einzelkarten von `LOG_ATL_YELLOW` werden gleichberechtigt trainiert. Auswahl nach
der schwächsten Karte, Mittel nur bei Gleichstand. Keine unabhängige Kohorte.

Entwicklung über `ai.public_case_eval.run_public_case` mit echter `ModuleEnv`,
ausdrücklichem Route/Kartenfall, ohne Allmodul-Forschungswrapper und ohne
Proxy-Uhr. Je 20 Partien pro Karte ab 14.910.000 mit Abstand 100, vor Training,
alle 20 Updates und am Ende. Dies sind Entwicklungsdaten, keine Qualifikation.
Neue Quelldateien und der optionale Hook ändern den Fingerprint ehrlich;
alte Reports/Hashes bleiben unverändert. Der Praktikantenvergleich wurde noch
vor dieser neuen Phase unter dem damaligen Fingerprint abgeschlossen. Er darf
nicht mit manipulierten alten Hashes als exaktes Resume fortgesetzt werden.

Sieben gezielte Leck-Engine-/Privacytests, vier Tests der echten Fallbewertung
und drei echte Rollout/PPO-/CLI-Tests bestehen. Dabei fiel ein realer
Integrationsfehler auf: `ModuleEnv.episode_record` enthielt bisher keine tatsächlichen
Modul-/Kartennamen. Diese öffentlichen Metadaten wurden ergänzt und die
fallgenauen Trainingszähler anschließend erfolgreich geprüft.

Der kleine Metal-Probelauf `runs/leak-profile11-smoke-v1` ist regulär beendet:
31 neue Entscheidungen, ein echtes Update, ursprüngliche Crew-2-Anfangsgewichte
exakt, Grundlage unverändert, Detailzweig tatsächlich verändert. Bericht
`ai/experiments/leak-2026-10-25/profile11-smoke-v1.json`. Seine Gewichte werden
nicht als Trainingsquelle verwendet. Aktive Worker wurden mit Priorität 15 und
etwa 58–64 % CPU beobachtet. Im echten Lauf Seed 251054, Quelle weiterhin
originales `ai/releases/crew2-v1/best.pt`, frischer Adam. Aktuelle Zähler/Quoten aus
Logs lesen, währenddessen keine aktiven Trainings-/Planungsquellen ändern.

Der gewählte letzte Stand bei 80.206 neuen Zügen erzielt je 20 feste
Entwicklungspartien: **Adaptation 1/20 = 5 %, Anticipation/Control/Mastery/
Synchronisation/Working-together jeweils 0/20**. Vorher und bei 44.191 Zügen
alle sechs Fälle 0/20. Best wurde regelgemäß nach schwächstem Fall und Mittel
bei Gleichstand gewählt; auch die Anfangsgewichte waren zugelassen. Das Ziel
ist klar nicht erreicht. Kein neues unabhängiges Testset verwendet.

Die tatsächlichen Fallzähler: Adaptation 13.714, Anticipation 14.719, Control
12.503, Mastery 14.387, Synchronisation 10.797, Working-together 14.086.
Zusammen genau 80.206. **Keine der 2.481 stochastischen Trainingspartien wurde
gewonnen; die vorgesehene Selbstnachahmung erfolgreicher Partien war daher in
keinem Update aktiv.** Das ist ein konkreter Befund des Lernpfades, kein Beweis,
dass der Planer allein die Ursache ist. Nicht einfach denselben Lauf verlängern.
Als nächste begrenzte Diagnose öffentliches Referenzspiel und NN-Auswahl trennen
(z.B. endliche Abstände 4/8/12 auf neuen Entwicklungsfällen), anschließend
enginegeprüfte erfolgreiche Übungen/Partien erzeugen und konkrete frühe
Trudel-/Verkehrs-/Kerosinfehler lokalisieren.

Auf ausdrücklichen Nutzerwunsch wird der sehr schwache Zwischenstand zusätzlich
bereitgestellt: **Crew 4 · Leck (Test)**,
`ai/releases/crew4-leak-preview-v1/best.pt`, Gewichts-SHA
`14c9420c314b318c8cc134fa4aaa1dd1a8b80abe476f3b6a8c29fb772151a3d2`.
Alle sechs offiziellen Einzelkarten auf `LOG_ATL_YELLOW` werden einzeln
aufgelistet, auch die 0-%-Fälle. `quality.approved=false`, `preview.enabled=true`,
keine Prognose menschlicher Gewinnquoten, keine Freigabe. Daten:
`ai/experiments/leak-2026-10-25/profile11-stage1.json` und separate
`profile11-preview-development-v1.json`, identisches Release-development.json.

Neue Kartenrouten benötigen `preview.supported_cases` und fallgenaue
`preview.case_results`; ein bloßer Routeneintrag reicht nicht. Das Kartenset wird
explizit ausgewählt und beim Start erneut geprüft. Die Sitzung speichert den
exakten Fall. KI-Tausch wählt/bestätigt atomar mit einer Undo-Revision;
legale menschliche Offturn-Kartenschritte werden ohne falsches Policylabel erfasst.
Kein weiterer schwerer Trainingslauf aktiv. Die vollständige lokale Testsuite
besteht: **354 Tests in 93,79 Sekunden**. Zusätzlicher echter Vergleich mit dem
Code aus `7fcaf14`: 72/72 Ranglisten und Sequenzen exakt unverändert (24 öffentliche
Grundspiel-/Kerosinviews, Versionen 1/3/4, sieben Landungsviews). Profil 11 stimmt
in 24/24 Route/Karte/Rolle/Zustandsfällen nativ mit der Browserbridge überein;
24/24 Partnerhand-Poisoningprüfungen bleiben unverändert. Das sind technische
Nachweise, keine zusätzlichen Qualifikationspartien. Dokumentiert unter
`profile11-technical-checks.json`. Alle 72 bisherigen Katalogeinträge sind exakt
erhalten. Alle **sechs echten Browserprüfungen** bestehen: Crew 4 mit exakten
Kartenfällen/echten Gewichten, Crew-3-Vorschau, Praktikantenruntime, Kerosin,
ursprüngliche Crew 2 und vollständiges Daumen-/Mobil-/Speicherverhalten. Neue
Kartenfixture-Korrekturen betrafen nur den regelgemäßen Synchronisationsakteur,
die Wartezeit auf eine abgeschlossene Speicherversion und den Ergebnisdialog;
kein Produktionsfix nach der vollständigen Python-Suite. Chrome und Scoped-Server
sind beendet, letzter Job finished/0. Mobile Kartenauswahl bei 390 px visuell geprüft.
Geprüfter Code und abgeschlossene Berichte werden nach main gepusht.

Neues **öffentliches Modulprofil 10** in `ModuleEnv`: separate, weiche
Planungsreferenz, gemeinsame Kapazitätsregel, weiterhin lernbare Alternativen.
Grundspiel/Kerosin ohne Karten ist exakt Profil 9 mit Referenz 7 gleich.
Kompatible Kerosin-/Kartenfälle erhalten wieder öffentliche Kerosinplanung.
Praktikant erhält eine Rundenquote und eine Planung für den tatsächlich
ausgegebenen Ersatzwürfel. Er ersetzt einen regulären Würfel und zählt nicht
als zusätzlicher fünfter Handwürfel. Ziele für Ruder, Schub, Funk und Kerosin
werden mit öffentlichen Informationen bewertet. Keine Partneraugen oder echter
zukünftiger Spiel-RNG. Die bisherigen Profile/Releases bleiben semantisch
unverändert; geänderte Quelldateien ergeben ehrlich einen neuen Fingerprint,
alte Hashes werden nicht nachträglich angepasst. Der neue Lauf verwendet die
tatsächlich im Browser verfügbare `ModuleEnv`-Umgebung und keine heimlich
umbenannte Allmodul-Forschungsmaske.

Zusätzliche reine Physikfunktionen in `ai.module_physics` sind enginegeprüft:
Wind nach vollständigem Ruder, echte Schubgeschwindigkeit, strenge Eisbremsgrenze,
Leckverbrauch und notwendige Kerosinreserve. Wind-/Leckeffekte bereits öffentlicher
Kontrollpaare werden nicht zweimal berechnet. Diese Funktionen sind noch kein
Wind-/Eis-Gewinnnachweis und steuern das neue Praktikantenprofil nicht.

Neun Physiktests, sieben Praktikantenplanungstests, sechs Integrations-/Privacytests
über alle 186 Startfälle und drei echte Rollout→PPO-Tests bestanden. Letztere
zeigen korrekte Referenzmasken, exakte Logwahrscheinlichkeiten vor dem Update,
veränderten Detailzweig und unveränderte Grundlage. Technischer Metal-Probelauf
`runs/intern-profile10-smoke-v1/`: 79 Entscheidungen, ein Update, exakte Crew-2-
Anfangsgewichte, eingefrorene Grundlage bestätigt. Probelaufgewichte verworfen.

Der Browser führt jetzt echte Bonusaktionen aus, auch wenn der reguläre Zug
gewechselt hat oder keine regulären Würfel mehr übrig sind. Menschliche
Bonusaktionen werden aufgezeichnet und bestätigen Daumenfeedback; fremde
KI-Bonusziele sind nicht anklickbar. Technischer Browserfall mit echten
Gewichten und Profil 10 besteht. Dabei wurden eine fehlende Bundle-Abhängigkeit
(`ai.throttle`) und die Pyodide-`None`/JavaScript-`undefined`-Zuordnung zu
Modell-`null` behoben. Profil 10 ist gebündelt, alte Profile bleiben erhalten.
Vier abschließende echte Browserprüfungen bestehen: tatsächlicher Crew-3-Katalog
mit ehrlichem Previewstatus und beiden Routen, Praktikanten-Bonusablauf samt
Feedback, bestehende Kerosin-KI und Crew 2 mit acht Routen/beiden Rollen. Kein
JavaScript-Seitenfehler; Chrome und Scoped-Server danach beendet. Die Vorschau
zeigt die Entwicklungsquoten im Singleplayer und erlaubt Daumenfeedback.
Die vollständige lokale Testsuite besteht: **331 Tests in 87,31 Sekunden**,
einschließlich echter Rollout-/PPO-Tests, Privacy, aller 186 Adapter-Startfälle
und der unberührten fremden Transfer-Tests. Alle 71 bisherigen Katalogeinträge
blieben exakt erhalten; hinzu kommt nur das explizite Praktikanten-Preview.
Der Preview-Publisher verweigert das Überschreiben bestehender Releaseordner.
Mit `7fcaf1494cb699907708c343055d248d7946645f` nach main gepusht und per
GitHub Pages erfolgreich veröffentlicht. Live-Katalog, Cache-Version,
Singleplayer-JavaScript und tatsächliches Browsergewicht bytegenau geprüft.
Der Push enthält keine Änderungen an fremden Notebooks/Transferdateien.

## Abgeschlossener Allmodul-Lauf und Daumenfeedback

Das 20-Minuten-Budget wird nach einer erfolglosen Halbzeitprüfung in zwei
ausdrücklich getrennte Forschungsphasen aufgeteilt. `runs/allmodules-20min-v1/`,
Log `/tmp/cockpit-allmodules-20min-v1.log`, wurde nach **350.639 neuen Zügen,
160 Updates, 16.348 Partien und 668,37 Trainingssekunden** zur Wartung mit SIGINT
beendet. Kein Nutzer-Stopp und keine STOP-Datei. Checkpoint und ursprünglicher
Code sind erhalten (Commit `4fdd0eb`); der unterbrochene Bericht heißt
`ai/experiments/modules-30pct-2026-10-25/allmodules-raw-stage1.json`.
Ursprünglicher Befehl: `python -m ai.train_all_modules --run-dir
runs/allmodules-20min-v1 --training-seconds 1200 --workers 8 --cpu-duty-cycle .8
--device mps --seed 251046 --eval-seed 14800000 --eval-games-per-case 3
--eval-interval-seconds 600`, unter `nice -n15` und `ai.job_control`.

Quelle ist exakt die veröffentlichte Crew 2, frischer Adam, neue Forschungsphase
mit eigenem Umgebungsfingerprint. Nur der vorhandene Detailzweig lernt; die
Grundlage bleibt eingefroren. Der technische MPS-Probelauf
`runs/allmodules-smoke-v1/` bestätigte 107 neue Entscheidungen, ein echtes Update,
identische Anfangsgewichte und unveränderte Grundlage. Seine Gewichte wurden
nicht übernommen. 15 gezielte Tests einschließlich echtem Worker→PPO-Datenweg
bestanden vor dem langen Lauf.

Das Curriculum zieht zuerst gleichverteilt eine Route, dann deren erlaubte
Kartenkombination. Alle sechs Module und Karten werden ausdrücklich abgedeckt.
Die erste Forschungsumgebung `AllModulesEnv` bewahrt Maske 9/Referenz 7 für
Grundspiel/Kerosin ohne Karten. Andere Fälle erhalten enginelegale Auswahl mit
Referenzmaske. Eine endlose Tausch-Start/Abbruch-Folge wird verhindert. Erreichen
des Entscheidungslimits zählt als terminaler Trainingsfehler ohne Bootstrap,
während das ursprüngliche Engineergebnis unverändert bleibt. Echtzeit verwendet
eine logische Sekunde je Entscheidung: reproduzierbare Trainingsnähe, kein
Nachweis realer menschlicher Zeitdruckfähigkeit.

Das gesamte Budget zählt etwa 1.200 Sekunden Rollout/PPO-Rechenzeit; eine letzte vollständige
Charge kann die Grenze leicht überschreiten. Validierungen und Speichern kommen
zur Wandzeit hinzu. Vorher, nach 600 Trainingssekunden und am Ende werden je
drei Entwicklungspartien für jeden der 186 Fälle gespielt. Dies ist nur eine
kleine Auswahlprobe, keine Qualifikation. Auswahl zuerst nach Zahl der Fälle
mit beobachteten >=30 %, dann schwächstem Fall, erst zuletzt beschreibendem Mittel;
auch die Anfangsgewichte bleiben als `best.pt` zugelassen.

Die Anfangsprobe hatte fünf Siege aus 558 Partien, verteilt auf nur drei Fälle
(YUL drei, LHR einer, OSL einer). Eine unabhängige Datenprüfung fand 473 frühe
Verluste wegen fehlender Pflichtsteuerung und keinen Budgetabbruch. Ein zusätzlicher
öffentlicher Trainingszustand reproduziert das Problem: unter der breiten
Modulauswahl verbraucht die bisherige Politik den letzten regulären Würfel für
Konzentration statt fehlenden Schub. Das ist eine konkrete Planungsgrenze des
Ausgangsspielers, kein behaupteter Modulerfolg. Nach 315.754 neuen Zügen brachte
die Halbzeitprüfung sogar nur vier Siege in zwei Fällen; kein Verbesserungsbeleg.
Die aktiven Quellen wurden erst nach dem geordneten Ende geändert, die alte
Phase wird nicht als exaktes Resume fortgesetzt.

Die neue Phase für die verbleibenden **531,63 Trainingssekunden**,
`runs/allmodules-capacity-stage2/`, ist regulär beendet (Exit 0).
Log `/tmp/cockpit-allmodules-capacity-stage2.log`; Start wieder von exakt Crew 2
und frischem Adam, nicht von den schwachen letzten Gewichten. `CapacityModulesEnv`
reserviert nur öffentlich nachweisbar benötigte Kontrollwürfel; Praktikantentraining
bleibt als Ersatz erlaubt, ein tatsächlich ausgegebener schwarzer Würfel zählt
einmal gemeinsam. Bei möglicher späterer Synchronisation wird konservativ auf
die Beschränkung verzichtet. Neue Trainings-/Bewertungsoption `--capacity-guard`
und eigener Fingerprint; alte Produktionsprofile bleiben unverändert.
Elf enginegeprüfte Tests decken Kapazitätsregel und neue Umgebung ab. Der echte
MPS-Probelauf `runs/allmodules-capacity-smoke-v1/` endete mit 161 Entscheidungen
und einem Update; Quellgewichte am Anfang exakt gleich und Grundlage danach
unverändert. Seine Gewichte werden nicht verwendet. Insgesamt 32 gezielte
Kapazitäts-, Datenweg- und Feedbacktests bestanden. Ein leistungsfähigerer
Spieler ist damit noch nicht bewiesen.

Ergebnis: **303.770 neue Entscheidungen, 138 Updates, 11.676 Partien und
532,47 Trainingssekunden**, alle 186 Fälle besucht, Grundlage exakt unverändert.
Modulentscheidungen: Kerosin 106.368, Wind 38.642, Eis 31.021, Praktikant 28.313,
Leck 41.871, Echtzeit 28.208. Kartenzähler: Zusammenarbeit 45.261, Anpassung
44.162, Meisterung 42.666, Synchronisation 32.717, Kontrolle 41.061,
Voraussicht 41.578. Überlappende Modul-/Kartenzähler nicht aufsummieren.
Je drei feste Entwicklungspartien: zuvor YUL/LHR/OSL 3/1/1 Siege, zuletzt 3/2/1;
alle übrigen Fälle ohne Sieg. Die Auswahlregel wählt den letzten Stand, aber
dies ist **kein belegter Modulfortschritt und keine Freigabe**. Beide Phasen
zusammen verbrauchten 1.200,84 Trainingssekunden, 654.409 Entscheidungen und
28.024 Partien. Da Phase zwei erneut von Crew 2 startete, sind die verworfenen
350.639 Züge nur Aufwand, keine geerbten Trainingszüge dieses Kandidaten.
Abgeschlossene Berichte und alle 186 Einzelzeilen:
`allmodules-20min-summary.json`, `allmodules-capacity-stage2.json` und
`allmodules-20min-cases.csv` im neuen Experimentordner.

Nächste Ursache: Das rohe Modul-Referenzset ändert die Aktionsverteilung des
eingefrorenen Planers stark. Auf zwölf frischen Trainingszuständen änderte allein
eine kompatible öffentliche Kerosin-Referenz sieben Entscheidungen. Das ist
kein Gewinnvergleich. Als nächster begründeter Versuch weiche Planungshinweise
für kompatible Kerosin-/Kartenfälle prüfen, alle legalen Aktionen beibehalten.
Wind, Eis und Leck benötigen ausdrücklich ihre wirkliche Physik; den alten
Grundspielplaner dort nicht unverändert als harte Maske verwenden. Keine weitere
unveränderte PPO-Wiederholung oder unbegründete Architekturänderung.

**Unabhängige Qualifikation regulär abgeschlossen (Exit 0, 102,85 s):**
Vorab festgelegte Qualifikation
der UNVERÄNDERTEN Crew 2 auf `LOG_OSL_GREEN`, 500 Selbstspiele plus je 100 je Rolle
mit Heuristikpartner. Wieder acht Worker zu .7, Torch 1, nice 15.
Log `/tmp/cockpit-crew2-kerosene-qualification-v1.log`, Bericht
`ai/experiments/modules-30pct-2026-10-25/crew2-kerosene-qualification-v1.json`.
Neues ausdrücklich vom Nutzer akzeptiertes Kriterium: Wilson-Untergrenze >=.3.
Alte .5-Berichte bleiben unverändert. Seeds **15.200.000–15.200.499** und
**15.300.000–15.300.099** sind ab jetzt verbraucht/reserviert für diesen
vorab gewählten Test, keine Trainings-/Debugdaten. Ab **15.400.000** bleibt die
nächste unabhängige Kohorte unbenutzt. **199/500 Siege (39,8 %), Wilson
35,6–44,2 %**, bestanden. Heuristikpartner separat 6/100 als Pilotin und
9/100 als Kopilot (zusammen 7,5 %); keine Prognose menschlicher Partnerquote.
Separater Release `ai/releases/crew2-kerosene-v1/`, Name **Crew 2 · Kerosin**,
nur Oslo ohne Karten. Gewichte und Browserasset exakt identisch zur alten
Crew 2, ihre bisherige Freigabe bleibt unverändert. Die schwachen neuen
Allmodulgewichte werden nicht veröffentlicht. Weitere Module oder Karten
sind daraus nicht freigegeben.

Abschlussprüfung: **296 lokale Python-Tests bestanden** (67,12 s), einschließlich
der geschützten fremden Transfer-Tests. Ein erster temporärer Teststarter hatte
keinen macOS-Spawn-`__main__`-Schutz; nach Korrektur wurde die gesamte Suite
erneut ausgeführt. Worker-/Archivtests mit echtem SQLite ebenfalls bestanden.
Drei abschließende Browserprüfungen liefen nacheinander unter nice 15 und
`ai.job_control`: allgemeine Daumen-/Singleplayer-UI, tatsächlicher qualifizierter
Oslo-Spieler samt menschlichem Kerosinzug und Schema-3-Upload, bestehende Crew 2
auf acht Routen und mit beiden Rollen. Keine JavaScript-Seitenfehler.
Chrome und der auf 127.0.0.1 begrenzte Server sind beendet; **kein schwerer Job
mehr aktiv**. Letzter verwalteter Job: `tests/crew2-ui.cjs`, Exit 0. Vor einem
neuen Lauf weiterhin tatsächliche Prozesse/STOP/Status prüfen, Grenze wieder
acht Worker zu .7.

Der obere, mitlaufende Daumenbereich ist im Browser auf 320/390 Pixeln, mit
Tastatur, neutralem Standard, Rücknahme und letzter Spielaktion geprüft. Er
speichert +1/−1 statt der bisherigen Skala; alte Daten bleiben lesbar. Der Audit
entdeckte zusätzlich eine bisherige Cloud-Schranke für Crew-2-Daten (nur Schema 1
akzeptiert) und den fehlenden Import von Daumenfeedback ins Training. Diese
Datenwege sind jetzt korrigiert: Worker-Version
`b850056c-0c7c-49d4-a6e1-6001feee32a5` nimmt registrierte Schemas 1/2/3 an;
technischer Crew-2-Liveupload mit HTTP 200 und D1 geprüft, eigene Testzeile wieder
entfernt. Daumenpanel ist mit `8a11642` gepusht und live bytegleich geprüft.
`ai.feedback` importiert bestätigte explizite Bewertungen samt ursprünglicher
Referenzmaske, ohne Schema-Padding. `ai.train_feedback` bietet einen optionalen
Offline-Actor-Kopf-Lauf mit KL-Begrenzung und Validierung nach ganzen Partien.
Grundlage, Encoder und Kritiker bleiben unverändert; mindestens 64 informative
Bewertungen aus vier Partien. Kandidaten erben keine alte Freigabe.
14 gezielte Import-/Refinementtests bestanden. Vorhanden sind erst 16 nicht
neutrale alte Schema-1-Bewertungen aus drei Partien; damit wurde kein Modell
trainiert. Die Speicherung allein verändert weiterhin keine Gewichte.

## Abgeschlossene erste Versuche

Der Kerosinlauf erreichte 500.292 kumulative neue Modulentscheidungen. Auf 200
festen Entwicklungspartien lag der beste Stand bei 31,5 %, der letzte bei 29,5 %.
Die 80-Partien-Probe zuvor stieg auf 36,3 %; sie ist nicht derselbe Prüfvertrag.
Mehr Training dieses eingeschränkten Lernzweigs hat das 50-%-Ziel nicht erreicht.
Berichte: `ai/experiments/kerosene-2026-10-25/`.

Der Forschungsadapter `ai/modules.py` hat 489 Eingänge und 217 Aktionen für
alle sechs Module und Karten. Alle 186 Fälle starten, die geprüften Feldaktionen
stimmen mit der Engine überein und verdeckte Partnerwürfel bleiben ausgeschlossen.
Der schwarze Synchronisationswürfel wird als EIN gemeinsamer Würfel gezählt.
Echtzeitablauf, Praktikantentoken, Eisbremsen, Anpassung und bestätigter Tausch
haben eigene Tests. **Das ist Regelunterstützung, kein Nachweis guter Spielstärke.**
Im Browser stimmen Beobachtungen und Masken aller 186 Startaufstellungen mit
nativem Python überein (0,181 s für den vollständigen Vergleich). 204 Tests
bestanden; anschließend wurden nur die Routenentscheidungszähler ergänzt,
deren Summe sich im laufenden PPO-Protokoll exakt mit den Gesamtschritten deckt.

Das neue Netz erhält den alten Spieler als eingefrorenen Teil und ergänzt einen
zweischichtigen 256er-Residualzweig. Dessen Actor-/Kritikerausgänge beginnen bei
null, wodurch die bisherige Politik anfangs erhalten bleibt. Das Vortraining
lernt nur den neuen Encoder und temporäre Köpfe für erlaubte Aktionen sowie
öffentliche Aktionsfolgen. Gezielte Wind-/Ruder-, Schub-/Leck-, Eis-, Kerosin-
und Praktikantenübungen werden über die Engine ausgeführt. Es sind synthetische
Regelübungen, keine behaupteten gewonnenen Partien.

Finales Regelvortraining `runs/rules-allmodules-v3/rules.pt`: 37.016 Übungen,
12.375 getrennte Validierungsübungen, 99,73 % ausgewogene Regelerkennung.
Der mittlere Fehler öffentlicher Folgezustände sank unter die Nulländerungs-
Baseline. **Wind ist im Einzelvergleich weiterhin schwach**; diese Regelquote
ist keine Gewinnquote. Berichte mit Fehlern je Größe stehen unter
`ai/experiments/modules-50pct-2026-10-25/rule-pretraining-v3.json`.

## Residual-PPO abgeschlossen und Planungsmaske untersucht

`runs/modules-residual-stage1/` endete regulär nach **500.313 neuen PPO-Zügen**
in 25,4 Minuten. Davon entfielen 215.980 auf Oslo/Kerosin; 284.333 waren
Grundspielzüge auf HND/LHR/YUL. Mit 100.054 übernommenen Kerosinzügen sind es
316.034 kumulative Modulzüge. Die 37.016 Regelübungen bleiben separat.
Bericht: `ai/experiments/modules-50pct-2026-10-25/residual-stage1.json`.

Initialisierung war `runs/rules-allmodules-v3/rules.pt`, Seed 251026,
Curriculum OSL/OSL/OSL/HND/HND/LHR/YUL und Gewinnzug-Nachahmung mit Gewicht 0,03.
Auf jeweils 200 festen Entwicklungspartien ab 14.000.000 änderten sich die
Quoten von OSL 31,5 / HND 33 / LHR 69 / YUL 81,5 % auf zuletzt
**34,5 / 34 / 65 / 80 %**. Der nach schwächster Route gewählte Stand ist am Ende
identisch mit `latest.pt`. Kein ausreichender Fortschritt, keine Freigabe.
Für neue Läufe wurde korrigiert, dass auch das unveränderte Ausgangsmodell
als bester Stand erhalten werden kann; zuvor wurde die erste trainierte
Messung selbst bei Verschlechterung gespeichert.

`ai.planner_probe` misst passiv rohe Regelmasken, Kapazitätsgrenzen und die
engere Suchauswahl, ohne RNG oder Spielentscheidungen zu verändern. Gleiche
Würfel auf demselben Zielfeld zählen als dieselbe inhaltliche Wahl.
Auf zusätzlichen 100 Entwicklungsseed-Partien je Route ab 14.100.000:

| Stand | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Ausgang | 28 % | 29 % | 64 % | 78 % |
| Ende | 33 % | 31 % | 62 % | 85 % |

Beim Endstand sind rund 30 / 51 / 48 / 47 % der Entscheidungen inhaltlich
erzwungen, während die Kapazitätsmaske allein nur 3,5 / 4,9 / 3,0 / 1,8 %
vollständig erzwingt. Das begründet einen Versuch mit mehr Strategieraum,
beweist aber nicht, dass entfernte Aktionen gut wären. `best.pt` und `latest.pt`
haben identische Gewichte: deren wiederholte Prüfung zählt NICHT als zusätzliche
unabhängige Stichprobe. Bericht: `planner-probe-v1.json` im selben Berichtsordner.

Forschungsprofil 9 für Schema 2/3 erweitert ausschließlich Platzierungen auf
16 Scorepunkte Abstand zum besten Plan. Kaffeeauswahl, Neuwurfauswahl,
Budgetgrenzen und Profile 3–8 bleiben gleich. Das separate Grundspielprofil 9
bleibt unverändert. Eine Probe mit den unveränderten Ausgangsgewichten ergibt
nur **4 / 6 / 18 / 50 %**: mehr Aktionen ohne passenden Lernstart schadet.
Bericht: `planner-probe-wide-v1.json`. Diese Maske wird nicht veröffentlicht.

## Politikvortraining und abgeschlossener DAgger-Versuch

`runs/planner-distillation-v1/` ist nach 40 Epochen abgeschlossen. Das vorhandene
Hybridmodell mit Profil 7 erzeugte in 400 frischen Trainingspartien 23.439
erlaubte eigene Beobachtungen und Aktionsverteilungen. 100 zusätzliche Partien
lieferten 5.734 Validierungsbeispiele in einem getrennten String-Namensraum.
Diese Daten kommen weder aus den PPO-Validierungs- noch aus den Prüfseeds.
Auch verlorene Lehrerpartien sind enthalten; dies ist kein stärkerer Experte.

Ein weiterer Residualzweig lernt die Lehrerpolitik unter der breiteren Maske 9.
Sein Encoder übernimmt die bisherigen Merkmale; die alten Gewichte bleiben
eingefroren. Der neue Kritiker bleibt während dieses Politikvortrainings null,
damit Wertlernen die Nachahmung nicht stört. Auswahl nach Validierungs-KL,
**nicht** nach einer behaupteten Gewinnquote. Nachahmungsbeispiele und PPO-Züge
werden getrennt gezählt. Der neue Planerfingerabdruck beginnt einen expliziten
neuen Forschungsabschnitt; kein exaktes Resume des alten Laufs. Validierungs-KL
2,468 → 0,615; Übereinstimmung mit Lehreraktionen zuletzt 75,76 %.
Auf denselben zusätzlichen 100 Entwicklungsseed-Partien je Route wie der Lehrer
(14.100.000) erreicht der Schüler nur **11 / 15 / 24 / 55 %**, gegenüber
33 / 31 / 62 / 85 % beim Lehrer. Noch keine ausreichend erhaltene Spielweise.
Berichte: `planner-distillation-v1.json`, `planner-distillation-games-v1.json`.

`runs/planner-dagger-v1/` ist nach 200 Epochen beendet. Derselbe eingefrorene
Lehrer beschriftete auch vom Schüler erreichte Zustände. In 50 % der Züge
entschied der Schüler, sonst der Lehrer; separater Verhaltens-RNG, keine
zukünftigen Spielwürfe. Seed 251029 ergänzte 23.444 Trainings- und 5.793
Validierungsbeispiele, insgesamt 46.883 / 11.527 im jeweils getrennten Split.
Kein dritter Residualzweig wurde angelegt. Der beste Validierungs-KL lag in
Epoche 52 bei 0,4954; bis Epoche 200 stieg er auf 0,5968 (Überanpassung).
Die beste Aktionsübereinstimmung am ausgewählten Stand beträgt 78,28 %.

Auf je 100 neuen, identischen Entwicklungsseed-Partien ab 14.200.000:

| Modell | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Lehrer, Profil 7 | 33 % | 30 % | 68 % | 84 % |
| DAgger, Profil 9 | 20 % | 18 % | 40 % | 72 % |

Der Schüler ist weiterhin deutlich schwächer; daher kein PPO-Start aus diesem
Stand und keine Freigabe. Berichte `planner-dagger-v1.json`,
`dagger-teacher-games-v1.json`, `dagger-student-games-v1.json`. Nicht beliebig
mehr Epochen auf dieselben Daten verwenden.

## Geführte PPO-Stufe 1: erstmals positive Lernkurve

`runs/guided-residual-stage1/`, Log `/tmp/cockpit-guided-residual-stage1.log`.
Vor jedem Folgelauf `runs/ai-job.json`, Prozesse und STOP-Datei prüfen.
Der neue Typ `guided_residual` erhält den bisherigen Spieler als eingefrorene
Quelle. Die zusätzliche Politik startet mit Nullausgängen. Als öffentlicher
Hinweis wird die bisherige Auswahl aus Profil 7 mitgegeben; die tatsächlich
wählbare Maske bleibt die breitere Platzierungsauswahl aus Profil 9.

Die alten zugelassenen Aktionen behalten ihre Quell-Logits. Weitere Platzierungen
beginnen vier Logitpunkte unter dem besten Quellzug. Damit bleiben die anfänglichen
deterministischen Entscheidungen erhalten, während zusätzliche Aktionen eine
endliche Wahrscheinlichkeit und trainierbare Gradienten haben. Der Residualzweig
kann diesen Abstand später überwinden. Das ist eine weiche Planungsvorgabe,
keine vollständig planungsfreie Politik; Profil 9 grenzt weiterhin den Suchraum
ein. Fähigkeiten/andere Module sind in dieser PPO-Stufe noch ausgeschlossen.

Referenzmasken entstehen ausschließlich aus der erlaubten eigenen Sicht.
Sie werden für Rollouts, PPO, Gewinnzug-Nachahmung, Bewertung und Browserinferenz
identisch mitgeführt. Der Export nutzt Modellformat 4 bei unverändertem
489/217-Beobachtungs-/Aktionsschema. Bestehende Modelle/Browserformate bleiben
verfügbar. Ein geführter Spieler darf nicht als einfache rohe Quelle eines
weiteren Residualzweigs eingefroren werden, weil dabei sein Hinweis verloren
ginge; zum Fortsetzen `--resume` verwenden.

219 lokale Tests bestanden, einschließlich vollständiger Anfangspartien gegen
die eingefrorene Quelle, lernbarer Abweichungen, versteckter Partnerwürfel,
realem PPO samt Nachahmungs-Referenzen und JS-/PyTorch-Parität. Der Metal-Smoke-Test
`runs/guided-smoke-v1/` absolvierte 311 neue Entscheidungen mit zwei Workern.
Seine acht Validierungspartien sind nur ein Integrationstest, kein Qualitätsbeleg.

Der begrenzte PPO-Lauf startete vom besseren bisherigen Lehrer, nicht vom
schwächeren Nachahmungsmodell: Ziel 200.000 neue Entscheidungen, Seed 251031,
OSL/OSL/OSL/HND/HND/LHR/YUL, 200 Entwicklungsvalidierungen je Route ab
14.000.000, Auswahl zuerst nach schwächster Route. Ausgangsmodell bleibt als
Fallback im Modellvergleich. 316.034 geerbte Modulzüge, neue PPO-Züge und die
früheren Regel-/Nachahmungsübungen bleiben getrennt gezählt.
Die 800 Anfangspartien bestätigten exakt die bisherigen Quoten
**34,5 / 34 / 65 / 80 %**, einschließlich identischer Verlustzählungen.

Der Lauf endete regulär nach **200.115 neuen Entscheidungen** in 19,6 Minuten.
Davon waren 86.357 Kerosinzüge auf OSL und 113.758 Grundspielzüge. Mit der
eingefrorenen Quellenhistorie sind es 402.391 kumulative Modulzüge in dieser
Modelllinie. Neue Entscheidungen nach Route: OSL 86.357, HND 52.622,
LHR 31.253, YUL 29.883. Bericht `guided-stage1.json` enthält die gesamte
Entwicklungsvalidierung und die tatsächlichen Zähler.

| Feste Entwicklungsvalidierung, je 200 Partien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Anfang | 34,5 % | 34 % | 65 % | 80 % |
| Ende | 39,5 % | 38,5 % | 70,5 % | 85 % |

Zusätzlicher Vergleich auf denselben **frischen Entwicklungsseeds ab 14.300.000**,
200 Partien pro Route und Modell:

| Modell | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Quelle, Profil 7 | 35 % | 39,5 % | 63,5 % | 86,5 % |
| Geführt, Profil 9 | 37 % | 44 % | 67 % | 88 % |

Alle Differenzen sind positiv, aber klein und die Intervalle überlappen.
Dies ist ein Entwicklungssignal, kein abschließender Signifikanznachweis und
keine Freigabe. Einzelergebnisse wurden nicht für einen gepaarten Test behalten;
keine scheinbar präzisere gepaarte Statistik daraus ableiten. Berichte
`guided-teacher-games-v1.json`, `guided-candidate-games-v1.json` und
`guided-comparison-v1.json`. Oslo und Haneda bleiben deutlich unter dem Ziel.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --guided-source runs/modules-residual-stage1/best.pt \
  --run-dir runs/guided-residual-stage1 --guide-margin 4 --steps 200000 \
  --workers 8 --cpu-duty-cycle .7 --device mps --seed 251031 \
  --eval-games 800 --eval-every 20 \
  --eval-airports LOG_OSL_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --curriculum-airports LOG_OSL_GREEN LOG_OSL_GREEN LOG_OSL_GREEN LOG_HND_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --self-imitation-coef .03
```

## Geführte PPO-Fortsetzung abgeschlossen

`runs/guided-residual-stage2/`, Log `/tmp/cockpit-guided-residual-stage2.log`.
Vor jedem Folgelauf `runs/ai-job.json`, Prozesse und STOP-Datei prüfen.
Wegen der positiven Lernkurve und durchgängig positiven frischen Vergleiche
wurde bis zum Ziel von **500.000 kumulativen PPO-Entscheidungen in dieser
Phase** weitertrainiert, also ungefähr 300.000 weitere nach den vorhandenen 200.115.
Kein neues Residualnetz, keine neuen Beobachtungen oder geänderten Planer.
Optimizer, RNG, Gewinnzugpuffer, Referenzmasken, Seed 251031 und Routen-Curriculum
wurden aus `latest.pt` übernommen. Weitere Module/Karten waren noch nicht Teil
dieses Laufs. Die alten Quellen- und Regelübungsschritte bleiben separat.
Die 800 Partien unmittelbar nach Resume reproduzierten exakt die letzten
Quoten 39,5 / 38,5 / 70,5 / 85 % und Verlustzählungen des ersten Abschnitts.

Die Fortsetzung endete regulär nach 31,3 Minuten bei **500.347 kumulativen
Phasenentscheidungen**, also **300.232 weiteren** Entscheidungen. Davon waren
133.792 Oslo/Kerosin, 75.561 Haneda, 44.382 London und 46.497 Montréal.
Inklusive der Quellenhistorie sind es 536.183 Modulentscheidungen. Bericht
`guided-stage2.json` enthält tatsächliche Zähler und alle Entwicklungsprüfungen.

| Feste Entwicklungsvalidierung, je 200 Partien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Vor Fortsetzung, 200.115 Schritte | 39,5 % | 38,5 % | 70,5 % | 85 % |
| Letzter Stand, 500.347 Schritte | 38 % | 35,5 % | 80,5 % | 86 % |

Auf diesen festen Seeds verbessert sich die schwächste Route nicht; der bessere Mittelwert ersetzt das
Einzelfallziel nicht. `stage2/best.pt` ist nach Gewichts-Fingerprint weiterhin
**exakt identisch** mit `stage1/best.pt` bei 200.115 Schritten. Keine doppelte
Messung identischer Gewichte als zusätzliche unabhängige Evidenz ausgeben.
Der letzte Stand weicht bei rund 8,8 % der gesampelten Trainingszüge von der
alten Planerempfehlung ab; das ist weder die deterministische Spielquote noch
ein Nachweis besserer alternativer Züge. Kein weiterer unveränderter PPO-Lauf.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --resume runs/guided-residual-stage1/latest.pt \
  --run-dir runs/guided-residual-stage2 --steps 500000 \
  --workers 8 --cpu-duty-cycle .7 --device mps \
  --eval-games 800 --eval-every 20 --self-imitation-coef .03
```

## Frischer Entwicklungsvergleich und aktuelle Lernanalyse

Der Entwicklungsvergleich lief über `ai.planner_probe` auf **200 frischen
Partien pro Route und Modell ab 14.400.000**, Profil 9, acht Worker zu 70 %.
Er vergleicht `runs/guided-residual-stage1/best.pt` mit dem tatsächlich letzten
Stand `runs/guided-residual-stage2/latest.pt`. Bericht
`guided-stage2-comparison-v1.json`, Log
`/tmp/cockpit-guided-stage2-comparison-v1.log`. Er ist regulär abgeschlossen.

| Frische Entwicklungsseeds ab 14.400.000 | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Bisher bestes Modell, 200.115 Schritte | 38,5 % | 37 % | 76,5 % | 84,5 % |
| Letzter Stand, 500.347 Schritte | 46,5 % | 42 % | 72,5 % | 87 % |

Die beiden schwächeren Routen verbessern sich hier, London verschlechtert sich.
Das widerspricht einer pauschalen Aussage, längeres Training helfe überhaupt
nicht. Die feste Auswahl auf nur 200 Partien je Route reagiert offenbar anders
als diese frischen 200 Partien. Keine dieser kleinen Entwicklungsstichproben
ersetzt die unabhängige Qualifikation; Oslo/Haneda bleiben unter 50 %.

`ai.gradient_probe` misst auf frischen **Trainingszuständen** die
Gradienten der Zugwahl, der mit 0,5 gewichteten Wertschätzung und der bisherigen
Gewinnzug-Nachahmung im gemeinsamen trainierbaren Encoder. Gewichte und bereits
vorhandene Gradienten bleiben erhalten; keine Optimierung, kein Gewinnnachweis.
Negative Skalarprodukte können Interferenz zeigen, beweisen allein aber nicht,
dass eine kleinere Kritikergewichtung mehr Spiele gewinnt. Der Entropieterm
wird in dieser Diagnose ausdrücklich nicht mitgemessen. Kein privater
Partnerwürfel und kein zukünftiger echter Spielzufall wird gelesen.

Die Diagnose ist abgeschlossen: **8.412 Entscheidungen aus 150 frischen
Trainingspartien**, Seed 251033, 33 Minibatches. Bericht
`guided-gradient-probe-v1.json`, Log `/tmp/cockpit-guided-gradient-probe-v1.log`.
Der gewichtete Wertgradient erreicht im Mittel nur das **0,42-Fache** des
Politikgradienten; der mittlere Kosinus beträgt 0,031. In 16/33 Minibatches ist
das Skalarprodukt negativ, aber in **0/33** kehrt der gemeinsame Gradient die
Politikrichtung um. Kein klarer Beleg für dominierende Kritikerinterferenz;
deshalb keine unbegründete Architekturänderung oder kleinere Kritikergewichtung.
Die Messung beschreibt rohe Gradienten am Anfang eines PPO-Updates; sie
berücksichtigt weder Adam-Momente noch spätere PPO-Schritte, Clipping oder den
Entropieterm. Der maximale Unterschied der Rollout-Wahrscheinlichkeitsverhältnisse
zu 1 war 0,00000883. Der Gewichts-Fingerprint blieb unverändert.

Alle drei neuen Diagnosetests und die vollständige **lokale Suite mit 222 Tests**
bestanden (38,6 s). Die lokale Suite enthält auch die geschützten fremden Tests;
das ist keine Aussage über deren Verfügbarkeit im Remote-Repository.
Die anschließend gestartete Suchprüfung steht im nächsten Abschnitt.

Der unabhängige Kerosinvergleich ab 15.000.000 wurde noch NICHT gestartet.
Auch 12.000.000 und 13.000.000 bleiben unbenutzt. Keine neue Modul-KI ist
freigegeben; das Menü zeigt weiter die bisherigen Modelle.

## Gemeinsame Würfelzuordnung und abgeschlossener Suchvergleich

`ai/joint_round.py` berechnet statische Belegungen für hypothetische Hände:
Ruder, Schub, rollenbezogene Aufgaben und gemeinsame Aufgaben verwenden
**verschiedene Würfel**; Kaffee ist ein einziges gemeinsames Budget.
126 gewichtete Viererhände je Rolle decken alle 6^8 gleichverteilten Würfe ab.
Ein ausdrücklich verfügbarer schwarzer Zusatzwürfel wird entweder der Pilotin
oder dem Kopiloten zugeschlagen. Erfolgreiche Handpaare werden über beide
Zuordnungen vereinigt, nicht doppelt gezählt. Besitz der Synchronisationskarte
allein gewährt hier keinen kostenlosen Würfel. Gemeinsame Aufgaben wie Kerosin
werden ebenso genau einmal einer Rolle zugeordnet.

Sieben Tests prüfen unter anderem vollständige unabhängige Zuordnungen,
gemeinsamen Kaffee, konkurrierende Aufgaben, den einzelnen schwarzen Würfel
und eine tatsächlich in der Engine gewonnene konstruierte Landung. Bei drei
Zusatzaufgaben pro Rolle helfen auch neun Gesamtwürfel nicht: vier Kontrollen
plus sechs Aufgaben benötigen zehn. Das ist ein Regel-/Belegungsnachweis,
keine Quote auf offiziellen Routen.

`ai/joint_forecast.py` plant in der vorletzten und drittletzten Runde bis zur
Landung: frühere Vorbereitung, Funkzuordnung, Bewegung, Fluglage, Kaffeeverbrauch
und Kerosin konkurrieren um dieselben acht Zukunftswürfel. Ein Kerosinplatz pro
Zukunftsrunde und das Überlebensreservoir werden mitberechnet. Der bekannte
hypothetische eigene Kerosinverbrauch wird weitergegeben; ein noch nicht
bezahlter Partnerverbrauch bleibt optimistisch bei eins. Zukünftige
Verkehrswürfe werden weiterhin nur über einen öffentlichen Näherungsabschlag
berücksichtigt. Dies ist keine kalibrierte Gewinnwahrscheinlichkeit und keine
vollständige Suche über alle Zugfolgen oder Kartenwirkungen.

`ai/search_teacher.py` ist ein ausdrücklich experimenteller Suchlehrer auf dem
**unveränderten** geführten 500.347-Schritte-Netz. In frühen Runden, in der
Landung und beim Neuwurf entscheidet weiter die Quelle. Nur auf 1.000/2.000 Fuß
kann eine öffentliche Eigenhand-Suche die Auswahl neu ordnen. Drei Varianten
werden verglichen: `model` ohne Zusatzsuche, `legacy` mit der bisherigen
getrennten Zukunftsnäherung, `joint` mit gemeinsamer Zuordnung. Bestehende
Assistenzprofile bleiben semantisch gleich; `plan_actions` erhielt lediglich
einen optionalen, standardmäßig ungenutzten Forecast-Aufruf. Der dadurch neue
Quellcode-Fingerprint markiert ausdrücklich eine Forschungsphase, kein exaktes
Resume alter PPO-Läufe. Keine gespeicherten Fingerprints nachträglich anpassen.

Die neue Suche unterstützt vorerst **Grundspiel/Kerosin ohne Fähigkeitskarten**.
Andere Module/Karten werden ausdrücklich zurückgewiesen. Die Belegungsprimitive
kann einen bereits verfügbaren schwarzen Würfel behandeln; Karten-Auslösung,
Praktikantenketten, Wind, Leck, Eis und Echtzeit sind dadurch noch nicht in der
Zukunftssuche abgedeckt. Der Produktkatalog bleibt unverändert.

16 neue Tests und die gesamte **lokale Suite mit 238 Tests** bestanden
(39,4 s); die Browserquellen wurden neu gebaut. Ein Integrationstest mit zwei
gedrosselten Workern lief über **24 Partien** (2 je Variante und Route), Seed
14.900.000, Beam 32. Bericht `joint-search-smoke-v1.json` enthält keine
Freigabeevidenz. Der Bericht entstand noch vor Ergänzung der zusätzlichen
gepaarten Ausgabe `paired_against_legacy`; Spiel-/Suchcode blieb dabei gleich.

Der erste große Lauf wurde zur Wartung unterbrochen: die neue Suche erzeugte
zu lange CPU-Spitzen innerhalb einzelner Entscheidungen, weil vorher nur
zwischen Spielzügen pausiert wurde. Alle eigenen Prozesse sind beendet worden;
die dauerhafte Nutzer-STOP-Datei wurde weder gesetzt noch gelöscht.
`joint-search-development-v1.json` enthält ausschließlich die abgeschlossenen
Varianten `model` und `legacy`; keine fertige `joint`-Route. Er ist ausdrücklich
als unvollständig markiert. Modell/Legacy-Quoten: OSL 47/56, HND 48/44,
LHR 65/66, YUL 88/91 Siege pro 100 Partien.

Die Drosselung greift nun zusätzlich innerhalb der Eigenhand- und Zukunftssuche
in Zeitabschnitten von ungefähr 20 ms. Die äußere Drosselung bleibt ebenfalls
aktiv; das ist konservativer als 70 % insgesamt und vermeidet lange Volllast.
Ein zusätzlicher Test bestätigt unveränderte Suchwerte mit Kooperationsaufrufen.
Nach Neustart stimmen alle 800 bereits abgeschlossenen Modell-/Legacy-Ergebnisse
mit v1 exakt überein, einschließlich Verlustgründen und Eingriffszählern.
Eine Prozesskontrolle während der langen Joint-Suche zeigte aktive Worker bei
ungefähr 61–63 % CPU; alle acht Worker haben Priorität 15 und einen Torch-Thread.

**Regulär abgeschlossener Suchvergleich:** `ai.search_evaluate`, Log
`/tmp/cockpit-joint-search-development-v2.log`, Ausgabe
`ai/experiments/modules-50pct-2026-10-25/joint-search-development-v2.json`.
Je **100 neue Entwicklungspartien pro Route und Variante**, Seeds ab
14.500.000, OSL/HND/LHR/YUL, Beam 64, acht Worker zu 70 %, ein Torch-Thread,
`nice -n15`. Insgesamt 1.200 Partien; **keine neuen Trainingsentscheidungen**.
Dieselben Entwicklungsseeds wie v1: wiederholte Modell-/Legacy-Partien zählen
nicht als zusätzliche unabhängige Evidenz. Die Wartungsunterbrechung erfolgte
nicht aufgrund eines Ergebnisses der noch unvollständigen Joint-Variante.
Einzelergebnisse werden mit Route/Seed/Status/Grund gespeichert, damit
gepaarte Unterschiede nachvollziehbar bleiben. Die abschließenden Prüfseeds
ab 15.000.000 bleiben unbenutzt. Vor weiteren Läufen Status/STOP/Prozesse prüfen.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt \
  --games 100 --seed 14500000 --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/joint-search-development-v2.json
```

Der vollständige v2-Lauf endete regulär nach **28,9 Minuten**, Exit 0.

| Variante, je 100 Entwicklungspartien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Unverändertes Netz (`model`) | 47 | 48 | 65 | 88 |
| Getrennte Näherung (`legacy`) | 56 | 44 | 66 | 91 |
| Gemeinsame Zuordnung (`joint`) | 55 | 44 | 69 | 91 |

Gepaarte Gewinne/Verluste von Joint gegenüber dem Netz: OSL 17/9,
HND 1/5, LHR 8/4, YUL 5/2. Gegenüber Legacy: OSL 3/4, HND 2/2,
LHR 3/0, YUL 2/2. Die gemeinsame Zuordnung verbessert die schwächste
Route **nicht**. Keine Freigabe und kein Grund, diesen Lehrer unverändert zu
imitieren. Oslo brauchte allein 1.324 s statt 20,4 s bei Legacy: ungefähr
65-fache Laufzeit ohne bessere Quote. Die wiederholten 800 Modell-/Legacy-
Partien zählen weiterhin nicht als zusätzliche unabhängige Evidenz.

## Öffentliche Fehlerdiagnose und letzter eigener Würfel

`ai.search_diagnose` reproduzierte sechs Haneda-Fälle, die das Netz gewinnt und
mindestens eine Suche verliert: 18 Replays, Bericht
`haneda-search-failures-v1.json`, Log `/tmp/cockpit-haneda-search-failures-v1.log`.
Status und Verlustgrund jedes Replays stimmen exakt mit dem v2-Vergleich überein.
Alle schädlichen Eingriffe dieser Beispiele enthielten den ursprünglichen
Netzzug als bewerteten Suchplan. Die Hypothese eines fehlenden Vergleichszugs
im Beam wird dadurch **nicht** gestützt. Profiling misst reine Prozess-CPU-Zeit;
der Hauptaufwand dieser Beispiele liegt in der Zukunftssuche, nicht im Netz.

Eine erweiterte Instrumentierung zeichnet auch eigene Planfolgen und folgende
Netzzüge auf: `haneda-search-sequences-v2.json`, neun Replays der drei Fälle
14.510.008/047/068, Log `/tmp/cockpit-haneda-search-sequences-v2.log`.
Diese ausgewählten Wiederholungen sind **keine neue Quotenstichprobe** und
erzeugen keine Trainingsentscheidungen. Nur der eigene erlaubte Eingang wird
protokolliert; keine private Partnerhand und kein zukünftiger Spielzufall.
Die Instrumentierung verändert weder Pläne noch ausgewählte Aktionen.

Konkrete Grenzen:

- In 14.510.008 bauen beide Suchen vor der Landung Bremse 2 gegen Kaffee.
  Das Netz spart den Kaffee und gewinnt die spätere Landung. Die Suchvariante
  führt ihren Plan hier tatsächlich aus, verliert aber mit zu hohem Schub.
  Statische Aufgabenpunkte sind deshalb kein zuverlässiger Gewinnwert.
- In 14.510.047 priorisieren beide Suchen eine frühe Landeklappe gegen Kaffee;
  nachfolgende Netzzüge erreichen die vollständigen Klappen nicht. Auch hier
  wird die geplante letzte Platzierung ausgeführt. Kein allgemeiner Beleg,
  dass bloß konsequente Planausführung diese Niederlagen verhindert.
- In 14.510.068 plant Joint zuletzt Ruder 5; bei nur einem eigenen Würfel
  übernimmt bisher automatisch das Netz, startet einen Neuwurf und trudelt.
  Diese Inkonsistenz begründet einen **separaten** Versuch `joint-finish`, der
  auch den letzten eigenen Würfel unter der aktuellen erlaubten Maske neu
  plant. Er erzwingt keinen alten Plan nach Partnerzügen. Frühe Runden,
  Landung und offene Neuwürfe bleiben beim Netz; fehlen bewertete erlaubte
  Platzierungen, bleibt ebenfalls die Netzauswahl. `model`, `legacy` und
  `joint` behalten ihre bisherige Semantik.

**Ebenfalls regulär abgeschlossener Versuch:** 100 Haneda-Entwicklungspartien ab 14.510.000,
gleiche Gewichte, Varianten `model`, `joint`, `joint-finish`. Wiederholte
Kontrollen zuerst auf exakte Übereinstimmung mit v2 prüfen. Ein Erfolg auf
diesen bereits untersuchten Seeds erfordert anschließend frische Entwicklung;
die unabhängigen Prüfseeds ab 15.000.000 bleiben unbenutzt. Kein neues Modell
und kein Suchprofil wurde für den Singleplayer freigegeben.

Bericht `joint-finish-haneda-development-v1.json`, Log
`/tmp/cockpit-joint-finish-haneda-development-v1.log`. Alle 300 Partien sind
abgeschlossen: **Netz 48, Joint 44, Joint-Finish 45 Siege**. Modell- und
Joint-Kontrolle stimmen bei allen 200 Einzelresultaten exakt mit v2 überein.
Die letzte-Würfel-Erweiterung liegt weiterhin unter dem Netz: vier neu gewonnene
gegen sieben verlorene Netzsiege. Das begründet weder eine Freigabe noch eine
große frische Bestätigungsserie. Gegenüber Joint sind es vier Gewinne/drei
Verluste. Fall 14.510.008 wird gewonnen, 14.510.047 bleibt verloren und auch
14.510.068 endet weiterhin im Trudeln: die vermutete Ausführungskorrektur
behebt das konkrete Ruder-Gegenbeispiel nicht. Acht Worker zu höchstens 70 %, Torch-Threads 1,
`nice -n15`, verwaltet über `ai.job_control`; reguläres Ende nach 216 s, Exit 0.
Danach lief zunächst kein schwerer Job. Nach dieser Änderung bestanden **241 lokale Tests** (26,3 s),
einschließlich der geschützten fremden Tests. Keine neuen PPO-Entscheidungen.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model joint joint-finish --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/joint-finish-haneda-development-v1.json
```

## Frühe Verkehrs- und Kurvenverluste auf Haneda

`haneda-traffic-curves-diagnosis-v1.json` reproduziert **alle 28** entsprechenden
Netzverluste aus denselben 100 HND-Entwicklungspartien. Die Ausgänge und Gründe
stimmen exakt überein; ausgewählte Wiederholungen sind keine neue Quotenstichprobe.
Log `/tmp/cockpit-haneda-traffic-curves-diagnosis-v1.log`, zwei Worker zu 70 %,
reguläres Ende nach 9,2 s, keine Trainingsentscheidungen. Pro Spiel werden die
letzten acht Entscheidungen mit ausschließlich öffentlichem Kontext, eigener
Hand und erlaubter Aktionsauswahl gespeichert. Der Diagnoseadapter kann jetzt
auch gezielt Netzverluste und bestimmte Gründe auswählen, ohne Suchverluste
oder drei feste Vergleichsmodi vorauszusetzen.

| Verlusthöhe | Kollision | Kurvenkorridor | Summe |
| --- | ---: | ---: | ---: |
| 5.000 Fuß, Runde 2 | 4 | 1 | 5 |
| 4.000 Fuß, Runde 3 | 11 | 5 | 16 |
| 3.000 Fuß, Runde 4 | 1 | 4 | 5 |
| 2.000 Fuß, Runde 5 | 1 | 1 | 2 |

**26/28 entstehen vor dem bisherigen Suchfenster.** Einzelbeispiele zeigen,
dass eine Rolle optionale Aufgaben ausführt, während beide Seiten auf die
Funkarbeit des Partners hoffen. In Fall 14.510.029 verbraucht die Pilotin den
restlichen Kaffee für Schub, während das noch offene Partner-Ruder den Kaffee
für die aktuelle Linkskurve braucht. Dies ist eine nachträgliche Erklärung aus
jeweils erlaubten Eingängen, kein Zugriff des Spielers auf die verdeckte Hand.
Die Beispiele beweisen nicht, dass jede der 28 Partien zu retten gewesen wäre.

**Regulär abgeschlossener Vergleich:** `early-round-haneda-development-v1.json`,
Log `/tmp/cockpit-early-round-haneda-development-v1.log`, 100 HND-Partien ab
14.510.000, dasselbe Netz und dieselbe Assistenzmaske 9. Neue, ausdrücklich
experimentelle Varianten `round-plain` und `round-risk` suchen in **jeder
Nicht-Landerunde**, weiterhin nicht bei offenen Neuwürfen oder weniger als
zwei eigenen Würfeln. Beide verzichten in diesem Vergleich auf eine weitere
Zukunftsprognose. `round-plain` verwendet Planerversion 3; `round-risk` die
bereits vorhandene Version 4 mit gemeinsamem Ruder-/Schubprior über verschiedene
Partnerwürfel, einem Kaffeebudget und zusätzlicher Funk-Kapazitätsstrafe.
Diese Version ist weiterhin **keine vollständige gemeinsame Zuordnung von
Funk, Kontrollen und allen Aufgaben**. Der Versuch trennt die Wirkung früher
Suche von dieser bestehenden Risikoabschätzung. Alle alten Varianten behalten
ihre Semantik; keine Änderung bestehender Produktprofile oder Gewichte.

14 gezielte Tests einschließlich der neuen Varianten und der Diagnoseauswahl
bestanden. Acht Worker zu höchstens 70 %, Torch-Threads 1, `nice -n15`, über
`ai.job_control`. Nach 59,3 s regulär beendet: **Netz 48, frühe einfache Suche 42,
frühe Risiko-Suche 47 Siege**. Gegen das Netz gewinnt Round-Plain 14 andere
Partien und verliert 20 Netzsiege; Round-Risk gewinnt 17 und verliert 18.
Keine Verbesserung gegenüber dem Netz, keine neue Freigabeevidenz.

Ein wichtiger verbleibender Engpass ist in Fall 14.510.029 konkret sichtbar:
bei Schritt 27 lässt Assistenzmaske 9 ausschließlich Kaffee −2 auf den letzten
eigenen Schubwürfel zu. Einfaches Platzieren und Kaffee −1 sind ausgeschlossen.
Der Suchlehrer kann solche Alternativen trotz abweichender Risikobewertung
nicht auswählen. Die breitere Maske 9 erweiterte bisher nur Platzierungsabstände,
nicht alle Kaffee-/Neuwurfentscheidungen. Ein begründeter nächster Versuch
muss gezielt zusätzliche, enginegeprüfte Risiko-Vorschläge zulassen und die
Netzentscheidung weiterhin auf ihrer ursprünglichen Maske berechnen; die rohe
Politik unter einer beliebig weiten Maske war schon früher stark schlechter.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model round-plain round-risk --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/early-round-haneda-development-v1.json
```

## Gezielte legale Risikovorschläge außerhalb der alten Maske

`ai.search_environment.OpenRiskEnv` ist eine **getrennte Forschungsumgebung**.
Sie vereinigt die bisherige Maske 9 mit einer kleinen, aus der rohen
Engine-Regelmaske gewonnenen Risiko-Auswahl (Planerversion 4). Notwendige
Kapazitäts-/Kerosingrenzen bleiben erhalten. Schlechte Vorschläge unter −100
Suchpunkten verdrängen keinen Rettungsneuwurf. Die Netzentscheidung wird
ausdrücklich auf `source_action_mask` berechnet, nicht unter der erweiterten
Auswahl; auch Referenzmaske 7 bleibt exakt erhalten. Nur der separate Suchlehrer
`round-open` darf zusätzliche Vorschläge wählen, einschließlich des letzten
eigenen Würfels. Andere Produktprofile und Gewichte bleiben gleich.

Ein konstruierter, **in der Engine ausgeführter** Engpasstest zeigt: Die alte
Maske erzwingt Kaffee −2 für Schub 2. Die Risiko-Auswahl erlaubt stattdessen
Schub 4, bewahrt zwei Kaffee und ermöglicht danach ein um eins angepasstes
Partner-Ruder. Beide aktuellen Kurven werden mit Fluglage −1 durchflogen;
ein Kaffee bleibt. Dies belegt die einzelne Regelkorrektur, keine Routenquote.
Das versteckte Partner-Ruder in der Testaufstellung wird nicht an den Lehrer
übergeben. Weitere Tests prüfen exakt erhaltene Quell-/Referenzmasken,
Engine-Legalität der zusätzlichen Auswahl, Partnerwürfel-Privatsphäre und die
unveränderte Landemaske. **246 lokale Tests bestanden** (27,0 s); enthalten
sind weiterhin die geschützten fremden Tests. Browser-/Produktcode unverändert.

**Regulär abgeschlossener Vergleich:** `open-risk-haneda-development-v1.json`,
Log `/tmp/cockpit-open-risk-haneda-development-v1.log`, 100 HND-Entwicklungspartien
ab 14.510.000, Varianten `model`, `round-risk`, `round-open`, Beam 64, acht
Worker zu höchstens 70 %, Torch-Threads 1, `nice -n15`, über `ai.job_control`.
Kontrollen zuerst auf exakte Wiederholung prüfen. Die neuen Vorschläge
verwenden weiterhin nur die eigene Hand und öffentliche Daten; auch innerhalb
der zusätzlichen Planung wird ungefähr alle 20 ms freiwillig pausiert.
Keine neuen PPO-Entscheidungen, keine neue Modulfreigabe. Bei Vorteil sind
frische Entwicklungsseeds erforderlich, nicht sofort eine Freigabe. Ergebnis
nach 96,4 s: **Netz 48, Round-Risk 47, Round-Open 45 Siege**. Die 200
Kontrollresultate wiederholen sich exakt. Round-Open gewinnt 20 andere Partien
und verliert 23 Netzsiege. Die Einzelkorrektur beseitigt eine Beschränkung,
aber die feste Risikobewertung liefert keinen insgesamt stärkeren Lehrer.
Keine große Bestätigungsserie oder Nachahmung dieser festen Zugvorgabe.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model round-risk round-open --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/open-risk-haneda-development-v1.json
```

## Neues Lernen mit gezielt erweiterten Aktionen

`neural-open-haneda-development-v1.json` prüft die **unveränderten Gewichte**
unter der gezielt erweiterten Maske, ohne festen Suchlehrer. Auf denselben
100 bekannten HND-Partien: **Netz alt 48, Netz mit Zusatzaktionen 45 Siege**,
0 zusätzliche Siege gegen drei verlorene ursprüngliche Siege. Lauf regulär
nach 64,5 s beendet; wiederholte Kontrolle exakt gleich. Die neue Auswahl
liefert also vor Training noch keinen Vorteil. Diese Messung ist keine
zusätzliche unabhängige Stichprobe und keine Freigabe.

Der neue PPO-Weg lernt die Bewertung dieser begrenzten Zusatzaktionen selbst,
anstatt schwächere feste Lehrerzüge zu imitieren. **Keine zusätzliche Schicht,
keine Änderung der eingefrorenen Grundlage oder Kritikergewichtung.** Der
vorhandene trainierbare Detailzweig wird benutzt. `--phase-source` lädt exakt
die geführten 500.347-Schritte-Gewichte und startet ausdrücklich eine **neue
Forschungsphase** mit frischem Adam und Zählern. Quellpfad, Gewichts-SHA,
Quellschritte und alter Planer-Fingerprint werden separat gespeichert; alte
Checkpoints/Hashes werden nicht verändert. Es wird kein exaktes Resume über
geänderten Planungscode behauptet. Ein späteres Resume der neuen Phase verlangt
dieselbe Forschungsumgebung und denselben Such-Fingerprint.

`ParallelGames` führt die neue Umgebung in Training und Bewertung mit. Die
Referenzmaske 7 bleibt in Rollouts, PPO-Wahrscheinlichkeiten und erfolgreichem
Trainingsreplay erhalten. Tests prüfen vor dem Update Wahrscheinlichkeits-
verhältnisse von 1, anschließend echte Änderungen im bestehenden Detailzweig
bei exakt unveränderten eingefrorenen Gewichten. Parallele Bewertung stimmt
mit direkter Bewertung überein. **249 lokale Tests bestanden** (36,3 s),
einschließlich der geschützten fremden Tests. Die bisherigen Standardpfade
verwenden weiterhin ihre bisherigen Umgebungen.

Der komplette Befehl wurde mit dem echten Modell und nur einem kleinen
PPO-Update erfolgreich geprüft: `runs/open-risk-ppo-smoke-v1/`, Log
`/tmp/cockpit-open-risk-ppo-smoke-v1.log`, Ziel 64 neue Entscheidungen mit
möglichem Überschreiten zum Episodenende, tatsächlich **128 neue Entscheidungen
in einem Update**, hier zufällig beide Trainingspartien auf OSL. Zwei Worker
zu 70 %, CPU-Update, regulär nach 33 s beendet. Acht winzige Validierungspartien
pro Messung dienen nur der technischen Prüfung. `open-risk-ppo-smoke-v1.json`
belegt identische Anfangsgewichte und exakt unveränderte eingefrorene Grundlage
nach dem echten PPO-Update. Kein Modell aus dieser technischen Probe
wird freigegeben oder als Gewichtsquelle des eigentlichen Laufs benutzt.

**Regulär abgeschlossene PPO-Phase:** `runs/open-risk-ppo-stage1/`, Log
`/tmp/cockpit-open-risk-ppo-stage1.log`, begrenzte Phase von
**100.000 NEUEN Entscheidungen**:
OSL/HND/LHR/YUL, HND dreifach und OSL zweifach im Curriculum, 100 feste
Entwicklungspartien pro Route (400 insgesamt) ab 14.650.000, Auswahl nach der
schwächsten Route. Anfangsgewichte bleiben als möglicher bester Stand erhalten.
Bewertung etwa alle 50.000 Entscheidungen; bei Plateau kein unbegründetes
Endlos-PPO. Die unabhängige Qualifikation ab 15.000.000 bleibt unbenutzt.
Höchstens acht CPU-Worker zu 70 %, ein Torch-Thread, `nice -n15`; Metal kann die
PPO-Minibatches übernehmen und wurde außerhalb der Sandbox als verfügbar geprüft.
Seed 251039, Lernrate 0,00005, Selbstnachahmung nur erfolgreicher Trainingszüge
mit Gewicht 0,03. Quelle ist wieder der unveränderte 500.347-Stand, nicht die
128-Züge-Probe. Grobe Dauer 20–40 Minuten, abhängig von Episoden und Bewertungen.
Währenddessen keine Such-/Trainingsquellen ändern und keinen zweiten schweren
Job starten. Konkrete Schritte/Einzelquoten immer aus den laufenden Logs lesen.
Die Anfangsprüfung ist abgeschlossen: je 100 Partien auf den **neuen** festen
Entwicklungsseeds ergeben **OSL 48 / HND 36 / LHR 68 / YUL 88 %**. Das ist der
Stand vor dem ersten Update unter der neuen Auswahl, keine Verbesserung und
nicht dieselbe HND-Stichprobe wie die vorherigen 45/48-Vergleiche.
Erster protokollierter PPO-Stand: **2.283 neue Entscheidungen**, davon HND 1.095,
OSL 615, LHR 258, YUL 315. Die eingefrorene Grundlage blieb auch nach diesem
echten Metal-Update exakt unverändert. Weitere Zähler immer aus `training.jsonl`
lesen; sie steigen während des laufenden Jobs weiter.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --phase-source runs/guided-residual-stage2/latest.pt --open-risk-env \
  --run-dir runs/open-risk-ppo-stage1 --steps 100000 --workers 8 --cpu-duty-cycle .7 \
  --seed 251039 --eval-seed 14650000 --eval-games 400 --eval-every 25 \
  --curriculum-airports LOG_HND_GREEN LOG_HND_GREEN LOG_HND_GREEN LOG_OSL_GREEN LOG_OSL_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --eval-airports LOG_OSL_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --self-imitation-coef .03 --device mps
```

## Abschluss der neuen PPO-Phase und frischer Vergleich

Die Phase endete regulär nach **23,24 Minuten**, Exit 0, **100.214 NEUEN
Entscheidungen** in 45 Updates/1.758 Trainingspartien. Verteilung: HND 39.057,
OSL/Kerosin 29.668, LHR 14.396, YUL 17.093. Alle Zähler summieren sich korrekt;
kumulative Modulhistorie mit übernommener Quelle: 565.851 Entscheidungen.
Die eingefrorene Grundlage ist in `warm.pt`, `best.pt` und `latest.pt` exakt
gleich geblieben. Vollständiger abgeschlossener Bericht
`open-risk-ppo-stage1.json`, einschließlich Trainings- und Einzelvalidierung.

| Neue Phasenzüge, je 100 feste Entwicklungspartien | OSL | HND | LHR | YUL | Schwächste Route |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0, unveränderte Anfangsgewichte | 48 % | 36 % | 68 % | 88 % | 36 % |
| 56.480, gewähltes `best.pt` | 42 % | 42 % | 65 % | 91 % | 42 % |
| 100.214, `latest.pt` | 40 % | 44 % | 69 % | 91 % | 40 % |

**Best bleibt der 56.480-Stand**, weil die vorher festgelegte Auswahl zuerst
die schwächste Route betrachtet. Der etwas höhere Gesamtwert am Ende ersetzt
dieses Kriterium nicht. Es gibt einen Vorteil für die schwächste Route auf
festen Entwicklungsseeds, aber Oslo gibt nach. Keine Freigabe, kein 50-%-Nachweis
und kein Grund für eine ungeprüfte unbegrenzte Fortsetzung.

Der nächste begrenzte Schritt prüft auf **frischen Entwicklungsseeds ab
14.700.000**, 200 Partien je OSL/HND/LHR/YUL, drei gepaarte Varianten:
ursprüngliche 500.347-Gewichte unter alter Maske 9 (`source`), exakt dieselben
Anfangsgewichte unter der Zusatzmaske (`warm`), gewählter 56.480-Stand unter
Zusatzmaske (`candidate`). Damit wird auch gegen die ursprüngliche KI geprüft,
nicht nur gegen den durch die neue Auswahl zunächst geschwächten Anfang.
Das sind 2.400 Partien, kein unabhängiger Freigabetest. Ergebnisse werden pro
Route und Seed mit gepaarten Gewinnen/Verlusten gegen BEIDE Kontrollen
gespeichert. Außerdem wird gemessen, wie oft die Politik tatsächlich eine
zusätzliche Aktion außerhalb der alten Maske 9 auswählt; Abweichungen von der
engeren Referenzmaske 7 allein beantworten diese Frage nicht.

**Aktueller einziger schwerer Lauf:** Werkzeug `ai.open_risk_compare`, Bericht
`ai/experiments/modules-50pct-2026-10-25/open-risk-ppo-stage1-fresh-v1.json`,
Log `/tmp/cockpit-open-risk-ppo-stage1-fresh-v1.log`. Vor Start zuerst Status,
STOP-Datei und Prozesse prüfen; maximal acht Worker zu 70 %, Torch-Threads 1,
`nice -n15`, ein schwerer Lauf. Die unabhängigen Seeds ab 15.000.000 werden
vom Werkzeug ausdrücklich als Entwicklung abgelehnt. Instrumentierungstests
prüfen unveränderte Kontroll-/Kandidatenaktionen und Gewichte. **251 lokale
Tests bestanden** (37,5 s), einschließlich der geschützten fremden Tests.
Der laufend geschriebene frische Bericht wird erst nach Abschluss committed.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.open_risk_compare \
  --source runs/guided-residual-stage2/latest.pt --warm runs/open-risk-ppo-stage1/warm.pt \
  --candidate runs/open-risk-ppo-stage1/best.pt --games 200 --seed 14700000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/open-risk-ppo-stage1-fresh-v1.json
```

## Nächste Arbeit

### Nutzerauftrag: Crew 2 mit unabhängig bestandenen Routen

Der Nutzer hat ausdrücklich gebeten, das bisher beste verfügbare Modell mit
seinen bestandenen Routen als **Crew 2** hochzuladen. Das hebt das Ziel aller
186 Fälle nicht auf und ist kein Auftrag, schwache Modulrouten freizuschalten.
Vorab ausgewählt ist `runs/guided-residual-stage2/latest.pt`, Profil 9 mit
Referenzmaske 7, 500.347 Phasenentscheidungen, Gewichts-SHA
`1d846e7731d60c9cc84c8204e7b87b5dea643b501b5f59bc2185deb76e8609eb`.
Die Auswahl erfolgte vor dem unabhängigen Test. Keine OpenRisk-Zusatzmaske
und keine Veränderung der veröffentlichten Planungsregeln für diesen Export.

Der frische OpenRisk-Vergleich ist vollständig und regulär abgeschlossen:

| Je 200 Entwicklungspartien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Ursprüngliche Quelle | 42,5 % | 38,5 % | 70,5 % | 89,5 % |
| Gleiche Gewichte mit Zusatzmaske | 42 % | 38 % | 71 % | 89 % |
| Trainierter Kandidat | 38,5 % | 39 % | 72 % | 87 % |

Kein konsistenter Vorteil des letzten PPO-Versuchs. Der Kandidat wählt nur
7/14/11/13 echte Zusatzaktionen bei 11.705/10.540/12.164/12.115 Entscheidungen
(OSL/HND/LHR/YUL). Bericht `open-risk-ppo-stage1-fresh-v1.json` bewahrt alle
gepaarten Einzelresultate gegen beide Kontrollen. Die Anfangsgewichte sind
identisch und zählen nicht als zwei unabhängig trainierte Modelle. Die kleine
Erweiterung bietet hier selten andere Aktionen; Auswahl- und Routenkonflikte
sind weiter zu untersuchen, statt ungeprüft dasselbe PPO fortzusetzen.

**Regulär beendet nach 20,81 Minuten, Exit 0:** `ai.route_eval`, Bericht
`ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json`, Log
`/tmp/cockpit-crew2-qualification-v1.log`. Je 500 unabhängige Selbstspielpartien
auf den neun bisherigen Grundspielrouten und OSL/Kerosin, zusätzlich je
100 Partien pro Rolle mit Heuristikpartner: 7.000 Spiele insgesamt. Acht
Worker zu 70 %, Torch-Threads 1, `nice -n15`, über `ai.job_control`.
Nur Routen mit unterer 95-%-Wilson-Grenze mindestens 50 % werden übernommen;
Crew 1 bleibt auswählbar. Alle zehn Strecken sind vollständig geprüft:

| Strecke | Siege / 500 | Selbstspiel | Crew 2 |
| --- | ---: | ---: | --- |
| Montréal, LOG_YUL_GREEN | 433 | 86,6 % | freigegeben |
| Heathrow, LOG_LHR_GREEN | 340 | 68 % | freigegeben |
| Haneda, LOG_HND_GREEN | 179 | 35,8 % | nicht freigegeben |
| Frankfurt, FRA | 404 | 80,8 % | freigegeben |
| Eigene London-Strecke, LHR | 433 | 86,6 % | freigegeben |
| München, MUC | 494 | 98,8 % | freigegeben |
| München Verkehr 1, MUC_T1 | 495 | 99 % | freigegeben |
| München Verkehr 2, MUC_T2 | 495 | 99 % | freigegeben |
| München Verkehr 3, MUC_T3 | 478 | 95,6 % | freigegeben |
| Oslo/Kerosin, LOG_OSL_GREEN | 202 | 40,4 % | nicht freigegeben |

Crew 2 liegt unter `ai/releases/crew2-v1/`, Browserformat 4 mit exakt denselben
Gewichten wie der vorab gewählte Stand. Der Export vereinigt den Katalog mit
den bisherigen Modellen; Crew 1 bleibt die Vorauswahl. Neue Build-Version
für den Service-Worker-Cache. Keine neue Modul-/Kartenstrecke wird dadurch
freigeschaltet. Alle Intervalle und Partnerproben stehen in `evaluation.json`
und der README des Releases; Selbstspiel ist keine menschliche Partnerquote.

**Die unabhängigen Seeds 15.000.000–15.000.499 und die separate Partnerprobe
15.100.000–15.100.099 sind damit erstmals benutzt.** Sie gelten danach als
verbrauchte Qualifikation dieses vorab ausgewählten Standes, nicht als neue
Entwicklungs- oder Modellauswahlseeds. Dies ist noch keine Prüfung aller
Module/Karten; spätere geänderte Kandidaten erhalten gesonderte neue Kohorten.
Ab 15.200.000 ist eine neue abschließende Kohorte reserviert und noch unbenutzt;
auch sie darf nicht zur Modellauswahl oder Lernsteuerung dienen.

`ai.route_eval` dokumentiert jetzt den zur tatsächlichen Schema-Version
gehörenden Planer-Fingerprint, Ressourcen und einen Abschlussmarker.
`ai.publish` lehnt ausdrücklich laufende Berichte ab. **252 lokale Tests
bestanden** (42,8 s, einschließlich der geschützten fremden Tests).
`tests/crew2-ui.cjs` prüfte den echten Browserexport und die Pyodide-Engine:
acht richtige Routen, Crew 1 erhalten, beide menschlichen Rollen, echte
geführte KI-Züge, passende Referenzmasken und verdeckte Partnerwürfel.
Menü und Spiel wurden zusätzlich visuell geprüft. Die tatsächlich exportierten
Gewichte behalten den oben genannten Fingerprint; auf **96 technischen
Spielzuständen** stimmen alle JavaScript-/PyTorch-Entscheidungen überein,
maximaler Logitfehler 0,00000668. Dies sind technische Zustände, keine
zusätzlichen unabhängigen Testpartien.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.route_eval \
  --checkpoint runs/guided-residual-stage2/latest.pt \
  --airports LOG_YUL_GREEN LOG_LHR_GREEN LOG_HND_GREEN FRA LHR MUC MUC_T1 MUC_T2 MUC_T3 LOG_OSL_GREEN \
  --games 500 --partner-games 100 --seed 15000000 --workers 8 --cpu-duty-cycle .7 \
  --minimum-win-rate .5 \
  --output ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json
```

### Passive Diagnose des OpenRisk-Lernens nach Crew 2

`ai.route_policy_probe` isoliert Angebotsänderungen durch die Zusatzmaske und
Lernänderungen durch die Gewichte auf **denselben erlaubten eigenen Zuständen**.
Je Zustand werden die ursprüngliche Politik unter Maske 9, dieselben Gewichte
mit Zusatzmaske und der trainierte Kandidat mit Zusatzmaske verglichen.
Gleichwertige gleichaugige Würfel werden zusätzlich als dieselbe inhaltliche
Aktion gezählt. Nur aggregierte Zähler werden veröffentlicht; weder private
Partnerhände noch zukünftige echte RNG-Werte gehen in diese Berechnungen ein.

Die erste begrenzte Diagnose endete regulär nach **67,46 s**, Exit 0:
**8.369 gesampelte Trainingsentscheidungen in 143 Partien**, kein PPO-Update,
keine neuen trainierten Gewichte und keine Freigabetests. Namensraum
`train:route-policy-probe:251042:...`. Quelle sind die exakt gleichen Crew-2-
Gewichte, Kandidat ist der vorab gewählte 56.480-Stand des OpenRisk-PPO.
Acht Worker zu 70 %, Torch-Threads 1, `nice -n15`, ein verwalteter schwerer
Job; aktive Worker wurden bei 53–70 % beobachtet. Bericht
`ai/experiments/modules-50pct-2026-10-25/route-policy-probe-v1.json`, Log
`/tmp/cockpit-route-policy-probe-v1.log`. Aktuell ist dieser Job beendet.

| Trainingszustände | HND | LHR | OSL/Kerosin | YUL |
| --- | ---: | ---: | ---: | ---: |
| Entscheidungen | 4.056 | 1.410 | 1.718 | 1.185 |
| Zustand bietet eine Zusatzaktion | 168 | 19 | 18 | 18 |
| Zusatzaktion tatsächlich gesampelt | 20 | 3 | 1 | 1 |
| Zusatzaktion bei deterministischer Wahl | 6 | 2 | 0 | 0 |
| Lernbedingt andere deterministische Wahl | 161 | 69 | 87 | 62 |
| Davon beide Aktionen innerhalb alter Maske 9 | 155 | 68 | 87 | 62 |

Insgesamt gibt es nur **223/8.369 = 2,66 %** Gelegenheiten für Zusatzaktionen,
25 tatsächliche Zusatzaktionen (0,30 %) und acht deterministische Zusatzwahlen
(0,096 %). Von 379 lernbedingt geänderten deterministischen Wahlen liegen
**372 = 98,15 %** vollständig innerhalb der alten Maske. 336 Änderungen sind
auch nach Zusammenfassung gleichwertiger Würfel inhaltlich verschieden.
Das Lernen verändert somit überwiegend den alten Strategieraum. Es genügt
nicht, die geringe Nutzung neuer Aktionen nur als fehlende Trainingsdauer zu
deuten: Die zusätzliche Auswahl wird bereits vom Vorschlagsmechanismus selten
angeboten. Besonders Oslo bietet sie nur in 18 von 1.718 Zuständen an.
Dies ist eine Messung auf gesampelten Trainingspfaden, keine neue Spielquote
und kein Kausalitätsbeweis für die beobachteten Entwicklungsverluste.

Die lokale Actor-Gradientenmessung nutzt die tatsächlichen Entscheidungsanteile
des gemischten Curriculums und die PPO-Normalisierung der Vorteile. In keinem
der vier Fälle widerspricht die gemeinsame **vollständige Actor-Richtung** der
routeweisen Richtung. Im gemeinsamen Encoder gibt es einen negativen
YUL-Projektionswert; zugleich sind die Richtungen auf getrennten vollständigen
Episodenhälften **auf derselben Route** sehr instabil: Actor-Kosinus
HND −0,022 / LHR −0,015 / OSL −0,029 / YUL −0,134. Die Encoder-Hälften sind
ebenfalls negativ. Damit sind einzelne negative Winkel zwischen Routen kein
belastbarer Beleg für einen grundsätzlich falschen gemeinsamen Netzaufbau.
Keine getrennten Routennetze oder neue Kritikergewichtung allein daraus ableiten.
Wert-, Entropie- und Nachahmungsgradienten sind in dieser Actor-Diagnose bewusst
nicht enthalten; sie simuliert keinen vollständigen PPO-Update oder Gewinnzuwachs.
Maximaler Fehler des erneut berechneten Rollout-Wahrscheinlichkeitsverhältnisses:
0,00000716. Die Gewichte bleiben unverändert.

**Acht relevante Tests bestanden** (3,6 s): Instrumentierung erhält sämtliche
gesampelten Aktionen, RNG-Folge, Rollout-Tensoren und Endresultate exakt;
Gradientenmessung erhält vorhandene `.grad`-Felder und Gewichte; die synthetische
Gegenrichtung wird erkannt; Referenzmasken und reservierte Prüfpartition bleiben
geschützt. Keine Produktionsprofile, Browsermodelle oder freigegebene Quoten
wurden geändert.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.route_policy_probe \
  --source ai/releases/crew2-v1/best.pt --candidate runs/open-risk-ppo-stage1/best.pt \
  --steps 8192 --seed 251042 --workers 8 --cpu-duty-cycle .7 \
  --output ai/experiments/modules-50pct-2026-10-25/route-policy-probe-v1.json
```

### Historischer Forschungsplan vor dem Ausbau um Praktikant und Leck

Die folgenden Punkte dokumentieren den damaligen Stand vor Crew 3/4 und werden
nicht als aktuelle Einschränkung von Karten-Vorschauen oder als neuer Auftrag
über die oben dokumentierten Phasen gelesen. Aktuell gelten die Abschnitte am
Anfang dieses Arbeitsstands und die ausdrückliche Preview-Anweisung.

1. Zuerst Prozessstatus, STOP-Datei und zuletzt dokumentierten Vergleich prüfen;
   keinen zweiten schweren Job. `joint-finish` erreichte nur 45 statt 48
   Netzsiege auf Haneda; keine weitere große Bestätigungsserie dieses Ansatzes.
   Bei schwachem Lehrer nicht wieder dessen Labels endlos imitieren: aktuelle
   gemeinsame Kontrollzuordnung, Annahmen über nachfolgende Partnerzüge,
   Kaffee-/Neuwurfreserven und kalibrierte Fortsetzungswerte bearbeiten.
   Die 17 Kollisionen und elf Kurvenverluste sind inzwischen lokalisiert:
   26/28 entstehen vor 2.000 Fuß. Der oben dokumentierte frühe Suchvergleich
   brachte noch keinen Vorteil. Auch Round-Open (45) und das unverändert
   unter der Zusatzmaske spielende Netz (45) blieben unter dem ursprünglichen
   Netz (48). Die neue PPO-Phase hat 100.214 neue Züge regulär abgeschlossen;
   der frische Vergleich zeigt keinen konsistenten Vorteil gegen beide
   Kontrollen. Die Diagnose oben zeigt: Die zusätzlichen Vorschläge sind selten, Lernänderungen
   betreffen überwiegend alte Aktionen; die Routen-Gradienten sind schon
   innerhalb derselben Route instabil. Kein Beleg, dass getrennte Netze den
   Engpass lösen. Als nächsten begründeten Schritt den öffentlichen
   Vorschlagsraum und seine Bewertung verbessern: zusätzliche enginelegale
   Kaffee-/Platzierungsfolgen aus den bekannten Engpässen systematisch erfassen
   und gegen den unveränderten Spieler prüfen. Eine eng begrenzte statische
   Heuristik nicht wieder unverändert als starken Lehrer behandeln. Für eine
   stärkere Suche wären unabhängige öffentliche Simulationszustände nötig,
   deren Partnerhand und künftige Würfe ausschließlich aus einem getrennten
   Simulations-RNG entstehen; zuerst exakte Rekonstruktion der sichtbaren
   Engine-Zustände und Privatsphäre enginegeprüft herstellen. Keine
   Qualifikationsseeds dafür verwenden. Nicht unterstellen, alle Fehler
   entstehen kurz vor Landung.
   Ein besserer statischer Belegungswert allein ist kein Gewinnnachweis. Die
   Planung für Oslo braucht außerdem eine begründete Laufzeitbegrenzung.
   Die ausdrückliche Crew-2-Veröffentlichung oben ist abgeschlossen; weitere
   neue Modulqualifikationen erst bei ausreichenden Entwicklungsquoten.
2. Assistenzprofil 7 im allgemeinen Adapter und Forschungsprofil 9 unterstützen
   taktisch nur Grundspiel/Kerosin ohne Karten. Für weitere Module/Karten sind
   Modultaktik und Planung noch zu entwickeln; rohe legale Aktionen funktionieren
   bereits. Vor allgemeinem PPO Helferschleifen/Trunkierung als Flucht vor einer
   Niederlage ausschließen. Nicht aus Regelunterstützung Spielstärke ableiten.
3. Den Strategieraum erweitern, falls die bisherige harte Planung bessere
   Aktionen aus der PPO-Auswahl ausschließt. Mehr-Runden-Suche, probabilistische
   eigene/Partner-Zukunft und Suchlehrer mit anschließender Distillation sind
   mögliche nächste Ansätze. Simulations-RNG strikt vom echten Spiel-RNG trennen;
   niemals echte verdeckte Partnerwürfel verwenden.
4. Danach Curriculum über Wind, Leck, Eis, Praktikant und Echtzeit sowie alle
   sechs Karten und 186 Fälle erweitern. Den gemeinsamen schwarzen Würfel auch
   in ZUKÜNFTIGEN Kapazitätsabschätzungen exakt einmal zuordnen. Windvortraining
   braucht bessere Einzelvorhersagen; gute Gesamtfehler genügen nicht.
5. Frontend-Kartenwahl und automatische KI-Abwicklung offener Zusatzwürfel und
   Tauschbestätigungen ergänzen, bevor entsprechende Modelle veröffentlicht
   werden. Aktuell unterstützen die produktiven Singleplayer-Flows nur Grundspiel;
   die neue Kerosin-Schnittstelle ist vorbereitet, aber ohne freigegebene Gewichte.
6. Fallweise unabhängige Qualifikation und Veröffentlichung für Kartenfälle
   ergänzen. `ai.publish` weist Kartenrouten noch ausdrücklich ab. Das nicht
   einfach umgehen: erst passende Einzelberichte und Browserabläufe herstellen.
   Kerosinfreigaben verlangen bereits echte Modulentscheidungen und eine
   Qualitätsgrenze von mindestens 50 %. Neue schwache Modelle bleiben verborgen.
7. Relevante Tests und Browserparität prüfen, geprüfte Fortschritte nach main
   pushen (ausdrücklich autorisiert). Nicht behaupten, das Ziel sei erreicht,
   solange auch nur ein Fall nicht unabhängig besteht.

## Geschützte fremde Änderungen

Nicht anfassen/stagen: `ai/analysis.ipynb`, `ai/tuning/README.md`,
`ai/tuning/analysis.ipynb`, `ai/tuning/transfer.py`, `tests/test_ai_transfer.py`.
