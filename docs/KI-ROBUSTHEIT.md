# Partnertraining und Unsicherheit

Crew 1 bleibt die eingefrorene Referenz. Assistenzprofil 3 wird unverändert
ausgeführt; das neue Profil 4 ergänzt eine explizite Würfelprior-Verteilung.
Die Partnerhand wird weder gelesen noch an den Planer übergeben.

Nach gemeldeter CPU-Überhitzung wurden sämtliche Trainings-Worker beendet.
Zunächst wurden die Läufe auf zwei Worker begrenzt. Anschließend hat der Nutzer
ausdrücklich höchstens sechs CPU-Worker mit jeweils halbem Rechenanteil erlaubt.
Weitere lokale Läufe erfolgen daher einzeln mit höchstens sechs CPU-Workern,
`--cpu-duty-cycle 0.5` und niedriger Prozesspriorität (`nice -n 15`). Der
Rechenanteil wird nach jedem Simulationsschritt durch proportional lange
Pausen begrenzt. Das ist eine Lastbegrenzung, keine Temperaturmessung.

Die automatische Fortsetzung alle 15 Minuten wurde ausdrücklich freigegeben
und als „KI schonend weitertrainieren“ eingerichtet. Sie startet keine
parallelen schweren Läufe und bleibt bei unverändertem Zustand still.

## Vorab festgelegtes Versuchsprotokoll

- Entwicklung: Seeds ab 10.000.000 für den ersten Planervergleich, anschließend
  ab 11.000.000 für die Auswahl trainierter Kandidaten.
- Freigabe: zwei getrennte Seed-Sätze ab 12.000.000 und 13.000.000. Diese
  Ergebnisse werden nicht zum Abstimmen einzelner Planergewichte verwendet.
- Paarweise Vergleiche verwenden pro Strecke, Partner und Rolle dieselben
  Anfangs-Seeds für Referenz und Kandidat. Protokoll 2 setzt auch den
  Policy-Zufall pro Partie nach dem Laden der Modelle zurück. Intervalle der
  Gesamtänderung fassen sämtliche Routen, Rollen und Partner mit demselben
  Anfangs-Seed zu einem Cluster zusammen: Auch verschiedene Routen können
  bei gleichem Seed korrelierte Würfe haben. Diese Korrektur erfolgte vor
  Benutzung der finalen Testkohorten.
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
die beiden Anforderungen erfüllen. Vorhandener Kaffee kann dabei beide Würfel
anpassen; die gemeinsame Ressource wird nur einmal verbraucht. Die
Wahrscheinlichkeit wird über gewichtete Würfel-Multimengen exakt summiert.
Das ist eine optimistische Partnerwahl
mit einer expliziten Prior-Annahme, keine vollständige Simulation menschlicher
Entscheidungen oder bedingte Rekonstruktion bereits beobachteter Partnerzüge.

Eine etwas breitere Auswahl guter erster Aktionen erlaubt PPO mehr eigene
Entscheidungen. Die Bewertungsgewichte bleiben programmiert. Die eingefrorene
Partnerliga läuft getrennt vom trainierten Netz; ihre Aktionen werden nicht
als PPO-Entscheidungen des trainierten Spielers ausgegeben.

Die Suche prüft außerdem die öffentliche Funk- und Platzierungskapazität
eines gesamten hypothetischen Eigenplans. Ein guter erster Zug allein darf
keinen Plan bevorzugen, dessen spätere optionalen Züge benötigte Würfel
verbrauchen würden. Ein Neuwurf wird nicht allein aufgrund angenommener
schlechter Partnerwürfel erzwungen.

## Bisherige Entwicklungsergebnisse, keine Freigabe

Der erste Versuch mit sehr breiter Auswahl und ungekapptem Risiko verschlechterte
die Leistung deutlich. Auch 116.376 neue Trainingsentscheidungen machten ihn
nicht konkurrenzfähig. Er wird nicht angeboten. Der getrennte Kontrolllauf
mit unverändertem Profil 3 wurde nach 109.025 neuen Entscheidungen wegen der
gemeldeten Überhitzung beendet; ein kleiner Vergleich zeigte keinen belastbaren
Gesamtfortschritt.

Die überarbeitete Planung erreichte auf einem kleinen Entwicklungsvergleich
auf HND im Selbstspiel 9 statt 7 Siege aus 20 Partien und mit Heuristikpartner
3 statt 1 Siege aus 40 Partien. Insgesamt über vier Routen war die Änderung
aber nur +0,8 Prozentpunkte mit einem Intervall von −5,2 bis +6,9 Punkten.
Das genügt ausdrücklich noch nicht als Verbesserungsnachweis. Die Ergebnisse
begründen einen weiteren, gedrosselten Trainingsversuch, keine Veröffentlichung.

Der Lauf `league-cool-v4` wurde anschließend mit zwei Workern bei 50 Prozent
Rechenanteil bis 33.850.068 absolute Entscheidungen abgeschlossen, also 166.239
neue Entscheidungen. Beste und letzte Gewichte sind identisch. Die letzte
HND-Selbstspielvalidierung betrug 34 Prozent; die getrennte Partnerauswertung
folgt. Für Folgeversuche kann die Auswahl des besten Modells nun über mehrere
Routen und eingefrorene Partner erfolgen (`--eval-airports` und
`--eval-partner-fraction`), statt allein über HND-Selbstspiel. Nach dieser
Erweiterung bestanden alle 170 Tests.

Ein anschließender Entwicklungsvergleich auf 1.400 gepaarten Fällen (2.800
tatsächlich gespielte Partien) zeigte weiterhin keinen Gesamtfortschritt:
−0,29 Prozentpunkte, 95-%-Intervall −3,67 bis +3,09. Die Rollen unterschieden
sich: Pilotin +3,67 Punkte, Co-Pilot −3,83 Punkte, jeweils mit breiten
Intervallen. Das ist ein Hinweis für getrennte Rollengewichte, kein
Verbesserungsnachweis. Eine zusätzliche isolierte Kapazitätsvariante (Profil 5)
veränderte auf 360 gepaarten Fällen keinen einzigen Spielausgang.

Die nächste Variante trennt die Rollengewichte vollständig: Der neue
Pilotinnen-Stand wird mit dem bisherigen Co-Piloten kombiniert. Assistenzprofil 6
verwendet dafür Profil 4 bei der Pilotin und Profil 3 beim Co-Piloten. Beide
Netze bekommen jeweils dieselbe erlaubte eigene Beobachtung; es werden keine
Partnerwürfel geteilt. Bei einem späteren gemeinsamen Training können die
Gradienten einer Rolle die Gewichte der anderen Rolle nicht mehr verändern.
Checkpoints und Browser unterstützen beide Rollennetze; der bestehende
Beobachtungs-/Aktionsvertrag bleibt erhalten. Vor dem Entwicklungsvergleich
bestanden 174 Tests einschließlich Python/JavaScript-Parität beider Netze.

Der Rollen-Kandidat erreichte auf einem weiteren Entwicklungsvergleich
(1.400 gepaarte Fälle, bisheriges Vergleichsprotokoll) +0,86 Prozentpunkte,
Intervall −1,74 bis +3,46. Das genügt weiterhin nicht. Beide unabhängigen
Rollenköpfe wurden deshalb im getrennten Lauf `role-league` mit gemischter
Routen-/Partnervalidierung bis 33.950.105 Entscheidungen weitertrainiert,
also 100.037 weitere Entscheidungen. Der nach der Trainingsvalidierung beste
Stand stammt von Entscheidung 33.913.446. Der unveränderte Kandidat bleibt
als Kontrollstand erhalten. Stochastische Vergleichspartner werden künftig
mit Protokoll 2 geprüft, damit Netzinitialisierung und Prozessverteilung den
Zufallsstrom nicht verschieben.

Profil 7 ergänzt Profil 6 um eine eigene Neuwurfauswahl. Es bewertet mögliche
Teilmengen der sichtbaren eigenen Würfel, statt eine schlechte Hand vollständig
neu zu würfeln. Einzelne Würfel und Hände mit höchstens zwei Würfeln werden
exakt über alle möglichen Würfe geprüft; größere Teilmengen verwenden zwölf
feste, ausgeglichene Proben. Die hypothetische Planung berücksichtigt auch
spätere Kaffeeanpassungen. Die Proben sind unabhängig vom Zufallsgenerator
des Spiels. Diese Variante ist zunächst ein Entwicklungsexperiment.

Nach dieser Erweiterung bestanden alle 178 Tests. Ein lokaler Browser-Smoke-Test
bestätigte Spielzüge mit beiden Rollennetzen. Die Neuwurfprüfung lief auch in
Pyodide: Der gezielte Zwei-Würfel-Fall dauerte 22 ms, der hier geprüfte schlechte
Vier-Würfel-Fall 765 ms auf diesem Rechner. Das ist keine Laufzeitgarantie für
andere Geräte und kein Nachweis einer verbesserten Gewinnrate.

Der fertige `role-league`-Kandidat war auf dem neuen Entwicklungsvergleich
(Protokoll 2, 1.400 gepaarte Fälle, Seed 11.004.000) exakt gleichauf mit Crew 1:
106 verbesserte und 106 verschlechterte Spielausgänge, Änderung 0,00 Punkte,
Intervall −2,93 bis +2,93. Der Trainingshöchststand wird deshalb nicht freigegeben.
Profil 8 isoliert als nächsten Versuch die Neuwurfänderung mit unveränderten
Crew-1-Gewichten und Profil-3-Platzierungsplanung für beide Rollen.

`ai.compare` erzeugt die paarweisen Berichte. `ai.route_eval` prüft anschließend
jede angebotene Route auf unabhängigen Seeds. Die vollständigen Ergebnisse
und tatsächlich ausgeführten Trainingsläufe werden beim Release ergänzt.
