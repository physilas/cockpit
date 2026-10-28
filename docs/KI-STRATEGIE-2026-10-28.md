# Neuer KI-Anlauf vom 28. Oktober 2026

## Auftrag und Zeitfenster

Der Nutzer erlaubt acht Stunden Entwicklung ab ungefähr 01:25 UTC
(02:25 Berlin), bis 09:25 UTC (10:25 Berlin), einschließlich neuer Crews,
gezielter Partner-Mischung und geprüfter Pushes. Ziel sind nachvollziehbare,
sinnvolle Entscheidungen auf **allen** Routen. Niedrige Gewinnraten auf sehr
schweren Routen sind akzeptabel; ein hoher Gesamtdurchschnitt genügt nicht.

Eine geplante wiederkehrende Hintergrundfortsetzung wurde vom automatischen
Approval-Review abgelehnt. Es wurde keine neue Automation angelegt. Die Arbeit
wird innerhalb der aktiven Sitzung fortgesetzt; diesen Entscheid nicht durch
Cron, andere Chats oder einen indirekten Scheduler umgehen. Die historische
Automation `ki-schonend-weitertrainieren` gehört zu einem anderen Chat und
bleibt pausiert.

Die fremden Änderungen in `ai/analysis.ipynb`, `ai/tuning/README.md`,
`ai/tuning/analysis.ipynb`, `ai/tuning/transfer.py` und
`tests/test_ai_transfer.py` erhalten und niemals mitstagen.

## Forschung und daraus abgeleitete Strategie

* [SPARTA, Lerer et al., AAAI 2020](https://arxiv.org/abs/1912.02318):
  vorhandene Grundstrategie durch simulierte Fortsetzungen verbessern. Die
  theoretische Absicherung setzt passende Überzeugungen über verdeckte
  Informationen und das tatsächliche Partnerverhalten voraus. Unabhängig
  suchende Partner sind kein automatisch korrektes SPARTA-Team.
* [POMCP, Silver und Veness, NeurIPS 2010](https://papers.nips.cc/paper/2010/hash/edfbe1afcf9246bb0d40eb4d8027d90f-Abstract.html):
  Simulator und Stichproben über verborgene Zustände statt vollständiger
  expliziter Zustandsraumsuche. Für uns besonders brauchbar, weil eine genaue
  Spielengine bereits vorhanden ist.
* [Other-Play, Hu et al., ICML 2020](https://proceedings.mlr.press/v119/hu20a.html):
  reines Selbstspiel kann fragile Konventionen lernen. Für neue Partner muss
  Zusammenarbeit separat geprüft werden. Würfelindex-Permutationen sind hier
  eine echte Symmetrie; Rollen-, Farb- oder Augenzahlvertauschungen im
  Allgemeinen nicht.
* [Fictitious Co-Play, Strouse et al., NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/797134c3e42371bb4979a462eb2f042a-Abstract.html):
  wechselnde Trainingspartner und ältere Zwischenstände können Robustheit
  fördern. Das Papier untersucht Overcooked; eine Übertragung auf dieses
  Spiel ist eine zu prüfende Hypothese, kein bereits nachgewiesener Nutzen.
* [Off-Belief Learning, Hu et al., ICML 2021](https://arxiv.org/abs/2103.04000):
  trennt die Interpretation vergangener Handlungen von der aktuellen
  Verbesserung. Langfristig interessant für nachvollziehbare Kooperation;
  für diesen Anlauf zunächst genaue Informationsgrenzen und einfache
  deklarierte Hypothesen statt eines ungetesteten komplexen Lernverfahrens.

Prioritäten: (1) messbare vermeidbare Fehler ausschließen, (2) echte
Rundenergebnisse und danach Landungen planen, (3) einen brauchbaren Lehrer
in eine schnelle Policy destillieren, (4) kontrolliert mit Partnerpopulation
trainieren und gegen Selbstspiel vergleichen. Neue Suche und Schutz bleiben
zunächst getrennt von bestehenden Browserprofilen und deren Fingerprints.

## Was die bisherigen Daten sagen

Die letzte bestehende kurze Crew-4-Liga war **keine** Verbesserung: der
gleichgewichtete Routenmittelwert im frischen Vergleich sank von etwa 16,17 %
auf 13,56 %. Sie wurde zu Recht nicht übernommen. Einfach denselben kurzen
PPO-Lauf länger zu wiederholen ist deshalb nicht die erste Maßnahme.

`ai/experiments/fresh-strategy-2026-10-28/screen-v1.json` enthält einen
abgeschlossenen technischen Vorvergleich: sieben Routen, je ein Kartenset,
drei Spiele je Baseline/Schutz/Rundensuche, zusammen 63 Partien. Kein
Qualifikationsnachweis. MUC: jeweils 3/3. HND grün: Baseline 0/3,
Rundensuche 1/3. OSL grün: Baseline 1/3, Rundensuche 0/3. Auf KEF gelb
stieg die mittlere erreichte Runde von 3 auf 6, weiterhin ohne Sieg. Daraus
folgt **keine** allgemeine Gewinnverbesserung. Die reine Schutzvariante wählte
im geprüften Lauf keinen von ihr als vermeidbar erkannten unmittelbaren
Verlustzug; frühe Fehlplanung bleibt möglich.

Die erste Suche hatte noch keinen Schutz in ihren Fortsetzungen. Der
Folgeversuch prüft beides zusammen und mehr Kandidaten/Stichproben. Die
Quellen während eines laufenden Versuchs nicht verändern; neue Phase mit
neuem Bericht und Fingerprint beginnen.

## Implementierte Bausteine

* `ai/belief_simulator.py`: rekonstruiert ausschließlich aus öffentlicher
  Sicht und eigener Hand eine neue Engine; kein privater Save, keine echte
  Partnerhand, kein echter zukünftiger RNG. Verbleibende Partnerwürfel sind
  zunächst IID-gleichverteilt. Nach informativen Handlungen ist dies kein
  korrekter Posterior. 186 offizielle Startfälle und Zwischenzustände geprüft.
* `ai/safety_guard.py`: einfache deterministische Ruder-/Leck-/Treibstofffehler
  direkt aus öffentlichen Werten erkennen; bei abschließenden Platzierungen
  die echte Engine für das unmittelbare Ergebnis benutzen. Bei ausschließlich
  verlierenden Alternativen zurückfallen, statt künstlich zu terminieren.
  Keine erfundene zusätzliche Chance, keine Veränderung der Regeln.
* `ai/rollout_search.py`: gleiche hypothetische Ausgangshände/RNG je Kandidat,
  gefilterte Sicht für jeden simulierten Spieler. Unvollständige gepaarte
  Stichproben bei Zeitablauf verwerfen. Ganze Spiele bewerten tatsächliche
  Siege; die Rundensuche verwendet ausdrücklich einen heuristischen Blattwert.
  Keine Wahrscheinlichkeits- oder Konfidenzgarantie für diesen Blattwert.
* `ai/research_compare.py`: fortsetzbarer Vergleich, konkrete Kartensets,
  gepaarte Entwicklungsseeds, reale Engine-Uhr auch bei Echtzeit, vollständige
  Einzelresultate und Prüfung vermeidbarer unmittelbarer Verluste. Nach einem
  Quellwechsel neuen Bericht beginnen, nicht alte Evidenz weiterverwenden.
* `ai/safe_environment.py`: getrennte Trainingsumgebung mit logischer Uhr,
  deterministischem Schutz, öffentlicher Kontrollreservierung und dem alten
  Planer als endlichem Prior. Kein veröffentlichter Browserstand.

Offene Punkte: stärkerer Partnerposterior, Kandidatenabdeckung, ausreichende
Suchzeit auf schweren Strecken, gezielte Lernsignale für frühes Funk-/Ruder-/
Schub-Commitment, Rundenwechsel mit halben Eisbremsen und langfristige
Aufgabenverteilung. Reine Endreward-Suche mit schwacher Fortsetzung produziert
zu viele gleich schlechte Nullwerte; deswegen getrennte Rundensuche prüfen.

## Temperatur und Ausführung

Tatsächlich lesbar sind sowohl HID-Sensoren als auch AppleSMC-CPU-/GPU-
Hotspots einschließlich `TCMz` und der `Tp*`-/`Te*`-Sensoren. Lesender
IOKit-Zugriff funktioniert hier außerhalb der Sandbox, ohne sudo. Die
SMC-Implementierung enthält nur Read-Key-Info, Read-Bytes und Read-Index;
keine Lüfter-, Takt- oder Spannungsänderungen.

```bash
.venv/bin/python -m ai.thermal
.venv/bin/python -m ai.job_control --max-temperature 75 run -- nice -n 10 .venv/bin/python -m ai.research_compare ...
```

Alle schweren Jobs und vollständigen Tests über den Wrapper starten. Er
überwacht die heißeste verfügbare Messung, pausiert die eigene gesamte
Prozessgruppe bei 72 °C und setzt bei höchstens 67 °C fort. Sensorverlust
beendet den Job. `runs/ai-job.json` protokolliert Zustand, letzten Wert und
Maximum. Im Vorvergleich lag das gemessene Maximum bei rund 73,1 °C.
Eine absolute Temperaturgarantie für den gesamten Computer ist wegen anderer
Programme und Messverzögerungen nicht möglich. Zunächst drei Worker,
Torch/BLAS ein Thread, ein schwerer Job gleichzeitig. Der persistente STOP
bleibt bindend.

## Nächste überprüfbare Schritte

1. Neue Schutz-/Suchphase auf allen Routen, zunächst einem deklarierten
   Kartenset pro Route; danach bei brauchbaren Resultaten sämtliche 186
   offiziellen Fälle. Nicht aus sieben kurzen Routenvergleichen freigeben.
2. Vorzeitige Kollisionen und Ausgaben des letzten Korrekturmittels vor
   öffentlicher Kontrollfestlegung diagnostizieren; kleine konkrete Gegenfälle
   festhalten. Endspiel, Pflichtfelder, Ressourcen und Karten einzeln prüfen.
3. Nur einen brauchbaren Lehrer destillieren. Trainingspartien verwenden
   String-Seed-Namensräume; Entwicklungs- und Testzustände nie als Training
   zurückführen. Gemischte Partner und Selbstspiel mit gleicher Rechenzeit
   vergleichen. Beide Rollen getrennt zählen.
4. Frische Entwicklungskohorte und Partner außerhalb des Trainings prüfen.
   Routenmittel gleich gewichten und jede Route/Kartenkombination ausweisen.
   Vermeidbare Fehler, Kaffeereversals, sinnlose Neuwürfe und Endlosaktionen
   zusätzlich zur Siegquote berichten.
5. Nur tatsächlich bessere, browserkompatible Spieler veröffentlichen;
   ehrliche Vorschau-/Qualifikationskennzeichnung erhalten. Eigene getestete
   Fortschritte dürfen nach main gepusht werden, fremde Dateien bleiben außen.

Entwicklungsseeds des Vorvergleichs: 14.900.000 + 100*i, i=0..6, je drei
Spiele; Wiederholung ist keine neue unabhängige Evidenz. Bisher reservierte
Abschlusskohorten ab 15.400.000 nicht zum Debuggen oder zur Auswahl verwenden.

## Fortschritt nach der ersten Stunde

Commit `12bede5` ist lokal vorhanden. Der Push nach `origin/main` wurde vom
automatischen Approval-Review zweimal abgelehnt, auch nach Bestätigung des
öffentlichen, dem Nutzer gehörenden Repositories `physilas/cockpit` über den
GitHub-Connector. Eine präzise asynchrone Rückfrage an den Nutzer ist offen:
Veröffentlichung der geprüften KI-/Test-/Entwicklungsberichte dieses Laufs in
diesem öffentlichen Repository auf main. Ohne neue menschliche Antwort keinen
weiteren Push versuchen und keinen anderen Übertragungsweg verwenden. Lokale
Arbeit bleibt erlaubt.

Abgeschlossene neue Vergleiche:

* `shield-routes-v3.json`: alle 27 spielbaren Routen, je ein explizites
  Kartenset, zehn Spiele je Baseline/Schutz, 540 Partien. Baseline 89/270,
  Schutz 90/270. Erkannte sofort verlierende Entscheidungen bei vorhandener
  Alternative 133 → 0. Das ist eine unmittelbare Aktionskennzahl; sie behauptet
  nicht, dass sämtliche später verlorenen Partien noch gewinnbar waren.
* `search-hard-v4.json`: sieben schwierige Modul-/Kartenfälle, je vier
  Spiele pro Schutz/Rundensuche/Information-State-UCT, 84 Partien. Jeweils
  1/28 Siege. Mittlere Runde 3,50 / 5,46 / 4,50. Kein Gewinnnachweis durch
  tiefe Suche. Nicht unbesehen als erfolgreichen Lehrer destillieren.
* `routes-v2.json` bleibt ausdrücklich unvollständig. Der Lauf deckte eine
  leere alte Referenz nach Verengung durch den neuen Schutz auf. Rückfall auf
  verbliebene legale Aktionen korrigiert und getestet. Executor beendet bei
  Fehler jetzt eigene Worker, statt auf sämtliche lange Suchaufträge zu warten.

`ai.train_robust` wurde technisch in beiden Modi geprüft: Selbstspiel 813
Lernentscheidungen; Population 3.232 Entscheidungen mit tatsächlich allen
Crews 1/2/3 plus aktuellem Selbstspiel in beiden Rollen. Partneraktionen sind
nicht im Lernpuffer, Zählersummen stimmen. Neue Optimizer, Quellen unverändert.
Die 20-Minuten-Selbstspielphase unter
`runs/robust-2026-10-28/self-20min` hat 89.456 Entscheidungen/4.170 Partien
erreicht und befindet sich beim Schreiben dieses Standes in der abschließenden
Validierung. Die bisher beste kleine Validierung lag nach 24.128 Schritten bei
50/135 statt initial 49/135; später sank sie wieder. Kein belastbarer
Lernfortschritt. Geplanter fairer Gegenversuch: gleiches 1.200-Sekunden-Budget,
Quelle und Validierung, `--partner-mode population`, eigener Trainingsseed.
Eine einzelne solche Gegenprobe beweist keine allgemeine Überlegenheit.

Neuer, noch nicht auf Spielstärke geprüfter Ansatz: `ai.contract_planner`
plant die gesamte eigene Hand, einschließlich Kaffee/Anpassung und genau
einmaliger Nutzung ausgegebener Zusatzwürfel. Beide Rollen bekommen denselben
aus öffentlichen Zählwerten abgeleiteten Bewegungsvertrag. Ein übervoller
Verkehrsstau verlangt Stillstand und Funk; ansonsten Höhe/Entfernung folgen
und stark Verkehr erzeugende Felder bei ausreichender Funkkapazität schneller
verlassen. Gegensätzliche Kurven, irreversible Langsamkeit nach zu frühem
Klappenausbau und zurückgelassene nicht mehr erreichbare Flugzeuge werden
berücksichtigt. Partnerkontrollen, notwendiger Funk und Treibstoff konkurrieren
im statischen IID-Handmodell um verschiedene Würfel und einen Kaffeepool.
Dies ist eine eigene heuristische Übertragung der Literatur, keine exakte
dezentrale Lösung oder kalibrierte Gewinnwahrscheinlichkeit. Erste Rechenproben
lagen bei ungefähr 10–30 ms pro Handplanung. Neue Projektionstests vergleichen
Module, Kosten und Belegungen mit der echten Engine. Praktikant darf keinen
Kaffee erzeugen; halbe Eispaare sind kein dauerhafter Ausbau.

`contract_advice.py` und `contract_environment.py` trennen den öffentlichen
Berater von NN-Gewichten und bieten eine gemeinsame Grundlage für später
identische native-/Browser-Entscheidungen. Noch keine Browserregistrierung,
kein Modell oder altes Profil ersetzt. `research_compare` kennt nun auch
`--modes contract` und protokolliert neu zurückgelassene Flugzeuge sowie
irreversible Entfernungsdefizite; alte Berichte haben diese Spalten nicht.

`search_demonstrations.py` ist für **Trainingsseeds** vorbereitet: öffentliche
Kontrakt- oder UCT-Lehrerlabels mit exakten Masken, optional auf Zuständen des
Schülers oder einer Mischung beider. Noch keine erfolgreiche Lehrer-/Schüler-
Verbesserung behaupten. Relevante weitere Literatur:
[DAgger, Ross et al. 2011](https://proceedings.mlr.press/v15/ross11a.html)
motiviert Labels auf den vom Schüler tatsächlich erreichten Zuständen;
[Expert Iteration, Anthony et al. 2017](https://arxiv.org/abs/1705.08439)
motiviert die Trennung von Planung und Verallgemeinerung. Deren veröffentlichte
Ergebnisse belegen keine Übertragbarkeit auf dieses konkrete verdeckte Spiel.

Nächste Priorität nach Ende des aktuellen Jobs: den Kontraktplaner schnell
auf allen 27 Routen gegen den geschützten Ausgangsspieler messen. Nur bei
brauchbarem Ergebnis die komplette 192-Fall-Matrix und danach frische Seeds
verwenden; dann gegebenenfalls Lehrer-/Schülerphase und neues Browserprofil.
Die Temperaturregelung hat bisher höchstens rund 73,7 °C gemeldet.

## Stand nach zwei Stunden

Beide gleichen 1.200-Sekunden-Trainingsphasen sind vollständig beendet:

| Phase | Lernentscheidungen | Partien | Initial / beste / letzte Validierung |
|---|---:|---:|---:|
| Selbstspiel | 89.456 | 4.170 | 49 / 50 / 46 von 135 |
| Population 1/2/3/Selbstspiel | 92.286 | 4.208 | 49 / 51 / 48 von 135 |

In der Population wurden beide Rollen mit jedem Partner tatsächlich trainiert.
Die Optimizer waren neu, die geerbte eingefrorene Quelle blieb unverändert.
Ein einzelner Lauf pro Modus und ein beziehungsweise zwei zusätzliche Siege
sind keine robuste Verbesserung. Die besten Stände sind nur lokale Kandidaten;
spätere Stände wurden wieder schwächer. Kein veröffentlichtes Modell ersetzt.

`contract-routes-v1.json` (27 Routen, ein Kartenset, fünf Spiele je Spieler)
war insgesamt schlechter: Schutz 46/135, erster Kontrakt 40/135. Auf KEF gelb
kam er zwar jedes Mal bis Runde 7, konnte aber nicht bremsen. Die konkrete
Ursache war häufig zu wenig früh abgeschlossene Eisbremsen; eine halbe Paarung
verfällt am Rundenende. Wenn die Landung bereits wegen fehlender Pflichtfelder
unmöglich war, verschwanden im bisherigen binären Wert außerdem alle sinnvollen
Unterschiede zwischen guten und schlechten Flugkontrollen.

Der zweite Planer berücksichtigt explizite hypothetische Partner-Eiszüge
zwischen eigenen Zügen, verbraucht deren unterschiedliche Würfel und denselben
Kaffeepool in der Aufgabenverteilung, hält unterschiedliche erste Ziele im
Suchstrahl und belohnt frühe öffentliche Kontrollfestlegung. Bei ausschließlich
unerfüllbaren Rundenzielen verwendet er eine gesonderte physikalische
Rückfallbewertung: möglichst waagerecht, langsam genug, ohne Treibstoffverlust.
Ein optimistischer öffentlicher Endrunden-Zähltest verhindert nutzlose Neuwürfe
bei bereits sicher unerfüllbaren Pflichtfeldern. Diese Grenzen ignorieren
Augenzahlen/Reihenfolge und können nur Unmöglichkeit feststellen.

`coherent_safety.py` erweitert den alten Sofortschutz für genau einen letzten
Würfel: nur wenn selbst alle durch Kaffee/Anpassung/Neuwurf optimistisch
erreichbaren Augenzahlen keine rettende native Platzierung erlauben, wird die
Partie durch Platzieren beendet. Das verhindert sinnloses Verzögern durch
Hilfsaktionen. Keine künstliche Spielbeendigung, keine Änderung der Regeln.
Die neue Auditkennzahl verwendet diese strengere Bedeutung; ältere Berichte
mit dem alten Sofortschutz nicht ungekennzeichnet damit vergleichen.

`contract-routes-v2.json` ist vollständig: Schutz 50/135, Kontrakt 53/135.
KEF gelb 0 → 2 Siege, TGU gelb 0 → 3, YUL grün 3 → 5; ATL gelb und LHR gelb
je 2 beziehungsweise 1 → 0. Auf sechs schweren Modulrouten steigt die mittlere
erreichte Runde deutlich, auf anderen gibt es Rückschritte. Nur fünf gepaarte
Partien je konkretem Fall; keine belastbare allgemeine Stärkeaussage.
`contract-routes-v2-analysis.json` und `.md` weisen sämtliche Routen aus.

Der laufende `contract-matrix-v2.json` vergleicht alle 192 Fälle mit fünf
gepaarten Spielen je Fall: alter geschützter Spieler, direkte Kontraktwahl
und endliche Kontraktempfehlung mit unveränderten Tensoren/Guide-Margin 12.
Letztere Konfiguration ist ausdrücklich eine neue Policy, kein neu trainiertes
Netz. Seeds 14.930.000 + 100*i, i=0..191; drei Modi, 2.880 Partien.
Alle Varianten unter realer Engine-Uhr, auch Echtzeitrouten. Quellen während
dieses Vergleichs eingefroren. Noch kein Ergebnis, keine Veröffentlichung.
