# Partnertraining und Unsicherheit

Crew 1 bleibt die eingefrorene Referenz. Assistenzprofil 3 wird unverändert
ausgeführt; das neue Profil 4 ergänzt eine explizite Würfelprior-Verteilung.
Die Partnerhand wird weder gelesen noch an den Planer übergeben.

## Vorab festgelegtes Versuchsprotokoll

- Entwicklung: Seeds ab 10.000.000 für den ersten Planervergleich, anschließend
  ab 11.000.000 für die Auswahl trainierter Kandidaten.
- Freigabe: zwei getrennte Seed-Sätze ab 12.000.000 und 13.000.000. Diese
  Ergebnisse werden nicht zum Abstimmen einzelner Planergewichte verwendet.
- Paarweise Vergleiche verwenden pro Strecke, Partner und Rolle dieselben
  Anfangs-Seeds für Referenz und Kandidat. Intervalle der Gesamtänderung fassen
  wiederholte Rollen und Partner nach Strecke und Seed zu Clustern zusammen.
- Partner: unabhängige einfache Heuristik, eingefrorene Crew 1 und deren
  stochastische Variante. Selbstspiel wird zusätzlich separat berichtet.
- Ein neuer Standardspieler braucht einen positiven Fortschritt in beiden
  Freigabesätzen und eine vollständige Routenqualifikation. Ein bloßer neuer
  Trainingshöchststand genügt nicht. Schwache Experimente bleiben unsichtbar.
- Zusatzmodule beginnen erst nach diesem Grundspiel-Nachweis. Erster Kandidat
  ist Kerosin auf Oslo grün; Fähigkeitskarten und Zusatzwürfel benötigen eine
  eigene Schnittstelle und werden dadurch nicht automatisch freigeschaltet.

## Aufbau

Profil 4 berechnet den Erwartungswert des besten verfügbaren Schubwürfels
unter einer Gleichverteilungsannahme. Für unbekanntes Ruder und Schub wird
zusätzlich die Wahrscheinlichkeit berechnet, dass **zwei verschiedene** Würfel
die beiden Anforderungen erfüllen. Das ist eine optimistische Partnerwahl
mit einer expliziten Prior-Annahme, keine vollständige Simulation menschlicher
Entscheidungen oder bedingte Rekonstruktion bereits beobachteter Partnerzüge.

Eine etwas breitere Auswahl guter erster Aktionen erlaubt PPO mehr eigene
Entscheidungen. Die Bewertungsgewichte bleiben programmiert. Die eingefrorene
Partnerliga läuft getrennt vom trainierten Netz; ihre Aktionen werden nicht
als PPO-Entscheidungen des trainierten Spielers ausgegeben.

`ai.compare` erzeugt die paarweisen Berichte. `ai.route_eval` prüft anschließend
jede angebotene Route auf unabhängigen Seeds. Die vollständigen Ergebnisse
und tatsächlich ausgeführten Trainingsläufe werden beim Release ergänzt.
