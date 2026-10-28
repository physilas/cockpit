# Neuer KI-Anlauf vom 28. Oktober 2026

## Auftrag und Zeitfenster

Der Nutzer erlaubt acht Stunden Entwicklung ab ungefähr 01:25 UTC
(02:25 Berlin), bis 09:25 UTC (10:25 Berlin), einschließlich neuer Crews,
gezielter Partner-Mischung und geprüfter Pushes. Ziel sind nachvollziehbare,
sinnvolle Entscheidungen auf **allen** Routen. Niedrige Gewinnraten auf sehr
schweren Routen sind akzeptabel; ein hoher Gesamtdurchschnitt genügt nicht.

Eine geplante wiederkehrende Hintergrundfortsetzung wurde vom automatischen
Approval-Review abgelehnt. Es wurde keine neue Automation angelegt. Die Arbeit
wird innerhalb der aktiven Sitzung fortgesetzt; diesen Entscheid nicht durch
Cron, andere Chats oder einen indirekten Scheduler umgehen. Die historische
Automation `ki-schonend-weitertrainieren` gehört zu einem anderen Chat und
bleibt pausiert.

Die fremden Änderungen in `ai/analysis.ipynb`, `ai/tuning/README.md`,
`ai/tuning/analysis.ipynb`, `ai/tuning/transfer.py` und
`tests/test_ai_transfer.py` erhalten und niemals mitstagen.

## Forschung und daraus abgeleitete Strategie

* [SPARTA, Lerer et al., AAAI 2020](https://arxiv.org/abs/1912.02318):
  vorhandene Grundstrategie durch simulierte Fortsetzungen verbessern. Die
  theoretische Absicherung setzt passende Überzeugungen über verdeckte
  Informationen und das tatsächliche Partnerverhalten voraus. Unabhängig
  suchende Partner sind kein automatisch korrektes SPARTA-Team.
* [POMCP, Silver und Veness, NeurIPS 2010](https://papers.nips.cc/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html):
  Simulator und Stichproben über verborgene Zustände statt vollständiger
  expliziter Zustandsraumsuche. Für uns besonders brauchbar, weil eine genaue
  Spielengine bereits vorhanden ist.
* [Other-Play, Hu et al., ICML 2020](https://proceedings.mlr.press/v119/hu20a.html):
  reines Selbstspiel kann fragile Konventionen lernen. Für neue Partner muss
  Zusammenarbeit separat geprüft werden. Würfelindex-Permutationen sind hier
  eine echte Symmetrie; Rollen-, Farb- oder Augenzahlvertauschungen im
  Allgemeinen nicht.
* [Fictitious Co-Play, Strouse et al., NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/797134c3e42371bb4979a462eb2f042a-Abstract.html):
  wechselnde Trainingspartner und ältere Zwischenstände können Robustheit
  fördern. Das Papier untersucht Overcooked; eine Übertragung auf dieses
  Spiel ist eine zu prüfende Hypothese, kein bereits nachgewiesener Nutzen.
* [Off-Belief Learning, Hu et al., ICML 2021](https://arxiv.org/abs/2103.04000):
  trennt die Interpretation vergangener Handlungen von der aktuellen
  Verbesserung. Langfristig interessant für nachvollziehbare Kooperation;
  für diesen Anlauf zunächst genaue Informationsgrenzen und einfache
  deklarierte Hypothesen statt eines ungetesteten komplexen Lernverfahrens.

Prioritäten: (1) messbare vermeidbare Fehler ausschließen, (2) echte
Rundenergebnisse und danach Landungen planen, (3) einen brauchbaren Lehrer
in eine schnelle Policy destillieren, (4) kontrolliert mit Partnerpopulation
trainieren und gegen Selbstspiel vergleichen. Neue Suche und Schutz bleiben
zunächst getrennt von bestehenden Browserprofilen und deren Fingerprints.

## Was die bisherigen Daten sagen

Die letzte bestehende kurze Crew-4-Liga war **keine** Verbesserung: der
gleichgewichtete Routenmittelwert im frischen Vergleich sank von etwa 16,17 %
auf 13,56 %. Sie wurde zu Recht nicht übernommen. Einfach denselben kurzen
PPO-Lauf länger zu wiederholen ist deshalb nicht die erste Maßnahme.

`ai/experiments/fresh-strategy-2026-10-28/screen-v1.json` enthält einen
abgeschlossenen technischen Vorvergleich: sieben Routen, je ein Kartenset,
drei Spiele je Baseline/Schutz/Rundensuche, zusammen 63 Partien. Kein
Qualifikationsnachweis. MUC: jeweils 3/3. HND grün: Baseline 0/3,
Rundensuche 1/3. OSL grün: Baseline 1/3, Rundensuche 0/3. Auf KEF gelb
stieg die mittlere erreichte Runde von 3 auf 6, weiterhin ohne Sieg. Daraus
folgt **keine** allgemeine Gewinnverbesserung. Die reine Schutzvariante wählte
im geprüften Lauf keinen von ihr als vermeidbar erkannten unmittelbaren
Verlustzug; frühe Fehlplanung bleibt möglich.

Die erste Suche hatte noch keinen Schutz in ihren Fortsetzungen. Der
Folgeversuch prüft beides zusammen und mehr Kandidaten/Stichproben. Die
Quellen während eines laufenden Versuchs nicht verändern; neue Phase mit
neuem Bericht und Fingerprint beginnen.

## Implementierte Bausteine

* `ai/belief_simulator.py`: rekonstruiert ausschließlich aus öffentlicher
  Sicht und eigener Hand eine neue Engine; kein privater Save, keine echte
  Partnerhand, kein echter zukünftiger RNG. Verbleibende Partnerwürfel sind
  zunächst IID-gleichverteilt. Nach informativen Handlungen ist dies kein
  korrekter Posterior. 186 offizielle Startfälle und Zwischenzustände geprüft.
* `ai/safety_guard.py`: einfache deterministische Ruder-/Leck-/Treibstofffehler
  direkt aus öffentlichen Werten erkennen; bei abschließenden Platzierungen
  die echte Engine für das unmittelbare Ergebnis benutzen. Bei ausschließlich
  verlierenden Alternativen zurückfallen, statt künstlich zu terminieren.
  Keine erfundene zusätzliche Chance, keine Veränderung der Regeln.
* `ai/rollout_search.py`: gleiche hypothetische Ausgangshände/RNG je Kandidat,
  gefilterte Sicht für jeden simulierten Spieler. Unvollständige gepaarte
  Stichproben bei Zeitablauf verwerfen. Ganze Spiele bewerten tatsächliche
  Siege; die Rundensuche verwendet ausdrücklich einen heuristischen Blattwert.
  Keine Wahrscheinlichkeits- oder Konfidenzgarantie für diesen Blattwert.
* `ai/research_compare.py`: fortsetzbarer Vergleich, konkrete Kartensets,
  gepaarte Entwicklungsseeds, reale Engine-Uhr auch bei Echtzeit, vollständige
  Einzelresultate und Prüfung vermeidbarer unmittelbarer Verluste. Nach einem
  Quellwechsel neuen Bericht beginnen, nicht alte Evidenz weiterverwenden.
* `ai/safe_environment.py`: getrennte Trainingsumgebung mit logischer Uhr,
  deterministischem Schutz, öffentlicher Kontrollreservierung und dem alten
  Planer als endlichem Prior. Kein veröffentlichter Browserstand.

Offene Punkte: stärkerer Partnerposterior, Kandidatenabdeckung, ausreichende
Suchzeit auf schweren Strecken, gezielte Lernsignale für frühes Funk-/Ruder-/
Schub-Commitment, Rundenwechsel mit halben Eisbremsen und langfristige
Aufgabenverteilung. Reine Endreward-Suche mit schwacher Fortsetzung produziert
zu viele gleich schlechte Nullwerte; deswegen getrennte Rundensuche prüfen.

## Temperatur und Ausführung

Tatsächlich lesbar sind sowohl HID-Sensoren als auch AppleSMC-CPU-/GPU-
Hotspots einschließlich `TCMz` und der `Tp*`-/`Te*`-Sensoren. Lesender
IOKit-Zugriff funktioniert hier außerhalb der Sandbox, ohne sudo. Die
SMC-Implementierung enthält nur Read-Key-Info, Read-Bytes und Read-Index;
keine Lüfter-, Takt- oder Spannungsänderungen.

```bash
.venv/bin/python -m ai.thermal
.venv/bin/python -m ai.job_control --max-temperature 75 run -- nice -n 10 .venv/bin/python -m ai.research_compare ...
```

Alle schweren Jobs und vollständigen Tests über den Wrapper starten. Er
überwacht die heißeste verfügbare Messung, pausiert die eigene gesamte
Prozessgruppe bei 72 °C und setzt bei höchstens 67 °C fort. Sensorverlust
beendet den Job. `runs/ai-job.json` protokolliert Zustand, letzten Wert und
Maximum. Im Vorvergleich lag das gemessene Maximum bei rund 73,1 °C.
Eine absolute Temperaturgarantie für den gesamten Computer ist wegen anderer
Programme und Messverzögerungen nicht möglich. Zunächst drei Worker,
Torch/BLAS ein Thread, ein schwerer Job gleichzeitig. Der persistente STOP
bleibt bindend.

## Nächste überprüfbare Schritte

1. Neue Schutz-/Suchphase auf allen Routen, zunächst einem deklarierten
   Kartenset pro Route; danach bei brauchbaren Resultaten sämtliche 186
   offiziellen Fälle. Nicht aus sieben kurzen Routenvergleichen freigeben.
2. Vorzeitige Kollisionen und Ausgaben des letzten Korrekturmittels vor
   öffentlicher Kontrollfestlegung diagnostizieren; kleine konkrete Gegenfälle
   festhalten. Endspiel, Pflichtfelder, Ressourcen und Karten einzeln prüfen.
3. Nur einen brauchbaren Lehrer destillieren. Trainingspartien verwenden
   String-Seed-Namensräume; Entwicklungs- und Testzustände nie als Training
   zurückführen. Gemischte Partner und Selbstspiel mit gleicher Rechenzeit
   vergleichen. Beide Rollen getrennt zählen.
4. Frische Entwicklungskohorte und Partner außerhalb des Trainings prüfen.
   Routenmittel gleich gewichten und jede Route/Kartenkombination ausweisen.
   Vermeidbare Fehler, Kaffeereversals, sinnlose Neuwürfe und Endlosaktionen
   zusätzlich zur Siegquote berichten.
5. Nur tatsächlich bessere, browserkompatible Spieler veröffentlichen;
   ehrliche Vorschau-/Qualifikationskennzeichnung erhalten. Eigene getestete
   Fortschritte dürfen nach main gepusht werden, fremde Dateien bleiben außen.

Entwicklungsseeds des Vorvergleichs: 14.900.000 + 100*i, i=0..6, je drei
Spiele; Wiederholung ist keine neue unabhängige Evidenz. Bisher reservierte
Abschlusskohorten ab 15.400.000 nicht zum Debuggen oder zur Auswahl verwenden.
