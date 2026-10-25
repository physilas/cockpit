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

## Aktueller schwerer Lauf: geführte PPO-Fortsetzung

`runs/guided-residual-stage2/`, Log `/tmp/cockpit-guided-residual-stage2.log`.
Vor jedem Folgelauf `runs/ai-job.json`, Prozesse und STOP-Datei prüfen.
Wegen der positiven Lernkurve und durchgängig positiven frischen Vergleiche
wird begrenzt weitertrainiert: **500.000 kumulative PPO-Entscheidungen in dieser
Phase**, also ungefähr 300.000 weitere nach den vorhandenen 200.115.
Kein neues Residualnetz, keine neuen Beobachtungen oder geänderten Planer.
Optimizer, RNG, Gewinnzugpuffer, Referenzmasken, Seed 251031 und Routen-Curriculum
werden aus `latest.pt` übernommen. Weitere Module/Karten sind noch nicht Teil
dieses Laufs. Die alten Quellen- und Regelübungsschritte bleiben separat.
Die 800 Partien unmittelbar nach Resume reproduzierten exakt die letzten
Quoten 39,5 / 38,5 / 70,5 / 85 % und Verlustzählungen des ersten Abschnitts.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --resume runs/guided-residual-stage1/latest.pt \
  --run-dir runs/guided-residual-stage2 --steps 500000 \
  --workers 8 --cpu-duty-cycle .7 --device mps \
  --eval-games 800 --eval-every 20 --self-imitation-coef .03
```

Der unabhängige Kerosinvergleich ab 15.000.000 wurde noch NICHT gestartet.
Auch 12.000.000 und 13.000.000 bleiben unbenutzt. Keine neue Modul-KI ist
freigegeben; das Menü zeigt weiter die bisherigen Modelle.

## Nächste Arbeit

1. Aktuelle geführte PPO-Fortsetzung/Logs prüfen; niemals einen zweiten schweren
   Lauf starten. Die erste Messung nach Resume reproduzierte
   39,5 / 38,5 / 70,5 / 85 %. Nach Ende `best.pt` unter Profil 9 mit öffentlicher Referenzmaske
   gegen den bisherigen Stand auf identischen weiteren Entwicklungsseeds
   (z. B. 14.400.000, 200 je Route) vergleichen. `ai.planner_probe` berücksichtigt
   den neuen Politiktyp. Kein Nachahmungsfehler ersetzt die Gewinnprüfung.
   Bei Plateau tatsächliche neu gewählte Platzierungen (`reference_departure_rate`),
   Wert-/Politikinterferenz und stärkere öffentliche Suchlehrer untersuchen,
   nicht bloß dieselben schwachen Lehrerlabels länger trainieren.
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
