# Crew 2 · Kerosin

Oslo/Gardermoen (`LOG_OSL_GREEN`) mit Kerosin, ohne Fähigkeitskarten.
Die Gewichte sind exakt dieselben wie bei Crew 2; Crew 1 und die bisherige
Crew 2 bleiben unverändert verfügbar. Diese zusätzliche Auswahl erfüllt das
vom Nutzer am 25.10.2026 ausdrücklich gelockerte 30–40-%-Ziel für diesen einen
Fall. Sie behauptet keine Beherrschung der übrigen Module.

Vor einer neuen unabhängigen Prüfung ausgewählt: `ai/releases/crew2-v1/best.pt`,
500.347 Entscheidungen in der ursprünglichen geführten Phase, Gewichts-SHA
`1d846e7731d60c9cc84c8204e7b87b5dea643b501b5f59bc2185deb76e8609eb`.
Der neue 20-Minuten-Allmodulversuch zeigte keinen ausreichenden Fortschritt;
seine Gewichte sind hier **nicht** enthalten.

Neue unabhängige Prüfung: **199 Siege aus 500 Selbstspielen, 39,8 %**,
95-%-Wilson-Intervall **35,6–44,2 %**. Damit liegt auch die untere Grenze über
der vorab festgelegten Freigabeuntergrenze von 30 %. Selbstspielseeds
15.200.000–15.200.499, keine zuvor verwendeten Trainings-/Entwicklungsseeds.
Die alte 50-%-Qualifikation wird nicht umgeschrieben.

Mit festem Heuristikpartner: 6/100 als Pilotin und 9/100 als Kopilot, zusammen
7,5 %. Diese deutlich schwächere Partnerprobe bleibt separat ausgewiesen.
Selbstspiel ist keine Vorhersage der Quote mit einem menschlichen Mitspieler.
Partnerseeds 15.300.000–15.300.099 sind ebenfalls verbraucht; nächste unabhängige
Kohorte ab 15.400.000 reservieren.

Inferenz: Schema 3 (489 Merkmale, 217 Aktionen), Browserformat 4,
unverändertes Profil 9 mit Referenzmaske 7. Die eigene Hand und öffentliche
Felder sind sichtbar, Partnerhand und zukünftige echte Zufallswerte bleiben
verborgen. Das Browserasset wird mit Crew 2 geteilt, weil die Gewichte gleich sind.
Die KI-ndergartenbetreuung zeichnet Schema-3-Kerosinaktionen und Daumen auf;
Gewichte ändern sich dadurch nicht automatisch.

`evaluation.json` enthält den vollständigen abgeschlossenen Bericht,
`training.json` Auswahl und Herkunft. Alle 700 Prüfpartien sind echte zusätzliche
Qualifikation; technische Browsertests zählen nicht dazu.
