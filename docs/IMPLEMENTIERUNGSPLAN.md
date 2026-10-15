# Sky Team: Landungen und Zusatzfunktionen

Stand: 15. Oktober 2026. Grundlage: das bereitgestellte **Sky Team Flight Log**, insbesondere S. 2–8, die acht nachgereichten Flughafenfotos sowie die [vom Verlag gepflegten Regeln bei Dized](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/sky-team). Die Schwierigkeitsfarben bezeichnen den Anspruch beim Spielen, nicht den Aufwand beim Programmieren.

## Jetzt umgesetzt

Der Ablauf lautet **Menü → Landung auswählen → Flug vorbereiten → Spiel**. Beide Spielmodi verwenden denselben Katalog. Der Host wählt im Multiplayer vor dem Erzeugen des Einladungscodes. Bei einer neuen Landung während einer Verbindung wartet der Co-Pilot auf die Auswahl des Hosts.

- Alle **21 Varianten an 11 Flughäfen**, mit frei lizenzierten Stadtpanoramen und Bildnachweisen, deutscher Kurzbeschreibung, Schwierigkeitsfarbe, Modulvorgaben und Anzahl der Fähigkeitskarten.
- Filter nach Schwierigkeit, Suche nach Stadt/Code/Flughafen und ein eigener Bereich für die bisherigen Strecken MUC, FRA und LHR.
- Alle **21 Originalstrecken** aus den acht Flughafenfotos übertragen: Streckenlänge, Flugzeugverteilung, Verkehrswürfel und Kurven. Beide Höhenleisten sind ebenfalls erfasst: Grün/Gelb mit Neuwurf bei 6000 und 2000 Fuß, Rot/Schwarz nur bei 6000 Fuß. **YUL, LHR und HND grün** benötigen keine weiteren Module und sind als Grundspiel-Landungen spielbar. Die anderen 18 Varianten starten ausdrücklich mit **Übungsregeln**, solange ihre Zusatzmodule und Karten fehlen. Die ursprünglichen Mock-Daten bleiben isoliert für spätere Modultests verfügbar.
- Die sechs bei Dized beschriebenen Fähigkeitskarten können als **Set-Entwurf** vorgemerkt werden. Die Auswahl ist optional, auf die vorgesehene Kartenzahl begrenzt und wird lokal gespeichert. **Karteneffekte und Zusatzmodule sind noch nicht aktiv.** Der Übungsflug startet auch ohne vollständigen Set-Entwurf.
- Übungserfolge werden lokal gespeichert und als solche angezeigt. Sie sind getrennt von späteren Erfolgen auf verifizierten Strecken.

Die Fotos schließen die Lücke bei den offiziellen Entfernungsleisten. Die ursprünglichen drei App-Strecken enthalten weiterhin eigene beziehungsweise teilweise angenommene Daten und sind separat auswählbar. Die Regeltexte der sechs Fähigkeitskarten sind durch Dized verfügbar; fehlende Kartenscans blockieren ihre spätere Implementierung nicht. Eine belegte Abweichung zum englischen PDF wurde korrigiert: **HND rot benötigt Kerosin und Praktikant**, wie auf dem fotografierten Bauteil und in den [Dized-Regeln für rote Szenarien](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/WGi9kz_jRBSASNcJUa96yw/red-scenarios-elite-pilots-only) angegeben.

## Funktionen nach Implementierungsaufwand

Die Schätzungen gelten für Umsetzung einschließlich sinnvoller Engine-Tests und Prüfung beider Browser-Spielmodi. Sie sind Richtwerte in konzentrierten Arbeitstagen, keine Terminversprechen. Abhängige Arbeiten dürfen sich überschneiden; die Werte sind deshalb nicht einfach zu addieren.

| Rang | Funktion | Aufwand | Umsetzung und wesentliche Schwierigkeit |
| --- | --- | --- | --- |
| 1 | Erfolgsmarkierungen | Sehr gering; umgesetzt | Lokaler Eintrag je Szenario und Streckentyp. Später Profil-/Cloudspeicher optional. |
| 2 | Kurven und unterschiedliche Streckenlängen | Gering; Grundfunktion vorhanden | Reine Streckendaten. Beim Vorrücken jedes überflogene Feld prüfen; bei Bewegung 0 kein Kurvenzwang. Originaldaten aus den Fotos sind jetzt hinterlegt. |
| 3 | Verkehrswürfel vervollständigen | Gering; umgesetzt | Mehrfachwürfe und Rundenphase existieren. Das offizielle Regelprofil begrenzt den Vorrat auf 12 Flugzeuge und setzt einen zu großen Wurf auf das Flughafenfeld. Eigene Strecken behalten ihr bisheriges Verhalten. |
| 4 | Kerosin | Gering bis mittel, ca. 1–2 Tage | Start bei 20; gemeinsames Würfelfeld; sofortiger Verbrauch entsprechend dem Würfel. Ohne Würfel am Rundenende 6 verbrauchen. Bei leerem Tank sofort verlieren, auch in der letzten Runde. |
| 5 | Kerosinleck | Gering nach Kerosin, ca. 0,5–1 Tag | Alternative Verbrauchsregel: Differenz der Triebwerkswürfel plus 1. Kerosinfeld deaktivieren; normalen Verbrauch ersetzen, nicht addieren. |
| 6 | Einfache Fähigkeitskarten | Gering bis mittel, ca. 1–3 Tage für vier Karten | Kontrolle, Anpassung, Voraussicht, Meisterschaft: vorhandene Würfel-/Kaffee-/Neuwurfaktionen ergänzen. Einmalige Auslösung und begrenzte Ressourcen sorgfältig prüfen. |
| 7 | Wind | Mittel, ca. 1–2 Tage | Persistente Position auf einem Windring. Nach dem Ruder anhand der aktuellen absoluten Fluglage drehen; Modifikator zur Triebwerkssumme addieren, auch beim Landen. Ringwerte anhand des Bauteils beziehungsweise der Dized-Abbildung erfassen. |
| 8 | Eisbremsen | Mittel, ca. 1–2 Tage | Eigenes Bremsenlayout mit Würfelpaaren gleicher Zahl in derselben Runde; Reihenfolge und Rücksetzen unvollständiger Paare. Zusätzliche Siegbedingung: Bremsmarker hinter der 5; Geschwindigkeit strikt darunter. |
| 9 | Zusammenarbeit | Mittel bis hoch, ca. 1–2 Tage | Koordinierter Würfelwerttausch mit den verdeckten Würfeln beider Rollen. Eigener Ablauf für Pass & Play und Multiplayer; einmal pro Runde, ohne regulären Zugverbrauch. |
| 10 | Praktikant | Hoch, ca. 2–3 Tage | Geordneter Vorrat zufällig aufgedeckter Zahlenplättchen, Zugriff von beiden Seiten, Trainingsfeld je Rolle und anschließende Plättchenplatzierung. Sonderregeln für Kaffee, Konzentration und Zahlengleichheit; zusätzliche Siegbedingung. |
| 11 | Synchronisation | Hoch, ca. 1–2 Tage nach Aktionswarteschlange | Zusatzwürfel nach Fahrwerk + Klappen; Co-Pilot platziert unabhängig von der Feldfarbe. Das erweitert den bisherigen festen Pool von acht Aktionen und benötigt eine gesonderte Aktionsquelle. |
| 12 | Echtzeit | Am höchsten im Multiplayer, ca. 2–4 Tage | 60 Sekunden ab den Spielerwürfen; automatische Rundenauswertung auch mit ungespielten Würfeln. Der Host prüft eine feste Deadline; verspätete Aktionen werden abgewiesen. Hintergrundtabs und Verbindungsprobleme dürfen den Timer nicht verlängern. |

### Warum Programmieraufwand und Einführungsreihenfolge abweichen

Das Kerosinleck ist isoliert einfach, setzt aber die Kerosin-Infrastruktur voraus. Synchronisation hat einen kurzen Regeltext, greift jedoch in die Aktions- und Rollenverwaltung ein. Echtzeit wirkt im Einzelbrowser wie ein einfacher Countdown, braucht im Multiplayer aber eine verbindliche Zeitprüfung und eine andere Bedingung für das Rundenende.

## Empfohlene Reihenfolge

### 1. Regelprofile und verlässliche Streckendaten

**Erledigt:** Katalog, Originalstrecken und Höhenleisten stehen. Die Kurven-/Verkehrsregeln sind mit Logbuch und Dized abgeglichen. Die Logbuch-Strecken verwenden ein offizielles Verkehrsprofil: Bei zu großem Wurf landet das neue Flugzeug auf dem Flughafenfeld; ohne Flugzeuge im 12er-Vorrat entfällt das Setzen. Entfernte Flugzeuge werden dadurch wieder verfügbar. Die vorhandenen eigenen Strecken behalten ihr bisheriges Verkehrsprofil.

Abnahme: Bewegung 0/1/2, zwei Kurvenfelder, wiederholtes Stehenbleiben, mehrere Verkehrssymbole, zu großer Wurf, leerer Vorrat, zurückgegebene Flugzeuge. Jede Originalstrecke und jede isolierte Mock-Strecke bleibt separat startbar.

### 2. Kerosin, danach Kerosinleck

Eine Ressourcenanzeige und ein zusätzliches gemeinsames Würfelfeld ergänzen. Die Anzeige zeigt den aktuellen Vorrat und den fälligen Verbrauch. Das Leck verwendet dieselbe Ressource mit einer anderen Verbrauchsstrategie.

Abnahme: Verbrauch durch Aktion nur einmal; −6 ohne Aktion; genau 0 führt zum Verlust; Leck bei gleichen und weit auseinanderliegenden Triebwerkswerten; kein doppelter Verbrauch; letzte Runde und Modulwechsel.

Damit lassen sich zuerst **OSL grün und PRG grün**, danach **PRG gelb und ATL gelb** vollständig mit ihren Modulregeln testen. Die Originalstrecken sind bereits verfügbar; Karteneffekte werden erst nach ihrer Implementierung aktiviert.

### 3. Vier einfache Karten und verbindliche Set-Auswahl

Zunächst Kontrolle und Anpassung, danach Voraussicht und Meisterschaft. Bei echten Partien die exakt geforderte Zahl unterschiedlicher implementierter Karten validieren. Set und verbleibende Nutzungen in den Spielzustand aufnehmen und an beide Rollen übertragen. Der aktuelle lokale Set-Entwurf wird dann zu einer wirksamen Spielkonfiguration.

| Karte | Effekt in eigenen Worten | Besonderer Test |
| --- | --- | --- |
| Kontrolle / Control | Gleiche Ruderwürfel geben eine Kaffeetasse. | Einmal nach Auflösung; maximaler Kaffeevorrat. |
| Anpassung / Adaptation | Jede Rolle darf einmal pro Partie einen freien Würfel auf seine Gegenseite drehen. | 1↔6, 2↔5, 3↔4; eigener Nutzungszähler je Rolle. |
| Voraussicht / Anticipation | Der Startspieler darf vor seiner ersten Platzierung einen eigenen Würfel neu werfen. | Nur in diesem Zeitfenster und einmal pro Runde. |
| Meisterschaft / Mastery | Gleiche Triebwerkswürfel geben ein verfügbares Neuwurf-Plättchen. | Plättchen auf Höhenleiste oder im Cockpit-Vorrat zählen nicht als verfügbar. |
| Zusammenarbeit / Working Together | Einmal pro Runde tauschen die Rollen die Werte je eines freien Würfels. | Verdeckte Auswahl; beide Werte erst nach vollständiger Wahl tauschen. |
| Synchronisation / Synchronisation | Nach mindestens einem Fahrwerk- und einem Klappenwürfel wird ein Zusatzwürfel geworfen und durch den Co-Piloten platziert. | Beide Auslösereihenfolgen; genau ein Bonus; Feldfarbe ignorieren, übrige Platzierungsregeln einhalten. |

Die deutschen Kartennamen sind Arbeitsübersetzungen. Referenztexte: [Kontrolle](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/Zzi0Z46LSDSbmdU7txo2NA/control-special-ability), [Anpassung](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/NGq-uKeATOaeW7glEEHg1Q/adaptation-special-ability), [Voraussicht](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/-ROoYoI1QBe7KMclsZs-sA/anticipation-special-ability), [Meisterschaft](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/rfj57n1yQP-jSbISfRmOoA/mastery-special-ability), [Zusammenarbeit](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/oCSa8_gAT761jRZKCsxvEg/working-together-special-ability), [Synchronisation](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/3uymNf7pTVGe7NxLUaaFfw/synchronisation-special-ability).

### 4. Wind, danach Eisbremsen

Ein Windinstrument und ein austauschbares Bremsenpanel ergänzen. Beide erweitern die Geschwindigkeitsberechnung, deshalb anschließend gezielt kombiniert prüfen. Beispiele: **GIG gelb**, **KEF gelb**, dann **GIG rot, OSL rot, TGU rot und KEF schwarz**.

Abnahme Wind: unveränderte, aber schiefe Fluglage dreht den Ring erneut; Ringumlauf; Geschwindigkeitsänderung in normaler und letzter Runde. Abnahme Eis: passendes/unpassendes Paar, Paar nur innerhalb derselben Runde, mehrere Aktivierungen, unvollständige Bremse bei der Landung, Geschwindigkeit genau am Grenzwert.

### 5. Erweiterte Aktionsabläufe: Praktikant und die zwei übrigen Karten

Eine kleine Warteschlange für verpflichtende Zusatzaktionen einführen, getrennt vom regulären Rollenwechsel. Darauf Praktikanten-Training und Synchronisation aufbauen. Zusammenarbeit ergänzt einen eigenen koordinierten Tauschdialog. Die Regeln bleiben in Python; Browser und Transport zeigen die erlaubten Schritte an.

Abnahme Praktikant: Zugriff von beiden Seiten, unzulässige gleiche Zahl, keine Kaffeeänderung, keine Konzentration, Plättchenplatzierung einschließlich Pflichtfeldern, vollständige Ausbildung als Siegbedingung. Danach alle Karten paarweise mit den Modulen prüfen, die sie verändern.

### 6. Echtzeit zuletzt

Der Host speichert eine Deadline im Spielzustand und prüft sie vor jeder Aktion. Die Browser zeigen die verbleibende Zeit an. Nach Ablauf endet die Runde automatisch; fehlende Ruder-/Triebwerkswürfel führen zum Verlust, andere ungespielte Würfel werden ignoriert. Der bestehende manuelle Rundenabschluss und die Pflicht, alle acht Würfel zu legen, brauchen dafür eine gezielte Erweiterung.

Abnahme: letzte Millisekunde, verspätetes Netzwerkpaket, Hintergrundtab, Timer während Zusatzaktionen, fehlende Pflichtfelder, bereits beendetes Spiel. Beispiele: **PBH rot/schwarz und KUL schwarz**. Pass & Play benötigt dabei einen praxistauglichen Sichtwechsel innerhalb der 60 Sekunden.

## Vollständiger Szenariokatalog

Module und Kartenanzahlen sind aus den Symbolen der PDF-Seiten 6–8 übernommen und mit den Fotos abgeglichen. HND rot wurde nach Foto und Dized um Kerosin ergänzt. Verkehr und Kurven sind Streckeneffekte und stehen nicht in der Modulspalte; ihre konkrete Verteilung ist in [STRECKENDATEN.md](STRECKENDATEN.md) dokumentiert.

| Seite | Farbe | Flughafen | Zusatzmodule | Karten |
| --- | --- | --- | --- | ---: |
| 6 | Grün | YUL Montréal-Trudeau | Keine | 0 |
| 6 | Grün | LHR Heathrow | Keine | 0 |
| 6 | Grün | HND Haneda | Keine | 0 |
| 6 | Grün | OSL Gardermoen | Kerosin | 0 |
| 6 | Grün | ATL Hartsfield-Jackson | Praktikant | 0 |
| 6 | Grün | PRG Václav Havel | Kerosin | 2 |
| 7 | Gelb | LHR Heathrow | Praktikant | 0 |
| 7 | Gelb | TGU Toncontín | Kerosin | 2 |
| 7 | Gelb | GIG Galeão | Wind | 1 |
| 7 | Gelb | KEF Keflavík | Eisbremsen | 1 |
| 7 | Gelb | PRG Václav Havel | Kerosinleck | 2 |
| 7 | Gelb | KUL Kuala Lumpur | Kerosin | 1 |
| 7 | Gelb | ATL Hartsfield-Jackson | Kerosinleck | 1 |
| 8 | Rot | PBH Paro | Kerosin, Echtzeit | 2 |
| 8 | Rot | HND Haneda | Kerosin, Praktikant | 1 |
| 8 | Rot | GIG Galeão | Wind, Kerosinleck | 2 |
| 8 | Rot | OSL Gardermoen | Kerosinleck, Eisbremsen | 2 |
| 8 | Rot | TGU Toncontín | Kerosin, Wind | 2 |
| 8 | Schwarz | KEF Keflavík | Wind, Eisbremsen | 2 |
| 8 | Schwarz | KUL Kuala Lumpur | Kerosin, Echtzeit | 2 |
| 8 | Schwarz | PBH Paro | Kerosin, Echtzeit | 2 |

## Technische Form und weitere Freischaltung

`backend/landekatalog.json` ist die gemeinsame Quelle für Szenarioidentität, Texte, Modulvorgaben, Kartenzahl und Originalstrecken (`track`). Die erfundenen `mock_track`-Werte bleiben ausschließlich als Test-Fixtures erhalten. Für jede fotografierte Strecke sind Dateiname und SHA-256 der Quelle hinterlegt. `backend/katalog.py` liefert Engine-Konfigurationen; `build.py` bündelt dieselben Daten für Pyodide und erzeugt den Browserkatalog. Eigene YAML-Strecken kommen automatisch dazu.

Die IDs enthalten Flughafen **und** Farbe, etwa `LHR-green` und `LHR-yellow`. Die bisherige eigene LHR-Strecke hat die getrennte ID `custom-LHR`. Die Engine-Codes heißen `LOG_LHR_GREEN` für das Original und `MOCK_LHR_GREEN` für die erfundene Teststrecke. So werden Varianten und Datenquellen nicht verwechselt.

Originalstrecke und vollständiges Regelset sind getrennte Eigenschaften: `mock` ist bei allen 21 Originalen `false`; `practice` beziehungsweise `uebung` kennzeichnet die 18 Varianten mit noch fehlenden Modulen/Karteneffekten. Übungserfolge verwenden einen eigenen Speicherbereich. Zum Freischalten einer Variante ihre erforderlichen Module und Karten implementieren, die Startkonfiguration in Python validieren und erst dann den Übungsstatus aufheben. Die Strecke und Bilder brauchen dabei nicht erneut erfasst zu werden.

Für neue Regeln schmale, explizite Erweiterungspunkte verwenden: nach Ruderauflösung, nach Triebwerksbelegung, bei der Geschwindigkeitsberechnung, am Rundenende und bei der Siegprüfung. Keine zweite Regelimplementierung im JavaScript.

Gezielte Mock-Strecken pro neuem Modul beibehalten: eine leichte Strecke isoliert die Regel, eine zweite provoziert Grenzfälle. Vor dem Freischalten kombinierter Landungen jeweils die betroffenen Modulpaare prüfen.

## Regelreferenzen für die nächsten Schritte

- [Verkehrswürfel](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/_WPce283SP63APWmCnFSPA/traffic-die-approach-track-effect)
- [Kerosin](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/PWqgL6m9SFiIlQRuIMrtFQ/module-kerosene) und [Kerosinleck](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/cqr_4ZwOQ461R5wnZgU6WA/module-kerosene-leak)
- [Wind](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/JNNK7ICVTFGUv5cFhJLVyw/module-wind) und [Eisbremsen](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/RbvY4rs7T5SsHdlAY_VGQw/module-ice-breaks)
- [Praktikant](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/CZdwSo0GSFKGRTWk4dFXug/module-intern) und [Echtzeit](https://rules.dized.com/game/HPLDQm89RB-4e9yi2MQQGw/Uf2D_8IwSQSruNWqIQtaew/module-real-time)
