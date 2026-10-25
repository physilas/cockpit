# Kerosin: erste Entwicklungsversuche

Diese Berichte sind Entwicklungsauswertungen, keine Freigabe. Weder die erste
Heuristik noch längeres PPO mit eingefrorenem Grundspielactor erreichten das
später vom Nutzer gesetzte Ziel von mindestens 50 % je Route/Kartenfall.

- `development-v1.json`: 60.238 Entscheidungen, erster Kerosinplaner.
- `development-v2.json`: früh beendeter Versuch mit anderer Tankbewertung.
- `planner-screen.json`, `capacity-screen.json`: eingefrorene Gewichte,
  Vergleich der Planungsprofile auf denselben 80 Entwicklungspartien.
- `development-v3.json`: 500.292 kumulative Entscheidungen über mehrere
  Fortsetzungen; die größere 200-Partien-Probe lag bestenfalls bei 31,5 %,
  zuletzt bei 29,5 %. Die frühere 80-Partien-Probe ist gesondert ausgewiesen.

Kein Modell aus diesem Ordner wurde ins Menü aufgenommen. Die unabhängigen
Seeds ab 15.000.000 wurden nicht benutzt. Neue Regelübungen und ein größerer
Residualzweig werden im [laufenden Modulversuch](../modules-50pct-2026-10-25/README.md)
weiterverwendet.
