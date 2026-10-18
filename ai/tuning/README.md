# Architekturvergleich und Optuna

Alle Befehle im Projektordner `cockpit` ausführen. Die Suche steuert dasselbe PPO-
Self-play wie `ai.train`; Informationsgrenzen und Aktionsmasken bleiben erhalten.
Jeder Kandidat beginnt mit neuen Gewichten. Lange Studien werden nicht automatisch
gestartet.

```bash
python -m pip install -r ai/requirements-tuning.txt
```

## Zuerst 2×128 gegen 2×256

```bash
python -m ai.tuning.optimize \
  --study-dir runs/optuna/muc-architecture \
  --mode architecture \
  --trials 2 \
  --steps 3000000 \
  --device cpu
```

Das sind **zwei neue Trainingsläufe mit jeweils drei Millionen Entscheidungen**.
Validiert wird alle 100.000 Entscheidungen auf denselben 100 Partien, zusätzlich
am Ende. Ganze Partien können diese Grenzen leicht überschreiten. Beide Rollen
nutzen weiterhin ein gemeinsames Netz. Die frischen Baselines verwenden dieselben
Einstellungen wie `muc5`: Aufgabenstrafe 0,01, Synchronisationsgewicht 0,05,
Toleranz 1, kein Rundenbonus, Uniform-Mischung 0,03, Lernrate 0,0003,
Entropiegewicht 0,01, Trainings-Seed 42. Historisches `muc5` bleibt unangetastet;
seine häufigeren Validierungen sind kein exakt identisches Vergleichsprotokoll.

Den **gleichen Befehl** erneut aufrufen, um die Studie zu öffnen. `--trials` ist
die Gesamtzahl versuchter Trials einschließlich fehlgeschlagener/abgebrochener
Versuche. Bereits fertige Versuche werden nicht wiederholt. Mit `--trials 4`
kommen zusätzlich `3×256` und `2×512` hinzu. Der Architekturvergleich verwendet
kein Pruning und maximal diese vier Konfigurationen.

## Anschließend eine kleine Parametersuche

```bash
python -m ai.tuning.optimize \
  --study-dir runs/optuna/muc-search \
  --mode search \
  --trials 12 \
  --steps 3000000 \
  --pruner median \
  --prune-warmup-steps 1000000 \
  --device cpu
```

Der editierbare Suchraum liegt in `search_space.py`:

| Parameter | Kandidaten / Bereich |
|---|---|
| Architektur | 2×128, 2×256, 3×256, 2×512; jeweils Tanh |
| Lernrate | 0,00003 bis 0,001, logarithmisch |
| Entropiegewicht | 0,001 bis 0,03, logarithmisch |

Die ersten beiden Versuche prüfen die bekannten 2×128-/2×256-Baselines.
Rewards, Exploration, Rollout-Größe und übrige PPO-Parameter werden innerhalb
einer Studie festgehalten. Es läuft jeweils nur ein Trial; Optunas Thread-
Parallelisierung ist wegen der globalen Zufallszustände der Engine ungeeignet.
`--threads` steuert nur die PyTorch-Rechen-Threads.

Pruning ist standardmäßig aus. Der optionale Median-Pruner beginnt erst nach vier
vollständigen Versuchen und frühestens nach einer Million Entscheidungen. Er
vergleicht gemeinsame Entscheidungsmeilensteine. Auch diese konservative Auswahl
kann spät lernende Kandidaten verwerfen; aussichtsreiche Konfigurationen deshalb
anschließend ohne Pruning bestätigen. Ein kleines Budget wie `--steps 128` prüft
lediglich die Technik und sagt nichts über Spielstärke aus.

## Bewertung und Dateien

Die Zielfunktion maximiert **Siege**, mit einem begrenzten Zusatz für Fortschritt:

```text
Navigation = clip(1 - Restentfernung / Anfangsentfernung, 0, 1)
Vorbereitung = clip(1 - offene Aufgaben / anfängliche Aufgaben, 0, 1)
Fortschritt pro Partie = Navigation × Vorbereitung
Score = Anzahl Siege + 0,49 × Mittelwert(Fortschritt)
```

Ein zusätzlicher Sieg schlägt jeden möglichen Fortschrittszusatz. Im Stand gibt
es keinen Zusatz für bloßes Aufgabenabarbeiten. Sicherheitsabbrüche erhalten
keinen Fortschrittszusatz. Der Zusatz ist nur ein Vergleichskriterium bei gleichem
Validierungsumfang, kein Trainingsreward und keine Garantie für eine gewinnbare
Strategie. Loss und geformter Return bestimmen das Ranking nicht.

Bewertet wird die **letzte** Validierung nach dem gleichen Trainingsbudget. So
gewinnt kein Trial allein durch einen glücklichen Zwischenstand. Der zugehörige
Checkpoint ist `latest.pt`. Das zusätzlich gespeicherte `best.pt` folgt dem
bisherigen Auswahlkriterium des normalen Trainers und kann ein anderes Modell sein.

| Datei / Ordner unter `--study-dir` | Inhalt |
|---|---|
| `study.sqlite3` | Optuna-Studie, Trial-Zustände und Zwischenwerte |
| `study-config.json` | Feste Parameter, Suchraum, Paketversionen und Code-Fingerabdruck |
| `trials.csv` | Vergleich inklusive Parameteranzahl, Spielleistung und Laufzeit |
| `best.json` | Beste vollständige Konfiguration und Checkpoint-Pfad |
| `trial-0000/` usw. | Normale Trainingslogs, `latest.pt`, `best.pt`, Terminalprotokoll |
| `trial-0000/progress.jsonl` | Validierung je Meilenstein mit Suchscore |
| `trial-0000/validation.json` | Letzte Validierung mit einzelnen Partien |

Die gesamte Studie liegt unter dem bereits ignorierten Ordner `runs/` und wird
nicht gepusht. SQLite erhält die bisherigen Trials beim Neustart. Die Sequenz
künftiger TPE-Vorschläge muss dabei nicht identisch zu einer unterbrechungsfreien
Suche sein; der Sampler wird mit einem vom Studienfortschritt abgeleiteten Seed neu
erstellt. Geänderte Budgets, Rewards, Seeds, Suchräume oder Trainingsquellen
brauchen einen neuen Studienordner, damit die Vergleiche konsistent bleiben.

`Ctrl+C` lässt fertige Trials bestehen; der laufende Trial wird als `FAIL`
markiert und behält den letzten gespeicherten Checkpoint. Ein erneuter Suchlauf
beginnt neue Trials und setzt diesen angefangenen Trial nicht automatisch fort.
Nach einem harten Prozessabbruch kann ein `RUNNING`-Eintrag stehen bleiben;
diesen erst nach Prüfung, dass der Prozess beendet ist, mit Optunas `Study.tell`
als `FAIL` markieren. Nur einen Suchprozess pro Studienordner starten.

## Notebook und Bestätigung

```bash
python -m jupyterlab ai/tuning/analysis.ipynb
```

`STUDY_DIR` in der ersten Codezelle wählen. Das Notebook zeigt das Ranking,
Gewinnraten, Restentfernung, erledigte Aufgaben samt Maximum, Fortschritt,
Value-Loss, Geschwindigkeit und Parametervergleiche. Es startet keine Trainings.
Für Detailanalysen eines einzelnen Kandidaten bleibt `ai/analysis.ipynb` nutzbar:
beispielsweise `RUN_NAME = "optuna/muc-architecture/trial-0001"`.

Beste Konfiguration mit drei neuen Trainings-Seeds von Grund auf bestätigen:

```bash
python -m ai.tuning.retrain --study-dir runs/optuna/muc-architecture --seeds 101 102 103
```

Baseline zum Vergleich ebenfalls bestätigen:

```bash
python -m ai.tuning.retrain --study-dir runs/optuna/muc-architecture --trial 0 --seeds 101 102 103
```

Diese Läufe verwenden wieder das volle Budget und dieselben Validierungspartien.
Die Ergebnisse werden im Notebook getrennt nach Trainings-Seed angezeigt. Bei
Unterbrechung setzt derselbe `retrain`-Befehl am letzten gespeicherten Update fort.
Erst nach der Konfigurationsauswahl auf unangetasteten Testpartien prüfen:

```bash
python -m ai.evaluate \
  --checkpoint runs/optuna/muc-architecture/confirmation/trial-0001/seed-101/latest.pt \
  --games 1000 --seed 2000000 \
  --json runs/optuna/muc-architecture/test-seed-101.json
```

Den Trial-Pfad an das Ergebnis anpassen und alle bestätigten Trainings-Seeds
testen. Testpartien nicht zur weiteren Parameterauswahl verwenden. Die Netzgröße
lässt sich auch direkt einstellen:

```bash
python -m ai.train --hidden-size 256 --hidden-layers 3 --steps 3000000 --run-dir runs/muc-3x256
```

Alte Checkpoints ohne Schichtanzahl werden weiter als zweischichtig geladen.
`--resume` übernimmt immer die gespeicherte Architektur; eine andere Architektur
braucht einen neuen Lauf ohne `--resume`.

Optuna-Referenzen: [SQLite-Studien](https://optuna.readthedocs.io/en/stable/tutorial/20_recipes/001_rdb.html),
[Median-Pruner](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.pruners.MedianPruner.html).
