# Fähigkeiten und Wind: Arbeit an der nächsten Crew

Arbeitsstand vom 28. Oktober 2026. Die bisherigen fünf Crews und ihre Messdaten
bleiben unverändert. Die neue Strategie ist ein zusätzliches Profil 15, keine
Änderung der neuronalen Gewichte. Eine Veröffentlichung setzt eine vollständige
frische Bestätigung gegen Crew 5 voraus.

## Was bisher fehlte

Der bisherige Handplaner bewertet noch nicht ausgegebene Synchronisationswürfel
nicht als Planungsziel. Seine Fortschrittspunkte bevorzugen deshalb manchmal
mehrere neue Klappen/Fahrwerke in einer Runde, obwohl verteilt mehr Bonuswürfel
entstünden. Bei Wind bewertet er vor allem die aktuelle Runde.

Wichtig bei **Kontrolle**: Gleiche Ruder halten die vorhandene Fluglage. Bei einer
bestehenden Neigung dreht sich das Windrad trotzdem weiter und es gibt Kaffee.
Waagerecht bleiben und Kaffee sammeln kann dagegen die nötige Winddrehung
verhindern. Rückenwind ist kein automatischer Verlust: Mit genügenden Bremsen
sind manche Landungen möglich; Gegenwind erleichtert sie aber erheblich.

## Neue Bausteine

- Zukunftswert für noch mögliche frische Klappen/Fahrwerk-Paare. Vier Klappen
  und drei Fahrwerke erlauben dem Co-Piloten einen zusätzlichen ungepaarten
  Fortschritt. Im Notfall darf die reale Engine weiterhin grüne Felder belegen.
- Der Bonus zählt nur als erwarteter Nutzen. Ein noch nicht gewürfelter Würfel
  wird nie als sichere Ressource für Physik oder Pflichtaufgaben eingesetzt.
- Der Verkehrswürfel hat **2, 3, 3, 4, 4, 5**. Die Nutzenabschätzung verwendet
  diese Verteilung und prüft tatsächlich noch nützliche Zielfelder. Erneutes
  Belegen grüner Schalter erzeugt keinen künstlichen Fortschrittswert.
- Ein endlicher Windhorizont berücksichtigt Position auf dem Windrad, Fluglage,
  Reststrecke, verbleibende Runden, Kurven und Aerodynamik. Gegenwind zu früh
  kann die Reichweite zerstören; eine rein möglichst negative Windzahl wäre
  deshalb ebenfalls eine schlechte Regel.
- Gemeinsame Aufgaben werden mit verschiedenen hypothetischen Partnerwürfeln
  und einem einzigen Kaffeebudget gerechnet. Überlappende Möglichkeiten werden
  vereinigt, statt ihre Wahrscheinlichkeiten mehrfach zu addieren.

Der Windhorizont bleibt bewusst eine **optimistische Planungspräferenz**:
Zukünftige konkrete Würfel sind unbekannt; Funkarbeit und künftige Upgrades sind
nicht vollständig mit ihren Ressourcen simuliert. Deshalb darf der Horizont
keine neue Garantie oder harte Legalitätsprüfung vortäuschen.

## Entwicklung und Trennung der Tests

Der erste vollständige Entwicklungstest umfasste 19 Kombinationen mit je drei
Partien pro Strategie: 6/57 Siege statt 4/57 und 90 statt 47 Bonuswürfel. Er
zeigte aber auch 20 statt 6 erneute Schalterbelegungen. Dieser Stand wurde
**nicht veröffentlicht**. Der größere Folgelauf wurde wegen dieser Schwäche
und einer kurzen Temperaturspitze von 75,28 °C abgebrochen; seine unvollständigen
Ergebnisse sind keine Freigabegrundlage.

Die Korrektur verwendet den tatsächlichen erwarteten Bonusnutzen und eine
höhere Bewertung der verbrauchten grünen Schalter. Alle Vergleichsdateien und
Manifeste liegen in `ai/experiments/ability-strategy-2026-10-28/`.
Entwicklung und Bestätigung verwenden getrennte benannte Startseed-Kohorten.
Gleiche Startseeds bedeuten gemeinsame Ausgangszufälle; zusätzliche Bonuswürfe
können die spätere Zufallsfolge der beiden Strategien unterschiedlich weit
verbrauchen.

Vor einer neuen Crew sind mindestens fünf Partien auf jedem der 192 registrierten
Strecken/Kartenfälle vorgesehen. Die vorab festgelegte Hürde verlangt mindestens
fünf zusätzliche Siege insgesamt und in den betroffenen Wind-/Synchronisationsfällen, einen höheren nach Routen gleich gewichteten Mittelwert,
keine erkannten vermeidbaren unmittelbaren Verluste und keine Abbrüche wegen
Schrittlimits. Fälle ohne Wind und ohne Synchronisation verwenden exakt die alte Strategie. Ohne Echtzeitmodul wird der identische Verlauf übernommen; Echtzeitfälle werden mit tatsächlicher Wanduhr separat gespielt, da die Zeit unabhängig vom Algorithmus schwanken kann. Auch Nullquoten werden veröffentlicht; das ist keine Zusage einer
Mindestgewinnrate auf jeder Route.

## Literatur und Grenzen

[Foerster et al., Bayesian Action Decoder](https://arxiv.org/abs/1811.01458)
behandeln Kooperation mit öffentlichen Überzeugungen in Spielen mit verdeckten
Informationen. Hier dient das als Orientierung für die Informationsgrenze;
implementiert ist ein erklärtes Fair-Hand-Modell, kein vollständiger BAD-Agent.

[Ng, Harada und Russell, Reward Shaping](https://ai.stanford.edu/~ang/papers/shaping-icml99.pdf)
zeigen, warum zusätzliche Belohnungen unerwünschte Strategien erzeugen können.
Das Bonus-Sammeln über grüne Schalter ist ein konkreter Anlass, Nutzen und
verbrauchte Ressourcen gemeinsam zu bewerten. Der hiesige begrenzte Planer
beansprucht keine theoretische Garantie der Policy-Invarianz aus diesem Papier.


[Hu et al., Other-Play](https://proceedings.mlr.press/v119/hu20a.html) beschreiben,
wie reines Selbstspiel schwer übertragbare Absprachen lernen kann. [Strouse et
al., Fictitious Co-Play](https://arxiv.org/abs/2110.08176) verwenden verschiedene
Partner und historische Trainingsstände, um die Zusammenarbeit mit unbekannten
Partnern zu verbessern. Das spricht für die Idee wechselnder Crews; wahlloses
gegenseitiges Training garantiert aber keine Verbesserung.

Zusätzlich ist deshalb ein festgelegter Vergleich von Crew 6 als Pilot oder
Co-Pilot mit unveränderter Crew 5 auf den 19 Entwicklungsfällen vorgesehen:
je drei Startfolgen für Crew 5/5 und beide gemischten Besetzungen. Die Startfolgen
sind von der Bestätigung getrennt. Diese Diagnose trainiert keine Gewichte und
ist kein Ersatz für eine Untersuchung mit menschlichen Spielern.
