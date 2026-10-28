# Gemeinsame KI für Strecken ohne Module

Der Singleplayer bietet die Strecke und anschließend nur dafür freigegebene
Modelle an. Ein Modell kann mehrere Strecken unterstützen. Forschungsstände
ohne bestandene Freigabe erscheinen nicht im Menü.

Der Spieler ist ein **hybrides System aus PPO-Netz und öffentlicher
Rundenplanung**. Die hohen Gewinnraten beziehen sich auf dieses vollständige
System. Das Netz allein erreicht diese Leistung nicht. Die Planung erhält
ausschließlich eigene Würfel, öffentliche Feldbelegungen und Streckendaten;
sie liest keine Partnerhand und keine zukünftigen Würfe.

## Training vom 24. Oktober 2026

Lokal auf Apple M2 Pro: isolierte CPU-Prozesse simulieren Partien, größere
PPO-Minibatches werden auf der Apple-GPU über Metal aktualisiert. Die 19
GPU-Kerne gehören zu einem gemeinsamen Metal-Gerät. Die Sandbox meldete
Metal zunächst als nicht verfügbar; außerhalb der Sandbox wurde der Zugriff
mit einer Tensorberechnung und den Trainingsläufen verifiziert.

Die aufeinanderfolgenden Stufen liegen lokal unter `runs/muc-natural-v1/`:

1. `train`: vorhandene Gewichte mit Planung, Hilfsaktionen ohne zusätzliche
   Abzinsung, reine Sieg-/Verlustbelohnung.
2. `traffic1`: ein Flugzeug weiter voraus; einfache Strecke bleibt im Mix.
3. `traffic2-lengths`: zwei Flugzeuge, kurze und lange Übungsstrecken.
4. `curves`: mehr Verkehr und zunächst isolierte Kurven.
5. `basegame` und `basegame-final`: gemeinsame Feinabstimmung einschließlich
   unveränderter Logbuch-Strecken YUL grün, LHR grün und HND grün sowie der
   eigenen Strecken. Der erste Lauf wurde für die abschließende, festgelegte
   Planung unterbrochen; der Folgelauf hat ein getrenntes Verzeichnis.

25 % der parallelen Rollout-Batches verwenden die unabhängige einfache
Heuristik als Partner, abwechselnd in beiden Rollen. Deren Aktionen werden
**nicht** als vom Netz gezogene PPO-Aktionen ausgegeben. Die Heuristik ist
kein guter Kurvenpilot; Partnerergebnisse werden deshalb getrennt von
Selbstspielergebnissen angegeben und sagen keine menschliche Gewinnrate voraus.

`TRAIN_*`-Strecken sind ausschließlich Trainingsaufgaben und bleiben im
Menü verborgen. `MUC_T1`, `MUC_T2` und `MUC_T3` sind sichtbare Übungsvarianten.
Die bisherige verkehrsfreie MUC-Strecke und die Originaldaten der Logbuch-Routen
bleiben erhalten. Das Netz beobachtet die tatsächlichen Streckenfelder und
keine fest codierte Flughafenkennung.

## Planung und Grenzen

Assistenzprofil 1 bleibt für die veröffentlichte MUC-Vorschau verfügbar.
Profil 2 ergänzt Verkehr und die erreichbare Restentfernung bei ausgebauten
Klappen. Profil 3 ergänzt Kurvenvorausschau, öffentliche Funkkapazität beider
Rollen und Reservierung der verbleibenden Platzierungen für Verkehr und
Landungsvorbereitung. Kaffee wird zusammen mit einer folgenden Platzierung
geplant; Neuwürfe werden bei schlechter eigener Fortsetzung angeboten.

Die Kapazitätsprüfung verwendet optimistische Schranken. Sie behauptet keine
Lösbarkeit allein aufgrund ausreichender Würfelzahlen. Die praktische
Rundenplanung ist eine Heuristik und beschränkt zusätzlich die Aktionsauswahl;
sie ist kein Beweis, dass sämtliche ausgeschlossenen Aktionen verlieren würden.
Alle spielentscheidenden Regeln gelten weiterhin in der Engine.

Module und Fähigkeitskarten sind ausdrücklich ausgeschlossen. Insbesondere
darf die Kapazitätsprüfung nicht unverändert bei einer Karte mit zusätzlichem
schwarzen Würfel verwendet werden. Ein späterer Ausbau muss Verfügbarkeit,
Rollenrechte und die einmalige Zuweisung gemeinsam nutzbarer Zusatzwürfel
abbilden. Aktuell haben sämtliche sichtbaren Routen ohne Module auch keine
Fähigkeitskarten.

## Freigabe und Nachweise

`ai/releases/<release>/evaluation.json` enthält Ergebnisse pro Strecke,
95-%-Wilson-Intervalle, Verlustgründe, Kaffeeverbrauch, direkte
Kaffeekorrekturen in Gegenrichtung und Neuwürfe am Spielanfang. Selbstspiel
und beide Rollen mit dem Heuristikpartner werden getrennt ausgewertet.

Die erste MUC-Vorschau gewann 794 von 1.000 unabhängigen Partien. Das alte
Netz ohne Planung gewann auf denselben Seeds 31 Partien. Mit Planung und
alten Gewichten waren es 796: Der große erste Fortschritt kam aus der Planung;
der kurze erste Trainingslauf brachte keinen zusätzlichen messbaren Gewinn.

Die Freigabe verlangt mindestens 200 unabhängige Selbstspielpartien pro
angebotener Route und eine untere 95-%-Intervallgrenze von mindestens 20 %.
Das verhindert die Veröffentlichung von Modellen, die auf einer angebotenen
Route fast nie gewinnen. Es bedeutet keine einheitlich hohe Gewinnrate auf
allen Schwierigkeitsgraden; insbesondere Haneda ist deutlich anspruchsvoller.
Die tatsächliche Selbstspielquote der ausgewählten Strecke wird im Menü genannt.

Freigaben prüfen einen Fingerabdruck der Gewichte **und** der aktuellen
Planungsimplementierung. Nach einer Änderung ist eine neue Auswertung nötig.
Die komplette Beobachtungs-/Aktionsschnittstelle bleibt mit älteren Modellen
kompatibel; die zusätzliche Assistenz steht separat in den Modellmetadaten.

## Selbst weitertrainieren

Aus dem Projektordner, nach der Veröffentlichung von `crew-basegame-v1`:

```bash
.venv/bin/python -m ai.train \
  --resume ai/releases/crew-basegame-v1/best.pt \
  --run-dir runs/crew-basegame-next \
  --steps 35000000 --device mps --workers 2 --cpu-duty-cycle 0.5 \
  --rollout-steps 8192 --minibatch-size 1024 --epochs 4 \
  --assistance-version 3 --discount-unit placement \
  --partner-fraction 0.25 --eval-every 8 --eval-games 150
```

`--steps` ist das absolute Gesamtziel einschließlich bisheriger Entscheidungen.
Die gespeicherte Streckenmischung wird übernommen. Ohne Metal `--device cpu`
verwenden; parallele Simulationen bleiben möglich. Ein neues Verzeichnis
verhindert das Vermischen unterschiedlicher Versuche. Strg+C erhält das letzte
vollständig gespeicherte Update.

Die Fortschritte stehen in `metrics.csv`, `episodes.csv` und der Terminalausgabe.
Die CPU-Simulationen begrenzen hier häufig den Durchsatz; eine größere GPU allein
beschleunigt nicht jeden einzelnen Spielschritt.

Einen **fertigen, unveränderten** Checkpoint auf neuen Seeds prüfen und freigeben:

```bash
.venv/bin/python -m ai.route_eval \
  --checkpoint runs/crew-basegame-next/best.pt \
  --games 500 --partner-games 100 --seed 9000000 --workers 2 --cpu-duty-cycle 0.5 \
  --output runs/crew-basegame-next/qualification.json

.venv/bin/python -m ai.publish \
  --checkpoint runs/crew-basegame-next/best.pt \
  --evaluation runs/crew-basegame-next/qualification.json \
  --release-id crew-basegame-v2 --name 'Crew 2'

.venv/bin/python build_pwa.py
```

Die Freigabe bricht ab, wenn eine modulfreie Strecke nicht qualifiziert ist
oder Auswertung, Gewichte und Planung nicht zusammenpassen. Neue Gewichte
werden im Browser über eine neue unveränderliche Datei geladen. Nach einer
Veröffentlichung kann wegen des Service Workers ein weiteres Neuladen nötig sein.
