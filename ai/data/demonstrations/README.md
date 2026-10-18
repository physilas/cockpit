# KI-no-Beispielpartien

Dieser Ordner archiviert vollständige Aufzeichnungen für späteres
Demonstrationstraining. Die JSON-Dateien entsprechen bytegenau der in Cloudflare
D1 gespeicherten `payload`, einschließlich Schema, Einwilligung, Beobachtungen,
Aktionsmasken, Spielausgang und rückgängig gemachter Ereignisse. Die
installationsbezogene Datenbankkennung `participant_hash` und Upload-Zugangsdaten
sind nicht Bestandteil des Archivs.

## MUC-Sieg vom 18.10.2026

Datei: [2026-10-18-MUC-605a503f-d565-4450-b62e-a05031efc5fb.json](2026-10-18-MUC-605a503f-d565-4450-b62e-a05031efc5fb.json)

- Quelle: D1-Datenbank `flyteam-training`, Tabelle `training_sessions`.
- Session: `605a503f-d565-4450-b62e-a05031efc5fb`, Revision 70.
- Modus: `examples` (KI-no); Strecke: `custom-MUC`; Ergebnis: `gewonnen`.
- Letzter Eingang in D1: `2026-10-18T10:17:18.315Z`.
- Umfang: 283.168 Bytes, 68 Ereignisse.
- 60 nicht zurückgenommene, schema-kompatible Entscheidungen: 56 Platzierungen
  und vier Kaffeeaktionen, jeweils 30 Entscheidungen pro Rolle.
- Eine zurückgenommene Kaffeeaktion und sieben Rundenabschlüsse bleiben für die
  Nachvollziehbarkeit erhalten, zählen aber nicht zu den Lernentscheidungen.

Für den späteren Trainingsimport nur Ereignisse verwenden, bei denen
`voided == false`, `training_compatible == true` und `action_id != null` gilt.
Zusätzlich Schema und Aktionsmaskenversion mit dem jeweiligen Trainer prüfen.
Ein gewonnener Spielausgang kennzeichnet eine erfolgreiche Partie; er bewertet
nicht jeden einzelnen Zug als optimal. Mit `--demo-data ai/data` kann der
PPO-Trainer die gewonnenen, kompatiblen KI-no-Partien als vorsichtig gewichteten
Nachahmungsterm einlesen. Einzelheiten und Resume-Regeln stehen in
[ai/README.md](../../README.md#gewonnene-ki-no-partien-im-ppo-training).

Beim Export wurden das vollständige Schema einschließlich Feature-Reihenfolge,
Aktions-IDs und Slots, die Maskenversion, Beobachtungsdimensionen, endliche
Beobachtungswerte sowie die Übereinstimmung der aufgezeichneten Aktionen mit den
IDs und erlaubten Aktionen geprüft. Dies ist keine vollständige Wiederholung der
Partie in der Engine.

Die Prüfsumme der unveränderten JSON-Datei steht in `SHA256SUMS`. Prüfung aus
diesem Ordner:

```bash
shasum -a 256 -c SHA256SUMS
```
