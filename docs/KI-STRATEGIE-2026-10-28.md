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

Zusätzlich recherchiert: [Nayyar, Mahajan und Teneketzis, 2013,
Common Information Approach](https://arxiv.org/abs/1209.1695). Gemeinsame
öffentliche Informationen können Vorschriften bestimmen, die jeder Spieler
danach auf seine eigenen privaten Informationen anwendet. Die vollständige
Optimierung über solche Vorschriften ist anspruchsvoll. Unser öffentlicher
Bewegungsvertrag ist eine einfache heuristische Nutzung dieser Idee, keine
Implementierung des optimalen dynamischen Programms. Als nächste getrennte
Hypothesen sind öffentliche Funk-/Treibstoff-/Praktikanten-Zuständigkeiten
(`round_responsibility.py`) und ein prospektiver Landungs-Neuwurfvergleich
(`reroll_advice.py`) vorbereitet, aber noch nicht in den laufenden Planer
eingebaut oder auf Spielstärke geprüft.

`distillation.py` lernt Mengen gleichwertiger erster Aktionen statt eines
beliebigen Würfelindex. Ganze **Trainings**episoden werden zur Imitations-
Validierung zurückgehalten. Diese Metrik ist keine Spielstärkemessung.
`search_demonstrations.py --teacher hybrid` soll auf Wind/Eis den Planer,
auf den übrigen Modulen den geschützten Ausgangsspieler als Erhaltungsziel
verwenden. Neue Sammel-/Lernläufe erst nach Ende des aktuellen schweren Jobs;
noch kein trainierter Schüler, noch keine nachgewiesene Beschleunigung.

`strategy_bridge.py` und `strategy_environment.py` bereiten getrennte Profile
13 (Kontraktempfehlung) und 14 (schneller kohärenter Sofortschutz mit altem
Prior) vor. Ihre Masken/Beobachtungen stimmen über echte Übergänge überein,
verbergen die echte Partnerhand und funktionieren ohne Torch/NumPy. Sie sind
noch **nicht** im Browser registriert oder veröffentlicht. Alte Profile und
Fingerprints bleiben unverändert.

Ein zusätzlicher Seed-Audit fand 10.356 unterschiedliche historisch
protokollierte Zahlenseeds. Manche neuen Entwicklungsbereiche überlappen auf
Zahlenebene ältere Berichte; die Route/Kartenidentität wurde dafür noch nicht
vollständig abgeglichen. Die bisherigen Ergebnisse bleiben ausdrücklich
Entwicklungsevidenz und werden nicht als unabhängige kalte Bestätigung
ausgegeben. Die reservierten Bereiche ab 15.400.000 sind in den historischen
Episoden noch unbenutzt; erst nach endgültiger Policy-Auswahl zur separaten
Bestätigung einsetzen und danach keine Parameterauswahl darauf betreiben.

## Stand nach drei Stunden

`contract-matrix-v2.json` ist vollständig: **192 konkrete Fälle**, fünf
gepaarte Partien je Spieler, drei Spieler, insgesamt 2.880 Partien.

| Spieler | Siege/Partien | Gleichgewichtetes Routenmittel |
|---|---:|---:|
| geschützter Ausgangsspieler | 78/960 | 33,26 % |
| direkte Kontraktwahl | 127/960 | 39,33 % |
| endliche Kontraktempfehlung, Margin12 | 121/960 | 36,00 % |

Für den direkten Planer gibt es 74 nur von ihm gewonnene und 25 nur vom
Ausgangsspieler gewonnene Seed-Paare. Das rein deskriptive Normalintervall
für den gleichgewichteten Routengewinn liegt bei ungefähr +0,33 bis +11,82
Prozentpunkten; keine Korrektur für vorausgehende Strategieauswahl, daher
kein unabhängiger endgültiger Qualitätsnachweis. PRG grün: 16 → 29 von75;
TGU gelb: 3 → 15 von75. Weiterhin ohne Sieg: **HND rot, OSL rot, PBH schwarz**.
Auch Rückschritte sichtbar, etwa PBH schwarz 2 → 0. Die vollständigen
Routentabellen stehen neben dem Bericht als JSON und Markdown.

Die Portierung verwendet jetzt die **direkt getestete** Arbitration statt
einer bloß ähnlich gewichteten Empfehlung: `public_contract.py` liefert
öffentliche Planwerte, die alte Baseline-Maske und eine gegebenenfalls
erzwungene Hilfsaktion. Python und JavaScript verwenden dieselbe explizite
Regel. Das NN löst alte Präferenzen und enge Gleichstände auf; neue Tensoren
werden für diesen Spieler nicht behauptet. Profil13 ist hierfür reserviert,
Profil14 für den kohärenten schnellen NN-Schüler. Die neue native
`StrategyEnv` und Browserübergabe verwenden dieselben Eingaben.

Die reale IAB-/Pyodide-Prüfung (`browser-runtime-v2.json`) führte 72 legale
Entscheidungen auf sechs Routen aus: MUC, KEF gelb, GIG gelb, PRG grün,
HND rot und PBH rot einschließlich Echtzeituhr. 12 Entscheidungen je Route,
jeweils bis Runde2. Maximum0,3394s, Routenmittel0,0620–0,1010s. Kein
Ganzspiel- oder Stärkeversprechen daraus ableiten. Ein echter Transportfehler
wurde gefunden und korrigiert: Pyodide wandelt Python `None` in JavaScript
`undefined`, JSON-Fixtures dagegen in `null`. Optionale Planaktionen
akzeptieren beide; zusätzlicher Regressionstest. Vorher/Nachher-Temperatur
je51,85 °C; kein kontinuierlicher Peak für diese kurzen Browserproben erfasst.

### Temperaturkorrektur

Der Lehrerjob meldete einmal **75,0813 °C am SMC-HotspotTCMz**. Den Wert nicht
als „unter75“ ausgeben. Der Job wurde daraufhin geordnet unterbrochen.
731 bereits vollständig gespeicherte Trainingspartien mit37.967 Labels
bleiben gültig; das geplante 800-Episoden-Sammelziel ist ausdrücklich
unvollständig. Keine halbfertige Episode importiert. 266 dieser Lehrerpartien
gewonnen, aber wegen Trainingsverteilung/logischer Uhr keine Stärkeaussage.

Der Wrapper pausiert künftig standardmäßig **5 °C unter der Grenze**, also
bei70 °C, Fortsetzung bei65 °C; Abtastung alle0,25s. Bei bereits heißem
Start wird der eigene Prozess sofort pausiert. Schwellen im Status protokolliert
und mit einem realen Testkind geprüft. Weitere parallele Spieljobs höchstens
zwei Worker; NN-Lernen ein CPU-Thread. Absolutes Systemmaximum trotz fremder
Apps und Sensorlatenz weiterhin nicht garantiert. Der darauffolgende erste
Schülerjob blieb bei höchstens58,46 °C.

### Schüler und nächste kontrollierte Phasen

`distillation.py` wurde auf den37.967 gespeicherten, explizit als Training
markierten Beispielen ausgeführt. Ganze Episoden zur Imitationsvalidierung
zurückgehalten, eingefrorene NN-Quelle geprüft. Keine Entwicklungsseeds oder
fremden Würfel als Lernziel. Normale BC50-Epochen, normale BC200-Epochen und
BC200 mit Würfelindex-Augmentation sind lokale Kandidaten; ihre tatsächliche
Spielstärke ist noch zu prüfen. Geerbte `total_steps` werden nicht als neue
Spielentscheidungen ausgegeben; `imitation_rows_seen` separat.

`dice_symmetry.py` permutiert eigene Würfel, Aktionsindizes, Neuwurf-Bits und
eigene Kooperationsindizes gemeinsam. Alle24 Permutationen gegen echte
Engine-Masken/Beobachtungen und inverse Rücktransformation geprüft. Augmentation
ist eine begründete Übertragung der Other-Play-Idee, keine bereits nachgewiesene
Stärkeverbesserung.

V3-Hypothesen bleiben explizite Optionen des Planers: `coordination=True`
für öffentliche Funk-/Treibstoffzuständigkeiten und frühere Ausbildung;
`prospective_rerolls=True` für den Vergleich aller sechs Ersatzaugen eines
einzelnen eigenen Würfels vor der Landung. Ihr Nutzen muss im Vergleich
getrennt und zusammen geprüft werden. Alte Standardwahl bleibtV2. Ein
konkreter Testfall verwendet einen schon positiv bewerteten, aber schlechten
Landungswurf; der Neuwurf verbessert den modellierten Wert und wird gewählt,
ohne die echte Partnerhand oder den echten zukünftigen Zufall zu lesen.

`strategy_crossplay.py` ist für gepaarte Spiele mit Crews1/3/4 in beiden
Rollen vorbereitet. KI-Partner sind kein Nachweis menschlicher Gewinnraten.
Nach vollständigen Tests zunächst V3-Abgleich auf27 Routen und frische
Schülerevaluation. Erst anschließend endgültige Policy einfrieren und den
bisher unbenutzten Bestätigungsbereich ab15.400.000 verwenden.

## Stand gegen 05:50 Berlin

Die vollständige Suite bestanden: **595 Tests in114,59s**, einschließlich der
zusätzlichen96 tatsächlichen nativen/JavaScript-Entscheidungen des direkten
Planers. Gemessener Testlauf-Peak66,44 °C mit der verschärften Regelung.

Für die Zugqualität zeigt die vollständige V2-Matrix zusätzlich:

| Kennzahl über je960 Partien | Schutz | direkter Planer |
|---|---:|---:|
| registrierte Kaffeekorrekturen in Gegenrichtung | 232 | 2 |
| Ereignisse mit nicht mehr erreichbaren zurückgelassenen Flugzeugen | 198 | 28 |
| vom jeweiligen kohärenten Sofortschutz als vermeidbar erkannte Verlustzüge | 0 | 0 |
| Abbruch am Schrittlimit | 0 | 0 |

Die ersten beiden sind Fehlerindikatoren, keine Behauptung, dass jedes Ereignis
zwingend vermeidbar war. Die Sofortschutz-Kennzahl darf nicht als bereits
gewonnene Partie interpretiert werden.

`contract-options-v3.json` ist vollständig:27 Routen, ein deklariertes
Kartenset, fünf gepaarte Spiele, fünf Varianten =675 Partien. Direkter V2-Planer
46/135, öffentliche Zuständigkeiten41/135, prospektive Neuwürfe47/135,
Kombination46/135, browserportierte Arbitration46/135. Alle135 Spiele der
Portierung stimmen in Status/Grund/Runde/Schritten mit dem nativen direkten
Planer überein. Die Zuständigkeiten werden nicht übernommen, der einzelne
zusätzliche Neuwurfsieg ist nicht belastbar. Beide Optionen bleiben aus.

Die endgültige kalte Bestätigung wird durch `strategy_confirmation.py`
vorbereitet: ausgewählten Checkpoint, öffentliche Strategiequellen einschließlich
JavaScript/Engine, alle192 Fälle und Protokoll vorab einfrieren. Veraltetes
Browserbundle, geänderte Dateien oder wiederverwendete Seeds werden abgelehnt.
Ein persistentes Ledger reserviert den kalten Bereich nur einmal. Ergebnisse
erteilen keine automatische Qualitätsfreigabe und senken keine alte Gewinnfloor.
`publish_preview` unterstützt dafür die exakt fingerprintierten Profile13/14
mit expliziten Karteneinzelfällen; der alte reine Routen-Qualifier bleibt dafür
gesperrt. Legacy-Fingerprints und Freigaben wurden nicht verändert.

Eine weitere örtlich begrenzte Hypothese ist vorbereitet: Ein Eisbremsenpaar
kostet zwei Würfel und war bisher mit32 Punkten gegenüber je26/30 für ein
einzelnes Fahrwerk-/Klappenfeld unterbewertet. `early_ice=True` bewertet das
abgeschlossene Paar mit64, halbe Paare weiterhin nur vorsichtig. Auf Routen
ohne Eis ergibt die Option identische Pläne; überprüft. Noch kein Wirksamkeits-
nachweis, noch nicht Standard. Nach der laufenden NN-Prüfung nur die36
betroffenen Eis-Kartenfälle gezielt vergleichen.

Zusätzlich korrigiert: Bereits zurückgelassene Flugzeuge oder eine selbst bei
maximaler Geschwindigkeit unerreichbare Entfernung werden jetzt schon vor
der Landung als irreversible öffentliche Grenzen erkannt. Dadurch wird kein
Neuwurf allein wegen eines unerfüllbaren Siegziels erzwungen, wenn noch ein
sinnvoller physikalischer Rückfallplan existiert. Alle186 offiziellen
Startzustände bestehen diese optimistische Prüfung; eigene/verdeckt fremde
Augenzahlen werden für diese Grenzen nicht verwendet.

Laufend: `neural-routes-v1.json`, sechs eingefrorene Netze,27 Routen, je10
Spiele mit identischen kohärenten Masken. Unbenutzte Entwicklungsseeds
14.955.050 +100*i. Drei BC-Schüler (50 Epochen,200 Epochen,200 Epochen mit
Symmetrie), bester Selbstspiel- und Populationsstand sowie Quelle. Auswahl
weiterhin Entwicklung; kalter Bestätigungsbereich nicht angerührt.

## Abgeschlossene Variantenwahl gegen 07:00 Berlin

Die oben als laufend bezeichnete NN-Prüfung ist abgeschlossen: Quelle89/270,
BC50 91/270, BC200 89/270, BC200 mit Symmetrie86/270, Selbstspiel87/270,
Partnerpopulation88/270. Das zusätzliche Lernen wird damit nicht als
Stärkeverbesserung veröffentlicht. Die sehr gute Imitationsgenauigkeit allein
hat nicht genügt. Auf den Wind-/Eisrouten gewann keine dieser schnellen
NN-Varianten eine der zusammen50 Partien je Variante.

Weitere abgeschlossene Entwicklungstests, jeweils27 konkrete Routenfälle
mit fünf gepaarten Partien:

| Versuch | Standard | Variante | Entscheidung |
|---|---:|---:|---|
| V4: höherer Eisbonus | 50/135 | 50/135 | bleibt aus |
| V4: zusätzliche Treibstoff-Kapazitätskosten | 50/135 | 50/135 | bleibt aus |
| V5: Beam24 →48 | 52/135 | 54/135 | zu kleiner Vorteil, etwa1,45-fache Rechenzeit |
| V6: Beam24 →48 nach öffentlicher Funkkorrektur | 52/135 | 52/135 | Beam24 bleibt |
| V6: hypothetische Partner-Fahrwerke | 52/135 | 51/135 | bleibt aus |

Die Varianten haben unterschiedliche Entwicklungsseeds und teilweise
unterschiedliche Quellenstände. Die Zahlen nicht zu einem scheinbar
homogenen Gesamtversuch zusammenfassen. Alle vollständigen JSON-Berichte
und Einzelanalysen liegen unter `ai/experiments/fresh-strategy-2026-10-28/`.

Der gewählte Stand wird als separates Profil13 vorbereitet, Name
**Crew5 · Navigator**. Seine NN-Tensoren entsprechen weiterhin exakt der
Crew4-Quelle. Neu ist die öffentliche physikalische Handplanung mit
gemeinsamem Kaffee-/Würfelbudget und einer exakt nach JavaScript portierten
Arbitration. `selection-before-confirmation.md` legt Auswahl und Prüfplan vorab
fest. Noch keine Aussage über die Ergebnisse der kalten Bestätigung.

Der Cross-Play-Versuch prüft die alten Crews1/3/4 als unveränderte Partner,
beide Rollen,27 Routenfälle und drei gepaarte Spiele je Bedingung. Das prüft
Zusammenspiel; es ist kein weiterer Trainingslauf und keine Übertragung
dieser Quoten auf menschliche Mitspieler.

Der erste Cross-Play ist abgeschlossen:152/486 für die alte geschützte
Strategie gegen136/486 für den direkten Planer,20 gepaarte Verbesserungen
und36 Verschlechterungen. In beiden Varianten keine vom Sofortschutz
erkannten vermeidbaren Verlustzüge. Das ist eine erkennbare Schwäche der
neuen Konvention bei unbekannten Partnern und wird nicht als positive
Zusammenarbeitsevidenz dargestellt. Vor dem Einfrieren wird deshalb eine
reaktive Hypothese geprüft: sichere vertraute Grundstrategie, bis der Partner
einen Ruder- oder Schubwürfel öffentlich platziert; anschließend ganze
verbleibende eigene Hand unter diesem öffentlichen Zwang planen.

Die Suite vor dieser zusätzlichen Hypothese ist erneut vollständig bestanden:
**609 Tests in117,449s**. Die neue Hypothese ist davon noch nicht abgedeckt.

## Fortsetzung gegen 09:00 Berlin

Ein Browser-Werkzeugaufruf zum Speichern einer PNG-Datei hing bis zur
Unterbrechung durch den Nutzer gegen08:58 Berlin. Der bereits gestartete
Rechenvergleich wurde währenddessen regulär beendet; danach lief kein
weiterer Lern- oder Vergleichsjob. Diese Wartezeit ist keine Entwicklungs-
oder Trainingszeit. Der Nutzer erlaubt weitere zwei Stunden und bestätigt
ausdrücklich den Push in das zuvor benannte öffentliche Repository.

Der Stand mit vier Entwicklungscommits wurde nach regulärem Merge des
zwischenzeitlichen entfernten Archiv-Commits auf `main` gepusht, Merge
`5010aef`. Uncommittete Nutzerdateien blieben ausgeschlossen.

Reaktiver Cross-Play V2:159/486 Siege der Kontrolle gegen153/486 der
reaktiven Variante,26 Verbesserungen gegen32 Verschlechterungen. Andere
Seeds als V1: daraus keinen direkten kausalen Vergleich mit dessen136/486
ableiten. Deshalb wird der direkte Planer zusätzlich auf exakt den V2-Seeds
geprüft. Selbstspiel V7 auf27 Routenfällen, je fünf Spiele: Schutz51/135,
direkt48/135, reaktiv54/135. Kaffeekorrekturen in Gegenrichtung3/0/1;
Stranding-Ereignisse24/4/4. Das spricht für weitere Prüfung der reaktiven
Variante, noch nicht für eine gesicherte Verbesserung.

`current-crews-route-table.md` enthält die vollständige Tabelle der vier
bereits sichtbaren Crews auf allen21 Standardrouten. Sie basiert auf den
unveränderten Veröffentlichungsberichten, nicht auf dem neuen kurzen V7-Test.

## Eingefrorener Kandidat gegen09:20 Berlin

Der direkte V2-Partnernachlauf ist vollständig und nutzt exakt dieselben
Seeds, Partner und Quellen wie der reaktive V2-Versuch:159/486 Kontrolle,
148/486 direkt,153/486 rein reaktiv. Die modulare Zusammensetzung erreicht
145/486 und ist damit ausdrücklich keine Verbesserung des alten Cross-Plays.
Sie erhält im kurzen Selbstspiel54/135 und auf Wind/Eis/Praktikant die
größere erreichte Rundenzahl des direkten Planers. Auswahl und Abwägung in
`final-selection-adaptive-v2.md`; keine Behauptung allgemeiner Partnerrobustheit.

613 Tests in113,211s bestanden, Peak66,21 °C. Tatsächliche Browserprüfung mit
Pyodide und JS-Inferenz: sechs ganze Partien,318 erlaubte Entscheidungen,
keine technischen Fehler, maximal0,8944s pro Entscheidung. MUC und GIG gelb
gewonnen; KEF gelb mit unvollständigen Eisbremsen verloren, PRG grün mit
fehlendem Fahrwerk/schräger Fluglage, HND rot und PBH rot mit Kollision.
Das sind technische Entwicklungsproben mit stringbasierten Testseeds,
keine unabhängigen Stärke- oder Menschquoten. Ein Temperaturmesspunkt
währenddessen51,85 °C; kein kontinuierlicher Browser-Peak gemessen.

Die endgültige kalte Bestätigung läuft unter `frozen-adaptive-v3.json` mit
zehn gepaarten Partien je192 Fällen und Variante, zusammen3840 Spielen.
Das zuerst erzeugte20er-ManifestV2 wurde nie gestartet. Reduktion vor dem
ersten kalten Ergebnis wegen des verbleibenden Zeitfensters; keine Auswahl
anhand kalter Ergebnisse. Eingefrorene Quellen und Evaluator währenddessen
nicht ändern. Erst nach vollständigem Bericht kann die separate Crew5 als
ehrlich gekennzeichnete Vorschau veröffentlicht werden. Exakte Eingabebytes
werden zusätzlich komprimiert im Release erhalten; neue Tensoren sind es nicht.

## Abschließender Stand

Der Zusatzvergleich der NN-Grundlagen erfüllt die vorab festgelegte
Wechselregel nicht: Crew4-Basis44/135, Crew3-Basis42/135. Crew4 bleibt die
Grundlage. Erst danach wurden die unabhängigen Quoten gelesen. Der kalte
Vergleich ist vollständig:171/1920 Siege Kontrolle gegen231/1920 Kandidat;
gleichgewichtetes Mittel der21 sichtbaren Standardrouten14,02 % →20,25 %.
Alle27 registrierten Routen einschließlich der sechs historischen Teststrecken:
32,00 % →37,22 %. Standardrouten mit mindestens einem Sieg13 →18.

Gegenkorrekturen beim Kaffee499 →14, Stranding-Ereignisse365 →99.
Öffentliche Restentfernungsgrenzen dagegen53 →162; diesen schlechteren
Indikator nicht verstecken. Bei118 von147 nur beim Kandidaten auftretenden
solchen Fällen wurde eine spätere Runde erreicht als von der Kontrolle;
das ändert die Exposition, beweist aber keine Ursache und entschuldigt keine
konkrete Fehlentscheidung. GIG rot, HND rot und PBH schwarz bleiben ohne Sieg.
Kein vom Sofortschutz erkannter vermeidbarer unmittelbarer Verlustzug und
kein Schrittlimit-Abbruch in beiden Varianten; keine Optimalitätsgarantie.

Crew5 · Navigator wurde als zusätzliche Entwicklungsvorschau exportiert,
ohne bisherige Empfehlungen zu ersetzen. Alle alten Modell-Metadaten und
Dateihashes sind unverändert.622 Tests in120,865s bestanden; darin zusätzliche
Torch/JS-Parität für beide geprüften NN-Grundlagen und Integritätsprüfungen
des tatsächlichen Releases. Eine zusätzliche normale YUL-Partie über das
Spielmenü gestartet: Crew5 sichtbar,21 Routen verfügbar, erste KI-Platzierung
ausgeführt, Co-Pilot danach am Zug, keine Browserfehler. Prüfbild im
Experimentordner. Bericht und vollständige Fünf-Crews-Tabelle dort.

Zeitangaben Berlin am28.10. sind CET (UTC+1); zuvor versehentlich mitUTC+2
beschriftete Zwischenüberschriften wurden berichtigt. Maßgeblich für die
Reihenfolge bleiben UTC-Werkzeugzeiten, Git-Commits und Jobprotokolle.
