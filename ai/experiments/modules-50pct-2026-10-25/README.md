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

Die aktuelle automatische Fortsetzung bleibt bei acht Workern zu je 70 %, einem
schweren Job und niedriger Prozesspriorität. „Training und automatische
Fortsetzung stoppen“ beendet den Job und pausiert die Automation.

Details, Befehle, tatsächliche Grenzen und nächste Schritte:
[KI-MODULE-ARBEITSSTAND.md](../../../docs/KI-MODULE-ARBEITSSTAND.md).
