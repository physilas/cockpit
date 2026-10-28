# Crew 5 · Navigator

Zusätzlich auswählbare Entwicklungsversion für alle21 Standardrouten mit
186 Kartenfällen; zusätzlich wurden sechs historische Teststrecken geprüft.
Neu ist die zusammenhängende Planung der eigenen Würfelhand mit gemeinsamem
Kaffeebudget und öffentlicher Modulphysik. Bei Wind, Eis und Praktikant beginnt
sie sofort; sonst reagiert sie zunächst auf einen offen gelegten Steuerwürfel
des Partners. Die NN-Tensoren stammen unverändert aus Crew4. Keine echte
Partnerhand und keine zukünftigen echten Zufallszahlen werden gelesen.

## Unabhängiger Vergleich

Vorher ausgewählter, eingefrorener Kandidat gegen Crew4 mit altem Profil12
und Sofortschutz.192 konkrete Fälle, je10 gepaarte Partien pro Variante,
insgesamt3840 Spiele mit echter Engine-Uhr. Alle Nullquoten bleiben sichtbar.

| Kennzahl | Kontrolle | Navigator |
|---|---:|---:|
| Routenmittel der21 sichtbaren Standardrouten | 14,02 % | 20,25 % |
| Standardrouten mit mindestens einem Sieg | 13/21 | 18/21 |
| Siege über alle192 Fälle | 171/1920 | 231/1920 |
| Kaffeekorrekturen in Gegenrichtung | 499 | 14 |
| Ereignisse mit zurückgelassenen Flugzeugen | 365 | 99 |
| Ereignisse mit unerreichbarer Restentfernung | 53 | 162 |
| Vom Sofortschutz erkannte vermeidbare unmittelbare Verlustzüge | 0 | 0 |
| Abbruch am Schrittlimit | 0 | 0 |

Das vorab festgelegte Gesamtmittel über alle27 registrierten Routen steigt
von32,00 % auf37,22 %. Die sechs leichteren historischen Strecken zählen in
diesem Wert mit, im21-Routenmittel oben nicht.124 gepaarte Verbesserungen
gegen64 Verschlechterungen. Das deskriptive Normalintervall für die Änderung
des27-Routenmittels beträgt ungefähr+1,49 bis+8,96 Prozentpunkte; keine
Mindestgewinnrate pro Route und keine Zusage menschlicher Gewinnraten.

Besonders sichtbar: GIG gelb0/60 →7/60 und KEF gelb0/60 →16/60.
GIG rot, HND rot und PBH schwarz blieben ohne Sieg. Die erhöhte Zahl der
Restentfernungsgrenzen bleibt ein Problemindikator. Längeres Überleben
ändert seine Exposition; aus Endzusammenfassungen lässt sich die Ursache
nicht eindeutig bestimmen. Topniveau auf allen Routen ist nicht belegt.

## Auswahl und Prüfung

Gemischtes Crew-Training, zusätzliche PPO-/Imitationsgewichte, breitere Suche
und weitere Heuristiken wurden verglichen. Kein verlässlicher Zusatznutzen,
deshalb keine Übernahme ihrer Gewichte. Im abschließenden vorab festgelegten
Blueprint-Vergleich gewinnt die Crew4-Basis44/135 statt42/135 mit Crew3.
Erst nach dieser Auswahl wurden die unabhängigen Ergebnisse gelesen.

Die Partnerkompatibilität bleibt begrenzt: Im Entwicklungs-Cross-Play mit
alten Crews erreichte die gewählte modulare Variante145/486 statt159/486
der Kontrolle. Sie wird deshalb als zusätzliche Vorschau angeboten; alte
Crews und Empfehlungen bleiben erhalten. Deren Metadaten, Browserassets
und Checkpoints wurden per Hash geprüft.

622 Tests bestanden. Tatsächliche Pyodide-/JS-Browserprüfung: sechs ganze
Partien,318 erlaubte Entscheidungen, keine technischen Fehler, maximal
0,8944s je Entscheidung. Zusätzlich über das normale Spielmenü gestartet:
Navigator ist auswählbar, alle21 Landungen erscheinen und die erste
KI-Platzierung funktioniert. Keine Browserfehler beobachtet.

In den verwalteten Rechenläufen des Zusatzfensters lag der höchste Messwert
bei73,08 °C. Pause ab70 °C, Fortsetzung ab65 °C, Abtastung alle0,25s.
Im früheren Lehrerjob gab es einmal75,0813 °C; danach wurde die Regelung
verschärft. Für die kurzen Browserproben wurde kein kontinuierlicher Peak
erfasst; ein Messpunkt lag bei51,85 °C.

## Dateien

- Vollständiger Fünf-Crews-Vergleich: `ai/experiments/fresh-strategy-2026-10-28/crews-and-navigator-route-table.md`.
- Gepaarte Auswertung und alle Fälle: `confirmation-v3-analysis.json` und `confirmation-adaptive-v3.json` im gleichen Ordner.
- Release: `ai/releases/crew5-planner-2026-10-28-v1/`, mit exakten eingefrorenen Eingabebytes, Protokoll und allen Einzelergebnissen.
- Forschung, Quellen, verworfene Varianten und Grenzen: `docs/KI-STRATEGIE-2026-10-28.md`.
- Sichtprüfung: `ai/experiments/fresh-strategy-2026-10-28/navigator-browser-check.jpg`.
