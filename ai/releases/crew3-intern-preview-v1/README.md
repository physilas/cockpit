# Crew 3 · Praktikant (Test)

Vom Nutzer ausdrücklich gewünschter spielbarer Zwischenstand mit dem Praktikantenmodul.

| Offizielle Route | Entwicklungs-Selbstspiele | Siege | Quote |
| --- | ---: | ---: | ---: |
| Atlanta grün (`LOG_ATL_GREEN`) | 80 | 21 | 26,25 % |
| Heathrow gelb (`LOG_LHR_YELLOW`) | 80 | 19 | 23,75 % |

Diese Partien wurden zur Modellauswahl genutzt. Sie sind keine unabhängige Qualifikation und keine Vorhersage für menschliche Partner. `quality.approved` bleibt deshalb `false`; nur `preview.enabled=true` macht diesen ausdrücklich gewünschten Zwischenstand sichtbar. Bisherige freigegebene Crews bleiben verfügbar und vorausgewählt.

120.272 neue PPO-Entscheidungen in 54 Updates, davon Atlanta 64.428 und Heathrow 55.844. Die vorhandene Detailpolitik wurde trainiert; die ursprüngliche Crew-2-Grundlage blieb exakt eingefroren. Rund 9,65 Minuten Rollout/PPO-Zeit plus Entwicklungstests, insgesamt rund 15,1 Minuten. Acht CPU-Worker zu 70 %, ein Torch-Thread, nice 15, Metal-Minibatches.

Öffentliches Modulprofil 10 und Browserformat 4 verwenden dieselben Beobachtungen, Masken und Gewichte. Der Praktikantenwürfel ersetzt einen regulären Würfel. Keine privaten Partnerwürfel und keine zukünftigen Spiel-RNG-Werte. Keine Fähigkeitskarten oder weiteren neuen Module sind hier freigegeben.

`development.json` enthält die abgeschlossenen Entwicklungsdaten; `training.json` dokumentiert die tatsächliche Herkunft. Die nächste unabhängige Abschlusskohorte ab 15.400.000 bleibt unbenutzt.
