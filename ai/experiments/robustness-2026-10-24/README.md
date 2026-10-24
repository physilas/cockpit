# Abschluss der Robustheitsuntersuchung vom 24. Oktober 2026

Crew 1 bleibt das freigegebene Standardmodell. Kein untersuchter Kandidat
zeigte einen belastbaren Gesamtfortschritt. Auf Wunsch des Nutzers wurde die
Untersuchung nach dem letzten laufenden Vergleich beendet. Die automatische
Fortsetzung ist pausiert; es laufen keine weiteren Trainings- oder Vergleichsjobs.
Zusatzmodule wurden mangels Grundspiel-Nachweis nicht begonnen.

Alle Zahlen sind Entwicklungsvergleiche mit Crew 1 auf vier Routen
(HND grün, LHR grün, YUL grün und MUC_T3), im Selbstspiel sowie mit
Heuristikpartner, eingefrorener Crew 1 und einer stochastischen Variante.
Beide Partnerrollen wurden geprüft. Ein gepaarter Fall umfasst zwei tatsächlich
gespielte Partien, jeweils Referenz und Kandidat. Protokoll 2 setzt den
Policy-Zufall pro Partie zurück; das Intervall clustert sämtliche Routen,
Rollen und Partner anhand des gleichen Anfangs-Seeds.

| Variante | Planercode | Gepaarte Fälle | Änderung in Prozentpunkten | 95-%-Intervall |
| --- | --- | ---: | ---: | ---: |
| [Trainierte, getrennte Rollen](role-league.json) | 3d237b9 | 1,400 | +0.00 | -2.93 bis +2.93 |
| [Teilmengen-Neuwurf mit Stichproben](reroll-sampled.json) | eba0b58 | 1,400 | +0.29 | -0.61 bis +1.18 |
| [Exakt gewichteter Teilmengen-Neuwurf](reroll-exact.json) | 11007c2 | 2,800 | +0.25 | -0.37 bis +0.87 |

Die beiden Neuwurfversuche verwenden unveränderte Crew-1-Netzgewichte.
Die Änderung betrifft die Auswahl der sichtbaren eigenen Neuwurfwürfel und
berücksichtigt spätere Kaffeeanpassungen. Profil 9 gewichtet alle möglichen
fairen Würfelergebnisse exakt; die anschließende eigene Rundenplanung bleibt
eine begrenzte Suche. Es werden keine privaten Partnerwürfel oder zukünftigen
Spielwürfe gelesen. Die neuen Rollengewichte aus dem vorherigen Trainingsversuch
waren nach 100.037 zusätzlichen Lernentscheidungen insgesamt neutral.

Die für eine mögliche spätere Freigabe vorgesehenen Kohorten ab 12.000.000 und
13.000.000 wurden nicht benutzt. Es gibt keine neue Modellfreigabe und keine
zusätzlichen experimentellen Modelle im Singleplayer-Menü. Experimentelle
Checkpoints bleiben lokal unter `runs/crew-robust-v2/`; die vollständigen
Ergebniszusammenfassungen sind hier versioniert.

Prüfung: 181 Python-Tests bestanden, JavaScript-Syntax geprüft, beide Rollennetze
im lokalen Browser ausgeführt. Profil 9 wurde nach Neuladen mit passendem
Quellfingerabdruck auch in Pyodide geprüft. Die geprüften Neuwurfbeispiele
benötigten dort 12 ms beziehungsweise 646 ms; dies ist keine allgemeine
Laufzeitgarantie.

Sinnvolle nächste Forschungsrichtungen sind eine Planung über mehrere Runden,
Lernen aus menschlichen Partien und Bewertungen sowie die Anpassung an
beobachtete Partnerentscheidungen. Dafür wurde kein weiterer Lauf gestartet.
