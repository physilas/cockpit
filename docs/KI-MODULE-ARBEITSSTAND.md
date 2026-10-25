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

## Aktueller schwerer Lauf

`runs/modules-residual-stage1/`, Log `/tmp/cockpit-modules-residual-stage1.log`,
verwalteter Job unter `runs/ai-job.json`. Ziel: 500.000 neue PPO-Entscheidungen
in diesem Abschnitt; nur Entscheidungen auf Modul-/Kartenrouten werden zusätzlich
als Modulentscheidungen gezählt. Übernommene Modulentscheidungen (100.054) und
37.016 Regelübungen werden separat geführt. Die rund 33,7 Millionen alten
Grundspielentscheidungen werden nicht als neues Modultraining ausgegeben.

Initialisierung: `runs/rules-allmodules-v3/rules.pt`, neuer Trainingsseed 251026.
Gewichtetes Curriculum: Oslo grün dreimal, Haneda grün zweimal, Heathrow grün
und Montréal grün je einmal. Validierung: 200 Partien je Route, insgesamt 800
ab 14.000.000. Die Modellauswahl maximiert zuerst die **schwächste** Route,
erst danach die Gesamtquote. Ausgangswerte: OSL 31,5 %, HND 33,0 %, LHR 69,0 %,
YUL 81,5 %. Die ersten Messungen zeigen noch keine Verbesserung.
PPO lernt zusätzlich aus bis zu 4.096 gewonnenen Trainingszügen (Koeffizient
0,03). Validierung und Tests gelangen nie in diesen Puffer.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --residual-source runs/rules-allmodules-v3/rules.pt \
  --run-dir runs/modules-residual-stage1 --steps 500000 \
  --workers 8 --cpu-duty-cycle .7 --device mps --seed 251026 \
  --eval-games 800 --eval-every 20 \
  --eval-airports LOG_OSL_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --curriculum-airports LOG_OSL_GREEN LOG_OSL_GREEN LOG_OSL_GREEN LOG_HND_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --self-imitation-coef .03
```

Bei Fortsetzung `--resume .../latest.pt` und ein NEUES Laufverzeichnis verwenden;
`--steps` ist das kumulative Ziel innerhalb dieses PPO-Abschnitts. Die CLI
übernimmt Seed und Profil bei ausgelassenen Argumenten. Alte Checkpoints mit
anderem Planerfingerabdruck brauchen einen ausdrücklich dokumentierten neuen
Trainingsabschnitt, keine stillschweigende Umdeutung.

Der unabhängige Kerosinvergleich ab 15.000.000 wurde noch NICHT gestartet.
Auch die früher reservierten Kohorten 12.000.000 und 13.000.000 sind unbenutzt.
**Keine neue Modul-KI ist freigegeben; das Menü zeigt weiter die bisherigen Modelle.**

## Nächste Arbeit

1. Aktuellen Job/Logs prüfen; niemals einen zweiten schweren Lauf starten.
   Bei Plateau Ursachen bearbeiten, statt denselben Ansatz endlos fortzusetzen.
2. Die aktuelle Planung (Assistenzprofil 7 im allgemeinen Adapter) unterstützt
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
