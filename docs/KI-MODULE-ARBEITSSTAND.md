# Laufendes Ziel: alle Module, mindestens 50 % je Fall

Stand: 25. Oktober 2026. **Nicht abgeschlossen. Keine neue Modul-KI freigegeben.**

## Verbindlicher Auftrag

Der Nutzer wünscht mindestens 50 % auf jeder offiziellen Route und **jeder**
erlaubten Fähigkeitskartenkombination. Die Matrix
`ai/experiments/modules-50pct-2026-10-25/matrix.json` enthält 21 offizielle
Routen und 186 einzelne Route/Karten-Fälle. Pro Fall sind zunächst 500 unabhängige
Partien vorgesehen; eine Freigabe verlangt eine untere Wilson-Grenze von
mindestens 50 %. Es darf nicht über einfache und schwere Fälle gemittelt werden.
Die Originalrouten und Regeln werden nicht erleichtert.

## Ressourcen, Stoppen und automatische Fortsetzung

Die jüngste ausdrückliche Grenze ist **acht Worker zu je 70 %**, ein Torch-Thread,
`nice -n 15`, ein schwerer Lauf gleichzeitig. Metal darf PPO-Minibatches rechnen.
Frühere Erlaubnisse für sechs/50 oder zehn/80 sind durch acht/70 ersetzt.

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

## Politikvortraining und laufender DAgger-Versuch

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

**Aktueller schwerer Lauf:** `runs/planner-dagger-v1/`, Log
`/tmp/cockpit-planner-dagger-v1.log`, Jobstatus `runs/ai-job.json`.
Vor jedem Folgelauf Prozesse und STOP-Datei prüfen. Derselbe eingefrorene Lehrer
beschriftet jetzt auch vom bisherigen Schüler erreichte Zustände. In 50 % der
Züge entscheidet der Schüler mit breiter Maske, sonst der Lehrer. Diese Mischung
nutzt einen separaten RNG, keine zukünftigen Spielwürfe. Je Route entstehen
100 neue Trainings- und 25 neue Validierungspartien mit Seed 251029; alte Daten
werden nur innerhalb ihres bisherigen Splits ergänzt. Der Schüler startet mit
seinen bisherigen Gewichten, kein dritter Residualzweig wird angelegt.
Budget: 200 Politikepochen, weiter ohne PPO und ohne neue Gewinnbehauptung.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.distill_planner \
  --source runs/modules-residual-stage1/best.pt \
  --student runs/planner-distillation-v1/distilled.pt \
  --initial-data runs/planner-distillation-v1/teacher-data.pt \
  --run-dir runs/planner-dagger-v1 --seed 251029 --student-fraction .5 \
  --train-games-per-route 100 --validation-games-per-route 25 --epochs 200 \
  --workers 8 --cpu-duty-cycle .7 --device mps
```

Der unabhängige Kerosinvergleich ab 15.000.000 wurde noch NICHT gestartet.
Auch 12.000.000 und 13.000.000 bleiben unbenutzt. Keine neue Modul-KI ist
freigegeben; das Menü zeigt weiter die bisherigen Modelle.

## Nächste Arbeit

1. Aktuellen DAgger-Job/Logs prüfen; niemals einen zweiten schweren Lauf
   starten. Nach Ende `distilled.pt` unter Profil 9 und den Lehrer unter Profil 7
   auf identischen NEUEN Entwicklungsseeds (z. B. 14.200.000, 100 je Route)
   vergleichen. Hohe Aktionsübereinstimmung allein ist kein Gewinnnachweis.
   Erst wenn die bisherige Spielstärke weitgehend erhalten ist, einen begrenzten
   neuen PPO-Lauf mit `--residual-source .../distilled.pt --assistance-version 9`
   und denselben vier Routen beginnen. Bei schlechtem Transfer zusätzlich auf
   vom Schüler besuchten Zuständen Lehreraktionen sammeln (DAgger), statt
   unvorbereitet sehr schwache breite Masken lange per PPO zu trainieren.
   38 relevante Tests bestanden, einschließlich unveränderter Grundspielprofile,
   Kapazitätsgrenzen, eingefrorenem Lehrer/Wertkopf, DAgger-Zielen und verschachteltem
   Browserexport. Die erweiterten Browser-Quelltexte sind neu gebaut.
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
