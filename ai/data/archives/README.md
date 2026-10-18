# Automatisch archivierte Trainingsaufzeichnungen

Der Workflow **Archive training data** läuft täglich gegen 03:17 Uhr in
`Europe/Berlin`, unabhängig vom lokalen Computer. Er übernimmt abgeschlossene
KI-no- und Feedbackpartien, deren letzter Upload mindestens zehn Minuten alt ist.

Die Dateien liegen unter
`YYYY-MM-DD/{examples|feedback}/SESSION-ID/rREVISION-SHA256.json`.
Das Datum ist das UTC-Empfangsdatum in Cloudflare. Jede JSON-Datei enthält die
vollständige, unveränderte `payload` aus D1. Die SHA-256-Prüfsumme ihrer UTF-8-Bytes
steht im Dateinamen. Die installationsbezogene Datenbankkennung und der
Archivschlüssel werden nicht veröffentlicht.

Nach dem Commit lädt der Workflow alle Dateien erneut über den aktuellen
GitHub-Branch herunter und vergleicht sie bytegenau mit den Originalen. Erst
danach bestätigt er die Löschung. Cloudflare löscht nur noch identische
Versionen. Laufende, kürzlich veränderte und inzwischen neu hochgeladene Stände
bleiben erhalten. Ein fehlgeschlagener Lauf kann gefahrlos erneut gestartet
werden; vorhandene identische Dateien werden geprüft und wiederverwendet.

Ein kleiner monatlicher Eintrag unter `.github/archive-keepalive/` verhindert,
dass GitHub den Zeitplan nach 60 Tagen ohne Repository-Aktivität deaktiviert.
Dieser Eintrag enthält keine Trainingsdaten.

Gewonnene, verlorene und abgebrochene Partien sind durch `session.status`
unterscheidbar. Nicht jede Aufzeichnung ist automatisch ein gutes
Nachahmungsbeispiel. Vor dem Training Schema und Regeln prüfen, Dubletten
entfernen sowie `voided` und `training_compatible` beachten. Archivieren startet
kein Modelltraining.

Am 18.10.2026 wurden zusätzlich drei abgeschlossene KI-no-Partien rein lesend
aus D1 übernommen: zwei Siege und eine abgebrochene Partie. Die vollständigen
Nutzlasten und ihre Prüfsummen wurden geprüft; die Cloudflare-Quelldaten blieben
erhalten. Für das Demonstrationstraining liefern die jeweils neuesten Revisionen
der beiden Siege zusammen 124 kompatible menschliche Entscheidungen.

Einzelheiten zu Zugang, manuellen Läufen und Grenzen stehen in
[docs/KI-CLOUD.md](../../../docs/KI-CLOUD.md).
