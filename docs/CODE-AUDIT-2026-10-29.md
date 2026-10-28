# Codeprüfung · 29.10.2026

Erste vollständige Python-Suite nach Abschluss von „Beste KI“: **700 Tests bestanden**, 127 Sekunden. Quellprüfung der Spiel- und Modulzustände, KI-/Feedback-/Speicherabläufe, PeerJS-Lobby/Transport, Offline-Update und Cloud-Archivierung. Generierter Code und Drittanbieterbibliotheken werden über Build-/Integritätstests geprüft; unveränderliche Forschungssnapshots werden nicht nachträglich umgeschrieben. Das ist kein Nachweis völliger Fehlerfreiheit.

## 1. Multiplayer: Wiederbeitritt während eines Flugs

**Fehler:** Nach Verbindungsabbruch öffnete der Host bei einem Ersatzkanal wieder die Lobby. Die Protokollbegrüßung sendete ausschließlich die bereits gestartete Lobby, deren Startschutz den erneuten Spielstart verhindert. Der Gast blieb dadurch ohne fortsetzbaren Flug.

**Korrektur:** Eine neue Verbindung lässt das aktive Cockpit des Hosts offen. Nach erfolgreichem Protokollabgleich erhält der Gast den bestehenden, für seine aktuelle Flugrolle gefilterten Spielzustand einschließlich eines eventuell offenen Neuwurfs. Kein neuer Engine-Start und kein vorzeitiger Versand privater Würfel an inkompatible Clients.

**Prüfung:** `node tests/multiplayer-actions.cjs` reproduziert tatsächliche Host-Verbindungsereignisse, Begrüßung, beide Rollenverteilungen, unveränderte Partie und private Partnerwürfel. Außerdem Rolle/Revision, Neuwurf, beidseitiges Behalten, Undo und Fehlerbehandlung. Der alte VM-Test wurde um die inzwischen erforderliche Lobby-Abhängigkeit und die getrennten Host-/Flugrollen ergänzt.


## 2. KI-Feedback: falsche Beschriftung von Fähigkeiten

**Fehler:** Anpassung, Voraussicht und alle Zusammenarbeitsaktionen fielen in denselben Textzweig wie die Auswahl für einen gemeinsamen Neuwurf. Dadurch beschrieb das Feedback die falsche Aktion.

**Korrektur:** Jede Fähigkeit erhält einen passenden Text, einschließlich Würfelnummer, Tauschbeginn/-abbruch und ausdrücklichem Behalten aller Würfel. Bewertungsdaten und Aktionskennungen bleiben identisch.

**Prüfung:** Produktionsfunktion im Node-Vertragstest für jede Fähigkeit und die Neuwurf-/Rundenaktionen geprüft; die exakte Auswahl der besten KI für alle 186 Fälle in beiden Modi wird dabei erneut geprüft.

## 3. Rückgängig: abgeschlossene Aufzeichnung und veraltete Rundenpläne

**Fehler:** Beim Rückgängigmachen eines verlorenen Spielschritts kehrte die Engine ins laufende Spiel zurück, aber die Lernaufzeichnung behielt `verloren` und ihre Abschlusszeit. Bereits berechnete Rundenergebnisse wurden nicht verworfen; spätere Absprachen und Vorschläge konnten nach dem Zurückspringen weiter auf dem alten öffentlichen Zustand beruhen.

**Korrektur:** Erfolgreiches Undo übernimmt den tatsächlichen Partiestatus und öffnet eine wieder laufende Aufzeichnung. Die betroffene Rundenauswertung wird neu berechnet. Spätere Absprachen bleiben als verworfene Historie erhalten und werden nicht ausgeführt oder als letzter Rundenbericht angezeigt. Veraltete Vorschlagsentwürfe werden verworfen. Die aktuelle bereits vereinbarte Strategie bleibt während der Runde gültig; ihr Synchronisationsstatus folgt den tatsächlich noch liegenden Fahrwerk-/Klappenwürfeln.

**Prüfung:** `node tests/singleplayer-undo.cjs` scheiterte vor der Korrektur am unveränderten Verluststatus. Danach geprüft: erfolgloses Undo verändert nichts; Wiederöffnung, neue Ergebnisberechnung nach anderem Flugweg, keine wiederbelebte Zukunftsabsprache, echte/aufgehobene Synchronisation und Rücksprung in die Verkehrsphase.


## 4. Multiplayer: verspätete Ereignisse eines ersetzten Kanals

**Fehler:** Ein Ersatzkanal erbte zunächst den Protokollstatus der alten Verbindung. Spät eintreffende `close`, `data` oder `open`-Ereignisse des alten Kanals konnten danach den neuen Verbindungsstatus überschreiben oder alte Nachrichten gegen die neue Verbindung verarbeiten.

**Korrektur:** Jeder neue Kanal beginnt ohne Protokollfreigabe und ohne alte Gast-Bereitschaft. Die Host-Callbacks verarbeiten Ereignisse ausschließlich, solange ihr eigener Kanal noch der aktuelle ist.

**Prüfung:** Im realen Callback-Ablauf des Node-Tests alten Kanal schließen, Ersatzkanal öffnen und begrüßen, danach verspätetes Schließen, falsche Protokollnachricht und Öffnen des alten Kanals einspeisen. Die neue Verbindung bleibt verbunden/freigegeben und erhält keine zusätzlichen alten Zustandsnachrichten. Der Test scheiterte vor der Korrektur bereits am geerbten Protokollstatus.


## 5. Aufzeichnungen: unnötiger RAM-Verbrauch nach erfolgreichem Speichern

**Fehler:** Jede in dieser App-Sitzung aufgezeichnete Partie blieb als vollständige JSON-Kopie im Fallback-Speicher, auch nach abgeschlossener IndexedDB-Transaktion. Die Liste wuchs mit jeder Partie und duplizierte die bereits gespeicherten Daten im RAM.

**Korrektur:** Nach erfolgreichem Transaktionsabschluss wird ausschließlich die gerade gespeicherte Revision aus dem RAM entfernt. Eine neuere noch ausstehende Revision und sämtliche fehlgeschlagenen Schreibvorgänge bleiben als exportierbare Fallbacks erhalten.

**Prüfung:** Der asynchrone Transaktionstest `node tests/singleplayer-storage.cjs` behielt vorher nach 20 erfolgreichen Partien alle 20 Kopien im RAM. Nachher: keine überzähligen Kopien, weiterhin alle Exporte, Fallback nach Abbruch, Erhalt bei fremdem erfolgreichem Schreibvorgang und zwei überlappende Revisionen einschließlich eines Abbruchs der neueren Revision.

## Abschlussprüfung dieses Durchlaufs

700 Python-Tests bestanden. Syntax von 293 eigenen Python-Dateien und 57 JavaScript-Dateien einschließlich generierter Bundles geprüft; doppelte HTML-IDs und fehlende lokale Skripte ausgeschlossen. Die unabhängigen JavaScript-Suites prüfen Modellwahl, Feedback, Undo, Speicherung, Planung, Fähigkeiten, Neuwurf, Multiplayer, Offline-Paket sowie Cloud-Ingestion und Archiv mit SQLite. Browserprüfung des neuen Standards einschließlich echtem KI-Zug und Fortsetzen nach Update erfolgt; sämtliche fünf Bugfixes besitzen gezielte Regressionstests. Die Prüfung erhebt keinen Anspruch, jeden möglichen Fehler gefunden zu haben.
