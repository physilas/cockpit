# Crew 1: gemeinsame KI ohne Module

Ein gemeinsames PPO-Netz mit öffentlicher Rundenplanung, lokal auf Apple M2 Pro mit Metal trainiert. Der Singleplayer wählt die passende geprüfte KI zur ausgewählten Strecke. Alte, ungeprüfte Trainingsstände werden ausgeblendet.

## Unabhängige Freigabe

500 vollständige Selbstspielpartien pro Route, Seeds ab 8.000.000. Zusätzlich 100 Partien je Rolle mit dem unabhängigen Heuristikpartner ab Seed 8.100.000. Insgesamt 6.300 Testpartien. Die Partnerheuristik versteht Kurven nur eingeschränkt; diese Zahlen sind keine Vorhersage menschlicher Gewinnraten.

| Strecke | Siege / 500 | Selbstspiel | 95-%-Intervall | Heuristikpartner |
|---|---:|---:|---:|---:|
| Montréal-Trudeau (`LOG_YUL_GREEN`) | 416 | 83.2% | 79.7%–86.2% | 54.5% |
| Heathrow (`LOG_LHR_GREEN`) | 321 | 64.2% | 59.9%–68.3% | 32.0% |
| Haneda (`LOG_HND_GREEN`) | 178 | 35.6% | 31.5%–39.9% | 4.0% |
| Frankfurt (eigene Strecke) (`FRA`) | 404 | 80.8% | 77.1%–84.0% | 38.5% |
| London Heathrow (eigene Strecke) (`LHR`) | 411 | 82.2% | 78.6%–85.3% | 46.5% |
| München (eigene Strecke) (`MUC`) | 498 | 99.6% | 98.6%–99.9% | 74.0% |
| München – Training mit 1 Flugzeug (eigene Strecke) (`MUC_T1`) | 496 | 99.2% | 98.0%–99.7% | 71.5% |
| München – Training mit 2 Flugzeugen (eigene Strecke) (`MUC_T2`) | 494 | 98.8% | 97.4%–99.4% | 68.0% |
| München – Training mit 3 Flugzeugen (eigene Strecke) (`MUC_T3`) | 479 | 95.8% | 93.7%–97.2% | 68.0% |

Haneda bleibt anspruchsvoll. Die einfache MUC-Strecke und die schrittweisen Verkehrsstufen sind für den Einstieg geeignet. Die Originaldaten von YUL, LHR und HND wurden nicht erleichtert.

## Inhalt und Reproduktion

- `best.pt`: portable CPU-gespeicherte Gewichte, Optimizer, RNG-Zustände und Trainingskonfiguration zum Fortsetzen.
- `evaluation.json`: vollständige öffentliche Diagnostik und Qualitätsprüfung je Strecke.
- `training.json`: tatsächliche Trainingsstufen, Budgets, Durchsatz und Laufzeiten.
- Das Assistenzprofil 3 ist Teil des Spielers. Es nutzt keine verdeckten Partnerwürfel.
- Module und Fähigkeitskarten einschließlich zusätzlicher schwarzer Spielerwürfel bleiben ausgeschlossen.

Die hohen Quoten gelten für Netz **mit** Rundenplanung. Ohne Planung erreicht das historische Netz diese Leistung nicht. Gewichte und Planung sind durch getrennte Fingerabdrücke mit der Auswertung verknüpft.

Training, Grenzen und reproduzierbare Befehle: [docs/KI-TRAINING.md](../../../docs/KI-TRAINING.md).

Gewählte Gewichte nach 33,683,829 absoluten Entscheidungen; der gesamte lokale letzte Lauf wurde bis 34.000.159 Entscheidungen ausgeführt. Der beste Validierungsstand wurde veröffentlicht.
