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
