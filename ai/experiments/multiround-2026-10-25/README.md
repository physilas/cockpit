# Mehr-Runden-Planung: abgeschlossener Versuch vom 25. Oktober 2026

Assistenzprofil 10 verwendet unveränderte Crew-1-Netzgewichte und ergänzt in den
letzten drei Runden eine öffentliche Fortsetzungsplanung. Planercode:
`efc9e6a`. Es wurden weder Netzarchitektur noch Eingangsmerkmale geändert.

| Vergleich | Seeds ab | Gepaarte Fälle | Verbessert / schlechter | Änderung | 95-%-Intervall |
| --- | ---: | ---: | ---: | ---: | ---: |
| [Erste Probe](screen.json) | 11.007.000 | 560 | 12 / 5 | +1,25 pp | −0,67 bis +3,17 pp |
| [Größere Folgeprobe](confirmation.json) | 11.008.000 | 2.800 | 48 / 36 | +0,43 pp | −0,45 bis +1,30 pp |

Die zweite Probe verwendete denselben Code und neue Seeds. Die kleinen positiven
Punktschätzungen belegen noch keinen verlässlichen Gesamtfortschritt. Crew 1
bleibt deshalb das freigegebene Standardmodell; Profil 10 erscheint nicht als
neues Modell im Singleplayer. Die für eine Freigabe reservierten Kohorten ab
12.000.000 und 13.000.000 wurden nicht benutzt.

Beide Berichte verwenden vier Routen (HND grün, LHR grün, YUL grün, MUC_T3),
Selbstspiel und beide Rollen mit Heuristik, Crew 1 und stochastischer Crew 1.
Ein Paar bedeutet zwei tatsächlich gespielte Partien. Protokoll 2 clustert die
Intervalle über alle Routen, Rollen und Partner mit gleichem Anfangs-Seed.
Die Zahlen sagen keine menschliche Gewinnrate voraus.

187 Tests bestanden. Der Planer wurde auch in Pyodide geprüft, einschließlich
Quellfingerabdruck und Python/Browser-Aktionsparität. Ein geprüftes Beispiel
benötigte im Browser 141 ms. Die Läufe blieben bei einem Job mit sechs Workern,
je 50 % Rechenzeit, einem Torch-Thread und niedriger Prozesspriorität.
Nach Abschluss sind die eigenen Vergleichs- und Testserverprozesse beendet.
Die automatische Fortsetzung bleibt pausiert. Es wurde kein Modultraining
begonnen; der KI-Adapter unterstützt weiterhin ausschließlich Grundspiel-Routen
und weist Module sowie Fähigkeitskarten ausdrücklich ab.

Details und Grenzen: [KI-MEHRRUNDENPLANUNG.md](../../../docs/KI-MEHRRUNDENPLANUNG.md).
