# Eigene KI für MUC

Der erste Meilenstein unterstützt das vollständige Grundspiel auf deiner **eigenen
Strecke MUC** aus `backend/landungen/MUC.yaml`: Platzieren, Kaffee, gemeinsamer
Neuwurf, Rundenwechsel, Warteschleife und Landung. Der Code verändert die Strecke
nicht und ersetzt sie nicht durch eine Logbuch-Variante. Die historischen Hinweise
auf Platzhalter in dieser YAML bleiben bestehen; trainiert wird genau die aktuell
spielbare Konfiguration.

Ein gemeinsames PyTorch-Modell spielt beide Rollen. Bei jedem Schritt erhält es
die öffentlichen Informationen und ausschließlich die eigenen freien Würfel.
Auch der Critic hat keinen Zugriff auf die Partnerhand. Rollouts werden mit festen
Gewichten gesammelt, danach folgen PPO-Updates für beide Rollen. Separate Modelle,
abwechselndes Einfrieren und ein Pool älterer Partner sind mögliche spätere
Experimente, im ersten Rahmen aber noch nicht eingebaut.

## Installation

Alle Befehle aus dem Projektordner `cockpit` ausführen. Python 3.11 oder neuer
verwenden. Training und Notebook verwenden dieselbe virtuelle Umgebung:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r ai/requirements-notebook.txt
```

Nur für Training und Terminalspiel genügt `ai/requirements.txt`.
Die Pakete wurden für den Funktionstest bereits in der bestehenden `.venv`
installiert. Ein GPU-System benötigt die zu seiner CUDA-Version passende
PyTorch-Installation. Für dieses kleine, sequentielle Netz ist CPU ein sinnvoller
Start; `--device mps` oder `--device cuda` ist optional.

## Dateien und Einstiegspunkte

| Datei | Zweck |
|---|---|
| `nn_model.py` | Actor-Critic mit konfigurierbarer Breite und Tiefe; Standard zwei Schichten à 128 Neuronen, Tanh |
| `train.py` | Vollständiges PPO-Self-play mit GAE, Logdateien und Checkpoints |
| `analysis.ipynb` | Jupyter-Analyse für Loss, Spielleistung und Trainingsstabilität |
| `environment.py` | Kleine Trainingsumgebung um die bestehende Python-Engine |
| `observation.py` | Sichtbare Informationen, 349 Features und deren feste Reihenfolge |
| `actions.py` | 121 feste Aktions-IDs, 20 Zielfelder und regelbasierte Maskierung |
| `agents.py`, `public_rules.py` | Modellagent, Zufallsagent und einfache Heuristik |
| `evaluate.py` | Separate Partien, Partnervergleich, Konfidenzintervalle und öffentliche Replays |
| `play.py` | Selbst im Terminal mit der KI spielen |
| `checkpoints.py` | Modellgewichte mit geprüftem Beobachtungs- und Aktionsschema speichern/laden |
| `tuning/` | Kontrollierter Architekturvergleich, Optuna-Suche und eigenes Analyse-Notebook |

Die Skripte als Module aufrufen (`python -m ai.train`), damit die Imports stimmen.
Sie benötigen keine Browser-Oberfläche und kein Pyodide. Die Umgebung besitzt ein
an Gymnasium angelehntes `reset`-/`step`-Format, ist aber kein Gymnasium-Untertyp.

Für den Vergleich `2×128` gegen `2×256`, eine kleine Optuna-Suche und Bestätigung
mit mehreren Trainings-Seeds siehe [tuning/README.md](tuning/README.md).
Die optionalen Pakete stehen in `ai/requirements-tuning.txt`; normales Training
benötigt Optuna nicht. `--hidden-size` und `--hidden-layers` steuern neue Netze;
beim Fortsetzen wird die gespeicherte Architektur geladen.

## Training starten

```bash
.venv/bin/python -m ai.train --airport MUC --steps 200000 --run-dir runs/muc
```

200.000 Schritte sind ein Startbudget, keine Zusage einer bestimmten Spielstärke.
Ein Schritt ist eine Entscheidung, einschließlich Kaffee und Neuwurfauswahl.
Eine Lernkurve auf mehreren unabhängigen Läufen entscheidet, ob wir Reward,
Architektur, Umfang oder Trainingspartner ändern müssen.

Standardwerte: 2.048 Entscheidungen pro Rollout (ganze Partien), vier PPO-Epochen,
Minibatches mit 256 Einträgen, Adam mit Lernrate 0,0003, Discount 0,995,
GAE-Lambda 0,95, PPO-Clipping 0,2, Entropiegewicht 0,01. Bei großer KL-Divergenz
endet das Update nach der aktuellen Epoche früher. Rollout-Masken werden gespeichert
und bei jedem Update unverändert wiederverwendet.

Reward bei einem **neuen** Training: Sieg +1, Niederlage −1, kein pauschaler
Rundenbonus, eine Synchronisationsstrafe mit Gewicht 0,05 und einem Feld Toleranz
sowie eine wachsende Aufgabenstrafe mit Gewicht 0,02.
Beide Rollen optimieren denselben gemeinsamen Return, ohne Vorzeichenwechsel zwischen Zügen.
Mit `--sync-weight 0 --task-weight 0 --round-reward 0` lässt sich reiner Endreward vergleichen. Das Netz produziert
Logits; ungültige Aktionen erhalten Wahrscheinlichkeit 0. Beim Training werden
Aktionen gezogen, bei der Standardauswertung wird Argmax verwendet.

Neue Trainingsläufe mischen standardmäßig 3 % Gleichverteilung über **erlaubte**
Aktionen mit 97 % Modellverteilung (`--uniform-mix 0.03`). Bei K erlaubten Aktionen
erhält jede dadurch mindestens die Wahrscheinlichkeit 0,03/K. Das ist eine
Explorationsuntergrenze, kein zusätzlicher Rauschwert auf den Logits. PPO verwendet
beim Sammeln und Aktualisieren dieselbe gemischte Verteilung, einschließlich
Log-Wahrscheinlichkeiten und Entropie. `--uniform-mix 0` schaltet den Zusatz ab.
Die deterministische Validierung bleibt bei der wahrscheinlichsten Modellaktion.

Ein Neuwurf besteht aus Start und je einer Teilmengenauswahl pro Rolle.
Mindestens ein Würfel muss gewählt werden; genau ein Plättchen wird verbraucht.
Der reguläre Zug bleibt bestehen. Menüöffnen, Animationen und Rückgängig sind
keine KI-Aktionen.

Die Maske reserviert pro Rolle genügend freie Würfel für die noch offenen
Pflichtfelder **Ruder und Schub**. Bei zwei freien Würfeln und zwei offenen
Pflichtfeldern sind nur noch Platzierungen auf diesen Feldern erlaubt. Ist eines
schon belegt, wird nur ein Würfel reserviert; der andere darf weiterhin für Funk,
Fahrwerk oder andere Aufgaben verwendet werden. Sind beide Pflichtfelder belegt,
stehen die restlichen Würfel wie gewohnt zur Verfügung. Kaffee und gemeinsame
Neuwürfe bleiben zur Vorbereitung erlaubt, da sie keine Würfel auf Nebenfelder
verbrauchen. Die Prüfung verwendet nur eigene verfügbare Würfel und öffentliche
Feldbelegungen. Würfelwerte, Reihenfolge, Fluglage und Geschwindigkeit bestimmt
weiterhin die KI; auch unmittelbar zum Trudeln führende Ruderzüge bleiben erlaubt.

Die Reservierung gilt automatisch für Training, Auswertung und Terminalspiel.
Die Python-Spielregeln und die Browser-Oberfläche werden dafür nicht verändert.

Jeder Lauf erzeugt:

- `config.json`: Konfiguration und PyTorch-Version.
- `metrics.csv`: Eine Zeile pro Update, getrennte Trainings- und Validierungswerte.
- `episodes.csv`: Ergebnis, Verlustgrund, Rundenzähler, Länge, getrennte Reward-Anteile,
  Restentfernung, Resthöhe, Rückstand und tatsächlicher Beginn der Landerunde pro Partie.
- `latest.pt`: Letztes vollständiges Update einschließlich Optimizer und RNG-Zustand.
- `best.pt`: Bester deterministischer Validierungsstand: zuerst Gewinnrate, dann
  begonnene Landerunden, erreichte Flughäfen, geringere Restentfernung und zuletzt
  Rundenzähler. Vor dem ersten Validierungslauf fehlt diese Datei.

Die Validierung spielt standardmäßig alle fünf Updates 100 Partien mit festen
Seeds. Training verwendet einen separaten Seed-Namensraum. Wiederholte Auswahl
nach diesen Partien kann zu Überanpassung führen: abschließend neue Seeds testen.

Fortsetzen, z. B. bis insgesamt eine Million Entscheidungen:

```bash
.venv/bin/python -m ai.train --resume runs/muc/latest.pt --steps 1000000 --run-dir runs/muc
```

`--steps` ist das **Gesamtziel**, kein Zusatzbudget. Ganze Partien können das Ziel
leicht überschreiten. Strg+C lässt den letzten vollständig gespeicherten Stand
erhalten. Beim Fortsetzen bleiben Strecke, Horizont, Discount, GAE,
Trainingsseed und Netzgröße des Checkpoints erhalten; der Optimizer behält seinen
gespeicherten Zustand samt Lernrate. Für ein älteres `best.pt` ein neues Laufverzeichnis
verwenden, damit ältere und neuere Logzeilen nicht vermischt werden.

Alte Modellgewichte bleiben mit der Pflichtfeld-Reservierung kompatibel, weil sich
Features und Aktions-IDs nicht ändern. Die neue Aktionsmaske wird separat als
`action_mask_version: 2` gespeichert. Beim ersten Fortsetzen eines älteren
Checkpoints ist ein **neues Laufverzeichnis** nötig; auch die Auswahl von `best.pt`
beginnt neu. Ein laufender Trainingsprozess muss dafür neu gestartet werden:

```bash
.venv/bin/python -m ai.train --resume runs/muc4-1/latest.pt --run-dir runs/muc4-2 --steps 4000000 --device cpu
```

Die gespeicherten Reward- und Explorationsparameter werden dabei übernommen.
Auswertungen mit der neuen Maske sind getrennt von früheren Auswertungen zu
interpretieren; JSON-Berichte enthalten dafür ebenfalls die aktive Maskenversion.

## Vom bisherigen Modell mit Synchronisationsstrafe weitertrainieren

Die bestehenden Modellgewichte bleiben kompatibel: Netz, Eingaben, Masken und
Aktions-IDs ändern sich nicht. Der Critic muss sich an die neue Belohnung anpassen;
eine zunächst größere Value-Loss ist deshalb erwartbar. Ein Neustart ist nicht nötig,
eine Verbesserung der Spielstärke aber auch nicht automatisch garantiert.

```bash
.venv/bin/python -m ai.train --resume runs/muc/latest.pt --steps 4000000 --device cpu --run-dir runs/muc-sync --round-reward 0 --sync-weight 0.05 --sync-tolerance 1
```

Der Zusatz wird **einmal nach einer Rundenauswertung** berechnet:

```text
Rückstand = max(0, verbleibende Entfernung - verbleibende Höhe / 1000 - Toleranz)
Synchronisationsreward = -Gewicht * Rückstand
```

Auf MUC passen 6 Entfernungsfelder zu 6000 Fuß. Bei 3000 Fuß, Entfernung 6 und
Toleranz 1 beträgt der Rückstand 2 und die Strafe −0,10. Ein Feld Abweichung ist
erlaubt, frühes Ankommen und Warteschleifen werden nicht bestraft. Kaffee und
Neuwurfauswahl erzeugen selbst keine Synchronisationsstrafe. Die Heuristik verändert
bewusst das Trainingsziel und ist kein potentialbasiertes Shaping. Sieg-/Verlustregeln
und Informationsgrenzen bleiben gleich. Die Abstimmung ist zunächst für MUC gedacht.

`--round-reward`, `--sync-weight`, `--sync-tolerance` und `--task-weight` übernehmen beim Fortsetzen
den gespeicherten Wert, **sofern der Parameter nicht ausdrücklich angegeben wird**.
Alte Checkpoints ohne Synchronisations- oder Aufgabenparameter bedeuten jeweils Gewicht 0. Explizite Werte,
auch `0`, überschreiben den Checkpoint. Änderungen erfordern ein neues Laufverzeichnis,
damit verschiedene Trainingsziele nicht in einer Kurve vermischt werden.

Später die Hilfe ausschalten und die Gewichte weiterverwenden:

```bash
.venv/bin/python -m ai.train --resume runs/muc-sync/latest.pt --steps 6000000 --run-dir runs/muc-no-shaping --round-reward 0 --sync-weight 0 --task-weight 0
```

Ohne Änderungen genügt zum Weitertrainieren von `muc-sync` das übliche `--resume`
mit demselben Laufverzeichnis und einem größeren Gesamtziel. Historische CSV-Dateien
werden bei Bedarf um neue Spalten erweitert; alte fehlende Kennzahlen bleiben leer.
Die Auswahl von `best.pt` wird bei einem neuen Reward oder dem Wechsel vom alten
Bewertungsverfahren neu begonnen.

Auch `--uniform-mix` übernimmt beim Fortsetzen den gespeicherten Wert. Bei alten
Checkpoints ohne diesen Parameter bleibt er 0, bis du ihn ausdrücklich setzt.
Änderungen der Mischung erfordern ebenfalls ein neues Laufverzeichnis und setzen
den Vergleich für `best.pt` zurück. Modellgewichte und Optimizer bleiben erhalten.

## Wachsende Strafe für offene Landungsvorbereitungen

`--task-weight` steuert einen weiteren, getrennt protokollierten Reward. Gezählt werden
die fehlenden drei Fahrwerks- und vier Klappenabschnitte, jedes verbleibende Flugzeug
und eine fehlende Mindestbremswirkung. Im Grundspiel genügt die erste Bremsstufe für
die kleinste mögliche Triebwerkssumme 1+1. Weitere Bremsausbauten bleiben optional.
Kaffee, Neuwurfplättchen und vorübergehende Ruderstellungen sind keine dauerhaften
Vorbereitungsaufgaben. Die Navigation wird weiterhin mit dem Synchronisationsreward erfasst.

Die Dringlichkeit steigt quadratisch über die sieben Runden. Pro ausgewerteter Runde
wird nur der **Zuwachs** abgerechnet, damit die Strafe langsam beginnt und insgesamt
begrenzt bleibt:

```text
U = min(1, ausgewertete Runden / 7)²
Aufgabenreward = -Aufgabengewicht * offene Aufgaben * (U_neu - U_alt)
```

Bei unverändert acht offenen Aufgaben und Gewicht 0,02 kostet die erste Runde
ungefähr −0,0033, die fünfte −0,0294. Abschließen von Aufgaben senkt spätere Kosten.
Auf MUC gibt es anfangs 17 Aufgaben; wenn keine abgeschlossen wird, beträgt das
gesamte undiscountete Aufgabenbudget bei Gewicht 0,02 höchstens 0,34. Neue
Verkehrsflugzeuge auf anderen Strecken können den Aufgabenbestand wieder erhöhen.

Bei einer echten Niederlage wird die verbliebene Dringlichkeit bis 1 abgerechnet.
So spart ein früher Absturz nicht einfach die noch offenen Kosten. Ein künstlicher
Abbruch am Sicherheitslimit löst keine solche Endabrechnung aus. Kaffee und
Neuwurfauswahl erhalten im normalen Verlauf keine zusätzliche Aufgabenstrafe.
Die eigentlichen Sieg-/Verlustregeln und das Netzformat ändern sich nicht.

Von deinem bisherigen Modell mit der neuen Hilfe weitertrainieren, beispielsweise
bis insgesamt acht Millionen Entscheidungen:

```bash
.venv/bin/python -m ai.train --resume runs/muc-sync/latest.pt --steps 8000000 --device cpu --run-dir runs/muc-tasks --task-weight 0.02 --uniform-mix 0.03
```

Die vorhandenen Synchronisationsparameter werden dabei übernommen. Falls dein
bisheriger Lauf anders heißt, den Checkpoint-Pfad entsprechend ändern. Ohne
ausdrückliches `--task-weight` bleibt die neue Hilfe bei älteren Checkpoints aus.
Die 3-%-Exploration wird dabei ebenfalls aktiviert. Später mit `--task-weight 0`
beziehungsweise `--uniform-mix 0` in einem neuen Laufverzeichnis wieder abschalten.
Im Notebook `RUN_NAMES = ["muc-tasks"]` auswählen.

## Loss-Kurven im Jupyter-Notebook

```bash
.venv/bin/python -m jupyterlab ai/analysis.ipynb
```

Im Notebook `RUN_NAMES = ["muc-tasks"]` für das neue Training setzen und
**Run → Run All Cells** wählen. Mehrere Runs werden in der angegebenen Reihenfolge
zu einem Verlauf verbunden, zum Beispiel die voreingestellte Auswahl
`RUN_NAMES = ["muc5", "muc5-1", "muc5-2"]`. Fortlaufende Schrittzähler werden
übernommen; zurückgesetzte Zähler werden für die Plots hinter den vorherigen Run
verschoben. Dezente vertikale Linien markieren die Übergänge in allen
Zeitverlaufsplots, und die Glättung beginnt an jeder Run-Grenze neu. Loss-Gewichte
gelten pro Run; alle ausgewählten Runs müssen dieselbe Strecke verwenden.
Die letzte Validierung wird anhand der gewählten Reihenfolge bestimmt.
Zusätzliche Testberichte werden für alle ausgewählten Runs angezeigt. Neue
Messwerte erscheinen nach erneutem Ausführen der Zellen, auch während des Trainings.
Wenn ein anderer Python-Kernel gewählt wird, muss er dieselben Pakete enthalten;
der Start über `.venv/bin/python -m jupyterlab` verwendet die Projektumgebung.

Enthalten sind:

- Policy- und Value-Loss auf getrennten Skalen sowie der gewichtete PPO-Gesamtloss
  auf einer symmetrisch logarithmischen Skala (`symlog`), mit optionaler Glättung.
- Trainings- und Validierungsgewinnrate mit 95%-Wilson-Intervallen.
- Erreichte Runde, Return, erledigte Landungsvorbereitungen und Verlustgründe.
- Getrennte Kurven für Endergebnis, Rundenbonus, Synchronisations- und Aufgabenstrafe.
- Restentfernung bei Spielende, Flughafenquote, tatsächliche Landerundenquote und Rückstand.
- Noch offene Vorbereitungsschritte im Zeitverlauf und nach Aufgabenart.
- Entropie, ungefähre KL-Divergenz, PPO-Clip-Anteil, Explained Variance,
  Gradientennorm und Durchsatz.
- Vergleich zusätzlicher Testberichte, einschließlich beider Rollen mit fremden Partnern.

`SAVE_FIGURES = True` exportiert PNGs unter `runs/<lauf>/plots/`.
Bei mehreren Runs liegen sie im Unterordner `concat-<run1>__<run2>…/` des letzten
ausgewählten Runs; `PLOT_DIR` zeigt den vollständigen Zielpfad.
Eine fallende Value-Loss kann bedeuten, dass das Netz lediglich die häufigen
Niederlagen besser vorhersagt. Policy-Loss ist durch Advantage-Normalisierung
häufig nahe null und muss nicht monoton sinken. Gewinnrate ist das primäre Ziel.
Der Rundenzähler allein belegt keinen Landefortschritt. Bei einer Notlandung kann
er schon 7 anzeigen, obwohl die eigentliche Landerunde gar nicht begonnen hat.
Gesamtrewards verschiedener Reward-Konfigurationen sind nicht direkt vergleichbar.

## Modell automatisch testen

```bash
.venv/bin/python -m ai.evaluate --checkpoint runs/muc/best.pt --games 500 --json runs/muc/evaluations/self.json
.venv/bin/python -m ai.evaluate --checkpoint runs/muc/best.pt --partner heuristic --ai-role both --games 200 --json runs/muc/evaluations/heuristic-partner.json
.venv/bin/python -m ai.evaluate --baseline heuristic --games 200 --json runs/muc/evaluations/heuristic-baseline.json
.venv/bin/python -m ai.evaluate --baseline random --games 200 --json runs/muc/evaluations/random-baseline.json
```

Mit `--partner heuristic --ai-role both --games 200` entstehen **400 Partien**:
200 als Pilot und 200 als Kopilot, jeweils auf derselben Seed-Liste.
Die Referenzheuristik ist ein einfacher Vergleich, kein starker oder optimaler
Spieler. Gute Self-play-Ergebnisse allein belegen keine gute Zusammenarbeit mit
Menschen; ergänzend selbst spielen und später abwechslungsreichere Partner trainieren.

Standard-Testseeds beginnen bei 2.000.000, Validierungsseeds bei 1.000.000.
`--seed` erlaubt weitere unabhängige Testreihen. `--stochastic` bewertet dieselbe
Sampling-Strategie wie beim Training, einschließlich der gespeicherten Mischung.
`--uniform-mix` kann sie für einen Test überschreiben. Werte mit unterschiedlichen Auswahlschemata
oder Partnern im Notebook getrennt interpretieren.

Eine einzelne Partie als öffentliches Replay und Textausgabe:

```bash
.venv/bin/python -m ai.evaluate --checkpoint runs/muc/best.pt --games 1 --render --replay runs/muc/replay.jsonl
```

Replays enthalten öffentliche Brettstände, Aktionen und sichtbar platzierte Werte;
verdeckte Hände werden nicht gespeichert. Die ausgegebene Runde ist die zuletzt
erreichte Runde, nicht die Zahl erfolgreich abgeschlossener Runden. Ein Sicherheitslimit
von 256 Entscheidungen ergibt eine gesonderte Truncation mit Value-Bootstrap,
keine künstliche Niederlage. Ein Zustand ohne erlaubte Entscheidung gilt als
festgefahrene Niederlage (`no_legal_actions`).

## Selbst mit der KI spielen

```bash
.venv/bin/python -m ai.play --checkpoint runs/muc/best.pt --role pilot
.venv/bin/python -m ai.play --checkpoint runs/muc/best.pt --role kopilot
```

Das Terminal zeigt nur deine Würfel und die öffentlich platzierten Würfel der KI.
Wähle eine der angezeigten Aktionsnummern; `q` beendet die Partie. Kaffee und
Neuwurf sind eigene Entscheidungen, nach denen ggf. dieselbe Rolle weiter am Zug ist.
Zum Ausprobieren ohne Modell: `python -m ai.play --baseline heuristic`.

Die Browser-App bietet unter **Singleplayer** drei Modi: mit einem Modell spielen,
**KI-ndergartenbetreuung** mit Bewertungen von −2 bis +2 und **KI-no** für
Pass-&-Play-Beispielpartien. Die beiden Lernmodi benötigen eine Zustimmung zur
Datennutzung. Bewertungen werden mit der nächsten erfolgreichen menschlichen
Platzierung gespeichert; ohne Slideränderung gilt 0. Am Spielende können sie
zusätzlich direkt gespeichert werden. Aufeinanderfolgende KI-Aktionen behalten
jeweils ihre eigene Bewertung, auswählbar oberhalb des Sliders.

Die Modelle werden als kompakte Float32-Gewichte exportiert und direkt im Browser
ausgeführt. Beobachtungen und Masken stammen aus demselben Python-Code wie beim
Training. Ein ONNX-Laufzeitsystem oder Python-Server ist dafür nicht erforderlich:

```bash
.venv/bin/python -m ai.export_browser
.venv/bin/python build.py
```

Der Export findet alle schema-kompatiblen `best.pt`-/`latest.pt` unter `runs/`;
neue Checkpoints müssen erneut exportiert und mit der Webseite veröffentlicht
werden. `build.py` selbst benötigt weiterhin kein PyTorch. Die App speichert
Aufzeichnungen zunächst in IndexedDB. Eine optionale Cloudflare-Anbindung sendet
die Lernmodi nach Zustimmung automatisch in eine private D1-Datenbank. Einrichtung:
[docs/KI-CLOUD.md](../docs/KI-CLOUD.md). Die gesammelten Daten verändern die Modelle
noch nicht automatisch; ihr Import in Demonstrations-/Feedbacktraining ist ein
separater Trainingsschritt.

## Tests und Erweiterungen

```bash
.venv/bin/python -m unittest tests.test_ai -v
.venv/bin/python -m unittest discover -s tests -v
```

Die Tests prüfen u. a. identische Eingaben/Masken bei veränderten verdeckten
Partnerwürfeln, Masken gegen tatsächliche Engine-Aktionen, Neuwürfe, die Reservierung
von Pflichtwürfeln über vollständige Partien, einen vollständigen Sieg,
getrennte RNGs, Truncation-Bootstrap, endliche Gradienten,
echte PPO-Updates und Checkpoint-Roundtrips. Ohne ML-Pakete werden die Lern-Tests
übersprungen; die übrigen Engine- und Informationstests benötigen kein PyTorch.

Beim Ändern von Features, deren Skalierung oder Aktionsbedeutung die
`SCHEMA_VERSION` in `actions.py` erhöhen. Checkpoints prüfen Reihenfolge und
Struktur; eine reine Bedeutungsänderung ist nur über die Versionsnummer erkennbar.
Netzänderungen in `nn_model.py` können ebenfalls neue Checkpoints erfordern.
Für Änderungen der Maskierung bei unveränderten Features und Aktions-IDs stattdessen
`ACTION_MASK_VERSION` erhöhen; die Gewichte bleiben ladbar, die Laufverzeichnisse
und Validierungsbestwerte werden getrennt.

Die Engine verwendet aktuell den globalen Python-Zufallsgenerator. Der Adapter
isoliert dessen Zustand pro Umgebung. Für mehrere parallele Umgebungen deshalb
Prozesse verwenden, keine Threads. Aktuell wird sequentiell trainiert.

Grundlagen: [PPO-Paper](https://arxiv.org/abs/1707.06347),
[Action Masking](https://arxiv.org/abs/2006.14171),
[Zusammenarbeit mit menschlichen Partnern](https://arxiv.org/abs/1910.05789).
