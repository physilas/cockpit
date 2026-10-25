# Kerosin: erster Modulversuch vom 25. Oktober 2026

**Noch keine Modul-KI freigegeben.** Der erste PPO-Ansatz erreichte nach
500.292 Entscheidungen weiterhin nur rund 30 % auf der Entwicklungsauswertung.
Das inzwischen gewünschte Ziel beträgt mindestens 50 % je Route/Kartenfall.
Aktueller Stand: [KI-MODULE-ARBEITSSTAND.md](KI-MODULE-ARBEITSSTAND.md).

Der erste Schritt ist die unveränderte offizielle Strecke Oslo grün
(`LOG_OSL_GREEN`): Kerosin, Verkehr und Verkehrswürfel, keine Fähigkeitskarten.
Andere Zusatzmodule und Fähigkeitskarten werden weiterhin ausdrücklich
abgewiesen. Das gilt auch für die Synchronisationskarte mit zusätzlichem
schwarzem Würfel. Deren gemeinsamer Würfel benötigt später eigene Aktionen und
muss im Kapazitätsbudget genau einmal berücksichtigt werden.

## Netzübernahme und tatsächliches Lernen

Schema 2 erhält die bisherigen 349 Eingänge und 121 Aktionsnummern als Präfix.
Es ergänzt drei öffentliche Eingaben (Modul aktiv, Tankinhalt, Tankfeld belegt)
und vier Platzierungsaktionen für das gemeinsame Tankfeld. Die neuen Eingangs-
spalten beginnen bei null; bestehende Schichten und Ausgänge werden kopiert.
Die alten Ausgaben bleiben zu Beginn bis auf Gleitkommarundung erhalten.

Der finale Trainingslauf lässt die bisherigen Actorgewichte unverändert und
lernt die zusätzlichen Eingangsspalten und Aktionsausgänge. Der Kritiker wird
mittrainiert. Auf Grundspiel-Beobachtungen mit drei angehängten Nullen bleibt
der alte Actor dadurch erhalten. PPO erhält kooperative vollständige Partien
und lernt tatsächlich neue Parameter; ein bloßes Umetikettieren alter Gewichte
wird nicht als Training gezählt. Modulentscheidungen werden getrennt von den
rund 33,7 Millionen übernommenen Grundspielentscheidungen ausgewiesen.

## Regeln und Planung

Ein Würfel auf Kerosin verbraucht seinen Augenwert; ein leeres Tankfeld kostet
am Rundenende sechs Einheiten. Es wird nichts aufgefüllt. Das gemeinsame Feld
wird nur einmal verbraucht und kann anschließend von keiner Rolle erneut
belegt werden. Die Engine bleibt für alle Spielregeln maßgeblich.

Die eigene Rundenplanung berücksichtigt den Tankstand und Mindestverbrauch in
zukünftigen Runden. Wenn ein leeres Tankfeld selbst bei künftigem Minimalverbrauch
zum Verlust führen würde, reserviert sie den letzten gemeinsamen freien Würfel.
Dabei wird keine unbekannte Partnerhand vorausgesetzt. Die bisherige Planung
wählt aus vollständigen eigenen Würfelplänen; das Netz bewertet die verbliebenen
Alternativen. Die hohe Leistung ist weiterhin eine Eigenschaft dieses Hybrids,
nicht eines allein spielenden Netzes. Sie bewertet ungesehene Partnerwürfel ausschließlich über
öffentliche Restkapazität und Wahrscheinlichkeiten. Sie bekommt weder die
Partnerhand noch den Spiel-RNG. Tankplanung und Neuwurfauswahl verwenden dieselbe
Information im Training und im Browser.

## Ressourcen und Reproduktion

Ein schwerer Lauf gleichzeitig, höchstens sechs CPU-Worker, je 50 Prozent
Rechenzeit, ein Torch-Thread und `nice -n 15`. Metal berechnet PPO-Minibatches im
Elternprozess. Die automatische Fortsetzung wurde mit ausdrücklicher Zustimmung wieder aktiviert.
Die jüngste Ressourcengrenze ist acht Worker zu je 70 %; frühere Versuche liefen
unter den jeweils damals genehmigten Grenzen.

```sh
nice -n 15 .venv/bin/python -m ai.train_fuel \
  --run-dir runs/kerosene-v3 --steps 100000 --workers 6 \
  --cpu-duty-cycle .5 --device mps --freeze-legacy --assistance-version 7
```

Trainingspartien haben String-Seeds im eigenen Namensraum. Die Entwicklung
verwendet die feste Validierung ab 14.000.000; die unabhängige Freigabe erhält
einen anderen Seedbereich. Die Auswahl von `best.pt` geschieht ausschließlich
auf der Validierung, bevor die unabhängigen Partien gespielt werden.

Im Singleplayer erscheinen Zusatzstrecken nur, wenn eine freigegebene KI sie
explizit unterstützt. Für Aufzeichnungen und Rückmeldungen bleibt vorerst das
Grundspiel verfügbar. Die bisherigen Grundspielmodelle werden weiter angeboten.
