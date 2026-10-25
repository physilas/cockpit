# Crew 2

Geführtes PPO-Modell mit öffentlicher Rundenplanung, einem eingefrorenen
Ausgangsspieler und einem trainierten Detailzweig. Crew 1 bleibt unverändert
verfügbar und ist weiterhin die Vorauswahl. Der Name Crew 2 bezeichnet einen
zusätzlichen Spieler; er behauptet keine Überlegenheit auf jeder Strecke.

## Auswahl und unabhängige Prüfung

Vor der abschließenden Prüfung ausgewählt:
`runs/guided-residual-stage2/latest.pt`, 500.347 Entscheidungen in der geführten
PPO-Phase, Gewichts-Fingerprint
`1d846e7731d60c9cc84c8204e7b87b5dea643b501b5f59bc2185deb76e8609eb`.
Der anschließende OpenRisk-Versuch zeigte keinen konsistenten Vorteil auf
frischen Entwicklungspartien und ist nicht Bestandteil dieser Veröffentlichung.

Pro Strecke 500 unabhängige Selbstspielpartien ab Seed 15.000.000 sowie
100 Partien je Rolle mit Heuristikpartner ab 15.100.000. Getestet wurden die
neun bisherigen Grundspielstrecken und Oslo mit Kerosin, insgesamt 7.000 Spiele.
Eine Strecke erscheint für Crew 2 nur dann, wenn die untere Grenze ihres
95-%-Wilson-Intervalls mindestens 50 % erreicht. Diese Prüfung gilt einzeln je
Strecke; ein Mittelwert über die Routen ersetzt sie nicht.

Die Heuristikpartnerprobe beschreibt die Zusammenarbeit mit einem einfachen
festen Partner. Sie ist keine Vorhersage der Gewinnquote mit Menschen. Das
weitergehende Ziel aller offiziellen Routen mit jeder erlaubten Kartenkombination
ist mit dieser Veröffentlichung nicht erreicht.

## Einzelresultate

| Strecke | Siege / 500 | Selbstspiel | 95-%-Intervall | Heuristikpartner | Crew 2 auswählbar |
| --- | ---: | ---: | ---: | ---: | --- |
| Montréal-Trudeau (`LOG_YUL_GREEN`) | 433 | 86,6 % | 83,3 %–89,3 % | 46,5 % | Ja |
| Heathrow (`LOG_LHR_GREEN`) | 340 | 68,0 % | 63,8 %–71,9 % | 33,5 % | Ja |
| Haneda (`LOG_HND_GREEN`) | 179 | 35,8 % | 31,7 %–40,1 % | 4,0 % | Nein |
| Frankfurt (`FRA`) | 404 | 80,8 % | 77,1 %–84,0 % | 44,5 % | Ja |
| London Heathrow (`LHR`) | 433 | 86,6 % | 83,3 %–89,3 % | 50,0 % | Ja |
| München (`MUC`) | 494 | 98,8 % | 97,4 %–99,4 % | 70,5 % | Ja |
| München – Training mit 1 Flugzeug (`MUC_T1`) | 495 | 99,0 % | 97,7 %–99,6 % | 67,5 % | Ja |
| München – Training mit 2 Flugzeugen (`MUC_T2`) | 495 | 99,0 % | 97,7 %–99,6 % | 69,0 % | Ja |
| München – Training mit 3 Flugzeugen (`MUC_T3`) | 478 | 95,6 % | 93,4 %–97,1 % | 66,5 % | Ja |
| Gardermoen (`LOG_OSL_GREEN`) | 202 | 40,4 % | 36,2 %–44,8 % | 5,5 % | Nein |

**Acht Grundspielstrecken sind freigegeben.** Haneda und Oslo/Kerosin bestehen
die Grenze nicht und werden für Crew 2 nicht angeboten. Zusatzmodule und
Fähigkeitskarten sind für diesen Spieler noch nicht freigegeben.

## Dateien und Inferenz

- `best.pt`: vollständiger CPU-Checkpoint mit unveränderten ausgewählten Gewichten.
- `evaluation.json`: abgeschlossener unabhängiger Bericht einschließlich der
  nicht freigegebenen Strecken und der separaten Partnerprobe.
- `training.json`: Auswahl, tatsächliche Trainingszähler und Quellenberichte.
- Der Browserexport verwendet Format 4, Schema 3 mit 489 Merkmalen und
  217 Aktionen, Assistenzprofil 9 sowie dessen öffentliche Referenzmaske 7.
  Die zusätzlichen OpenRisk-Aktionen gehören nicht zu diesem Spieler.
- Planung und Netz sehen die eigene Hand und öffentliche Informationen,
  keine privaten Partnerwürfel und keine zukünftigen echten Zufallswerte.

## Reproduktion

Die Prüfseeds sind nach diesem Lauf verbrauchte Qualifikationsdaten. Sie nicht
zur Auswahl oder Optimierung späterer Kandidaten verwenden. Für spätere
veränderte Modelle eine neue unabhängige Kohorte reservieren.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.route_eval \
  --checkpoint runs/guided-residual-stage2/latest.pt \
  --airports LOG_YUL_GREEN LOG_LHR_GREEN LOG_HND_GREEN FRA LHR MUC MUC_T1 MUC_T2 MUC_T3 LOG_OSL_GREEN \
  --games 500 --partner-games 100 --seed 15000000 --workers 8 --cpu-duty-cycle .7 \
  --minimum-win-rate .5 --output ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json

.venv/bin/python -m ai.publish --checkpoint runs/guided-residual-stage2/latest.pt \
  --evaluation ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json \
  --release-id crew2-v1 --name 'Crew 2' --qualified-routes-only
.venv/bin/python build.py
```

Die gesamte Inferenz bleibt im Browser. Ein neuer Modellkatalog mit aktualisierter
Build-Version sorgt dafür, dass der Service Worker das neue Paket übernimmt.
