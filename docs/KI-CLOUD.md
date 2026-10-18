# Kostenlose zentrale Spiellogs mit Cloudflare D1

GitHub Pages liefert weiterhin die App und die Modelle aus. Ein **Cloudflare
Worker** empfängt die Trainingsdateien und speichert sie als JSON in einer privaten
**D1-Datenbank**. Eine R2-Subscription wird nicht benötigt. Teilnehmer stimmen in
KI-no oder KI-ndergartenbetreuung per Checkbox zu und spielen anschließend ohne
Cloud-Anmeldung oder Upload-Schritte. Normale Partien „Mit KI spielen“ werden
nicht hochgeladen.

Stand 18.10.2026: Die EU-Datenbank und der Worker sind bereitgestellt. Der Endpunkt
`https://flyteam-training.silas-zelmer.workers.dev/logs` ist in der lokalen App
eingetragen. Ein echter Browser-Upload mit 56 Entscheidungen und die Speicherung
in D1 wurden geprüft; eine ältere Revision ersetzte die neuere nicht. Die eindeutig
markierte Testzeile wurde anschließend entfernt. Die App-Dateien werden über
GitHub Pages aus dem Branch `main` veröffentlicht.

## Kostenloser Rahmen

D1 ist im Workers-Free-Tarif enthalten: derzeit bis zu 500 MB pro Datenbank,
5 GB über alle Datenbanken, 5 Millionen gelesene und 100.000 geschriebene Zeilen
pro Tag. Workers Free enthält derzeit 100.000 Anfragen pro Tag. Auf dem Free-Tarif
werden bei ausgeschöpften Kontingenten Anfragen abgewiesen; die App behält
fehlgeschlagene Uploads lokal für einen späteren Versuch. Es wird kein bezahlter
Tarif durch die Einrichtung aktiviert. Die Kontingente gelten gemeinsam mit
anderen Anwendungen desselben Cloudflare-Kontos.

[Offizielle D1-Preise](https://developers.cloudflare.com/d1/platform/pricing/),
[D1-Limits](https://developers.cloudflare.com/d1/platform/limits/),
[Workers-Preise](https://developers.cloudflare.com/workers/platform/pricing/).

Eine Datenbankzeile enthält jeweils den aktuellen Stand einer Partie. Neuere
Stände ersetzen ältere atomar; sie erzeugen keine zusätzliche Partie. Für viele
Beispiele sollten Daten regelmäßig exportiert und gesichert werden, damit der
Speicher verfügbar bleibt. Die Einrichtung löscht keine Trainingsdaten automatisch.

## Konfiguration und erneute Bereitstellung

Das bestehende Cloudflare-Konto, die eigene EU-Datenbank `flyteam-training`, ihre
Kennung und der GitHub-Pages-Ursprung `https://physilas.github.io` stehen in
`cloud/wrangler.jsonc`. Andere Datenbanken werden nicht verwendet. Für eine neue
Installation kann eine Datenbank so angelegt werden:

```bash
npx wrangler login
npx wrangler d1 create flyteam-training --jurisdiction eu
```

Die ausgegebene Datenbankkennung wird unter `d1_databases` mit Binding-Namen
`TRAINING_DB` eingetragen. Anschließend:

```bash
npx wrangler d1 execute flyteam-training --remote --file cloud/schema.sql --config cloud/wrangler.jsonc
npx wrangler deploy --config cloud/wrangler.jsonc
```

Die Schema-Datei verwendet `CREATE TABLE IF NOT EXISTS` und ist erneut ausführbar.
Es gibt keine Lösch- oder kostenpflichtige Tarifänderung in diesen Befehlen.

Die ausgegebene Worker-URL mit `/logs` gehört in
`frontend/web/js/cloud-config.js`. Dort stehen ausschließlich die öffentliche
Upload-Adresse und keine Cloudflare-Zugangsschlüssel. Der Worker erhält seinen
Datenbankzugriff durch die Bindung. Bei einer anderen App-Adresse muss
`ALLOWED_ORIGINS` auf deren Ursprung gesetzt werden, **ohne Repository-Pfad**.

Die Webseite wird anschließend wie bisher gebaut und über GitHub Pages veröffentlicht:

```bash
.venv/bin/python -m ai.export_browser
.venv/bin/python build.py
```

Die generierten Dateien unter `frontend/web/models/` und der Modellkatalog müssen
mit veröffentlicht werden. Die ursprünglichen `.pt`-Checkpoints bleiben lokal.

## Aufzeichnungen ansehen und sichern

Im [Cloudflare-Dashboard](https://dash.cloudflare.com) unter
**Storage & databases → D1 → flyteam-training → Console** stehen die gesammelten
Partien in `training_sessions`. Eine Übersicht liefert:

```sql
SELECT session_id, mode, status, revision, event_count, received_at
FROM training_sessions
ORDER BY received_at DESC
LIMIT 100;
```

Die vollständigen Logs stehen in `payload`. Eine lokale Sicherung der Datenbank
ist mit dem eigenen Cloudflare-Zugang möglich:

```bash
npx wrangler d1 export flyteam-training --remote --output /tmp/flyteam-training.sql --config cloud/wrangler.jsonc
```

Die Datei ist ein SQL-Backup. Für den Trainingsimport lassen sich die gespeicherten
JSON-Dokumente lokal aus `payload` lesen. Admin- und Download-Zugangsdaten gehören
nicht in die Webseite. Sicherungen müssen an einem dauerhaft aufbewahrten Ort
abgelegt werden; `/tmp` dient im Beispiel nur als temporäres Exportziel.

## Datenfluss und Grenzen

Einwilligungsversion und Zeitpunkt werden gespeichert. Namen und E-Mail-Adressen
werden nicht abgefragt. Ein zufälliger Upload-Token pro Installation trennt die
Schreibbereiche; nur sein Hash wird als pseudonyme Kennung gespeichert. Der Token
steht nicht in den Spiellogs oder Exportdateien. Die App schreibt keine
IP-Adressen in ihre Spiellogs. Cloudflare verarbeitet Verbindungsdaten.

Aufzeichnungen und Upload-Warteschlange werden zuerst in IndexedDB gespeichert.
Nach kurzer Bündelung wird der aktuelle Stand gesendet. Bei Fehlern wird später
erneut versucht, auch nach erneutem Öffnen. Bei vollständig geschlossener
Handy-App ist kein Hintergrund-Upload garantiert. Der zusätzliche lokale Export
bleibt unter „Eigene Aufzeichnungen“ verfügbar.

Rückgängig gemachte Aktionen sind `voided`. Bewertungen unterscheiden Entwurf und
mit dem nächsten gültigen menschlichen Zug bestätigtes Feedback. Beobachtungen
enthalten nur öffentliche Lage und eigene Würfel. Erfolge, Niederlagen und
abgebrochene Partien sind getrennt gekennzeichnet. Ein Upload verändert noch
keine Modellgewichte.

Der Worker bietet Upload und CORS-Preflight an, keine öffentliche Lese- oder
Listenfunktion. Er prüft Format, Größe, Einwilligung, Bewertungswerte sowie
Beobachtungs- und Aktionsdimensionen. Die Nutzlast ist auf 1.800.000 Bytes begrenzt,
damit sie einschließlich Metadaten in eine D1-Zeile passt. Pro Installation gilt
ein Rate-Limit. Vor dem Lernen sind Replay-/Regelprüfung, Versionsprüfung,
Dublettenfilter und die Auswahl geeigneter Beispiele erforderlich; öffentliche
Clients sind kein Echtheitsnachweis für menschliche Demonstrationen.

## Prüfung

Die lokalen Worker-Tests verwenden echtes SQLite und prüfen Revisionen,
Teilnehmertrennung, ungültige Daten, Größenlimit, CORS und Datenbankfehler:

```bash
node tests/cloud-worker.mjs
```

Nach der Bereitstellung wird ein Testupload an den echten Endpunkt geschickt und
dessen Speicherung in D1 geprüft. Dabei angelegte Testzeilen werden anschließend
gezielt entfernt. Die aktualisierte GitHub-Pages-Version muss separat veröffentlicht
werden, bevor Teilnehmer die neuen Modi und den Endpunkt erhalten.
