# Laufendes Ziel: alle Module, mindestens 50 % je Fall

Stand: 25. Oktober 2026. **Crew 2 ist für acht Grundspielstrecken zusätzlich
freigegeben. Das Ziel aller Module/Karten ist nicht abgeschlossen; keine neue
Modulstrecke freigegeben. Crew 1 bleibt verfügbar und vorausgewählt.**

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

### Weitere Forschung nach der Veröffentlichung

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
