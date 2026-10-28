# Codeprüfung · 29.10.2026

Erste vollständige Python-Suite nach Abschluss von „Beste KI“: **700 Tests bestanden**, 127 Sekunden. Quellprüfung der Spiel- und Modulzustände, KI-/Feedback-/Speicherabläufe, PeerJS-Lobby/Transport, Offline-Update und Cloud-Archivierung. Generierter Code und Drittanbieterbibliotheken werden über Build-/Integritätstests geprüft; unveränderliche Forschungssnapshots werden nicht nachträglich umgeschrieben. Das ist kein Nachweis völliger Fehlerfreiheit.

## 1. Multiplayer: Wiederbeitritt während eines Flugs

**Fehler:** Nach Verbindungsabbruch öffnete der Host bei einem Ersatzkanal wieder die Lobby. Die Protokollbegrüßung sendete ausschließlich die bereits gestartete Lobby, deren Startschutz den erneuten Spielstart verhindert. Der Gast blieb dadurch ohne fortsetzbaren Flug.

**Korrektur:** Eine neue Verbindung lässt das aktive Cockpit des Hosts offen. Nach erfolgreichem Protokollabgleich erhält der Gast den bestehenden, für seine aktuelle Flugrolle gefilterten Spielzustand einschließlich eines eventuell offenen Neuwurfs. Kein neuer Engine-Start und kein vorzeitiger Versand privater Würfel an inkompatible Clients.

**Prüfung:** `node tests/multiplayer-actions.cjs` reproduziert tatsächliche Host-Verbindungsereignisse, Begrüßung, beide Rollenverteilungen, unveränderte Partie und private Partnerwürfel. Außerdem Rolle/Revision, Neuwurf, beidseitiges Behalten, Undo und Fehlerbehandlung. Der alte VM-Test wurde um die inzwischen erforderliche Lobby-Abhängigkeit und die getrennten Host-/Flugrollen ergänzt.
