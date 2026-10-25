# Alle Module: laufender Versuch vom 25. Oktober 2026

**Ziel noch nicht erreicht. Keine neue Modul-KI veröffentlicht.**

`matrix.json` enthält die vom Nutzer verlangten 186 Kombinationen aus 21
offiziellen Routen und jeder erlaubten Fähigkeitskartenkombination. Mindestens
50 % müssen pro Fall unabhängig bestätigt werden; ein Durchschnitt genügt nicht.

Die drei Berichte `rule-pretraining-v*.json` messen Regelerkennung und
Vorhersagen öffentlicher Aktionsfolgen. Sie messen keine Gewinnquote. Der letzte
Versuch nutzt 37.016 enginegeprüfte synthetische Übungen und 12.375 getrennte
Validierungsübungen. Er erreicht 99,73 % ausgewogene Regelerkennung. Die
Einzelfehler zeigen weiterhin Schwächen beim Wind; die Gesamtzahl verdeckt sie
nicht. Das vorherige Kerosin-PPO erreichte die 50 % trotz 500.292 Entscheidungen
nicht; seine Berichte stehen im benachbarten Kerosinordner.

Regeladapter, größere Residualarchitektur, erhaltene Ausgangsgewichte,
Nachahmung gewonnener Trainingspartien und die erste gemischte PPO-Stufe sind
umgesetzt. Regelvortraining verändert die neue Repräsentation, während die
Politikausgänge anfangs null bleiben. Alle 186 Adapterfälle wurden auch in
Pyodide mit nativem Python verglichen; 204 Tests bestanden.

Der gemischte Residual-PPO endete nach 500.313 neuen Entscheidungen, davon
215.980 auf Kerosin. `residual-stage1.json` enthält die vollständige
Entwicklungskurve. Die letzten Einzelquoten auf je 200 Partien betragen
OSL 34,5 / HND 34 / LHR 65 / YUL 80 %. Das genügt nicht.

`planner-probe-v1.json` untersucht vier Routen auf weiteren Entwicklungsseeds.
Bei 30–51 % der Züge lässt die bisherige Assistenz nur eine inhaltliche Wahl.
`best.pt` und `latest.pt` sind identisch; die Wiederholung zählt nicht als
zusätzliche unabhängige Stichprobe. `planner-probe-wide-v1.json` erweitert nur
die Platzierungsauswahl und zeigt mit den alten Gewichten starke Rückschritte
(4 / 6 / 18 / 50 %). Alle bisherigen Profile bleiben unverändert.

Deshalb folgt ein Politikvortraining durch Nachahmung des bisherigen öffentlichen
Planers unter der breiteren Maske. Der Lehrer sieht keine privaten Partnerwürfel;
er ist kein stärkerer Experte. Ein neuer Residualzweig lernt nur die Politik,
während die alten Gewichte und der Wertkopf erhalten bleiben. Nachahmungsfehler
und Aktionsübereinstimmung ersetzen keine Gewinnprüfung. Vor erneutem PPO muss
der Transfer in gesonderten Entwicklungspartien geprüft werden.

Die erste Nachahmung nutzte 23.439 Trainings- und 5.734 Validierungsbeispiele.
Nach 40 Epochen liegt die Aktionsübereinstimmung bei 75,76 %, die getesteten
Einzelquoten jedoch nur bei 11 / 15 / 24 / 55 %. Die Berichte
`planner-distillation-v1.json` und `planner-distillation-games-v1.json` halten
diese Grenze fest. Der nächste DAgger-Lauf beschriftet gezielt auch vom Schüler
besuchte Zustände, ergänzt die bisherigen Trainingsdaten und verwendet weiterhin
denselben eingefrorenen Lehrer. Auch dieser Lauf ist noch keine Modulfreigabe.

Die aktuelle automatische Fortsetzung bleibt bei acht Workern zu je 70 %, einem
schweren Job und niedriger Prozesspriorität. „Training und automatische
Fortsetzung stoppen“ beendet den Job und pausiert die Automation.

Details, Befehle, tatsächliche Grenzen und nächste Schritte:
[KI-MODULE-ARBEITSSTAND.md](../../../docs/KI-MODULE-ARBEITSSTAND.md).
