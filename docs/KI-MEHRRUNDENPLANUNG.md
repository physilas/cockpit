# Begrenzte Mehr-Runden-Planung vom 25. Oktober 2026

Dieser Versuch ergänzt Crew 1 um Assistenzprofil 10. Die Netzgewichte bleiben
für den Vergleich eingefroren. Die freigegebenen Modelle und ihre Menüeinträge
ändern sich dadurch zunächst nicht. Die automatische Fortsetzung des früheren
Versuchs bleibt pausiert.

## Umfang

Bei 2.000 und 1.000 ft bewertet die aktuelle eigene Rundenplanung auch die
Fortsetzung bis zur Landung: nächste Flugbewegung, nächste Kurvenlage und
anschließende Landerunde. Damit werden bis zu drei aufeinanderfolgende Runden
betrachtet. Frühe Runden und die eigentliche Landerunde verwenden weiterhin
Profil 3. Die Suche berücksichtigt maximal vier verschiedene aktuelle
Vorbereitungsstände und gibt der Fortsetzung einen Bonus von höchstens 40
Punkten. Unmittelbare Verlustkosten der bisherigen Planung bleiben bestehen.

Der Fortsetzungsplan verwendet eine feste Politik, die Pflichtvorbereitungen
spätestens vor Ablauf ihrer Platzierungskapazität einplant. Funkverteilung,
Flugbewegung und Ruderstellung können innerhalb dieses Budgets variieren.
Die Steuerbarkeit künftiger Ruder-/Schubkombinationen wird über die 126
ungeordneten Vier-Würfel-Hände beider Rollen mit korrekten Gewichten berechnet.
Ruder und Schub benötigen verschiedene Würfel; gemeinsamer Kaffee wird in dieser
Kontrollrechnung nur einmal verrechnet.

Die Machbarkeit optionaler Arbeiten wird separat geschätzt. Ihre Abhängigkeit
von den Steuerwürfeln ist vereinfacht; künftiger Verkehr wird über einen
Aufwandsabschlag an öffentlichen Verkehrswürfel-Feldern berücksichtigt. Der
Fortsetzungswert ist daher eine Suchheuristik und keine kalibrierte Gewinnchance.
Die Planung bekommt nur die eigene sichtbare Hand und den öffentlichen Zustand.
Sie liest weder private Partnerwürfel noch künftige Würfe oder den Spiel-RNG.

## Prüfplan

- Ein einzelner gedrosselter Vergleichslauf: höchstens sechs CPU-Worker,
  jeweils 50 % Rechenzeit, `torch`-Threads 1 und `nice -n 15`.
- Erste Probe: 20 neue Seeds ab 11.007.000 je Route, Partner und Rolle.
- Routen: HND grün, LHR grün, YUL grün und MUC_T3. Selbstspiel und beide Rollen
  mit Heuristik, eingefrorener Crew 1 und stochastischer Crew 1.
- Nur bei einem brauchbaren Entwicklungshinweis folgt ein größerer Vergleich
  mit unverändertem Code und neuen Seeds ab 11.008.000. Kleine Proben allein
  führen nicht zur Modellfreigabe.
- Die bislang unbenutzten Freigabekohorten ab 12.000.000 und 13.000.000 bleiben
  für eine spätere echte Freigabe reserviert.

Alle 187 Tests bestanden vor der ersten Probe. Der Fingerabdruck der Planung
umfasst nun auch `ai/horizon.py`. Browser-Builds bündeln dieses neue Modul.

## Zusatzmodule

Die Spielengine enthält die Zusatzregeln, der KI-Adapter weist Module und
Fähigkeitskarten weiterhin ausdrücklich ab. Crew 1 ist für neun modulfreie
Routen freigegeben. Es gibt derzeit kein freigegebenes Modulmodell.

Ein überschaubarer nächster Schritt wäre Oslo grün mit Kerosin und ohne Karten.
Dafür braucht die KI öffentliche Kerosin-Beobachtungen, die Kerosin-Platzierung
als zusätzliche Aktion, angepasste Kapazitäts-/Zukunftsplanung und getrennte
Tests sowie Training. Praktikant, Wind, Eis und Echtzeit benötigen weitere
spezifische Erweiterungen. Die Synchronisationskarte mit schwarzem Zusatzwürfel
braucht eine explizite Behandlung der gemeinsamen Ressource und darf nicht mit
der Annahme von vier Würfeln je Rolle bewertet werden.

## Erste Probe

Auf 560 gepaarten Entwicklungsfällen ergaben sich 12 Verbesserungen und fünf
Verschlechterungen: +1,25 Prozentpunkte, 95-%-Intervall −0,67 bis +3,17. Auf
YUL war die kleine Probe günstig, auf LHR uneinheitlich. Das begründet nur die
Prüfung auf 100 neuen Seeds je Kombination, keine Freigabe. Der größere
Vergleich verwendet denselben Planercode und Seed 11.008.000.

Die neue Planung wurde auch in Pyodide mit identischem Quellfingerabdruck
geprüft. Der konkrete späte Beispielzustand benötigte dort 141 ms und lieferte
dieselbe Aktionsauswahl wie Python. Das ist keine Laufzeitgarantie.

## Möglicher späterer Netzausbau

Zusätzliche abgeleitete Eingangsmerkmale können mit zunächst null gewichteten
Eingangsspalten ergänzt werden; die vorhandenen Merkmale behalten Reihenfolge
und Bedeutung. Eine Verbreiterung kann die bisherige Funktion ebenfalls
übernehmen. Ein zusätzlicher gewöhnlicher Tanh-Layer verändert sie dagegen;
ein zunächst wirkungsloser Residualzweig wäre dafür eine Alternative.
Neue Kapazität müsste anschließend getrennt mit Weitertraining geprüft werden.
Die harte Aktionsvorauswahl begrenzt weiterhin, welche Züge das Netz überhaupt
wählen kann. Dieser Planungsversuch verändert weder Features noch Netzgewichte.
