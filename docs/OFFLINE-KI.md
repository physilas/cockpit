# Mit der KI auf dem iPhone offline spielen

Die KI berechnet ihre Züge bereits im Browser. Für einen Offline-Neustart müssen
zusätzlich zum Modell die Python/WASM-Laufzeit und die App gespeichert sein.
Die bisherigen CDN-Dateien waren nicht Teil des Service-Worker-Caches.

1. Die aktuelle Website in Safari öffnen und zum Home-Bildschirm hinzufügen.
2. Fly Team über dieses App-Symbol öffnen. Bei einem Update gegebenenfalls noch
   einmal schließen und öffnen, damit die neue App-Version erscheint.
3. Im Hauptmenü **„Alle 5 Crews offline speichern“** antippen und die App geöffnet
   lassen, bis **„Alle 5 Crews offline verfügbar“** erscheint.
4. Danach können auch neue KI-Partien ohne Internet gestartet werden.

## Gemessener Speicherbedarf

Dezimale MB (1 MB = 1.000.000 Bytes), Dateiinhalte vor Browser-Verwaltungsaufwand:

| Datei/Paket | MB |
| --- | ---: |
| Crew 1 | 1,79 |
| Crew 2 | 3,16 |
| Crew 3 | 3,16 |
| Crew 4 | 3,16 |
| Crew 5 · Navigator | 3,16 |
| Alle fünf Crews, gemeinsame Gewichte nur einmal | 11,26 |
| Gemeinsame Python/WASM-Laufzeit einschließlich PyYAML | 14,27 |
| Vollständiges Offline-Paket einschließlich App, Regeln und Routenbildern | ca. 30,5 |

Crew 4 und 5 verwenden dieselbe Gewichtsdatei, aber unterschiedliche Planungslogik.
Die Laufzeit wird ebenfalls nur einmal gespeichert. Dies sind Speichergrößen der
Dateien, keine Messung des Arbeitsspeichers während einer Partie. Browser können
Dateien während des Downloads komprimieren und benötigen zusätzlichen Speicher
für Cache-Verwaltung und lokale Spielstände.

Der Offline-Download muss in der Home-Bildschirm-App selbst erfolgen, weil deren
Speicher auf iOS vom Safari-Speicher getrennt sein kann. Die App bittet, soweit
unterstützt, um dauerhaften Speicher. iOS kann Website-Daten bei Speicherdruck
löschen; die Anzeige prüft deshalb beim Öffnen und Wiederkehren alle benötigten
Cache-Einträge erneut. Nach Löschen der App-/Website-Daten erneut herunterladen.
Multiplayer-Verbindungen und Cloud-Übertragung benötigen weiterhin Internet.

## Umsetzung und Prüfung am 28. Oktober 2026

- Unveränderte Pyodide-Version 0.26.1 lokal ausgeliefert; kein Laufzeit-CDN für KI-Partien.
- Download nur der fünf sichtbaren Crews, mit vier eindeutigen Gewichtsdateien.
- SHA-256- und Größenprüfung jeder heruntergeladenen Laufzeit-/Gewichtsdatei.
- Abgebrochene Downloads wiederaufnehmbar; klare Meldung bei fehlendem Speicher.
- Unveränderliche Laufzeit und Gewichte bleiben beim App-Update gespeichert.
- 13 gezielte Tests bestanden, einschließlich Browser/PyTorch-Parität für 96 Entscheidungen.
- Im Browser bei abgeschaltetem lokalen HTTP-Server die App neu geladen, eine
  **neue GIG-Partie mit Wind, Kontrolle und Crew 5** gestartet und den ersten
  KI-Zug ausgeführt. Auch die finale App-Version erneut ohne Server geladen.
- Physisches iPhone nicht verfügbar; der Flugmodus-Test auf dem iPhone steht noch aus.
- Gemessene maximale Temperatur während der gezielten Tests: 62,77 °C.

Prüfbilder: [Offline-Anzeige](pruefbilder/offline-paket-2026-10-28.jpg),
[Offline-Partie mit erstem KI-Zug](pruefbilder/offline-ki-rio-2026-10-28.jpg).

## Entwicklung

`make build` (bzw. `python build_pwa.py`) bündelt die Engine und erzeugt das
Offline-Inventar mit Dateigrößen und SHA-256. Das bisherige `build.py` bleibt
unverändert, da veröffentlichte Strategie-Nachweise seinen Dateiinhalt binden.
Die neue Inventarversion ist Teil des Service-Worker-Cache-Namens und wird als
importierte Worker-Abhängigkeit bei Updates berücksichtigt.

Prüfen: `python -m unittest discover -s tests -p test_offline_pack.py -v` und
`node tests/offline-pack.cjs`. Die Worker-Prüfung verwendet Cache-/Netzwerk-Mocks;
der oben beschriebene Browser-Test lief separat mit der echten WASM-Laufzeit.

Primärquellen:
- [WebKit: Speicherpolitik und persistenter Speicher](https://webkit.org/blog/14403/updates-to-storage-policy/)
- [WebKit: Home-Screen-Speicher und Safari](https://webkit.org/tracking-prevention/)
- [Pyodide 0.26.1: lokale Bereitstellung](https://pyodide.org/en/0.26.1/usage/downloading-and-deploying.html)
