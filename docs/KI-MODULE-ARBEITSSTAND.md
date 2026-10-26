# Arbeitsstand: Vier Crews veröffentlicht, Trainingsauftrag abgeschlossen

## Bedienung vom 26.10.: Seed-Neustart, Quoten und sichtbare Spielzüge

Der neue UI-Auftrag ergänzt das Neustart-Popup um eine standardmäßig leere
Checkbox für denselben Seed. Dafür bleibt ausschließlich lokal ein Anfangs-
Snapshot einschließlich Engine-RNG erhalten; bei gleicher Zugfolge wiederholen
sich auch die späteren Würfe. Ohne Haken wird eine frische Partie erzeugt.
Der private Anfangszustand liegt getrennt von KI-Aufzeichnungen/Cloud-Uploads;
im Multiplayer verbleibt er beim Host. Lokales Fortsetzen erhält ihn. Alte
Spielstände ohne diesen Anfangszustand bieten die Option nicht an.

Die Singleplayer-Landungswahl zeigt nur die Bildgalerie. Die gemessene
KI-Selbstspielquote steht unter jeder Route, bei mehreren Kartensets als
Min/Max-Spanne der erlaubten Einzelwerte. Erst die letzte noch fehlende Karte
zeigt je Auswahl deren exakte Setquote. Bei einer Karte stehen die Werte sofort
an den sechs Karten; ohne Karten entfällt die Kartenansicht. Angezeigt werden
die bestehenden Entwicklungswerte, keine neu berechnete menschliche Siegchance.
Vier Crews, Gewichte und freigegebene Falllisten bleiben unverändert.

Ein Neuwurf-Hinweis bleibt beim Blick aufs Spielfeld oben sichtbar. Ein
Kopfleisten-Symbol öffnet das lokale Flugprotokoll; Fehler bleiben zusätzlich
kurz sichtbar. Kurze Würfelbewegungen und wegfliegende geräumte Flugzeuge
verdeutlichen öffentliche Zustandsänderungen, ohne Engine/RNG/Politik zu ändern.
Systemseitig reduzierte Bewegung wird berücksichtigt. Die Schaltfläche für die
nächste Runde erscheint unten rechts erst bei vollständig verbrauchten Händen
und ohne offenen Neuwurf-/Kartendialog. Rundenwechsel und Rückgängig werden nicht
als neue Funkräumungen animiert.

Geprüft mit vier erfolgreichen Chrome-Suiten: neue Bedienung/Quoten/Animationen,
KI-Feedback/Undo/Fortsetzen, alle vier realen Crew-Modelle einschließlich
Praktikantenlayout sowie gemeinsame Galerie/Neuwurf/Multiplayer. Der Host-Test
wiederholt auch Verkehr, Spielerwürfel und RNG exakt bei gleicher Seed-Option;
der Gast erhält keinen Anfangssnapshot. Hinzu kommen sechs lokale Speicher-
Tests, die Node-Fall-/Aktionsverträge, Syntaxprüfung und erneuerter SW-Build.
Die Neustart-Bestätigung bleibt während des KI-Modellladens modal, unterbindet
Doppelklick/Escape und erhält bei Ladefehlern die bisherige Partie.

Trainingsauftrag bleibt abgeschlossen; kein neuer Trainingsjob und keine
Reaktivierung der pausierten Automation durch diese UI-Arbeit.


## Auftrag vom 26.10. abgeschlossen – kein Trainingsjob aktiv

UI und vier kanonische Crews sind bereits mit 8dc081c / 7e56b19 nach main
gepusht und live bytegenau geprüft. Alle beauftragten UI-Funktionen und
21 Standardrouten/186 erlaubte Kartenfälle je Crew stehen bereit. Genau eine
sichtbare Version pro Crew; Archive bleiben für Backups und alte Spielstände.

Die ergänzend beauftragte Vier-Crew-Liga ist regulär beendet, Exit0:
80.113 **eigene** Lernentscheidungen, 4.590 Trainingspartien/38 Updates,
567,40 Trainingssekunden und 853,37 Sekunden Gesamtwandzeit. Quelle war die
veröffentlichte Crew4 v1, neue Phase/Adam/Zähler, Profil12/Abstand4. Alle acht
Partner/Rollen-Kombinationen bekamen ungefähr10.000 eigene Lernentscheidungen;
deren exakte Summe ist80.113. Alle186 Fälle tatsächlich besucht. Grundlage und
feste Partner blieben exakt unverändert. Gewähltes best.pt ist der letzte
80.113-Stand nach dem vorab festgelegten Kriterium. Kein exaktes Resume behauptet.

Alle16 geordneten Paarungen wurden vor und nach dem Lernen geprüft: jeweils
21 Routen, die lexikalisch erste erlaubte Kartenkombination, je2 Spiele, je672
Spiele. Die378 unveränderten Kontrollen ohne Crew4 stimmen exakt in Status und
Verlustgrund überein und zählen nicht als zusätzliche unabhängige Evidenz.
In den294 gepaarten Spielen mit Crew4: sechs zusätzliche Siege, sieben verlorene
alte Siege. Kein durchgängiger Kooperationsgewinn. Endmatrix verwendet tatsächlich
best.pt und protokolliert dessen Modell-SHA.

Der folgende vollständige frische Vergleich ist ebenfalls regulär fertig,
Exit0: je10 Spiele auf allen186 Fällen, **3.720 Spiele**, Seeds14.820.050+100*i
mit Offsets50..59. Veröffentlichte Crew4 gewinnt93/1.860, Liga68/1.860;
routeweise Mittel .161746→.135556. Kein Durchschnitt als Ersatz für Einzelwerte;
alle Fälle/Quoten/gepaarten Episoden gespeichert. 36 neu gewonnene Partien gegen
61 verlorene alte Siege. Deshalb **keine neue Crew4-v2**, v1 bleibt verfügbar.
Der Qualitätsrückschritt wird nicht versteckt und kein neuer best-Stand erfunden.
Berichte `league-stage1.json`, `league-team-analysis-v1.json`,
`league-fresh-comparison-v1*.json`, `league-fresh-analysis-v1.json` und
`league-publication-decision-v1.json` sind abgeschlossen, nicht mehr laufend.

Die525er-Python-Suite bestand zuvor vollständig; danach acht gezielte
Abschlussprüfungen einschließlich96 erneuter echter Browser-/PyTorch-Vergleiche.
Sechs zusätzliche gezielte Tests der Auswahl-/Publikationslogik bestehen.
Die neue Veröffentlichungsentscheidung weist identische/numerisch gleiche oder
schlechtere Modelle ab; positive Ersatzlogik bewahrt genau vier sichtbare Crews,
Crews1/2/3 und historische Archive. Keine zusätzlichen UI-/Gewichtsänderungen
nach dem live geprüften7e56b19. Metadatenpfade der neuen selection.json-Dateien
sind portabel relativ zum Repo, keine Gewichts-/Ergebnisänderung.

Die bisherige Automation bleibt **PAUSED**. Aktuell kein schwerer Job aktiv;
keine automatische Fortsetzung neu aktivieren. STOP ist weiterhin über
`python -m ai.job_control stop` bedienbar; falls gesetzt, nur bei ausdrücklicher
Fortsetzung clear-stop. Jüngste Ressourcengrenze bleibt8 Worker zu max60%,
Torch1/nice15, ein schwerer Lauf, Metal für PPO erlaubt. Keine E-Mail.

Neue verbrauchte Entwicklung: Variantenvergleich14.820.000+100*i, i0..185,
Offsets0..9; Liga-Fresh14.820.050+100*i, Offsets50..59; feste Phasenprüfungen
14.840.000+100*i je5 und14.860.000+100*i je3; Teamprobe14.880.000+100*i,
i0..20, je2, am Ende ausdrücklich wiederholt. Technischer Smoke14.889.500+100*i,
je1. Qualifikationskohorte ab15.400.000 weiter unbenutzt. Frühere belegte
Qualifikationsbereiche nicht für Training/Debugging/Modellwahl verwenden.

## Vier sichtbare Crews – veröffentlicht

Neue Releases `crew1-allroutes-2026-10-26-v1` bis
`crew4-allroutes-2026-10-26-v1`: genau eine sichtbare Version je Crew,
alle 21 Standardrouten/186 Fälle einschließlich Nullquoten. Genehmigungen
werden nicht auf die neue breite Vorschau übertragen (`quality.approved=false`).
Alle 75 alten Katalogeinträge/Assets bleiben erhalten, aber `ui_hidden=true`;
alte lokale Spielstände können weiterhin ihre exakten historischen Gewichte
laden. Neue sichtbare IDs haben `crew_number=1..4`; Crew 1 bleibt Vorauswahl.
Der Export bewahrt Sichtbarkeitsmetadaten bei späterem Merge.

Der vollständige Vergleich ist Exit 0, 11.160 echte neue Spiele, je zehn pro Fall
und sechs unterschiedlichen Politiken. Zwei Crew-2-Labels aliasieren dieselben
Gewichte und dieselben Episoden; keine zusätzliche unabhängige Evidenz.
Ausgewählt: crew1 / crew2-base / crew3-leak / crew4-trained. Routeweise Mittel
nur als Auswahlstatistik: .10476 / .11111 / .17778 / .13286. Der neue Crew-4-
Stand liegt über alter Crew 4 (.10254), aber nicht über seiner Ausgangsbasis
crew3-intern (.13460): keine konsistente reine Lernverbesserung behaupten.
Alle Einzelquoten und Grenzen in `docs/KI-CREWS-2026-10-26.md` und den Releases.

525 vollständige Python-Tests bestanden in 92,57 s; einschliesslich der fremden
Tests (nicht stagen). 96 echte Browser-/PyTorch-Entscheidungen aller vier
aktuellen Modelle stimmen überein. Dabei wurde ein Erweiterungsfehler im
Browser behoben: auch null gepaddete neue Aktionen gehören ins Maximum der
Referenzlogits. Gezielter Gegenfall und bestehende Modelle sind geprüft.
Echter Chrome testet exakt vier Menüpunkte, alle Fälle inklusive Nullquoten,
echte Aktionen beider Rollen, Privacy, Schwarz ohne Starttoken und vollständige
Praktikantenleiste bei 390×844/320×740. Neuer Bewertungs-Undo bewahrt auch nach
automatischer Alternative beide Bewertungsrücknahmen, ohne Engineänderung;
der gesamte Spielablauf-/Reload-/Fehlerneustarttest besteht erneut.

Veröffentlicht mit **7e56b1925388420666297934068b4beee4dc648c** nach main.
Der erste Upload brach mit HTTP 400 ab; der erneute Git-Upload über HTTP/1.1
mit größerem Postpuffer war erfolgreich. Pages-Run **40255266607** ist erfolgreich.
Katalog, Cacheversion, Singleplayer, Policy, Spielmenü, Enginebundle, Routen und
alle vier tatsächlichen Browserassets sind live bytegenau geprüft. Aktuell vier
sichtbare IDs, jede exakt 186 Fälle. Git-Arbeitsbaum enthält außer der neuen
Dokumentation/Weiterarbeit nur die fünf ausdrücklich geschützten Fremdänderungen.

## Ergänzender Nutzerauftrag: Vier-Crew-Liga

Der Nutzer möchte die vier KIs während des Trainings gegeneinander spielen
lassen. Sky Team ist kooperativ: vorgesehen sind geordnete Teams in beiden
Rollen, nicht ein erfundener kompetitiver Sieg gegeneinander. Crew 4 lernt dabei
mit eingefrorenen Crews 1/2/3 und ihrem aktuellen Selbst als Partner. Der Lernbatch
enthält ausschließlich eigene Crew-4-Entscheidungen; Partneraktionen werden
separat gezählt. Beide Spieler erhalten ihre jeweils eigene öffentliche
Profil-12-Referenz, niemals verdeckte Partneraugen. Die vorhandene generische
Partner-Rolloutfunktion schaltet Partnerassistenz sonst ab; die neue getrennte
PublicLeagueEnv bewahrt hier bewusst beide öffentlichen Referenzen.

Historischer Startstand der mittlerweile abgeschlossenen Liga: einziger schwerer Job
`runs/crew4-league-stage1-2026-10-26`, Log `/tmp/cockpit-crew4-league-stage1.log`.
Quelle ist die tatsächlich veröffentlichte Crew 4 v1; feste Partner aus
`runs/crew-refresh-2026-10-26-v2/league-partners.json` haben exakt die Gewichte
der veröffentlichten Crews 1/2/3. Frischer Adam/Zähler, Profil12/Abstand4,
80.000 eigene Lernentscheidungen oder 600 reine Trainingssekunden. Maximal
8 Worker .6/Torch1/nice15/Metal, kein zweiter schwerer Lauf. Alle acht
Partner/Rollen-Kombinationen sind nach echten Updates in decisions_by_partner_role
belegt; deren Summe entspricht exakt den gespeicherten Lernaktionen. Alle 186
Fälle wurden bereits im Training besucht. Partnergewichte werden nach jedem
Rollout auf Identität geprüft, alte Grundlage bei jedem Speichern. Noch keine
Erfolgsaussage für die Liga. Aktuelle Zähler immer aus dem Log lesen.

Die anfänglichen 16 geordneten Teams sind regulär ausgewertet: 21 Routen,
jeweils die lexikalisch erste erlaubte Kartenkombination, zwei Spiele je Paar
und Route, 672 Spiele insgesamt. Team-Kohorte 14.880.000+100*i, i=0..20;
die gleichen Spiele werden zum Abschluss wiederholt und sind keine zusätzliche
unabhängige Stichprobe. Die abschließende Teamprüfung verwendet den vorab
gewählten best.pt, nicht einfach latest; Modell-SHA steht bei jedem Teamstand.
Die Teilmatrix ersetzt keinen vollständigen 186er-Test.

Liga-Modellwahl: alle186 Fälle zu je3 festen Entwicklungsspielen ab14.860.000
mit Abstand100, Quelle/warm zulässig, Bewertung nach gleichem routeweisen
Kriterium wie zuvor. Nach Ende erfolgt eine NEUE gepaarte Entwicklungsprobe
gegen die veröffentlichte Crew4: 10 Spiele je Fall ab14.820.050+100*i,
also nur bisher unbenutzte Offsets50..59 im früheren Vergleichsbereich.
Erst dann gegebenenfalls neue Crew4-v2-Vorschau, alte v1 nur im Menü archivieren,
Crews1/2/3 unverändert erhalten. Bei identischen Gewichten Kontrolle aliasieren;
kein scheinbar neues Modell verkaufen. Die Abschlusskohorte ab15.400.000 bleibt
unberührt. Automation bleibt PAUSED; STOP bleibt per Nutzerbefehl bedienbar.

## Abgeschlossener erster Trainingslauf vom 26.10.2026

Die Oberfläche ist mit **8dc081cd4ff798b50e534d5ab9cdd896ce7c08ca** nach main
gepusht. Pages-Run 40251230279 ist erfolgreich; sieben veröffentlichte Dateien
(Buildversion, App, Singleplayer, Spielmenü/CSS, Enginebundle, Katalog) wurden
bytegenau live verglichen.

Die erneute ausdrückliche Trainingsanweisung wurde durch `ai.job_control
clear-stop` umgesetzt. **Die frühere Automation bleibt PAUSED**; nur der aktuelle
beauftragte Lauf arbeitet. Abgeschlossener erster schwerer Job:
`runs/crew4-allroutes-stage1-2026-10-26`, Log
`/tmp/cockpit-crew4-allroutes-stage1.log`. Neue PPO-Phase aus dem ursprünglichen
Praktikantenmodell `ai/releases/crew3-current-preview-v2/best.pt`, öffentliche
Umgebung Profil 12/Abstand 4, frischer Adam und Zähler. Keine zusätzliche Schicht,
keine Übernahme eines Forschungswrappers. Bestehender Detailzweig trainiert,
alte Grundlage wird bei jedem Speichern auf exakte Identität geprüft.
630 Curriculum-Einträge wählen zuerst jede der 21 Routen gleich häufig und
innerhalb einer Route jede erlaubte Kartenkombination gleich häufig; 186 Fälle.
Alle sechs Module und sechs Karten sind im Curriculum, einfachere Routen bleiben
als Anker erhalten. Budget 220.000 neue Entscheidungen oder 900 Trainingssekunden,
maximal acht Worker zu .6/Torch1/nice15, PPO auf Metal. Gesamte Wandzeit enthält
zusätzlich Entwicklungsbewertungen. Keine zweite schwere Arbeit gleichzeitig.

Ergebnis der Hauptphase: regulär Exit 0, 220.270 neue Entscheidungen,
6.782 Partien/100 Updates, 838,27 Trainingssekunden und 1.187,90 Sekunden
Gesamtwandzeit. Alle 186 Fälle tatsächlich im Training besucht. Ausgewähltes
best.pt bleibt der 111.052-Stand; Warm/55.666/111.052/166.630/220.270 werden in
report.json mit vollständigen Einzelwerten dokumentiert. Die Gesamtbewertung
verbesserte sich anfangs, nahm später wieder ab: latest ist kein Ersatz für best.
Grundlage blieb exakt unverändert. Der aktuelle Variantenvergleich nutzt nur
best als neu trainierten Kandidaten, getrennte neue Entwicklungsphase.

Der vorangegangene technische Probelauf ist regulär beendet: 212 neue
Entscheidungen/ein echtes Metal-Update, zehn Trainingspartien, Grundlage exakt
unverändert. Dessen Gewichte werden nicht weiterverwendet. Ein Spiel je Fall ist
nur Technik, keine Gewinnqualifikation. Neue Hauptphase verwendet je fünf feste
Entwicklungsspiele pro Fall, ab 14.840.000+100*i für 186 lexikalisch sortierte
Fälle. Auswahl vorab: gleichgewichtetes Mittel der 21 routeweisen Kartenmittel,
danach Grundspielmittel, dann schwächstes Routenmittel als Tie-Break. Es gibt
keine behauptete Mindestquote je Fall. Warmstand bleibt als Kandidat zulässig.

Vorbereitete Quellen in `runs/crew-refresh-2026-10-26-v2/`: originale Crew 1 mit
Schema-3-Adapter (Features/Aktionen sind exakte Präfixe, ursprüngliche Tensoren
bleiben eingefroren), Crew-2-Grund-/Kerosinvariante, Crew-3-Praktikanten-/Leckstand
und bisherige Crew 4. Alle werden ausdrücklich als neue öffentliche Profil-12-
Entwicklungsphase behandelt; keine alte Freigabe oder frühere Einzelquote wird
auf neue Module/Regeln übertragen. Nach dem Training folgt EIN gepaarter
Vergleich aller Kandidaten mit zehn frischen Entwicklungsspielen je Fall,
ab 14.820.000+100*i. Für Crew 4 kommt ausschließlich das nach obigem Kriterium
vorab gewählte best.pt hinzu; latest wird nicht nachträglich hineingetauscht.
Auswahl pro Crew nach demselben festgelegten Kriterium, dann Veröffentlichung
je einer sichtbaren Crew 1/2/3/4 mit allen 21 Routen/186 Fällen als Vorschau,
auch mit Nullquote. Historische Dateien und Belege bleiben archiviert erhalten.
Die Auswertung unter neuen Regeln ist keine unabhängige Qualifikation.

Technik-Testseeds: Probelauf ab 14.889.500+100*i, je ein Spiel/Fall;
separat von Entwicklung und Qualifikation. Die neue Abschlusskohorte ab
15.400.000 bleibt unberührt. Bei „Training und automatische Fortsetzung stoppen“
`python -m ai.job_control stop` setzen und Automation pausieren; STOP nicht ohne
explizite Fortsetzung löschen. Aktuelle Zähler/Quoten immer aus Logs lesen,
laufende Berichte nicht committen.

## Neuer Auftrag vom 26.10.2026 – UI abgeschlossen, Training in Bearbeitung

Der Nutzer hat weitere UI-Verbesserungen und anschließend erneutes Training
von Crew 4 beauftragt. Neue verbindliche Trainingsgrenze: **höchstens acht
CPU-Worker zu jeweils 60 %, Torch-Threads 1, nice 15, ein schwerer Lauf**.
Metal für PPO bleibt erlaubt. Die erneute Trainingsanweisung erlaubt für diesen
Auftrag das ausdrückliche `clear-stop`; der neue Lauf steht oben, die vorherige
Automation bleibt pausiert.

UI-Arbeit (noch nicht als abgeschlossen ausgeben): Neuwurf mit Spielfeldblick
und automatischer leerer Hand, zentrales Spielmenü mit Bestätigungen, dominantes
Endergebnis mit weißem Nebel, lokale Wiederaufnahme nach Reload, komplette
Praktikantenleiste, kein Start-Neuwurfplättchen auf Rot/Schwarz, Bild-/Kartenwahl
wie Mehrspieler. Im Kindergarten soll die letzte unveränderte KI-Aktion bei
erstem 👎 einmal durch die nächstbeste legale, inhaltlich andere Aktion ersetzt
werden; erneutes 👎 bleibt nur Bewertung. Zurückgezogene negative Labels bleiben
erhalten, aber gehören nicht als gespielter Zug in Demonstrationstrajektorien.
Kein Live-Update der Netzgewichte. Private Engine-/RNG-Spielstände bleiben
ausschließlich lokal und getrennt von öffentlichen KI-/Cloud-Aufzeichnungen.

**Oberfläche geprüft und bereit zum Push:** Fünf betroffene echte Chrome-Prüfungen
bestehen: Schrittauswahl/Bildgalerie, Feedback/Undo/Cloudretry, Pass & Play und
Host/Gast-Mehrspieler, neue Spielabläufe und Praktikantenlauf. Die NN-Alternative
wurde einmal tatsächlich ausgeführt; das zweite negative Urteil ließ den Zug
unverändert. Auch fehlgeschlagener Neustart lässt die alte Partie erhalten.
Neuladen setzt Felder, Rolle, KI und Karten wieder fort; leere Neuwurfhand
bestätigt automatisch. Beide Ergebnis-Popups und weißer Nebel visuell geprüft.
Praktikantenleiste passt bei 390×844 und 320×740 vollständig ins Sichtfenster.
51 native Tests für Spielstände, Standardregeln, Undo und Lernaufzeichnungen,
der Node-Kartenvertrag und Mehrspieler-Aktions-/Privacy-Test bestehen.
Zurückgezogene negative Labels bleiben im Feedbackdatensatz, werden aus
Demonstrationstrajektorien ausgeschlossen. Build, Cache und JS-Syntax geprüft.
Kein neues Training in diesem UI-Commit; Automation weiterhin pausiert.

Danach: nur eine sichtbare Version pro Crew; historische Dateien erhalten.
Alle 21 Standardrouten/186 erlaubten Kartenfälle sollen auch bei schwachen oder
null Quoten als ehrlich beschriftete Vorschau verfügbar sein. Höhere Nummer
ist kein Beweis besserer Leistung. Kandidaten nach vorher festgelegtem
Gesamtkriterium vergleichen und echte Einzelwerte dokumentieren; einfachere
Routen nicht allein wegen alter enger Veröffentlichungslisten ausschließen.
Crew 1 braucht für Module zunächst einen Schema-3-Adapter unter Erhalt ihrer
ursprünglichen Gewichte; Quellen nicht blind als voll modultrainiert ausgeben.
Neue Crew-4-Phase benötigt den nun gültigen Regelsatz ohne Starttoken auf
Rot/Schwarz, frische Entwicklung und ehrliche Lineage; kein exaktes Resume über
geänderte Regeldateien. Nicht unverändert endlos den alten schwachen Lecklauf
wiederholen. Verbesserte KIs nach Prüfung direkt pushen.

## Vorläufig ausschließlich Standardrouten im Spiel

Auf den ergänzenden Nutzerwunsch sind eigene Routen aus dem gemeinsamen
Browserkatalog entfernt. Einzelspieler, Pass & Play und die Mehrspieler-Auswahl
zeigen vorerst nur die **21 Logbuchrouten**; der Galerie-Filter „Eigene Strecken“
entfällt. Alte gespeicherte Auswahlen einer eigenen Route fallen auf eine
Standardroute zurück. Die KI-Auswahl bevorzugt eine freigegebene Crew für die
erste Standard-Grundspielroute, ohne fest eingebautes MUC-Startziel.

Backup unter `backups/custom-routes-2026-10-25/`: FRA, LHR, MUC, MUC_T1,
MUC_T2 und MUC_T3 als sechs bytegenau kopierte YAML-Dateien, vollständige alte
Katalogeinträge und SHA-256-Prüfsummen. Wiederherstellungshinweise in der README.
Originale Engine-Dateien und historische Trainings-/Release-Daten bleiben für
die Reproduzierbarkeit zusätzlich erhalten, werden aber nicht im Spiel angeboten.
Die vorläufige Sichtbarkeit wird zentral beim Browser-Build festgelegt.

**Nach dieser Ergänzung bestanden acht Katalogtests, der Node-Fallvertrag und
fünf betroffene Browserprüfungen:** getrennte Schritte/Handy/Querformat,
allgemeines Feedback und beide Rollen, Vorschauen, gemischte Kartenfälle sowie
Galerie/Pass & Play/Mehrspieler mit echter Engine und simuliertem Transport.
Geprüft sind 21 sichtbare Standardrouten, kein eigener Filter/Eintrag, Start einer
offiziellen Heathrow-Route, alte gespeicherte eigene Auswahl und Offline-Katalog.
Vier Einzelspielerprüfungen bestanden direkt; die Galerieprüfung wurde an den
Verkehrsdialog der nun offiziellen Ersatzstrecke angepasst und bestand danach.
Alle sechs Backups stimmen mit Original und Prüfsumme überein. Build/Cache
aktualisiert; Training und Automation bleiben pausiert.

## Einzelspieler-Auswahl in getrennten Schritten

Auf neuen Nutzerwunsch folgt die Auswahl jetzt **Modus → KI und eigene Rolle →
Landung und gegebenenfalls Karten**. Jede Stufe hat eine eigene Ansicht mit
Fortschritt und Zurück-Navigation. Modus und KI passen ohne Seitenscrollen auf
kleine Handybildschirme; die Landungsansicht darf scrollen. Die bereits gewählte
KI bestimmt die verfügbaren Landungen, statt durch eine andere Landung still
ausgetauscht zu werden. Nur passende, exakt deklarierte Kartenfälle bleiben
auswählbar. Freigegebene Crew bleibt voreingestellt. KI-no überspringt die
unnötige KI-Auswahl und hat zwei Schritte. Rolle, Karten und Einwilligung
bleiben bei Rücknavigation erhalten; ein Moduswechsel setzt Einwilligung zurück.

Neuer echter Browsertest prüft Desktop, 390×844, 320×568 und 568×320, Fokus,
Rücknavigation, sechs Crew-3-Kartenfälle einschließlich 0 %, gefilterte Strecken,
den zweistufigen KI-no-Weg und einen fehlgeschlagenen Modellabruf mit erneutem
erfolgreichen Spielstart. Screenshots der drei Handyansichten visuell geprüft.
Die bestehenden UI-Prüfungen folgen ebenfalls den neuen sichtbaren Schritten.
**Alle neun Browserprüfungen bestanden:** neue Schrittauswahl sowie bisherige
allgemeine Feedback-/Undo-/Cloudretry-, Vorschau-, Crew-3-/Karten-, gemischte
Routen-, Kerosin-, Praktikanten- und Profil-12-Prüfungen. Zwei alte Tests
erwarteten noch das Speichern beim nächsten menschlichen Zug; sie prüfen jetzt
korrekt das bereits geltende sofortige Speichern mit `trigger=thumb` und
`explicit=true`. Der Node-Fallvertrag und die JavaScript-Syntaxprüfung bestehen.
Build/Cache-Version aktualisiert. Diese UI-Arbeit hebt die Trainingspause oder
den persistenten STOP-Schalter nicht auf; keine neuen Trainingsentscheidungen.

**Neueste Nutzeranweisung vom 25.10.2026:** Niedrige Gewinnquoten auf sehr
schweren Strecken sind akzeptabel. Die frühere Forderung von zunächst 30–40 %
auf jedem schwierigen Fall ist damit kein starres Abschlusskriterium mehr.
Nachvollziehbares Spiel und verlässliche Modulbedienung sind wichtiger;
Einzelquoten, Vorschaukennzeichnung und unabhängige Nachweise bleiben ehrlich.
Die Matrix mit 21 Routen/186 Fällen bleibt die Abdeckungsliste, kein Mittelwert
ersetzt ihre Einzelwerte.

Der letzte Vergleich ist abgeschlossen. Auf „danach darfst du erstmal aufhören“
ist die automatische Fortsetzung **PAUSED** und der persistente Schalter
`runs/STOP_AI_TRAINING` gesetzt. Kein weiterer Trainings-/Vergleichslauf.
Fortsetzung erst nach ausdrücklichem Nutzerauftrag; dann erst `clear-stop`
und gegebenenfalls Reaktivierung der Automation. Code und abgeschlossene
Forschungsergebnisse gehören zum abschließenden Push.

Auf „Nenne es Crew 3“ heißt der **zuletzt spielbare Modellstand jetzt genau
Crew 3** in der Auswahl, bisher Crew 5 · Leck (Test). Die Release-ID
`crew5-leak-preview-v1/best.pt`, historischen Trainingsmetadaten, Tensoren,
Browserasset und sechs getesteten Atlanta-gelb-Kartenfälle bleiben erhalten.
Nur Anzeigename und Release-README ändern sich; `quality.approved=false` und
die sichtbare Testkennzeichnung bleiben bestehen. Die anderen Crew-3-Varianten
und alle übrigen Einträge bleiben unverändert. Kein neu trainiertes Netz und
keine Übernahme der folgenden noch nicht im Browser implementierten Forschung.
Die vollständige Katalogprüfung bestätigt genau eine Anzeigenamenänderung bei
75 Einträgen, sechs unveränderte Kartenfälle und den identischen Browserasset-
Hash. Der Node-Fallvertrag besteht; Build/Service-Worker-Version aktualisiert.

## Abgeschlossene Forschung: notwendige Aufgaben-Kapazität erhalten

`ai.task_deadline_guard` / `TaskDeadlineEnv` bilden eine ausdrücklich getrennte
Forschungsphase über den erhaltenen Prior-/Endrundenreferenzen. Nur wenn die
öffentliche optimistische Zählgrenze aktuell besteht, werden native eigene
Platzierungen entfernt, deren öffentlicher projizierter Zustand innerhalb
derselben Runde die Grenze verletzt. Hilfsaktionen bleiben vorhanden; bereits
verletzte, unbekannte oder offene Dialogzustände fallen unverändert zurück.
Noch möglicher Synchronisationsbonus führt zur Enthaltung, ein tatsächlich
ausgegebener schwarzer Würfel zählt einmal. Ein leeres Ergebnis fällt auf die
vorige Maske zurück, ohne künstlichen Verlustzustand. Keine echte private
Partnerhand und kein zukünftiger Spiel-RNG.

Alte Masken und ihre Referenzen werden als `pre_guard_*` separat bewahrt.
Die aktuelle Referenz wird unter der neuen Maske neu berechnet und muss deren
Teilmenge sein; alte Referenzen gehören ausdrücklich zu ihren alten Masken.
Native Beobachtung/Uhr bleiben erhalten. `research_task_deadline=true` sperrt
die nicht im Browser unterstützte Umgebung auch für Vorschauveröffentlichungen.
Bestehende Profile, Gewichte und vorherige Forschungsfingerprints unverändert.

**46 relevante Tests bestanden in 5,15 s.** Darunter über 100 Vergleiche
projizierter öffentlicher Platzierungsfolgen mit der nativen Engine,
unveränderte tatsächlich erfolgreiche Eis-/Brems-/Gegenwindfolgen, Rollen,
Bonus, Privacy/RNG, Pacing/Cache, Masken-/Referenzzuordnung, exakte alte
Kontrollpartien und STOP-/Berichts-/Publikationsschutz. Ein Gegenbeispiel zeigt
die Grenze der optimistischen Zählung: Ein halbes Eispaar kann beim Rundenwechsel
verfallen und erst dann zu fehlender Kapazität führen. Technische Übungen sind
keine Gewinnquoten.

`ai.task_deadline_compare` ist **regulär beendet, Exit 0, 154,70 s**:
Prior, erhaltene gemeinsame Endrundenplanung und zusätzliche Kapazitätsmaske,
je 20 Spiele in zwölf offiziellen GIG-/KEF-gelben Einzelkartenfällen,
**720 frische Entwicklungspartien**. Identische tatsächliche Crew-5-Tensoren
mit Referenzabstand 12, keine PPO-Updates, null neue Trainingsentscheidungen.
Acht Worker zu .7, Torch 1, nice 15; beobachtete aktive Worker etwa 45–46 %.
Bericht `ai/experiments/wind-ice-2026-10-25/task-deadline-development-v1.json`,
abgeleitete `task-deadline-analysis-v1.json`, beide `complete=true`.
Log `/tmp/cockpit-task-deadline-development-v1.log`.

| Einzelkarte | GIG Wind: Prior / gemeinsam / Kapazitätsmaske | KEF Eis: Prior / gemeinsam / Kapazitätsmaske |
| --- | ---: | ---: |
| Adaptation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Anticipation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Control | 0/20 / 0/20 / 0/20 | 0/20 / 1/20 / 1/20 |
| Mastery | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Synchronisation | 0/20 / 1/20 / 1/20 | 1/20 / 1/20 / 1/20 |
| Working-together | 0/20 / 1/20 / 1/20 | 0/20 / 0/20 / 0/20 |

**Kein zusätzlicher Sieg durch die neue Maske:** Alle 240 gepaarten Gewinn-/
Verluststatus stimmen mit der erhaltenen gemeinsamen Planung überein, davon
vier gemeinsame Siege. Die drei zusätzlichen Siege gegenüber dem reinen Prior
bestehen schon in der gemeinsamen Kontrolle. Gleiche Tensoren mit anderer
Maske/Referenz sind keine unabhängig trainierten Modelle.

Die Maske wird in 980 Zuständen enger, entfernt 11.383 Platzierungsoptionen und
verhindert 282 alte NN-Wahlen, darunter 243 Konzentrationszüge. Übergänge von
bestandener zu verletzter notwendiger Zählgrenze innerhalb derselben Runde
sinken von 85 auf 63; am Rundenwechsel steigen sie von 52 auf 72. Das sind
Pfaddiagnosen, kein Gewinnnachweis. 70 leere Ergebnisse fallen nativ zurück.
Nicht jedes Übergangsereignis enthält seine ursprüngliche Eignungs-/Fallback-
Markierung; die verbleibenden Verluste dürfen deshalb nicht pauschal einer
einzigen Ursache zugeordnet werden. Die Grenze ignoriert weiterhin Augen,
Kaffeekosten, Reihenfolge, halbe Eispaare und zukünftigen Verkehr. Bestehen
beweist keine gewinnbare Fortsetzung.

Verwendete Entwicklung **14.994.000 + 100*i**, zwölf Fälle zu je 20 Seeds,
zuletzt **14.995.100–14.995.119**; technische Tests 14.989.400/410/420/430/440
separat. Die nächste unabhängige Abschlusskohorte ab 15.400.000 bleibt unbenutzt.
Kein neues Modell und keine Wind-/Eisfreigabe aus diesem Vergleich.

**Bei später ausdrücklich gewünschter Fortsetzung:** Rundenwechsel und
verfallende Eispaare sowie Funk-/Kontrollpflichten an konkreten öffentlichen
Zuständen untersuchen. Die neue Maske nicht unverändert endlos trainieren;
geringe Quoten auf sehr schweren Routen sind nach Nutzerwunsch akzeptabel.
Weitere Forschung beginnt erst nach Aufhebung der Pause.

Stand: 25. Oktober 2026. **Crew 2 ist für acht Grundspielstrecken zusätzlich
freigegeben. Zusätzlich besteht Crew 2 · Kerosin für Oslo mit 39,8 % unter dem
neu akzeptierten 30-%-Kriterium. Das Ziel aller Module/Karten ist nicht
abgeschlossen. Crew 1 bleibt verfügbar und vorausgewählt. Ein ausdrücklich
gewünschter Zwischenstand heißt jetzt Crew 3 · Praktikant (Test), mit Atlanta
grün und Heathrow gelb; er ist als Entwicklungsmodell sichtbar, ohne Freigabe.
Zusätzlich wird Crew 4 · Leck (Test) für Atlanta gelb mit allen sechs Einzelkarten
bereitgestellt: erst 0–5 % auf Entwicklung, ausdrücklich noch sehr schwach.
Auf erneuten Nutzerwunsch kommt Crew 5 · Leck (Test) mit dem tatsächlich zuletzt
trainierten Profil-12-Stand hinzu: alle sechs Einzelkarten auf Atlanta gelb,
0–20 % auf bereits verwendeter Entwicklung, weiterhin ohne Freigabe.**

## Neue Forschung: gemeinsame Pflichtaufgaben vor der letzten Bindung

`ai.joint_landing_prior` erweitert den öffentlichen Fair-Hand-Ansatz um
**rollenbezogene Aufgaben im selben Würfel-/Kaffeebudget wie Ruder und Schub**.
Die bekannte eigene Fortsetzung und die Rollenverteilung gemeinsamer Aufgaben
stehen vor der Erwartung über hypothetische Partnerhände fest. Pro Hand werden
erfolgreiche Zuordnungen vereinigt, bevor ihre Multiplizität gezählt wird.
Die Erwartung ist exakt unter der ausdrücklich angenommenen IID-Fair-Hand-
Verteilung und den statischen Anforderungen; kein kalibrierter Posterior
wirklicher Resthände und keine Spielgewinnwahrscheinlichkeit.

`ai.joint_landing_advice` berücksichtigt offene Fahrwerk-/Klappenfelder, obere
Pilotinnen- und gemeinsame untere Eisfelder, tatsächliche Funkaugen und freie
Funkplätze. In der letzten Runde kann nur Funkwert 1 das aktuelle Zielfeld
räumen; Flugzeuge außerhalb davon sind dann nicht mehr erreichbar. Gewählte
zusätzliche reguläre Bremsstufen reservieren ihre tatsächlichen Würfelwerte
2/4/6, statt höhere Bremskraft ohne Aufgabenbudget anzunehmen. Alle Varianten
benutzen verschiedene Würfel und dieselbe Kaffeereserve. Ein aktueller
Konzentrationszug oder der aktuelle zweite gleiche Control-Ruderzug kann
Kaffee erzeugen; spätere Kaffeegeneration, Adaptation und Bonuswürfel werden
nicht vorweggenommen. Eine unmittelbar beratene Adaptation wird berücksichtigt.

Die Vorgabe greift schon während der gesamten letzten Runde, zunächst nur auf
reinen Wind-/Eisstrecken ohne offenen Dialog. Sie bewertet vollständige
**statische Belegungen**, keinen sequenziellen Engine-Gewinnbeweis: Reihenfolge,
Zusammenarbeit und zukünftige Karteneffekte bleiben Grenzen. Bei keiner positiv
bewerteten Belegung fällt sie auf den bisherigen Prior zurück. Der neue
`JointLandingEnv` verändert nur die weiche Referenz, bewahrt native Legalität,
Beobachtung, Uhr und die ursprüngliche Priorreferenz. Markierung
`research_joint_landing=true`; Publisher sperrt diese nicht im Browser
implementierte Forschung auch als Vorschau. Bestehende Quellen, Profile,
Veröffentlichungen und Fingerprints bleiben erhalten.

**58 relevante Tests bestanden, 4,45 s**: unabhängige Enumeration geordneter
Partnerwürfe, Rollen-/Würfel-/Kaffeezuordnung, unveränderliche veröffentlichte
Kontrollen, Erwartungsreihenfolge, tatsächliche geordnete Engine-Landungen mit
Eisbremse, regulärer Bremse sowie Funk und letzter Klappe. Die getesteten
Gegenfälle reservieren den einzigen passenden Eis-/Bremswürfel und verwerfen
einen Konzentrationszug, der die verbleibenden Funk-/Klappen-/Kontrollaufgaben
unmöglich macht. Ein positiver Windfall benötigt drei Bremsaktivierungen plus
zwei Pilotinnenkontrollen und passt ausdrücklich nicht in vier Würfel. Privacy,
RNG, Pacing/Cache, Instrumentierungsparität und Ressourcen-/STOP-/Berichts-/
Veröffentlichungsschutz sind geprüft. Technische Übungen, keine Gewinnquoten.

Der neue Vergleich `ai.joint_landing_compare` ist regulär beendet,
**Exit 0, 105,75 Sekunden**: native Crew-5-Auswahl,
bisheriger Prior und neue gemeinsame Endrundenvorgabe, exakt dieselben
tatsächlichen Crew-5-Tensoren/Abstand 12. Zwölf offizielle GIG-/KEF-gelbe
Einzelkartenfälle zu je 20 Spielen je Variante, 720 frische Entwicklungspartien,
keine PPO-Updates und null neue Trainingsentscheidungen. Acht Worker .7,
Torch 1, nice 15, ein verwalteter Lauf, native Engine-Uhr. Bericht
`ai/experiments/wind-ice-2026-10-25/joint-landing-development-v1.json`, Log
`/tmp/cockpit-joint-landing-development-v1.log`; Bericht `complete=true`,
abgeleitete Analyse `joint-landing-analysis-v1.json`.
Entwicklung **14.992.000 + 100*i**, zwölf Fälle zu je
20 Seeds, zuletzt **14.993.100–14.993.119**. Technische Vergleichstests
14.989.300/310 getrennt. Abschlusskohorte ab 15.400.000 weiter unbenutzt.

| Einzelkarte | GIG Wind: Quelle / Prior / gemeinsame Aufgaben | KEF Eis: Quelle / Prior / gemeinsame Aufgaben |
| --- | ---: | ---: |
| Adaptation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Anticipation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Control | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Mastery | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Synchronisation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Working-together | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |

**Kein Sieggewinn, kein neuer Modellrelease.** 1.604 geeignete Entscheidungen
in 158 Partien, nur 26 positive statische Belegungen in fünf Partien. Die neue
Vorgabe verändert 24 tatsächliche Prior-Wahlen in diesen fünf Partien. Alle
240 gepaarten Status bleiben verloren; in einer Partie ändert sich der
Verlustgrund (offene Eisbremse zu zu schneller Landung). Aktive Worker wurden
bei etwa 43–48 % CPU und Priorität 15 beobachtet. Dieselben Gewichte unter
anderen Referenzen sind keine unabhängig trainierten Modelle. Null statische
Belegung ist kein Engine-Unmöglichkeitsbeweis, unter anderem weil zukünftiger
Kaffee und Karteneffekte bewusst nicht vorweggenommen werden.

Deshalb folgt zunächst die **passive** Diagnose `ai.landing_task_budget` /
`ai.landing_budget_probe`, keine neue Maske und kein weiteres unverändertes PPO.
Sie prüft beim ersten Eintritt in 1.000 Fuß und die Landerunde eine optimistische
notwendige Zählgrenze: aktuelle und zukünftige reguläre Würfel, Pflichtkontrollen jeder
verbleibenden Runde, rollenbezogene Upgrades, gemeinsame Eisfelder und alle
aktuellen Flugzeuge mit freien Funkplätzen. Augen, Kaffeekosten, Reihenfolge,
künftiger Verkehr und Verlust halber Eispaare beim Rundenwechsel bleiben
optimistisch unberücksichtigt. Vor der Landerunde darf zukünftiger Wind maximal
günstig werden; in der Landerunde gelten unveränderliche veröffentlichte
Schubwerte und der Wind bei erfolgreicher waagerechter Ruderauflösung.
Nicht für jeden Windflug wird pauschal ein Bremswürfel verlangt: ein
enginegeprüfter starker Gegenwind kann sogar ohne reguläre Bremse landen.
Synchronisation mit noch möglichem künftigem Bonus bewirkt Enthaltung; ein
tatsächlich ausgegebener Bonus zählt einmal, nie einer nur wegen Kartenbesitz.

Weitere **neun Diagnosetests bestanden** (1,25 s), damit 67 unterschiedliche
relevante Tests dieser Phase. Der abschließende gemeinsame Lauf aller 67 Tests
bestand in **5,71 Sekunden**. Geprüft sind unveränderte erfolgreiche Engine-Präfixe,
Endrunden- und Zwei-Runden-Kapazität, Funkplatz-/Rollenbudgets, Kaffee ersetzt
keinen Würfel, Bonus-/Privacy-/RNG-/Stop-/Berichtsschutz. Die Diagnose ist
**regulär beendet, Exit 0, 40,06 Sekunden**: 24 Trainingspartien, zwei je
offiziellem Wind-/Eis-Kartenfall, 1.453 gesampelte Entscheidungen, mit
unverändertem Prior und tatsächlichen Crew-5-Gewichten. Ein Worker .7,
Torch 1, nice 15; Namensraum `train:landing-budget-probe:251070:...`, keine
Entwicklungs-/Qualifikationsseeds, keine PPO-Updates. Bericht
`ai/experiments/wind-ice-2026-10-25/task-budget-training-probe-v1.json`, Log
`/tmp/cockpit-task-budget-training-probe-v1.log`. Bericht `complete=true`,
abgeleitete Analyse `task-budget-training-analysis-v1.json`.

Erste Eintrittszustände: **1.000 Fuß: 9 falsch / 5 bestanden / 3 Enthaltungen**
unter 17 erreichten Partien; **Landerunde: 11 falsch / 1 bestanden /
3 Enthaltungen** unter 15 erreichten Partien. Enthaltungen betreffen möglichen
zukünftigen Synchronisationsbonus, ohne dafür Würfel zu erfinden. Einzelne
Eisfälle benötigen bei 1.000 Fuß bereits **19–20 Platzierungen bei nur
16 verbleibenden regulären Würfeln**. Ein Windfall hat zwar 16 Aufgaben bei
16 Würfeln, scheitert aber an Rollen-/Funkplatzkapazität. Diese kleine passive
Trainingspfaddiagnose ist kein Gewinnquotennachweis und erklärt nicht jede
Niederlage. Die übrigen Partien erreichten diese Eintrittszustände nicht.

**Nächster begründeter Schritt:** in einer ausdrücklich neuen Forschungsumgebung
früheres Verschlechtern einer noch bestandenen notwendigen Aufgaben-Kapazität
verhindern. Zunächst nur reine Wind-/Eisfälle; mögliche künftige Synchronisation
weiterhin ausnehmen. Aktuell ausgegebener Bonus zählt einmal. Kandidaten mit
der nativen Engine und öffentlichen Vorher-/Nachherzuständen prüfen, insbesondere
Konzentration, schon aktivierte Upgrades und wirkungslose Funkzüge an knapper
Kapazität. Keine noch rettbare erfolgreiche Enginefolge aufgrund zu strenger
Brems-/Rollenannahmen entfernen; Gegenwindbeispiel erhalten. Bereits nach der
optimistischen Grenze unrettbare oder unbekannte Zustände nicht durch einen
neuen künstlichen Terminalzustand ersetzen. Masken-/Referenzänderung klar als
neue Phase behandeln, alte Crews/Quellen unverändert lassen. Erst begrenzten
frischen Entwicklungsvergleich gegen erhaltene Kontrollen, dann gegebenenfalls
erneutes PPO/erfolgreiche Übungen. Nicht denselben unveränderten schwachen
Lehrer länger trainieren. Aktuell kein schwerer Job aktiv.

## Neue Forschung: enginegeprüfte letzte eigene Landefolge

`ai.solo_landing` rekonstruiert einen **getrennten** Endrundenzustand ausschließlich
aus eigener aktueller Hand, öffentlichen Feldern und überprüften Routendaten.
Keine Kopie des laufenden Spiels, keine alte private Partnerhand, kein echter
zukünftiger Spiel-RNG. Bereits verbrauchte private Würfel erhalten unverfügbare
Platzhalter; veröffentlichte Feldwerte bleiben separate öffentliche Tokens.
Schon aufgelöste Ruder-/Schubpaare werden nicht erneut bezahlt oder gedreht.
Kerosinbelegung, Leck, Wind, Eis, Kaffee, Fahrwerk, Klappen, Bremsen und Funk
werden durch **dieselbe native Spielengine** ausgewertet, nicht über unabhängig
geschätzte Einzelwahrscheinlichkeiten.

Die erste Stufe greift nur bei Höhe/Entfernung null ein, wenn der Partner keine
regulären Würfel mehr hat. Im normalen abwechselnden Spiel verbleibt dann meist
nur ein eigener regulärer Würfel: **keine allgemeine gemeinsame Planung einer
ganzen Runde**. Ein schon ausgegebener und geworfener schwarzer Würfel darf
einmal gemeinsam zugewiesen werden. Kartenbesitz erzeugt keinen, ein noch
unbekannter Wurf führt zur Enthaltung auf diesem Zweig. Praktikant, Echtzeit,
Tausch- und Neuwurfdialoge bleiben außerhalb dieses engen Simulationsumfangs.

Die Suche prüft native Platzierungen, Kaffee und Adaptation mit festen Grenzen
von 1.500 besuchten Zuständen und höchstens 32 Aktionen; CPU-Pacing prüft etwa
alle 20 ms. Sie liefert genau eine tatsächliche Gewinnfolge oder enthält sich.
Ein Fehlschlag oder Budgetabbruch beweist keine verlorene Partie. Der erste Zug
muss zusätzlich durch die wirkliche aktuelle Maske erlaubt sein; nach jedem
realen Schritt wird neu geprüft. Unter der alten weichen Referenz bleibt ein
neuer Suchspieler `SoloLandingEnv` ausdrücklich separat: Der bewiesene Zug
ersetzt gegebenenfalls die NN-Wahl, sonst exakt bisheriger Prior. Alte Referenzen,
Gewichte, Browserprofile und frühere Fingerprints bleiben erhalten. Markierung
`research_solo_landing=true`; Publisher sperrt diese nicht im Browser
implementierte Suche auch für Vorschauen.

**50 relevante Tests bestanden** (3,78 s): Rekonstruktion und native Übergänge
für beide Rollen, sechs Karten auf Wind/Eis/Leck; tatsächliche Radio-/Fahrwerk-/
Klappen-/Kerosin-/Adaptation-/Kaffee-/Eisfolgen, kein doppelt verwendeter Würfel,
ein geteilter schwarzer Würfel, bereits bezahltes Leck und aktueller Control-
Kaffee, Erhaltung privater Informationen und RNG, Pacing, Cache und feste
Budgetenthaltung. Native und bisherige Prior-Kontrolle reproduzieren exakt
die früheren Beobachtungen, Masken, tatsächlich gespielten Züge und Resultate.
Dies sind technische Übungen, keine zusätzlichen Qualifikationspartien.
Anschließend bestanden 26 weitere gezielte Prüfungen einschließlich zehn
bereits gezählter Endrundentests: insgesamt **66 unterschiedliche relevante
Tests**. Zusätzlich geprüft sind der Vorschau-Publisher und eine durch eigene
Platzierung erst ausgelöste, noch nicht geworfene Synchronisation ohne Zugriff
auf ihren zukünftigen Würfelwert.

Der neue begrenzte Drei-Varianten-Vergleich `ai.solo_landing_compare` ist
**regulär beendet, Exit 0, 107,11 Sekunden**:
native Crew-5-Auswahl, bisheriger Prior und Prior mit Endrundensuche. Je 20
frische Entwicklungspartien in zwölf offiziellen Wind-/Eis-Einzelkartenfällen,
720 insgesamt, alle mit exakt gleichen Crew-5-Tensoren/Abstand 12. Keine PPO-
Updates, null neue Trainingsentscheidungen, native Engine-Uhr. Bericht
`ai/experiments/wind-ice-2026-10-25/solo-landing-development-v1.json`, Log
`/tmp/cockpit-solo-landing-development-v1.log`. Bericht ist `complete=true`,
abgeleitete Analyse `solo-landing-analysis-v1.json`. Entwicklung
**14.990.000 + 100*i**, zwölf Fälle
zu je 20 Seeds, zuletzt **14.991.100–14.991.119**. Technische Kontrolltests
14.989.200/210/220, getrennt von der Entwicklung. Abschlusskohorte ab 15.400.000
bleibt unbenutzt. Acht Worker .7, Torch 1, nice 15, nur ein verwalteter Lauf;
aktive Worker bei der Kontrolle etwa 43–45 % CPU, alle Priorität 15.

| Einzelkarte | GIG Wind: Quelle / Prior / Endrundensuche | KEF Eis: Quelle / Prior / Endrundensuche |
| --- | ---: | ---: |
| Adaptation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Anticipation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Control | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Mastery | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Synchronisation | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Working-together | 0/20 / 1/20 / 1/20 | 0/20 / 0/20 / 0/20 |

**Kein zusätzlicher Sieg durch die Endrundensuche, kein neuer Modellrelease.**
Alle 240 gepaarten Status-/Verlustgrund-Ergebnisse stimmen mit der Prior-
Kontrolle überein. Die Suche prüfte 223 geeignete Entscheidungen in 150 Partien,
897 Zustände; kein Abbruch am Zustandsbudget. Drei bewiesene Entscheidungen,
davon eine andere NN-Wahl, stammen aus derselben ohnehin von der Prior-Kontrolle
gewonnenen Partie. Sieben Suchen begegneten einem noch ungeworfenen Bonuszweig
und enthielten sich dort. Eine erfolglose Suche ist ausdrücklich kein allgemeiner
Unmöglichkeitsbeweis. Das Berichtsfeld `same_policy_all_arms` meint identische
eingefrorene NN-Tensoren; der Endrundenarm ist ausdrücklich ein neuer Suchspieler.
Die 720 Spiele enthalten keine neuen Trainingsentscheidungen oder PPO-Updates.
Frühere Kontrollen und technische Wiederholungen sind keine neue unabhängige
Evidenz. Die bisherige Qualifikationskohorte ab 15.400.000 bleibt unangetastet.

Nächster begründeter Schritt: **gemeinsame Endrundenbelegung bereits vor den
ersten Bindungen der letzten Runde**, anstelle einer nur auf Ruder/Schub
bewerteten Prognose oder Rettung des letzten eigenen Würfels. Offene Fahrwerk-/
Klappen-/Eis-/Funkpflichten brauchen dieselben endlichen Würfel und dieselbe
Kaffeereserve wie die Kontrollen. In einem ausdrücklich neuen Forschungsprofil
die vorhandene Fair-Hand-Zuordnung um diese Pflichtaufgaben ergänzen, zunächst
enginegeprüfte eigene/öffentliche Endrundenübungen. Die eigene Zuordnung muss
vor der Erwartung über hypothetische Partnerhände feststehen. Keine realen
Partneraugen, kein zukünftiger Spiel-RNG oder unverdienter Bonus. Erst einen
begrenzten frischen Vergleich, dann gegebenenfalls Training auf tatsächlich
erfolgreichen Übungen; diesen unveränderten schwachen Lehrer nicht einfach
länger trainieren. Die enge Rekonstruktion ist keine allgemeine Simulation für
unbekannte Partnerhände, Echtzeit oder Praktikant und darf nicht so verwendet
werden. Aktuell kein schwerer Vergleichs-/Trainingsjob aktiv.

## Crew 5 und kompaktes Sofortfeedback

Der Nutzer wollte eine neue Crew unabhängig von ihrer aktuellen Stärke und alle
vorhandenen eigenen Änderungen gepusht haben. Abgeschlossene Forschungsberichte
und Tests sind mit `050e85f` auf main. Die geschützten fremden Dateien bleiben
unangetastet. Crew 5 veröffentlicht anschließend ausdrücklich den tatsächlichen
`runs/leak-profile12-stage1/latest.pt`-Stand unter
`ai/releases/crew5-leak-preview-v1/best.pt`. Der Release-Dateiname ist eine
Konvention: Die ursprüngliche Auswahl nach schwächster Entwicklungskarte hatte
weiterhin den Warmstand mit null neuen Entscheidungen als `best.pt` behalten.
Die Vorschau ist daher kein nachträglich umgedeuteter Auswahlsieg.

Tatsächliches Training: **80.139 neue Entscheidungen**, 1.425 Trainingspartien,
35 Updates, vorhandener Detailzweig trainiert, ursprüngliche Grundlage exakt
eingefroren. Profil 12, Referenzabstand 12, Schema 3, Browserformat 4.
Gewichts-SHA:
`e59d9f7bee62b12ed0faf094c80945cc2b1d984544eb619547940c752238bb83`.
Browserasset: `19e7a04826a9fb327cae2e1c8ac6d8d760c9ad0d46604e7f28a902d1dc41168d`.

| Atlanta gelb, Einzelkarte | Siege aus 20 | Entwicklungsquote |
| --- | ---: | ---: |
| Adaptation | 1 | 5 % |
| Anticipation | 3 | 15 % |
| Control | 3 | 15 % |
| Mastery | 2 | 10 % |
| Synchronisation | 4 | 20 % |
| Working-together | 0 | 0 % |

Alle sechs Fälle werden auf ausdrücklichen Wunsch gezeigt, einschließlich null
Siegen. `preview.enabled=true`, `quality.approved=false`, exakte Fallliste und
ganzzahlige Siege. Die bekannte Entwicklungsstichprobe wurde in der passiven
Diagnose exakt reproduziert; sie ist keine zusätzliche unabhängige Evidenz.
Bericht: `ai/experiments/leak-2026-10-25/profile12-preview-development-v1.json`,
identisch mit dem Release-Entwicklungsbericht. Alle 74 vorherigen Katalogeinträge
bleiben exakt erhalten; genehmigte Crew bleibt vorausgewählt. Die neue enge
Tauschforschung ist nicht Teil der Crew. Wind/Eis werden nicht als unterstützt
oder spielstark ausgegeben.

Das Feedbackpanel zeigt auf Nutzerwunsch nur 👎, 👍 und ein weißes eingekreistes i
auf leicht transparentem Hintergrund. Das i öffnet die Erklärung und die Auswahl
mehrerer KI-Aktionen; Schließen oder Escape klappt sie wieder zu. Jeder
Daumenklick speichert sofort explizit ±1 mit `committed=true`, Zeitstempel und
`trigger=thumb`. Derselbe Daumen erneut verändert nichts, der andere ändert die
gespeicherte Bewertung. Der separate Speichernknopf entfällt vollständig.
Die vorhandene Rückgängig-Taste nimmt zuerst die letzte Bewertung zurück,
einschließlich mehrerer Änderungen, ohne Engineaktion, Zugrücknahme, Pause oder
Voiding. Nach dem nächsten erfolgreichen Spielschritt gilt wieder die normale
Zugrücknahme; ungültige Aktionen erhalten den Bewertungs-Undo. Neutral bleibt
ohne Daumenauswahl die Voreinstellung. Datenrevisionen und Cloud-Outbox werden
auch beim Bewertungs-Undo regulär aktualisiert. Das ist aufgezeichnetes Feedback,
keine automatische Gewichtsänderung während der Partie.

Vier reale Chrome-Prüfungen bestanden: allgemeines mobiles Feedback mit
Sofortspeichern, mehrfacher Bewertungsrücknahme, unverändertem Enginezustand,
ungültigem Zug, neutralem Abschluss, Cloudretry und beiden Rollen; tatsächliche
Crew 5 mit sechs ehrlichen Fallquoten und geladenen Originalgewichten,
Referenzmasken, nativen Karten und verdeckten Partnerwürfeln; bisherige Crew 4
und alle sechs Karten; Crew 3 auf MUC sowie Kerosin/Echtzeit mit Control+Mastery
und exakter Fallbegrenzung. Der neue Test berücksichtigt das bestehende Format
legaler menschlicher Kartenaktionen außerhalb des eigenen Zuges: administrative
Aufzeichnung ohne erfundenes Policylabel. JavaScript-Syntax und Diffprüfung
bestanden, Build/Cacheversion aktualisiert. Die Ansichten bei 320/390 Pixeln
und geöffnete Info wurden visuell geprüft. Dies sind technische Nachweise,
keine zusätzlichen Qualifikationspartien. Browser und begrenzter lokaler
Webserver sind beendet; kein Trainingsjob aktiv.

Veröffentlicht mit **`6428eac6b39ab124039e081dd8539f99e226c72a`** nach main.
GitHub Pages lief erfolgreich durch (Run `40210307915`). Danach wurden Live-
und lokale Bytes von Modellkatalog, Cacheversion, Singleplayer-JavaScript,
App-JavaScript, Panel-CSS, Enginebundle und tatsächlichem Crew-5-Browsergewicht
verglichen: alle identisch. Live sind 75 Katalogeinträge und alle sechs
Crew-5-Kartenfälle vorhanden. Cacheversion `3981184b31be`.

## Verbindlicher Auftrag

Der Nutzer hat das ursprüngliche 50-%-Ziel ausdrücklich auf zunächst **30–40 %**
gelockert und einen etwa 20-minütigen Lauf mit Fokus auf sämtliche Module verlangt.
Verbindlich ist jetzt `ai/experiments/modules-30pct-2026-10-25/matrix.json`:
dieselben 21 offiziellen Routen und 186 einzelnen Route/Karten-Fälle, unveränderte
Originalregeln, aber Freigabeuntergrenze 30 % je Fall. Eine spätere Freigabe
verlangt unabhängige Einzeltests mit unterer Wilson-Grenze >=30 %. Die alte
50-%-Matrix und damalige Ergebnisse bleiben unverändert als Historie erhalten.
Es darf nicht über einfache und schwere Fälle gemittelt werden.

**Neueste ausdrückliche Nutzeranweisung:** Zwischenmodelle samt schwachen Routen
sollen schon vor Freigabe spielbar sein. Deshalb dürfen zusätzlich zu genehmigten
Modellen explizit markierte Vorschauen (`preview.enabled === true`) erscheinen.
`quality.approved` bleibt dabei `false`; Entwicklungsquoten sind separat beschriftet
und ersetzen keine unabhängige Qualifikation. Alte unqualifizierte Modelle ohne
dieses ausdrückliche Flag bleiben verborgen. Vorauswahl bleibt eine genehmigte Crew.

## Ressourcen, Stoppen und automatische Fortsetzung

Der frühere 20-Minuten-Lauf mit vorübergehend acht Workern zu 80 % ist beendet.
Für neue ausdrücklich beauftragte Modulversuche gilt wieder **acht/70 %**.
Ein Torch-Thread, `nice -n 15`, ein schwerer Lauf gleichzeitig; Metal darf
PPO-Minibatches rechnen. Die genaue Zuordnung zu Performance-Kernen steuert macOS.

Eine Nachricht im Chat **„Training und automatische Fortsetzung stoppen“** bedeutet:
aktiven eigenen Job stoppen und die 15-Minuten-Automation pausieren. Zusätzlich:

```sh
.venv/bin/python -m ai.job_control stop
```

setzt den dauerhaften Stoppschalter `runs/STOP_AI_TRAINING`. Der verwaltete Job
prüft ihn alle 0,5 Sekunden; nach SIGINT erhält der Prozess bis zu 15 Sekunden
für das geordnete Ende. Neue verwaltete Jobs bleiben blockiert. Die Automation
darf den Schalter nicht selbst löschen. Zum Wiederaufnehmen ist eine ausdrückliche
Nutzeranweisung nötig. Bereits gespeicherte Modelle bleiben erhalten.

Neue schwere Jobs laufen unter `python -m ai.job_control run -- ...`; eine
Dateisperre verhindert zwei verwaltete Läufe gleichzeitig. Vor jedem Start auch
bestehende unverwaltete Trainingsprozesse prüfen. Die wieder aktivierte Automation
`ki-schonend-weitertrainieren` prüft alle 15 Minuten; ihre Reaktivierung wurde nach
einer ersten automatischen Ablehnung ausdrücklich vom Nutzer bestätigt.
Keine E-Mail. Nur aussagekräftigen Fortschritt, Fehler, Abschluss oder benötigten
Input melden.

## Aktuelle Forschung: Fair-Hand-Prior für gemeinsame Kontrollen

Die getrennte neue Phase verändert keine alten Planungsprofile, Browsergewichte
oder Microplanquellen. Der alte Forschungsfingerprint bleibt exakt erhalten.
`ai.public_hand_prior` berechnet eine **exakte Erwartung unter einer ausdrücklich
angenommenen IID-Fair-Hand-Verteilung**, keine kalibrierte Wahrscheinlichkeit
der tatsächlich nach öffentlichen Entscheidungen verbliebenen Partnerhand.
Bereits veröffentlichte Kontrollen verbrauchen keinen hypothetischen Restwürfel.
Zwei offene Kontrollen brauchen zwei verschiedene Würfel; Kaffee für eigenen
Vorschritt, übrige eigene Kontrollen und Partnerkontrollen wird genau einmal
verteilt. Die eigene Fortsetzung steht **vor** der Erwartung über hypothetische
Partnerhände fest; keine spätere Wahl passend zur unbekannten wirklichen Hand.
Die besten Zuordnungen werden je hypothetischer Hand vereinigt, bevor ihre
Multiplizität gezählt wird. Bitmengen und Caches begrenzen die Berechnung;
CPU-Pacing prüft auch innerhalb der Vorbereitung regelmäßig, ohne Kandidaten
zeitabhängig wegzulassen. Kein echter Spiel-RNG, keine private Partnerhand.

`ai.wind_ice_prior_advice` kombiniert diese Erwartung mit dem erhaltenen
Ein-Platzierungsplaner. Zusätzlich nutzt sie eine **optimistische öffentliche
Radio-Kapazitätsgrenze**, nachdem beide Rollen ihre Kontrollen reserviert haben:
Bewegung wird am Rundenende aufgelöst, aktuelle Flugzeuge sind somit noch nicht
zwingend eine bereits unumkehrbare Kollision. Passende zukünftige Funkaugen
werden damit nicht bewiesen. Ein sicherer Kaffeegewinn der Control-Karte beim
gerade geplanten zweiten gleichen Ruder wird exakt berücksichtigt; andere
zukünftige Kaffeegeneration und zukünftige Bonuswürfel werden nicht vorweggenommen.
Der Versuch bündelt diese Änderungen und ist kein Kausalitätsnachweis allein
für den Fair-Hand-Prior.

`ai.wind_ice_prior_environment.PriorWindIceEnv` erhält die native Engine-Maske,
Beobachtung, Uhr, Quellreferenz und zusätzlich die bisherige Microplanreferenz.
Markierung `research_wind_ice_prior=true`; gleicher beschränkter Wind-/Eisbereich
und native Dialog-/Modulfallbacks. Publisher weist diesen noch nicht im Browser
unterstützten Forschungswrapper ausdrücklich ab. **50 relevante Tests bestehen**:
analytische Wahrscheinlichkeiten, unabhängige Enumeration geordneter Würfe,
keine Würfel-/Kaffee-Doppelzählung, veröffentlichte Werte, Erwartungsreihenfolge,
bekannte Engine-Gegenfälle, tatsächlicher Control-Kaffeevorschritt samt sicherem
Windschub, Privacy/RNG/Pacing, unveränderte alte Kontrollpartien und Ressourcen-/
STOP-/Berichts-/Veröffentlichungsschutz. Laufzeitprobe zweier Anfangszustände
mit einem Worker .7: 0,060/0,019 s, Trainingsnamensraum
`train:wind-ice-prior-runtime:251067:...`, keine Gewinnquotenprobe.

Der Drei-Varianten-Vergleich `ai.wind_ice_prior_compare` ist regulär beendet,
Exit 0, **64,29 Sekunden**: native Quelle, erhaltene Microplans und neuer Prior,
alle mit exakt denselben tatsächlichen Crew-5-Tensoren/Referenzabstand 12.
Zwölf Fälle mit je 20 Partien pro Variante, **720 frische Entwicklungspartien**,
native Engine-Uhr, acht Worker .7, Torch 1, nice 15, ein verwalteter Lauf.
Keine PPO-Updates, null neue Trainingsentscheidungen, keine Qualifikation.
Bericht `ai/experiments/wind-ice-2026-10-25/prior-development-v1.json`,
abgeleitete Analyse `prior-analysis-v1.json`,
Log `/tmp/cockpit-wind-ice-prior-development-v1.log`.

| Einzelkarte | GIG Wind: Quelle / Microplans / Prior | KEF Eis: Quelle / Microplans / Prior |
| --- | ---: | ---: |
| Adaptation | 0/20 / 1/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Anticipation | 0/20 / 0/20 / 0/20 | 0/20 / 2/20 / 0/20 |
| Control | 0/20 / 0/20 / 0/20 | 0/20 / 1/20 / 0/20 |
| Mastery | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Synchronisation | 0/20 / 2/20 / 0/20 | 0/20 / 0/20 / 0/20 |
| Working-together | 0/20 / 0/20 / 0/20 | 0/20 / 0/20 / 0/20 |

**Kein Gewinnquotenvorteil und kein neuer Spieler veröffentlicht.** Alle
Einzelquoten, gepaarten Episoden und Abweichungszähler bleiben erhalten. Der
Prior gewinnt keine Partie zusätzlich und verliert die sechs Microplansiege
dieser Kohorte; dieser Gesamtvergleich ersetzt nicht die Tabelle je Fall.
Die Kontrollen sind dieselben Gewichte mit anderer Referenz, keine unabhängig
trainierten Modelle. Diagnose: bei Wind Trudelverluste 47 → 2 und Landerunden
22 → 48, bei Eis Trudelverluste 42 → 5 und Landerunden 41 → 100, jeweils unter
den je 120 Microplan-/Priorpartien. Dafür bei Wind 26 statt 10 und Eis 44 statt
23 zu schnelle Landungen; weitere Niederlagen durch offene Eisbremsen, Klappen,
Fahrwerk und Flugzeuge. Mehr erreichte Landerunden sind kein Siegbeweis.
Kaffee wird häufiger verbraucht, aber längere Partien beeinflussen diese Zähler.
Die Analyse kennzeichnet Konzentrations-/Aufgabenanteile ausdrücklich als
Teilmenge der gegenüber der nativen Präferenz geänderten Züge, nicht als alle
Aktionen und nicht als bewiesene Ursache sämtlicher Niederlagen.

Nächster begründeter Schritt: **alle noch zwingenden Landeaufgaben und Funk-
räumungen gemeinsam mit Ruder/Schub in dasselbe endliche Würfel-/Kaffeebudget
einbeziehen**. Geeignete letzte-Runde-/Modulübungen oder eine ausdrücklich
getrennte gemeinsame Endrundenbelegung zuerst enginegeprüft herstellen; danach
neue begrenzte Entwicklung und gegebenenfalls Training auf tatsächlich
erfolgreichen Übungen. Diesen weiterhin schwachen festen Lehrer nicht einfach
länger imitieren oder per unverändertem PPO trainieren. Keine neue Architektur
oder Kritikergewichtung aus der Diagnose ableiten. Sichtbarkeit schwacher
Vorschauen bleibt erlaubt, verlangt aber weiterhin passende Browsersemantik.

Verbrauchte neue Entwicklung: **14.987.000 + 100*i**, zwölf lexikalisch sortierte
Fälle zu je 20 Seeds, zuletzt **14.988.100–14.988.119**. Technische Vergleichstests
zusätzlich 14.989.100/110. Keine Abschlusskohorte verwendet, ab 15.400.000 weiter
reserviert. Aktuell kein schwerer Job aktiv; zuletzt acht bestandene Prior-
Tests einschließlich des neuen einzelnen Control-Kaffee-Gegenfalls.

## Abgeschlossene erste Wind-/Eismicroplanung nach Crew 5

Die neue, getrennte Forschungsumgebung `ai.wind_ice_environment.WindIceEnv`
ändert ausschließlich die weiche Referenz, bewahrt Engine-Legalität, Schema,
native Uhr und ursprüngliche Referenz. Profil 12 und alle Veröffentlichungen
bleiben unverändert. `ai.wind_ice_advice` bewertet eine eigene Platzierung samt
Kaffee-/Adaptation-Vorschritten und einer gemeinsamen Zuordnung der verbleibenden
eigenen Ruder-/Schubwürfel. Jeder Würfel und das gemeinsame Kaffeebudget zählen
genau einmal. Physikalisch bewertet werden nur bereits bekannte Partnerkontrollen,
unbekannte Augen werden weder gelesen noch geraten. Wind wird einmal nach der
Ruderauflösung berücksichtigt; Eisfortschritt bleibt beim Rundenwechsel erhalten,
auch wenn die alten Felder geleert wurden. Zukünftige Bonuswürfel werden nicht
gutgeschrieben. Aktueller Anwendungsbereich nur reine Wind-/Eisrouten; offene
Bonus-/Tausch-/Neuwurfdialoge und gemischte weitere Module behalten die native
Referenz. Ein privater Würfel oder echter zukünftiger RNG ist kein Planungsinput.

**35 relevante Tests bestanden**: Engine-Gewinn des letzten Eispaares,
Kartenanpassung als echter Vorschritt, Windschub gegen Überschießen,
372 virtuelle Feld-/Augenchecks gegen die Engine, echte Fortschritts-/Kaffee-
Effekte, gemeinsame Würfel-/Kaffeebelegung, unveränderte Masken, Beobachtungen,
Uhr und RNG sowie technische Vergleichs-/STOP-/Ressourcen-/Berichtsschutztests.
`ai.publish` lehnt `research_wind_ice` für Vorschau und Freigabe ab, solange kein
passender Browseradapter existiert. Ein Sichtbarkeitswunsch für schwache Modelle
ersetzt diese technische Übereinstimmung nicht. Kein Browserrelease wurde geändert.

Der vorab begrenzte Vergleich `ai.wind_ice_compare` ist regulär beendet,
Exit 0, **8,72 Sekunden** Auswertungszeit: zwölf offizielle Fälle, je 20 Partien
pro Variante, insgesamt **480 Entwicklungspartien**. Gleiche tatsächliche
Crew-5-Tensoren und Referenzabstand 12 in beiden Armen, native Referenz gegen
Microplans. Keine PPO-Updates, null neue Trainingsentscheidungen, keine
Qualifikation. Native Engine-Uhr, acht Worker zu .7, Torch 1, nice 15,
`ai.job_control`. Bericht
`ai/experiments/wind-ice-2026-10-25/microplans-development-v1.json`,
Log `/tmp/cockpit-wind-ice-microplans-v1.log`; getrennte abgeleitete Analyse
`microplans-analysis-v1.json`. Alle Quoten und gepaarten Episoden bleiben einzeln:

| Einzelkarte | GIG Wind, Quelle → Microplans | KEF Eis, Quelle → Microplans |
| --- | ---: | ---: |
| Adaptation | 0/20 → 0/20 | 0/20 → 1/20 |
| Anticipation | 0/20 → 0/20 | 0/20 → 0/20 |
| Control | 0/20 → 0/20 | 0/20 → 0/20 |
| Mastery | 0/20 → 0/20 | 0/20 → 0/20 |
| Synchronisation | 0/20 → 0/20 | 0/20 → 1/20 |
| Working-together | 0/20 → 0/20 | 0/20 → 0/20 |

Kein belastbarer Gewinnquotennachweis, Ziel nicht erreicht, kein neuer Spieler
veröffentlicht. Die Planung verändert tatsächlich die Auswahl: 8.339 Zustände
mit anderer Referenz, 7.740 Abweichungen von der nativen NN-Präferenz auf denselben
öffentlichen Zuständen, kein Verlassen der neuen Referenz. Diagnose, nicht
Routequalifikation: Landerunden bei Wind 0 → 23 und Eis 0 → 38 unter den je 120
Fällen pro Variante. Häufigeres Erreichen der Landung ersetzt keine Siege je
Karte. Bei Wind bleiben 30 Trudel-, 50 Kollisions- und 14 zu schnelle Landungen;
bei Eis 43 Trudel- und 23 zu schnelle Landungen. Diesen festen Lehrer nicht
unverändert länger imitieren oder trainieren.

Die anschließende passive Diagnose `ai.wind_ice_rescue_probe` ist ebenfalls
regulär beendet, Exit 0, **7,10 Sekunden**, ein Worker .7/Torch 1/nice 15.
40 getrennte Trainingspartien im Namensraum
`train:wind-ice-rescue-probe:251066:0..39`, Wind+Adaptation und Eis+Control;
Bericht `fatal-rudder-training-probe-v1.json`,
Log `/tmp/cockpit-wind-ice-rescue-probe-v1.log`. 13 gewählte tödliche Ruder,
alle bereits ohne lokale Microplans; bei keinem war noch ein Neuwurf legal,
zwölf ohne Kaffee. Somit erklärt ein vergessener noch verfügbarer Neuwurf diese
beobachteten Fälle nicht. Kein allgemeiner Unmöglichkeitsbeweis aus 40 Partien.
Der nächste begründete Schritt sind **frühere Ruder-/Schubbindungen bei noch
unbekannten Partnerkontrollen und die gemeinsame Kaffeereserve**: separaten
öffentlichen Fair-Hand-Prior mit verschiedenen Würfeln untersuchen, statt erst
den bereits nicht mehr rettbaren letzten Zug zu korrigieren. Die bisherige
Microplanung enthält bewusst noch keine solche Prognose. Gute isolierte
Physikgegenfälle oder spätere Landerunden machen sie nicht zu einem starken Lehrer.

Verbrauchte frische Entwicklung: ab **14.985.000**, Abstand 100 je lexikalisch
sortiertem Fall, 20 Seeds je Fall, zuletzt **14.986.100–14.986.119**.
Technische Vergleichstests benutzen getrennt 14.989.000/010; keine Qualifikations-
kohorte wurde verwendet. Die nächste Abschlusskohorte ab 15.400.000 bleibt
unbenutzt. Zum Abschluss dieser ersten Microplanphase lief kein schwerer Job;
zuletzt bestanden zwei Diagnosetests. Den aktuellen Stand beschreibt die neuere
Priorphase oben.

## Abgeschlossene Diagnose nach Crew 3: Leck und Karten

Der Crew-3-Veröffentlichungsauftrag ist abgeschlossen. Neues Ziel dieser Runde:
die belegten Leck-/Kartenfehler und fehlende Wind-/Eisreferenz untersuchen,
bestehende Crews/Profile nicht verändern.

Drei neue Engine-Gegenbeispiele bestehen (`tests/test_ai_wind_ice_counterexamples.py`,
0,013 Sekunden): KEF gelb + Adaptation, letzte eigene 5 auf das vierte Eispaar
gewinnt saubere Landung, Konzentration verliert `eisbremsen_unvollstaendig`.
GIG gelb + Adaptation, öffentlich aufgelöstes Ruder/Wind +3 und Distanz 1:
eigener Schub 2 mit öffentlichem Partnerschub 2 fährt ein Feld; eigener Schub 6
fährt übers Ziel. P10/P11/P12 beraten beide Alternativen gleichberechtigt.
Die Fixtures sind ausdrücklich technische öffentliche Zustände mit geskripteten
Werten, keine gesampelten Partien oder neue Quoten. Verdeckte Partnerwerte und
RNG beeinflussen die Referenzen nicht. Die physikalischen Projektionen sind
vorhanden, aber Wind/Eis fallen bisher auf `reference=allowed` zurück.

Acht neue Tests des passiven Werkzeugs `ai.leak_failure_probe` bestehen in 4,42 s:
exakt unveränderte native Auswahlfolge/Inputs/Ergebnisse, beide RNGs und Gewichte;
öffentliche Allowlist, höchstens letzte drei Ereignisse pro Verlust; bekannte
Entwicklungsseeds und Linien-/Hash-/STOP-/Ausgabeschutz.

Die passive Wiederholung der bekannten Profil-12-Validierung ist regulär
beendet, Exit 0, **80,93 Sekunden**. Log `/tmp/cockpit-leak-failure-probe-v1.log`,
abgeschlossener Bericht `ai/experiments/leak-2026-10-25/profile12-failure-probe-v1.json`
und getrennte Auswertung `profile12-failure-probe-analysis-v1.json`.
Warm0 und letzter Stand, je 20 Partien auf allen sechs ATL-gelb-Einzelkarten,
240 Wiederholungen ab 14.930.000 mit Abstand 100. Alle zwölf gespeicherten
Einzelauswertungen reproduzieren Siege, Entscheidungen, Referenzabweichungen
und Verlustgründe exakt. Keine zusätzliche unabhängige Evidenz, kein PPO.
Working-together: 911/946 legale Tauschstart-Angebote, **kein einziges in der
Referenz und kein gewählter Tausch**. Quelle verliert 10/19 Partien auf Höhe 0,
letzter Stand 12/20; einschließlich 1.000 Fuß sind es 12/19 und 16/20. Diese
Leckfehler sind überwiegend spät; die frühere Haneda-Diagnose darf nicht pauschal
übertragen werden. In den auf drei Ereignisse begrenzten Verlustspuren tauchte
kein passender sicherer Spendenfall auf; das ist kein vollständiger Pfadnachweis.

Isolierte neue Spendenprimitive `ai.leak_donation_advice`: Empfänger hat einen
Würfel und ein fehlendes Ruder, Geber beide Pflichtfelder öffentlich fertig.
Sicherer eigener Spendenwert folgt aus öffentlicher Ruder-/Schubphysik. Rückgabe
bleibt unbekannt, zählt nicht als bekannter Aufgabenwürfel und muss auf freier
Konzentration nutzbar sein. Eigene einzigartige Aufgabenwerte werden geschützt.
Acht gezielte Engine-/Privacy-/Fallbacktests bestehen (0,052 s), unabhängiger
lesender Review ohne belegten Fehler. Der echte aktuelle Crew-2-Spieler mit
Abstand 12 wählt im technischen Gegenfall selbst den neuen Tauschstart;
ursprüngliche Gewichte und Torch-/Engine-RNG bleiben exakt erhalten. Das ist
keine neue Spielquote und kein geänderter veröffentlichter Spieler.

`ai.leak_donation_environment.DonationEnv` ist ein **separater Forschungswrapper**
mit unverändertem nativen Profil 12, Engine-Maske, Schema und Uhr. Er ändert nur
im engen Fall die weiche Referenz, bewahrt `source_reference_action_mask` und
markiert `research_leak_donation=true`. Keine Änderung bestehender Profile,
Planerfingerprints oder Browsermodelle. `ai.publish` lehnt den Forschungswrapper
für Freigaben und Vorschauen ausdrücklich ab; es gibt keinen Browseradapter dafür.
29 weitere gezielte Tests bestehen (9,84 s), einschließlich unveränderter anderer
Karten/Wind/Praktikant, Rollen, nativer Auswahl/RNG/Tensoren, exakter Paarung,
STOP-/Datei-/Ressourcengrenzen und Veröffentlichungssperre. Zusammen mit den
vorigen Prüfungen **48 relevante Tests bestanden**. Eine anfängliche Testannahme
über die absichtlich feste Fixture-Uhr wurde berichtigt, keine Produktionslogik.

**Der letzte beauftragte Vergleich ist abgeschlossen**, Exit 0, 29,44 Sekunden:
`ai.leak_donation_compare`, Log `/tmp/cockpit-leak-donation-working-fresh-v1.log`,
Bericht `ai/experiments/leak-2026-10-25/donation-working-fresh-v1.json`.
Vorab festgelegtes Warm0-Netz mit Abstand 12, identische Tensoren in beiden Armen;
natives Profil 12 gegen Forschungsreferenz. Je **50 frische Entwicklungspartien**
auf ATL gelb + Working-together ab **14.984.000**, acht Worker .7, Torch 1,
nice 15, ein Lauf. Ergebnis: **5/50 gegen 5/50**, alle 50 vollständigen
Episodenrecords identisch; Paarung fünf gemeinsame Siege und 45 gemeinsame
Niederlagen, null abweichende Siege. Die neue Spendenbedingung bot auf diesen
Pfaden **keine einzige zusätzliche Aktion** an. Kein Spielstärkengewinn,
kein PPO-Update, keine Qualifikation, keine neue Modellveröffentlichung.
Nicht denselben zu selten ausgelösten Vorschlag mit mehr Spielen oder PPO als
Fortschritt behandeln. Nächster begründeter Ausbau ist breitere öffentliche
Modulplanung, insbesondere Wind/Eis anhand der oben belegten Gegenbeispiele;
für Tausch größere öffentlich begründete Fälle erst nach neuer Hypothese.

Der Nutzer bat, alle bisherigen Änderungen zu pushen und den letzten Versuch
zuvor zu beenden; beides wurde mit `050e85f` und den nachfolgenden
Crew-5-/Feedback-Veröffentlichungen erledigt.
Fremde Notebook-/Transferänderungen bleiben entsprechend der Vereinbarung
unangetastet. Alle veröffentlichten Crews und ihre Gewichte bleiben erhalten.

## Neuer Veröffentlichungsauftrag: Crew 3 mit allen positiv getesteten Fällen

Der Nutzer verlangt erneut Crew 3 mit allen Routen, auf denen sie mehr als 0 %
gewinnt. Gemeint und im Chat angekündigt ist der **aktuelle vorhandene Crew-3-
Stand**, `ai/releases/crew3-intern-preview-v1/best.pt`, Profil 10 und Abstand 4:
keine still übernommenen Leckgewichte, keine neue Trainingsbehauptung.
Vorgesehen ist eine neue Veröffentlichung `crew3-current-preview-v2` namens
**Crew 3 · Aktuell (Test)**; vorhandene Veröffentlichungen bleiben erhalten.

Alle 186 offiziellen Fälle plus sechs vorhandene Grundspielrouten
FRA/LHR/MUC/MUC_T1/MUC_T2/MUC_T3 werden einzeln mit je 20 frischen
Entwicklungspartien geprüft (192 Fälle, 3.840 Spiele). Seedfolge ab 14.960.000,
Abstand 100 je Fall, vollständig unter 15.000.000. Nur tatsächlich positive
Einzelfälle (`wins > 0`) werden angeboten; 0/20 beweist keine Unmöglichkeit.
Explizite Falllisten gelten auch für Strecken ohne Karten. Anzeige nennt
Entwicklungsquote, keine unabhängige Freigabe (`quality.approved=false`).

Neue Module/Karten werden hier zunächst **getestet, nicht nachtrainiert**.
Eine spätere Metadatenkopie für die Veröffentlichung bewahrt alle Tensoren,
ursprünglichen Trainingsfelder und Zähler. Zusätzliche Laufzeitangaben und
getestete Fälle werden als reine Preview-Erweiterung getrennt dokumentiert.
Das neue `ai.preview_matrix_eval` und gemischte Falllisten sind implementiert.
30 relevante Python-Tests in 8,58 Sekunden und der strikte Node-Fallvertrag
bestehen. Read-only-Review ohne Befund. Das Frontend prüft ganzzahlige Siege,
konsistente Quote und exakte Fallzugehörigkeit auch ohne Karten. Neue Module
werden nicht pauschal aus `supported_airports` freigeschaltet.

Die vollständige Auswertung `ai.preview_matrix_eval` ist regulär beendet,
Exit 0, 167,22 Sekunden. Log `/tmp/cockpit-crew3-current-matrix-v1.log`,
abgeschlossener Bericht `ai/experiments/crew3-current-2026-10-25/matrix-development-v1.json`.
Alle **192 Fälle / 3.840 Partien**, keine Trunkierungen, echte Engine-Uhr auch bei
Echtzeit. 51 positive Fälle auf **18 Routen** (zwölf offizielle plus sechs alte
Grundspielrouten). Alle 141 Nullfälle bleiben vollständig im Bericht. Kein
unabhängiger Test, keine neuen Trainingsentscheidungen und keine neue Policy.
Modell-, Tensor-, Planer-, Engine- und Matrixhashes vor/nach dem Lauf geprüft.

Der neue Release `ai/releases/crew3-current-preview-v2/best.pt` ist lokal
zusammengestellt, **Crew 3 · Aktuell (Test)**. Exakt dieselben Tensoren und dasselbe
Browserasset wie bisheriges Crew 3, SHA
`d68bf9e86a7c2b514cb503f6e3aea12ef703f56f7b559c13b2649ab5acba7a8c`.
Keine zusätzlichen gelernten Modulkenntnisse behauptet. Reine Metadaten-Erweiterung
samt vollständiger ursprünglicher Trainingskonfiguration ist unter
`source-lineage.json` dokumentiert; Profil 10/Abstand 4 und 120.272 Phasenentscheidungen
bleiben unverändert. Testbare Erweiterung: Praktikant/Kerosin/Echtzeit und genau
die 39 positiv getesteten Kartenkombinationen, dazu zwölf kartenlose Fälle.
Wind/Eis/Leck haben mit diesem Modell auf den geprüften Fällen 0/20 und sind
in dieser neuen Crew daher nicht auswählbar. Andere ausdrücklich gewünschte
schwache Previews, insbesondere Crew 4, bleiben unverändert verfügbar.

`preview.positive_only=true`, `preview.enabled=true`, `quality.approved=false`.
Alle 73 vorherigen Katalogeinträge exakt erhalten, genehmigte Crew bleibt
vorausgewählt. Der komplette Auswertungsbericht wurde bytegenau ins Release
kopiert; Quoten je Fall, keine Durchschnittsfreigabe. Drei abschließende echte
Browserprüfungen bestehen: neue Crew 3 auf MUC ohne Karten und PBH Schwarz mit
Control+Mastery (Kerosin/Echtzeit), tatsächliche NN-Platzierungen und gespeichertes
Feedback; technische Wind-/NoCard- und 0%-Sperrprüfungen; unverändertes Crew 4/
Profil 11 mit allen sechs Karten; Daumen-/Mobil-/Privacy-/Speicher-/Cloudretry-
Regression. Chrome und Scoped-Server geschlossen, letzter Job regulär Exit 0.
Kein schwerer Job aktiv. **Mit `efa65649a65e55103220b47e95fb55694a846126`
nach main gepusht und erfolgreich per GitHub Pages deployed.** Live bytegenau
geprüft: Modellkatalog, Cacheversion, Singleplayer-JavaScript, Enginebundle und
tatsächliches Crew-3-Browsergewicht. Öffentlicher Katalog enthält alle 18 Routen
und genau 51 positive Fälle dieses Releases sowie alle 73 bisherigen Einträge.
Der Veröffentlichungsauftrag ist abgeschlossen; das 30–40-%-Ziel aller Module
bleibt offen.

## Aktueller Auftrag: weitere Module, zunächst Praktikant

Der Nutzer hat nach der Veröffentlichung ausdrücklich weitere Module beauftragt.
Nächste reale offizielle Fälle sind Atlanta-grün (`LOG_ATL_GREEN`) und
Heathrow-gelb (`LOG_LHR_YELLOW`), jeweils Praktikant ohne Karten. Die offiziellen
Wind-/Eisstrecken benötigen bereits Karten; solche Karten nicht für eine
scheinbare offizielle Freigabe entfernen.

**Der Praktikantenlauf ist regulär beendet**, Exit 0: `runs/intern-profile10-stage1/`,
Log `/tmp/cockpit-intern-profile10-stage1.log`, Bericht
`ai/experiments/intern-2026-10-25/profile10-stage1.json`.
120.272 **neue** Entscheidungen in 54 Updates und 2.935 Partien, davon Atlanta
64.428 und Heathrow 55.844. 579,17 Sekunden Rollout/PPO-Zeit, 903,78 Sekunden
Wandzeit einschließlich Entwicklungsbewertungen. Acht Worker zu .7, Torch 1,
nice 15, Metal-Minibatches. Quelle exakt `ai/releases/crew2-v1/best.pt`, Seed
251050, frischer Adam und ausdrücklich neue Phase. Nur der bestehende Detailzweig
lernte; die ursprüngliche Grundlage blieb exakt eingefroren.

Feste Entwicklung, je 80 Partien: ATL ab 14.940.000, LHR ab 14.950.000.
Vorher 0/80 und 1/80 Siege; ausgewähltes `best.pt` bei 120.272 neuen Zügen:
**Atlanta 21/80 = 26,25 %, Heathrow 19/80 = 23,75 %**. Auswahl vorab nach schwächerer
Route, dann Mittel; der letzte Stand wurde so tatsächlich ausgewählt. Diese
Partien wurden zur Auswahl benutzt und sind **keine unabhängige Qualifikation**.
Die nächste unabhängige Kohorte ab 15.400.000 bleibt unbenutzt.

Auf ausdrücklichen Wunsch wird dieser Stand bereits als
**Crew 3 · Praktikant (Test)** (`ai/releases/crew3-intern-preview-v1/best.pt`)
mit beiden Routen angeboten. Tatsächlicher Gewichts-SHA:
`d68bf9e86a7c2b514cb503f6e3aea12ef703f56f7b559c13b2649ab5acba7a8c`.
Browserasset `b101798fc398d46a28ba3c323399ae1ebe9ec85a2ff77bd5760b591b25677707.json`.
`quality.approved=false`, `preview.enabled=true`, ausdrücklich Entwicklungsdaten;
keine automatische Auswahl anstelle genehmigter Crews. Kein Karten-/Wind-/Eis-
oder weiterer Modulnachweis. Der Bericht
`profile10-preview-development-v1.json` und `development.json` im Release
enthalten dieselben tatsächlichen Einzelquoten.

Vor jedem neuen schweren Job Prozesse, `runs/ai-job.json` und STOP prüfen.
Nicht während eines aktiven Vergleichs dessen Planungs-/Trainingsquellen ändern.
Der begrenzte Vergleich `ai.intern_strength_compare` ist regulär beendet, Exit 0.
Log `/tmp/cockpit-intern-strength-v1.log`, vollständiger Bericht
`ai/experiments/intern-2026-10-25/intern-strength-v1.json`, separate gepaarte
Auswertung `intern-strength-v1-analysis.json`. 320 Partien insgesamt,
acht Worker zu .7, Torch 1, nice 15. Je 40 frische Entwicklungspartien auf
Atlanta ab 14.980.000 und Heathrow ab 14.990.000, keine Abschlusskohorte.

| Variante | Atlanta | Heathrow | Schwächere Route |
| --- | ---: | ---: | ---: |
| Ursprüngliche Quelle, Abstand 4 | 0/40 | 2/40 | 0 % |
| Trainiertes Modell, Abstand 4 | 14/40 | 13/40 | 32,5 % |
| Gleiche Tensoren, Abstand 8 | 17/40 | 12/40 | 30 % |
| Gleiche Tensoren, Abstand 12 | 17/40 | 12/40 | 30 % |

Der trainierte Spieler verbessert beide frischen Entwicklungsrouten deutlich
gegenüber der Quelle. Ein größerer Referenzabstand ist kein konsistenter Vorteil:
er verbessert Atlanta und verschlechtert Heathrow. Abstand 4 bleibt nach dem
vorab festgelegten Kriterium; **Crew 3 bleibt exakt unverändert**. Abstand 8/12
führt in allen 80 Spielen zu denselben Ausgängen, keine zusätzlichen unabhängigen
Modelle oder Partien. Diese kleine Probe ist keine unabhängige Qualifikation.

Nächster begründeter Modulschritt: Leck, zunächst offizielles Atlanta gelb mit
jeder der sechs erlaubten Einzelkarten. Das Rohschema beobachtet den tatsächlichen
Kerosinstand, aber die alte Grundspielsuche ignoriert Leckkosten. Ein Leck hat
kein Kerosinfeld; `fuel.present=true` würde eine falsche Zusatzaufgabe erzeugen.
Die Kosten `abs(Pilotschub-Kopilotschub)+1` müssen direkt mit dem hypothetischen
Schubpaar und seinen Bewegungsfolgen bewertet werden. Neue Planung separat
entwickeln, engineprüfen und ausdrücklich neue Phase/Profile deklarieren.

### Laufende Leck-Diagnose nach dem Preview-Push

Crew 4 und alle sechs Kartenfälle sind mit
`7d60ffa921cafb9cd321a93426ca0133667bf78d` nach main gepusht und live bytegenau
geprüft (Katalog, Cacheversion, Singleplayer, Enginebundle, tatsächliche Gewichte).

Der Leckvergleich `ai.leak_strength_compare` ist regulär beendet, Exit 0,
199,24 Sekunden. Log `/tmp/cockpit-leak-strength-v1.log`, vollständiger Bericht
`ai/experiments/leak-2026-10-25/leak-strength-v1.json`. Sechs Varianten:
ursprüngliche Phasenquelle und vorab gewähltes Leckmodell, jeweils endlicher
Referenzabstand 4/8/12. Identische Tensoren innerhalb einer Herkunft; keine
zusätzlichen unabhängigen Trainingslinien. Beide Kontrollen (Quelle 4 und
Kandidat 4) sind je Fall gepaart gespeichert.

Genau sechs Einzelkarten, je 20 frische Entwicklungspartien ab 14.920.000 mit
Abstand 100. 720 simulierte Partien, ein gemeinsamer Satz von 120 Fall/Seed-Paaren
unter sechs Konfigurationen, acht Worker zu .7, Torch 1, nice 15, kein Training.

| Karte | Quelle 4 / 8 / 12 | Trainierter Kandidat 4 / 8 / 12 |
| --- | ---: | ---: |
| Adaptation | 1 / 2 / 3 | 0 / 2 / 3 |
| Anticipation | 0 / 1 / 1 | 0 / 1 / 1 |
| Control | 0 / 1 / 2 | 0 / 3 / 4 |
| Mastery | 0 / 1 / 1 | 0 / 0 / 0 |
| Synchronisation | 0 / 2 / 4 | 0 / 2 / 3 |
| Working-together | 0 / 2 / 2 | 0 / 1 / 0 |

Alle Werte Siege aus je 20. Abstand 12 weicht in diesen Spielen nie von der
Referenz ab; das ist keine generelle Garantie. Stärkere Vorgabe hilft mehreren
Fällen, doch das trainierte Modell bleibt bei zwei Karten sieglos. Die Quelle
mit Abstand 12 erreicht 5–20 % je Karte; der kleine Entwicklungsvergleich ist
keine Qualifikation. **Keine bestehende Crew geändert oder Konfiguration heimlich
umgestellt.** Der Vergleich hinterließ keinen aktiven Job. Sieben gezielte Tests bestehen.

Nächster begründeter Schritt: getrenntes neues öffentliches Profil für das
belegte Anpassungsmanöver; dann neue Phase aus den ursprünglichen Gewichten mit
explizit stärkerem endlichem Planungsabstand und frischem Adam. Neue Hashes,
Anfangsgewichte und Konfigurationsänderung ehrlich festhalten. Keine 80.206
Entscheidungen der schwächeren Linie als geerbtes Lernen ausgeben.

Zusätzlicher enginegeprüfter öffentlicher Gegenfall (keine NN-Präferenzprobe):
`public-card-rescue-v1.py` und abgeschlossener Bericht `public-card-rescue-v1.json`.
Pilot hat als letzten freien Würfel 1, Partner-Ruder 4 liegt, Fluglage 0,
Kaffee/Neuwurf 0. Profil 11 empfiehlt ausschließlich Ruder 1 und trudelt sofort
mit +3. Die legale Anpassung dreht 1→6, danach Ruder 6 überlebt mit −2.
Die Quelle ist eine legale öffentliche Platzierungsfolge; kein Partnerblick,
kein zukünftiger Spiel-RNG. Das belegt ein fehlendes Kartenmakro der Referenz,
keine Verbesserung einer Modellquote. Adaptation ist einmal je Person pro Flug,
nicht jede Runde. Weitere Erweiterung separat entwickeln und engineprüfen;
Profil 11 und bestehende Releases nicht still verändern.

Der beobachtete Unterschied „Verkehr auf jedem überflogenen Feld“ gegenüber
„sofortige Kollision nur am Abflugfeld“ rechtfertigt keine pauschale Entfernung
des Strafterms: übersprungene Flugzeuge bleiben unerreichbar und verhindern
später die Landung. Kein belegter nutzbarer Regelvorteil. Ruderauflösung,
einmalige Leckzahlung und eigene Aerodynamikänderungen wurden korrekt gefunden.

### Neue öffentliche Planungsphase 12: Anpassung als geplantes Manöver

Der abgeschlossene Leckvergleich und der öffentliche Gegenfall sind mit
`78de538` gesichert und gepusht. Danach wurde ein **neues Profil 12** ergänzt;
Profil 11 und alle vorhandenen Releasegewichte bleiben unverändert. Neue
Quelldatei `ai.leak_card_advice` plant eine legale Anpassung als 1→6 bzw.
allgemein 7−Augenzahl-Manöver vor der anschließenden gewöhnlichen Handplanung.
Die virtuelle Hand hat dieselbe Würfelanzahl. Platzierungs-/Kaffeeregeln werden
für die veränderten Augen neu berechnet; keine alte Gesichtsmaske wird kopiert.

Normale Pläne und höchstens vier verschiedene Augenwert-Manöver werden gemeinsam
bewertet; ein Kartenverbrauch kostet einen weichen Punkt und muss netto einen
normalen Plan verbessern. Das ist eine begrenzte Heuristik, kein exakter
Gewinnwert oder Beweis richtiger Ressourcenbewertung. Fehlende/verwendete Karte,
andere Physik und Dialoge fallen exakt auf Profil 11 zurück. Keine Zeitlimits
oder lastabhängiges Weglassen von Kandidaten: feste Arbeit (maximal Beam 24),
CPU-Pausen etwa alle 20 ms ändern keine Referenzmaske. Native Worker übergeben
`planning_cpu_duty_cycle=.7`, Browser rechnet mit 1; Beobachtung/Maske bleiben gleich.
Gemessen etwa 20–52 ms CPU je neuer Planungsentscheidung, mit .7 etwa 33–73 ms
Wandzeit. Neun neue gezielte Tests plus sieben bestehende Lecktests bestehen,
inklusive beider Rollen, echter Rettungsfolge, Kartenverbrauch über Runden,
virtueller Legalität, Privacy, deterministischem Pacing und Browserbridge.

`ai.train_leak` kann jetzt ausdrücklich `--assistance-version 12 --guide-margin 12`
verwenden. Standard 11/4 bleibt semantisch erhalten, aber **kein exaktes Resume
alter Fingerprints**. Ein neuer Aufruf startet erneut von originalem
`ai/releases/crew2-v1/best.pt`, frischem Adam, Zählern und Replay 0; die 80.206
Entscheidungen der schwächeren Linie werden nicht geerbt. Gewichtsdatei-Fingerprint
vor Override und Anfangs-Fingerprint danach werden getrennt aufgezeichnet;
Tensorhashes stimmen exakt überein. Die endliche Vorgabe verändert ausdrücklich
die Anfangswahrscheinlichkeiten, keine Tensorwerte. Bestehender Detailzweig lernt,
ursprüngliche Grundlage bleibt eingefroren. Phasehash umfasst nun auch den
verwendeten Kopier-/Hashhelper; alte Reports bleiben unverändert.

Der technische Metal-Probelauf `runs/leak-profile12-smoke-v1` ist regulär fertig:
69 neue Entscheidungen, ein echtes Update, Grundlage exakt unverändert,
trainierbarer Detailzweig verändert. Anfangstensoren exakt originales Crew-2-
Release, Modellkonfiguration mit Abstand 12 ausdrücklich anders. Bericht
`profile12-smoke-v1.json`; Probelaufgewichte werden verworfen. Zehn fokussierte
Trainer-/Fallbewertungstests bestehen, inklusive echtem 12/12-Rollout→PPO.

**373 Python-Tests bestanden in 99,55 Sekunden**, verwalteter Job Exit 0,
Log `/tmp/cockpit-leak12-tests.log`. Drei echte Browserprüfungen bestehen:
Profil 12 mit originalen Crew-2-Tensoren und ausdrücklich Abstand 12 wählt selbst
Anpassung 1→6 und anschließend Ruder 6 des KI-Kopiloten; Fluglage +2, Flug läuft
weiter. Dies ist ein technischer öffentlicher Gegenfall, keine neue Spielquote.
Unverändertes Crew 4/Profil 11 mit allen sechs Karten sowie Daumen-/Mobil-/
Speicher-/Cloudretry-Verhalten sind ebenfalls geprüft. Chrome und scoped Server
sind geschlossen; danach wurde nur der unten genannte Lauf gestartet.
Unabhängiger Read-only-Review ohne konkreten Befund; bestehende Modellkataloge
und Releasegewichte bleiben exakt erhalten.

**Profil 12 ist regulär beendet, Exit 0**: `runs/leak-profile12-stage1/`,
Log `/tmp/cockpit-leak-profile12-stage1.log`, abgeschlossener Bericht
`ai/experiments/leak-2026-10-25/profile12-stage1.json`. 80.139 neue Entscheidungen,
1.425 Trainingspartien, 35 Updates, 386,35 Trainingssekunden und 547,17 Sekunden
Gesamtwandzeit. Grundlage exakt eingefroren; 57 Trainingssiege, erfolgreiche
Selbstnachahmung erstmals aktiv (35 von 35 Updates mit positiver demo_loss).
Alle sechs Fallzähler summieren exakt auf 80.139. Quelle erneut originales Crew 2;
keine vorherige schwache Linie geerbt. Geprüfter Code mit `f6948ad` nach main
gepusht und Pages deployed; Enginebundle und Cacheversion live bytegenau.

Entwicklung je 20 Partien/Karte, Seed 251057 und Evaluationsbasis 14.930.000,
Abstand 100. Reihenfolge Adaptation/Anticipation/Control/Mastery/Synchronisation/
Working-together: **Anfang 2/1/4/2/1/1**, bei 45.694 Zügen **1/2/4/2/3/0**,
letzter Stand **1/3/3/2/4/0** Siege aus je 20. Nach vorab festgelegtem Minimum-
Kriterium bleibt **best.pt tatsächlich der Warmstand bei 0 neuen Zügen**.
57 erfolgreiche Trainingspartien sind ein Fortschritt gegenüber der sieglosen
Profil-11-Trainingslinie, aber keine Verbesserung der schwächsten Entwicklungs-
karte. Kein unabhängiger Test und kein Profil-12-Modell veröffentlicht. Nicht
unverändert weitertrainieren oder den warmen Stand als neu gelernten Erfolg
verkaufen. Zuerst der neue Crew-3-Veröffentlichungsauftrag, danach konkrete
Working-together-Fehler bzw. erfolgreiche enginegeprüfte Kartenübungen untersuchen.
Kein schwerer Job nach Abschluss aktiv; nächste Auswertung separat prüfen.

### Abgeschlossene neue Phase: Leck auf Atlanta gelb

Implementiert und gezielt geprüft: öffentliches Modulprofil **11**, getrennt von 10. Die bestehende
Handplanung erhält einen optionalen Schub-Bewertungshook, der ohne Hook exakt
die bisherigen Rechenwege bewahrt. `ai.leak_advice` bewertet für jedes öffentliche
oder hypothetische Schubpaar die tatsächlichen Leckkosten und die notwendige
Mindestreserve für spätere Runden. Die öffentliche Partnerprior-Verteilung bleibt
eine Näherung; sie ist weder eine gelesene Partnerhand noch ein exakter
Gewinnwert. Bereits vollständig platzierter Schub hat bereits Kerosin verbraucht
und wird nicht nochmals belastet. Gemischte Wind-/Eis-/Praktikantenphysik und
Bonus-/Tauschdialoge behalten vorerst die bisherige Planungsreferenz.

`ai.train_leak` ist eine neue explizite Phase mit frischem Adam aus den originalen
Crew-2-Gewichten, ohne zusätzliche Netzschicht. Nur der vorhandene Detailzweig
lernt, die ursprüngliche Grundlage bleibt eingefroren. Der echte Lauf `runs/leak-profile11-stage1/`, Log
`/tmp/cockpit-leak-profile11-stage1.log`, ist regulär beendet, Exit 0.
**80.206 neue Entscheidungen**, 2.481 Trainingspartien und 37 Updates,
331,12 Rollout/PPO-Sekunden, 416,27 Sekunden gesamte Wandzeit. Budget war
höchstens 80.000 neue Entscheidungen oder 600 Trainingssekunden plus letzte Charge,
acht Worker zu .7, Torch 1, nice 15 und Metal-Minibatches. Alle sechs offiziellen
Einzelkarten von `LOG_ATL_YELLOW` werden gleichberechtigt trainiert. Auswahl nach
der schwächsten Karte, Mittel nur bei Gleichstand. Keine unabhängige Kohorte.

Entwicklung über `ai.public_case_eval.run_public_case` mit echter `ModuleEnv`,
ausdrücklichem Route/Kartenfall, ohne Allmodul-Forschungswrapper und ohne
Proxy-Uhr. Je 20 Partien pro Karte ab 14.910.000 mit Abstand 100, vor Training,
alle 20 Updates und am Ende. Dies sind Entwicklungsdaten, keine Qualifikation.
Neue Quelldateien und der optionale Hook ändern den Fingerprint ehrlich;
alte Reports/Hashes bleiben unverändert. Der Praktikantenvergleich wurde noch
vor dieser neuen Phase unter dem damaligen Fingerprint abgeschlossen. Er darf
nicht mit manipulierten alten Hashes als exaktes Resume fortgesetzt werden.

Sieben gezielte Leck-Engine-/Privacytests, vier Tests der echten Fallbewertung
und drei echte Rollout/PPO-/CLI-Tests bestehen. Dabei fiel ein realer
Integrationsfehler auf: `ModuleEnv.episode_record` enthielt bisher keine tatsächlichen
Modul-/Kartennamen. Diese öffentlichen Metadaten wurden ergänzt und die
fallgenauen Trainingszähler anschließend erfolgreich geprüft.

Der kleine Metal-Probelauf `runs/leak-profile11-smoke-v1` ist regulär beendet:
31 neue Entscheidungen, ein echtes Update, ursprüngliche Crew-2-Anfangsgewichte
exakt, Grundlage unverändert, Detailzweig tatsächlich verändert. Bericht
`ai/experiments/leak-2026-10-25/profile11-smoke-v1.json`. Seine Gewichte werden
nicht als Trainingsquelle verwendet. Aktive Worker wurden mit Priorität 15 und
etwa 58–64 % CPU beobachtet. Im echten Lauf Seed 251054, Quelle weiterhin
originales `ai/releases/crew2-v1/best.pt`, frischer Adam. Aktuelle Zähler/Quoten aus
Logs lesen, währenddessen keine aktiven Trainings-/Planungsquellen ändern.

Der gewählte letzte Stand bei 80.206 neuen Zügen erzielt je 20 feste
Entwicklungspartien: **Adaptation 1/20 = 5 %, Anticipation/Control/Mastery/
Synchronisation/Working-together jeweils 0/20**. Vorher und bei 44.191 Zügen
alle sechs Fälle 0/20. Best wurde regelgemäß nach schwächstem Fall und Mittel
bei Gleichstand gewählt; auch die Anfangsgewichte waren zugelassen. Das Ziel
ist klar nicht erreicht. Kein neues unabhängiges Testset verwendet.

Die tatsächlichen Fallzähler: Adaptation 13.714, Anticipation 14.719, Control
12.503, Mastery 14.387, Synchronisation 10.797, Working-together 14.086.
Zusammen genau 80.206. **Keine der 2.481 stochastischen Trainingspartien wurde
gewonnen; die vorgesehene Selbstnachahmung erfolgreicher Partien war daher in
keinem Update aktiv.** Das ist ein konkreter Befund des Lernpfades, kein Beweis,
dass der Planer allein die Ursache ist. Nicht einfach denselben Lauf verlängern.
Als nächste begrenzte Diagnose öffentliches Referenzspiel und NN-Auswahl trennen
(z.B. endliche Abstände 4/8/12 auf neuen Entwicklungsfällen), anschließend
enginegeprüfte erfolgreiche Übungen/Partien erzeugen und konkrete frühe
Trudel-/Verkehrs-/Kerosinfehler lokalisieren.

Auf ausdrücklichen Nutzerwunsch wird der sehr schwache Zwischenstand zusätzlich
bereitgestellt: **Crew 4 · Leck (Test)**,
`ai/releases/crew4-leak-preview-v1/best.pt`, Gewichts-SHA
`14c9420c314b318c8cc134fa4aaa1dd1a8b80abe476f3b6a8c29fb772151a3d2`.
Alle sechs offiziellen Einzelkarten auf `LOG_ATL_YELLOW` werden einzeln
aufgelistet, auch die 0-%-Fälle. `quality.approved=false`, `preview.enabled=true`,
keine Prognose menschlicher Gewinnquoten, keine Freigabe. Daten:
`ai/experiments/leak-2026-10-25/profile11-stage1.json` und separate
`profile11-preview-development-v1.json`, identisches Release-development.json.

Neue Kartenrouten benötigen `preview.supported_cases` und fallgenaue
`preview.case_results`; ein bloßer Routeneintrag reicht nicht. Das Kartenset wird
explizit ausgewählt und beim Start erneut geprüft. Die Sitzung speichert den
exakten Fall. KI-Tausch wählt/bestätigt atomar mit einer Undo-Revision;
legale menschliche Offturn-Kartenschritte werden ohne falsches Policylabel erfasst.
Kein weiterer schwerer Trainingslauf aktiv. Die vollständige lokale Testsuite
besteht: **354 Tests in 93,79 Sekunden**. Zusätzlicher echter Vergleich mit dem
Code aus `7fcaf14`: 72/72 Ranglisten und Sequenzen exakt unverändert (24 öffentliche
Grundspiel-/Kerosinviews, Versionen 1/3/4, sieben Landungsviews). Profil 11 stimmt
in 24/24 Route/Karte/Rolle/Zustandsfällen nativ mit der Browserbridge überein;
24/24 Partnerhand-Poisoningprüfungen bleiben unverändert. Das sind technische
Nachweise, keine zusätzlichen Qualifikationspartien. Dokumentiert unter
`profile11-technical-checks.json`. Alle 72 bisherigen Katalogeinträge sind exakt
erhalten. Alle **sechs echten Browserprüfungen** bestehen: Crew 4 mit exakten
Kartenfällen/echten Gewichten, Crew-3-Vorschau, Praktikantenruntime, Kerosin,
ursprüngliche Crew 2 und vollständiges Daumen-/Mobil-/Speicherverhalten. Neue
Kartenfixture-Korrekturen betrafen nur den regelgemäßen Synchronisationsakteur,
die Wartezeit auf eine abgeschlossene Speicherversion und den Ergebnisdialog;
kein Produktionsfix nach der vollständigen Python-Suite. Chrome und Scoped-Server
sind beendet, letzter Job finished/0. Mobile Kartenauswahl bei 390 px visuell geprüft.
Geprüfter Code und abgeschlossene Berichte werden nach main gepusht.

Neues **öffentliches Modulprofil 10** in `ModuleEnv`: separate, weiche
Planungsreferenz, gemeinsame Kapazitätsregel, weiterhin lernbare Alternativen.
Grundspiel/Kerosin ohne Karten ist exakt Profil 9 mit Referenz 7 gleich.
Kompatible Kerosin-/Kartenfälle erhalten wieder öffentliche Kerosinplanung.
Praktikant erhält eine Rundenquote und eine Planung für den tatsächlich
ausgegebenen Ersatzwürfel. Er ersetzt einen regulären Würfel und zählt nicht
als zusätzlicher fünfter Handwürfel. Ziele für Ruder, Schub, Funk und Kerosin
werden mit öffentlichen Informationen bewertet. Keine Partneraugen oder echter
zukünftiger Spiel-RNG. Die bisherigen Profile/Releases bleiben semantisch
unverändert; geänderte Quelldateien ergeben ehrlich einen neuen Fingerprint,
alte Hashes werden nicht nachträglich angepasst. Der neue Lauf verwendet die
tatsächlich im Browser verfügbare `ModuleEnv`-Umgebung und keine heimlich
umbenannte Allmodul-Forschungsmaske.

Zusätzliche reine Physikfunktionen in `ai.module_physics` sind enginegeprüft:
Wind nach vollständigem Ruder, echte Schubgeschwindigkeit, strenge Eisbremsgrenze,
Leckverbrauch und notwendige Kerosinreserve. Wind-/Leckeffekte bereits öffentlicher
Kontrollpaare werden nicht zweimal berechnet. Diese Funktionen sind noch kein
Wind-/Eis-Gewinnnachweis und steuern das neue Praktikantenprofil nicht.

Neun Physiktests, sieben Praktikantenplanungstests, sechs Integrations-/Privacytests
über alle 186 Startfälle und drei echte Rollout→PPO-Tests bestanden. Letztere
zeigen korrekte Referenzmasken, exakte Logwahrscheinlichkeiten vor dem Update,
veränderten Detailzweig und unveränderte Grundlage. Technischer Metal-Probelauf
`runs/intern-profile10-smoke-v1/`: 79 Entscheidungen, ein Update, exakte Crew-2-
Anfangsgewichte, eingefrorene Grundlage bestätigt. Probelaufgewichte verworfen.

Der Browser führt jetzt echte Bonusaktionen aus, auch wenn der reguläre Zug
gewechselt hat oder keine regulären Würfel mehr übrig sind. Menschliche
Bonusaktionen werden aufgezeichnet und bestätigen Daumenfeedback; fremde
KI-Bonusziele sind nicht anklickbar. Technischer Browserfall mit echten
Gewichten und Profil 10 besteht. Dabei wurden eine fehlende Bundle-Abhängigkeit
(`ai.throttle`) und die Pyodide-`None`/JavaScript-`undefined`-Zuordnung zu
Modell-`null` behoben. Profil 10 ist gebündelt, alte Profile bleiben erhalten.
Vier abschließende echte Browserprüfungen bestehen: tatsächlicher Crew-3-Katalog
mit ehrlichem Previewstatus und beiden Routen, Praktikanten-Bonusablauf samt
Feedback, bestehende Kerosin-KI und Crew 2 mit acht Routen/beiden Rollen. Kein
JavaScript-Seitenfehler; Chrome und Scoped-Server danach beendet. Die Vorschau
zeigt die Entwicklungsquoten im Singleplayer und erlaubt Daumenfeedback.
Die vollständige lokale Testsuite besteht: **331 Tests in 87,31 Sekunden**,
einschließlich echter Rollout-/PPO-Tests, Privacy, aller 186 Adapter-Startfälle
und der unberührten fremden Transfer-Tests. Alle 71 bisherigen Katalogeinträge
blieben exakt erhalten; hinzu kommt nur das explizite Praktikanten-Preview.
Der Preview-Publisher verweigert das Überschreiben bestehender Releaseordner.
Mit `7fcaf1494cb699907708c343055d248d7946645f` nach main gepusht und per
GitHub Pages erfolgreich veröffentlicht. Live-Katalog, Cache-Version,
Singleplayer-JavaScript und tatsächliches Browsergewicht bytegenau geprüft.
Der Push enthält keine Änderungen an fremden Notebooks/Transferdateien.

## Abgeschlossener Allmodul-Lauf und Daumenfeedback

Das 20-Minuten-Budget wird nach einer erfolglosen Halbzeitprüfung in zwei
ausdrücklich getrennte Forschungsphasen aufgeteilt. `runs/allmodules-20min-v1/`,
Log `/tmp/cockpit-allmodules-20min-v1.log`, wurde nach **350.639 neuen Zügen,
160 Updates, 16.348 Partien und 668,37 Trainingssekunden** zur Wartung mit SIGINT
beendet. Kein Nutzer-Stopp und keine STOP-Datei. Checkpoint und ursprünglicher
Code sind erhalten (Commit `4fdd0eb`); der unterbrochene Bericht heißt
`ai/experiments/modules-30pct-2026-10-25/allmodules-raw-stage1.json`.
Ursprünglicher Befehl: `python -m ai.train_all_modules --run-dir
runs/allmodules-20min-v1 --training-seconds 1200 --workers 8 --cpu-duty-cycle .8
--device mps --seed 251046 --eval-seed 14800000 --eval-games-per-case 3
--eval-interval-seconds 600`, unter `nice -n15` und `ai.job_control`.

Quelle ist exakt die veröffentlichte Crew 2, frischer Adam, neue Forschungsphase
mit eigenem Umgebungsfingerprint. Nur der vorhandene Detailzweig lernt; die
Grundlage bleibt eingefroren. Der technische MPS-Probelauf
`runs/allmodules-smoke-v1/` bestätigte 107 neue Entscheidungen, ein echtes Update,
identische Anfangsgewichte und unveränderte Grundlage. Seine Gewichte wurden
nicht übernommen. 15 gezielte Tests einschließlich echtem Worker→PPO-Datenweg
bestanden vor dem langen Lauf.

Das Curriculum zieht zuerst gleichverteilt eine Route, dann deren erlaubte
Kartenkombination. Alle sechs Module und Karten werden ausdrücklich abgedeckt.
Die erste Forschungsumgebung `AllModulesEnv` bewahrt Maske 9/Referenz 7 für
Grundspiel/Kerosin ohne Karten. Andere Fälle erhalten enginelegale Auswahl mit
Referenzmaske. Eine endlose Tausch-Start/Abbruch-Folge wird verhindert. Erreichen
des Entscheidungslimits zählt als terminaler Trainingsfehler ohne Bootstrap,
während das ursprüngliche Engineergebnis unverändert bleibt. Echtzeit verwendet
eine logische Sekunde je Entscheidung: reproduzierbare Trainingsnähe, kein
Nachweis realer menschlicher Zeitdruckfähigkeit.

Das gesamte Budget zählt etwa 1.200 Sekunden Rollout/PPO-Rechenzeit; eine letzte vollständige
Charge kann die Grenze leicht überschreiten. Validierungen und Speichern kommen
zur Wandzeit hinzu. Vorher, nach 600 Trainingssekunden und am Ende werden je
drei Entwicklungspartien für jeden der 186 Fälle gespielt. Dies ist nur eine
kleine Auswahlprobe, keine Qualifikation. Auswahl zuerst nach Zahl der Fälle
mit beobachteten >=30 %, dann schwächstem Fall, erst zuletzt beschreibendem Mittel;
auch die Anfangsgewichte bleiben als `best.pt` zugelassen.

Die Anfangsprobe hatte fünf Siege aus 558 Partien, verteilt auf nur drei Fälle
(YUL drei, LHR einer, OSL einer). Eine unabhängige Datenprüfung fand 473 frühe
Verluste wegen fehlender Pflichtsteuerung und keinen Budgetabbruch. Ein zusätzlicher
öffentlicher Trainingszustand reproduziert das Problem: unter der breiten
Modulauswahl verbraucht die bisherige Politik den letzten regulären Würfel für
Konzentration statt fehlenden Schub. Das ist eine konkrete Planungsgrenze des
Ausgangsspielers, kein behaupteter Modulerfolg. Nach 315.754 neuen Zügen brachte
die Halbzeitprüfung sogar nur vier Siege in zwei Fällen; kein Verbesserungsbeleg.
Die aktiven Quellen wurden erst nach dem geordneten Ende geändert, die alte
Phase wird nicht als exaktes Resume fortgesetzt.

Die neue Phase für die verbleibenden **531,63 Trainingssekunden**,
`runs/allmodules-capacity-stage2/`, ist regulär beendet (Exit 0).
Log `/tmp/cockpit-allmodules-capacity-stage2.log`; Start wieder von exakt Crew 2
und frischem Adam, nicht von den schwachen letzten Gewichten. `CapacityModulesEnv`
reserviert nur öffentlich nachweisbar benötigte Kontrollwürfel; Praktikantentraining
bleibt als Ersatz erlaubt, ein tatsächlich ausgegebener schwarzer Würfel zählt
einmal gemeinsam. Bei möglicher späterer Synchronisation wird konservativ auf
die Beschränkung verzichtet. Neue Trainings-/Bewertungsoption `--capacity-guard`
und eigener Fingerprint; alte Produktionsprofile bleiben unverändert.
Elf enginegeprüfte Tests decken Kapazitätsregel und neue Umgebung ab. Der echte
MPS-Probelauf `runs/allmodules-capacity-smoke-v1/` endete mit 161 Entscheidungen
und einem Update; Quellgewichte am Anfang exakt gleich und Grundlage danach
unverändert. Seine Gewichte werden nicht verwendet. Insgesamt 32 gezielte
Kapazitäts-, Datenweg- und Feedbacktests bestanden. Ein leistungsfähigerer
Spieler ist damit noch nicht bewiesen.

Ergebnis: **303.770 neue Entscheidungen, 138 Updates, 11.676 Partien und
532,47 Trainingssekunden**, alle 186 Fälle besucht, Grundlage exakt unverändert.
Modulentscheidungen: Kerosin 106.368, Wind 38.642, Eis 31.021, Praktikant 28.313,
Leck 41.871, Echtzeit 28.208. Kartenzähler: Zusammenarbeit 45.261, Anpassung
44.162, Meisterung 42.666, Synchronisation 32.717, Kontrolle 41.061,
Voraussicht 41.578. Überlappende Modul-/Kartenzähler nicht aufsummieren.
Je drei feste Entwicklungspartien: zuvor YUL/LHR/OSL 3/1/1 Siege, zuletzt 3/2/1;
alle übrigen Fälle ohne Sieg. Die Auswahlregel wählt den letzten Stand, aber
dies ist **kein belegter Modulfortschritt und keine Freigabe**. Beide Phasen
zusammen verbrauchten 1.200,84 Trainingssekunden, 654.409 Entscheidungen und
28.024 Partien. Da Phase zwei erneut von Crew 2 startete, sind die verworfenen
350.639 Züge nur Aufwand, keine geerbten Trainingszüge dieses Kandidaten.
Abgeschlossene Berichte und alle 186 Einzelzeilen:
`allmodules-20min-summary.json`, `allmodules-capacity-stage2.json` und
`allmodules-20min-cases.csv` im neuen Experimentordner.

Nächste Ursache: Das rohe Modul-Referenzset ändert die Aktionsverteilung des
eingefrorenen Planers stark. Auf zwölf frischen Trainingszuständen änderte allein
eine kompatible öffentliche Kerosin-Referenz sieben Entscheidungen. Das ist
kein Gewinnvergleich. Als nächster begründeter Versuch weiche Planungshinweise
für kompatible Kerosin-/Kartenfälle prüfen, alle legalen Aktionen beibehalten.
Wind, Eis und Leck benötigen ausdrücklich ihre wirkliche Physik; den alten
Grundspielplaner dort nicht unverändert als harte Maske verwenden. Keine weitere
unveränderte PPO-Wiederholung oder unbegründete Architekturänderung.

**Unabhängige Qualifikation regulär abgeschlossen (Exit 0, 102,85 s):**
Vorab festgelegte Qualifikation
der UNVERÄNDERTEN Crew 2 auf `LOG_OSL_GREEN`, 500 Selbstspiele plus je 100 je Rolle
mit Heuristikpartner. Wieder acht Worker zu .7, Torch 1, nice 15.
Log `/tmp/cockpit-crew2-kerosene-qualification-v1.log`, Bericht
`ai/experiments/modules-30pct-2026-10-25/crew2-kerosene-qualification-v1.json`.
Neues ausdrücklich vom Nutzer akzeptiertes Kriterium: Wilson-Untergrenze >=.3.
Alte .5-Berichte bleiben unverändert. Seeds **15.200.000–15.200.499** und
**15.300.000–15.300.099** sind ab jetzt verbraucht/reserviert für diesen
vorab gewählten Test, keine Trainings-/Debugdaten. Ab **15.400.000** bleibt die
nächste unabhängige Kohorte unbenutzt. **199/500 Siege (39,8 %), Wilson
35,6–44,2 %**, bestanden. Heuristikpartner separat 6/100 als Pilotin und
9/100 als Kopilot (zusammen 7,5 %); keine Prognose menschlicher Partnerquote.
Separater Release `ai/releases/crew2-kerosene-v1/`, Name **Crew 2 · Kerosin**,
nur Oslo ohne Karten. Gewichte und Browserasset exakt identisch zur alten
Crew 2, ihre bisherige Freigabe bleibt unverändert. Die schwachen neuen
Allmodulgewichte werden nicht veröffentlicht. Weitere Module oder Karten
sind daraus nicht freigegeben.

Abschlussprüfung: **296 lokale Python-Tests bestanden** (67,12 s), einschließlich
der geschützten fremden Transfer-Tests. Ein erster temporärer Teststarter hatte
keinen macOS-Spawn-`__main__`-Schutz; nach Korrektur wurde die gesamte Suite
erneut ausgeführt. Worker-/Archivtests mit echtem SQLite ebenfalls bestanden.
Drei abschließende Browserprüfungen liefen nacheinander unter nice 15 und
`ai.job_control`: allgemeine Daumen-/Singleplayer-UI, tatsächlicher qualifizierter
Oslo-Spieler samt menschlichem Kerosinzug und Schema-3-Upload, bestehende Crew 2
auf acht Routen und mit beiden Rollen. Keine JavaScript-Seitenfehler.
Chrome und der auf 127.0.0.1 begrenzte Server sind beendet; **kein schwerer Job
mehr aktiv**. Letzter verwalteter Job: `tests/crew2-ui.cjs`, Exit 0. Vor einem
neuen Lauf weiterhin tatsächliche Prozesse/STOP/Status prüfen, Grenze wieder
acht Worker zu .7.

Der obere, mitlaufende Daumenbereich ist im Browser auf 320/390 Pixeln, mit
Tastatur, neutralem Standard, Rücknahme und letzter Spielaktion geprüft. Er
speichert +1/−1 statt der bisherigen Skala; alte Daten bleiben lesbar. Der Audit
entdeckte zusätzlich eine bisherige Cloud-Schranke für Crew-2-Daten (nur Schema 1
akzeptiert) und den fehlenden Import von Daumenfeedback ins Training. Diese
Datenwege sind jetzt korrigiert: Worker-Version
`b850056c-0c7c-49d4-a6e1-6001feee32a5` nimmt registrierte Schemas 1/2/3 an;
technischer Crew-2-Liveupload mit HTTP 200 und D1 geprüft, eigene Testzeile wieder
entfernt. Daumenpanel ist mit `8a11642` gepusht und live bytegleich geprüft.
`ai.feedback` importiert bestätigte explizite Bewertungen samt ursprünglicher
Referenzmaske, ohne Schema-Padding. `ai.train_feedback` bietet einen optionalen
Offline-Actor-Kopf-Lauf mit KL-Begrenzung und Validierung nach ganzen Partien.
Grundlage, Encoder und Kritiker bleiben unverändert; mindestens 64 informative
Bewertungen aus vier Partien. Kandidaten erben keine alte Freigabe.
14 gezielte Import-/Refinementtests bestanden. Vorhanden sind erst 16 nicht
neutrale alte Schema-1-Bewertungen aus drei Partien; damit wurde kein Modell
trainiert. Die Speicherung allein verändert weiterhin keine Gewichte.

## Abgeschlossene erste Versuche

Der Kerosinlauf erreichte 500.292 kumulative neue Modulentscheidungen. Auf 200
festen Entwicklungspartien lag der beste Stand bei 31,5 %, der letzte bei 29,5 %.
Die 80-Partien-Probe zuvor stieg auf 36,3 %; sie ist nicht derselbe Prüfvertrag.
Mehr Training dieses eingeschränkten Lernzweigs hat das 50-%-Ziel nicht erreicht.
Berichte: `ai/experiments/kerosene-2026-10-25/`.

Der Forschungsadapter `ai/modules.py` hat 489 Eingänge und 217 Aktionen für
alle sechs Module und Karten. Alle 186 Fälle starten, die geprüften Feldaktionen
stimmen mit der Engine überein und verdeckte Partnerwürfel bleiben ausgeschlossen.
Der schwarze Synchronisationswürfel wird als EIN gemeinsamer Würfel gezählt.
Echtzeitablauf, Praktikantentoken, Eisbremsen, Anpassung und bestätigter Tausch
haben eigene Tests. **Das ist Regelunterstützung, kein Nachweis guter Spielstärke.**
Im Browser stimmen Beobachtungen und Masken aller 186 Startaufstellungen mit
nativem Python überein (0,181 s für den vollständigen Vergleich). 204 Tests
bestanden; anschließend wurden nur die Routenentscheidungszähler ergänzt,
deren Summe sich im laufenden PPO-Protokoll exakt mit den Gesamtschritten deckt.

Das neue Netz erhält den alten Spieler als eingefrorenen Teil und ergänzt einen
zweischichtigen 256er-Residualzweig. Dessen Actor-/Kritikerausgänge beginnen bei
null, wodurch die bisherige Politik anfangs erhalten bleibt. Das Vortraining
lernt nur den neuen Encoder und temporäre Köpfe für erlaubte Aktionen sowie
öffentliche Aktionsfolgen. Gezielte Wind-/Ruder-, Schub-/Leck-, Eis-, Kerosin-
und Praktikantenübungen werden über die Engine ausgeführt. Es sind synthetische
Regelübungen, keine behaupteten gewonnenen Partien.

Finales Regelvortraining `runs/rules-allmodules-v3/rules.pt`: 37.016 Übungen,
12.375 getrennte Validierungsübungen, 99,73 % ausgewogene Regelerkennung.
Der mittlere Fehler öffentlicher Folgezustände sank unter die Nulländerungs-
Baseline. **Wind ist im Einzelvergleich weiterhin schwach**; diese Regelquote
ist keine Gewinnquote. Berichte mit Fehlern je Größe stehen unter
`ai/experiments/modules-50pct-2026-10-25/rule-pretraining-v3.json`.

## Residual-PPO abgeschlossen und Planungsmaske untersucht

`runs/modules-residual-stage1/` endete regulär nach **500.313 neuen PPO-Zügen**
in 25,4 Minuten. Davon entfielen 215.980 auf Oslo/Kerosin; 284.333 waren
Grundspielzüge auf HND/LHR/YUL. Mit 100.054 übernommenen Kerosinzügen sind es
316.034 kumulative Modulzüge. Die 37.016 Regelübungen bleiben separat.
Bericht: `ai/experiments/modules-50pct-2026-10-25/residual-stage1.json`.

Initialisierung war `runs/rules-allmodules-v3/rules.pt`, Seed 251026,
Curriculum OSL/OSL/OSL/HND/HND/LHR/YUL und Gewinnzug-Nachahmung mit Gewicht 0,03.
Auf jeweils 200 festen Entwicklungspartien ab 14.000.000 änderten sich die
Quoten von OSL 31,5 / HND 33 / LHR 69 / YUL 81,5 % auf zuletzt
**34,5 / 34 / 65 / 80 %**. Der nach schwächster Route gewählte Stand ist am Ende
identisch mit `latest.pt`. Kein ausreichender Fortschritt, keine Freigabe.
Für neue Läufe wurde korrigiert, dass auch das unveränderte Ausgangsmodell
als bester Stand erhalten werden kann; zuvor wurde die erste trainierte
Messung selbst bei Verschlechterung gespeichert.

`ai.planner_probe` misst passiv rohe Regelmasken, Kapazitätsgrenzen und die
engere Suchauswahl, ohne RNG oder Spielentscheidungen zu verändern. Gleiche
Würfel auf demselben Zielfeld zählen als dieselbe inhaltliche Wahl.
Auf zusätzlichen 100 Entwicklungsseed-Partien je Route ab 14.100.000:

| Stand | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Ausgang | 28 % | 29 % | 64 % | 78 % |
| Ende | 33 % | 31 % | 62 % | 85 % |

Beim Endstand sind rund 30 / 51 / 48 / 47 % der Entscheidungen inhaltlich
erzwungen, während die Kapazitätsmaske allein nur 3,5 / 4,9 / 3,0 / 1,8 %
vollständig erzwingt. Das begründet einen Versuch mit mehr Strategieraum,
beweist aber nicht, dass entfernte Aktionen gut wären. `best.pt` und `latest.pt`
haben identische Gewichte: deren wiederholte Prüfung zählt NICHT als zusätzliche
unabhängige Stichprobe. Bericht: `planner-probe-v1.json` im selben Berichtsordner.

Forschungsprofil 9 für Schema 2/3 erweitert ausschließlich Platzierungen auf
16 Scorepunkte Abstand zum besten Plan. Kaffeeauswahl, Neuwurfauswahl,
Budgetgrenzen und Profile 3–8 bleiben gleich. Das separate Grundspielprofil 9
bleibt unverändert. Eine Probe mit den unveränderten Ausgangsgewichten ergibt
nur **4 / 6 / 18 / 50 %**: mehr Aktionen ohne passenden Lernstart schadet.
Bericht: `planner-probe-wide-v1.json`. Diese Maske wird nicht veröffentlicht.

## Politikvortraining und abgeschlossener DAgger-Versuch

`runs/planner-distillation-v1/` ist nach 40 Epochen abgeschlossen. Das vorhandene
Hybridmodell mit Profil 7 erzeugte in 400 frischen Trainingspartien 23.439
erlaubte eigene Beobachtungen und Aktionsverteilungen. 100 zusätzliche Partien
lieferten 5.734 Validierungsbeispiele in einem getrennten String-Namensraum.
Diese Daten kommen weder aus den PPO-Validierungs- noch aus den Prüfseeds.
Auch verlorene Lehrerpartien sind enthalten; dies ist kein stärkerer Experte.

Ein weiterer Residualzweig lernt die Lehrerpolitik unter der breiteren Maske 9.
Sein Encoder übernimmt die bisherigen Merkmale; die alten Gewichte bleiben
eingefroren. Der neue Kritiker bleibt während dieses Politikvortrainings null,
damit Wertlernen die Nachahmung nicht stört. Auswahl nach Validierungs-KL,
**nicht** nach einer behaupteten Gewinnquote. Nachahmungsbeispiele und PPO-Züge
werden getrennt gezählt. Der neue Planerfingerabdruck beginnt einen expliziten
neuen Forschungsabschnitt; kein exaktes Resume des alten Laufs. Validierungs-KL
2,468 → 0,615; Übereinstimmung mit Lehreraktionen zuletzt 75,76 %.
Auf denselben zusätzlichen 100 Entwicklungsseed-Partien je Route wie der Lehrer
(14.100.000) erreicht der Schüler nur **11 / 15 / 24 / 55 %**, gegenüber
33 / 31 / 62 / 85 % beim Lehrer. Noch keine ausreichend erhaltene Spielweise.
Berichte: `planner-distillation-v1.json`, `planner-distillation-games-v1.json`.

`runs/planner-dagger-v1/` ist nach 200 Epochen beendet. Derselbe eingefrorene
Lehrer beschriftete auch vom Schüler erreichte Zustände. In 50 % der Züge
entschied der Schüler, sonst der Lehrer; separater Verhaltens-RNG, keine
zukünftigen Spielwürfe. Seed 251029 ergänzte 23.444 Trainings- und 5.793
Validierungsbeispiele, insgesamt 46.883 / 11.527 im jeweils getrennten Split.
Kein dritter Residualzweig wurde angelegt. Der beste Validierungs-KL lag in
Epoche 52 bei 0,4954; bis Epoche 200 stieg er auf 0,5968 (Überanpassung).
Die beste Aktionsübereinstimmung am ausgewählten Stand beträgt 78,28 %.

Auf je 100 neuen, identischen Entwicklungsseed-Partien ab 14.200.000:

| Modell | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Lehrer, Profil 7 | 33 % | 30 % | 68 % | 84 % |
| DAgger, Profil 9 | 20 % | 18 % | 40 % | 72 % |

Der Schüler ist weiterhin deutlich schwächer; daher kein PPO-Start aus diesem
Stand und keine Freigabe. Berichte `planner-dagger-v1.json`,
`dagger-teacher-games-v1.json`, `dagger-student-games-v1.json`. Nicht beliebig
mehr Epochen auf dieselben Daten verwenden.

## Geführte PPO-Stufe 1: erstmals positive Lernkurve

`runs/guided-residual-stage1/`, Log `/tmp/cockpit-guided-residual-stage1.log`.
Vor jedem Folgelauf `runs/ai-job.json`, Prozesse und STOP-Datei prüfen.
Der neue Typ `guided_residual` erhält den bisherigen Spieler als eingefrorene
Quelle. Die zusätzliche Politik startet mit Nullausgängen. Als öffentlicher
Hinweis wird die bisherige Auswahl aus Profil 7 mitgegeben; die tatsächlich
wählbare Maske bleibt die breitere Platzierungsauswahl aus Profil 9.

Die alten zugelassenen Aktionen behalten ihre Quell-Logits. Weitere Platzierungen
beginnen vier Logitpunkte unter dem besten Quellzug. Damit bleiben die anfänglichen
deterministischen Entscheidungen erhalten, während zusätzliche Aktionen eine
endliche Wahrscheinlichkeit und trainierbare Gradienten haben. Der Residualzweig
kann diesen Abstand später überwinden. Das ist eine weiche Planungsvorgabe,
keine vollständig planungsfreie Politik; Profil 9 grenzt weiterhin den Suchraum
ein. Fähigkeiten/andere Module sind in dieser PPO-Stufe noch ausgeschlossen.

Referenzmasken entstehen ausschließlich aus der erlaubten eigenen Sicht.
Sie werden für Rollouts, PPO, Gewinnzug-Nachahmung, Bewertung und Browserinferenz
identisch mitgeführt. Der Export nutzt Modellformat 4 bei unverändertem
489/217-Beobachtungs-/Aktionsschema. Bestehende Modelle/Browserformate bleiben
verfügbar. Ein geführter Spieler darf nicht als einfache rohe Quelle eines
weiteren Residualzweigs eingefroren werden, weil dabei sein Hinweis verloren
ginge; zum Fortsetzen `--resume` verwenden.

219 lokale Tests bestanden, einschließlich vollständiger Anfangspartien gegen
die eingefrorene Quelle, lernbarer Abweichungen, versteckter Partnerwürfel,
realem PPO samt Nachahmungs-Referenzen und JS-/PyTorch-Parität. Der Metal-Smoke-Test
`runs/guided-smoke-v1/` absolvierte 311 neue Entscheidungen mit zwei Workern.
Seine acht Validierungspartien sind nur ein Integrationstest, kein Qualitätsbeleg.

Der begrenzte PPO-Lauf startete vom besseren bisherigen Lehrer, nicht vom
schwächeren Nachahmungsmodell: Ziel 200.000 neue Entscheidungen, Seed 251031,
OSL/OSL/OSL/HND/HND/LHR/YUL, 200 Entwicklungsvalidierungen je Route ab
14.000.000, Auswahl zuerst nach schwächster Route. Ausgangsmodell bleibt als
Fallback im Modellvergleich. 316.034 geerbte Modulzüge, neue PPO-Züge und die
früheren Regel-/Nachahmungsübungen bleiben getrennt gezählt.
Die 800 Anfangspartien bestätigten exakt die bisherigen Quoten
**34,5 / 34 / 65 / 80 %**, einschließlich identischer Verlustzählungen.

Der Lauf endete regulär nach **200.115 neuen Entscheidungen** in 19,6 Minuten.
Davon waren 86.357 Kerosinzüge auf OSL und 113.758 Grundspielzüge. Mit der
eingefrorenen Quellenhistorie sind es 402.391 kumulative Modulzüge in dieser
Modelllinie. Neue Entscheidungen nach Route: OSL 86.357, HND 52.622,
LHR 31.253, YUL 29.883. Bericht `guided-stage1.json` enthält die gesamte
Entwicklungsvalidierung und die tatsächlichen Zähler.

| Feste Entwicklungsvalidierung, je 200 Partien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Anfang | 34,5 % | 34 % | 65 % | 80 % |
| Ende | 39,5 % | 38,5 % | 70,5 % | 85 % |

Zusätzlicher Vergleich auf denselben **frischen Entwicklungsseeds ab 14.300.000**,
200 Partien pro Route und Modell:

| Modell | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Quelle, Profil 7 | 35 % | 39,5 % | 63,5 % | 86,5 % |
| Geführt, Profil 9 | 37 % | 44 % | 67 % | 88 % |

Alle Differenzen sind positiv, aber klein und die Intervalle überlappen.
Dies ist ein Entwicklungssignal, kein abschließender Signifikanznachweis und
keine Freigabe. Einzelergebnisse wurden nicht für einen gepaarten Test behalten;
keine scheinbar präzisere gepaarte Statistik daraus ableiten. Berichte
`guided-teacher-games-v1.json`, `guided-candidate-games-v1.json` und
`guided-comparison-v1.json`. Oslo und Haneda bleiben deutlich unter dem Ziel.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --guided-source runs/modules-residual-stage1/best.pt \
  --run-dir runs/guided-residual-stage1 --guide-margin 4 --steps 200000 \
  --workers 8 --cpu-duty-cycle .7 --device mps --seed 251031 \
  --eval-games 800 --eval-every 20 \
  --eval-airports LOG_OSL_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --curriculum-airports LOG_OSL_GREEN LOG_OSL_GREEN LOG_OSL_GREEN LOG_HND_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --self-imitation-coef .03
```

## Geführte PPO-Fortsetzung abgeschlossen

`runs/guided-residual-stage2/`, Log `/tmp/cockpit-guided-residual-stage2.log`.
Vor jedem Folgelauf `runs/ai-job.json`, Prozesse und STOP-Datei prüfen.
Wegen der positiven Lernkurve und durchgängig positiven frischen Vergleiche
wurde bis zum Ziel von **500.000 kumulativen PPO-Entscheidungen in dieser
Phase** weitertrainiert, also ungefähr 300.000 weitere nach den vorhandenen 200.115.
Kein neues Residualnetz, keine neuen Beobachtungen oder geänderten Planer.
Optimizer, RNG, Gewinnzugpuffer, Referenzmasken, Seed 251031 und Routen-Curriculum
wurden aus `latest.pt` übernommen. Weitere Module/Karten waren noch nicht Teil
dieses Laufs. Die alten Quellen- und Regelübungsschritte bleiben separat.
Die 800 Partien unmittelbar nach Resume reproduzierten exakt die letzten
Quoten 39,5 / 38,5 / 70,5 / 85 % und Verlustzählungen des ersten Abschnitts.

Die Fortsetzung endete regulär nach 31,3 Minuten bei **500.347 kumulativen
Phasenentscheidungen**, also **300.232 weiteren** Entscheidungen. Davon waren
133.792 Oslo/Kerosin, 75.561 Haneda, 44.382 London und 46.497 Montréal.
Inklusive der Quellenhistorie sind es 536.183 Modulentscheidungen. Bericht
`guided-stage2.json` enthält tatsächliche Zähler und alle Entwicklungsprüfungen.

| Feste Entwicklungsvalidierung, je 200 Partien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Vor Fortsetzung, 200.115 Schritte | 39,5 % | 38,5 % | 70,5 % | 85 % |
| Letzter Stand, 500.347 Schritte | 38 % | 35,5 % | 80,5 % | 86 % |

Auf diesen festen Seeds verbessert sich die schwächste Route nicht; der bessere Mittelwert ersetzt das
Einzelfallziel nicht. `stage2/best.pt` ist nach Gewichts-Fingerprint weiterhin
**exakt identisch** mit `stage1/best.pt` bei 200.115 Schritten. Keine doppelte
Messung identischer Gewichte als zusätzliche unabhängige Evidenz ausgeben.
Der letzte Stand weicht bei rund 8,8 % der gesampelten Trainingszüge von der
alten Planerempfehlung ab; das ist weder die deterministische Spielquote noch
ein Nachweis besserer alternativer Züge. Kein weiterer unveränderter PPO-Lauf.

```sh
nice -n 15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --resume runs/guided-residual-stage1/latest.pt \
  --run-dir runs/guided-residual-stage2 --steps 500000 \
  --workers 8 --cpu-duty-cycle .7 --device mps \
  --eval-games 800 --eval-every 20 --self-imitation-coef .03
```

## Frischer Entwicklungsvergleich und aktuelle Lernanalyse

Der Entwicklungsvergleich lief über `ai.planner_probe` auf **200 frischen
Partien pro Route und Modell ab 14.400.000**, Profil 9, acht Worker zu 70 %.
Er vergleicht `runs/guided-residual-stage1/best.pt` mit dem tatsächlich letzten
Stand `runs/guided-residual-stage2/latest.pt`. Bericht
`guided-stage2-comparison-v1.json`, Log
`/tmp/cockpit-guided-stage2-comparison-v1.log`. Er ist regulär abgeschlossen.

| Frische Entwicklungsseeds ab 14.400.000 | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Bisher bestes Modell, 200.115 Schritte | 38,5 % | 37 % | 76,5 % | 84,5 % |
| Letzter Stand, 500.347 Schritte | 46,5 % | 42 % | 72,5 % | 87 % |

Die beiden schwächeren Routen verbessern sich hier, London verschlechtert sich.
Das widerspricht einer pauschalen Aussage, längeres Training helfe überhaupt
nicht. Die feste Auswahl auf nur 200 Partien je Route reagiert offenbar anders
als diese frischen 200 Partien. Keine dieser kleinen Entwicklungsstichproben
ersetzt die unabhängige Qualifikation; Oslo/Haneda bleiben unter 50 %.

`ai.gradient_probe` misst auf frischen **Trainingszuständen** die
Gradienten der Zugwahl, der mit 0,5 gewichteten Wertschätzung und der bisherigen
Gewinnzug-Nachahmung im gemeinsamen trainierbaren Encoder. Gewichte und bereits
vorhandene Gradienten bleiben erhalten; keine Optimierung, kein Gewinnnachweis.
Negative Skalarprodukte können Interferenz zeigen, beweisen allein aber nicht,
dass eine kleinere Kritikergewichtung mehr Spiele gewinnt. Der Entropieterm
wird in dieser Diagnose ausdrücklich nicht mitgemessen. Kein privater
Partnerwürfel und kein zukünftiger echter Spielzufall wird gelesen.

Die Diagnose ist abgeschlossen: **8.412 Entscheidungen aus 150 frischen
Trainingspartien**, Seed 251033, 33 Minibatches. Bericht
`guided-gradient-probe-v1.json`, Log `/tmp/cockpit-guided-gradient-probe-v1.log`.
Der gewichtete Wertgradient erreicht im Mittel nur das **0,42-Fache** des
Politikgradienten; der mittlere Kosinus beträgt 0,031. In 16/33 Minibatches ist
das Skalarprodukt negativ, aber in **0/33** kehrt der gemeinsame Gradient die
Politikrichtung um. Kein klarer Beleg für dominierende Kritikerinterferenz;
deshalb keine unbegründete Architekturänderung oder kleinere Kritikergewichtung.
Die Messung beschreibt rohe Gradienten am Anfang eines PPO-Updates; sie
berücksichtigt weder Adam-Momente noch spätere PPO-Schritte, Clipping oder den
Entropieterm. Der maximale Unterschied der Rollout-Wahrscheinlichkeitsverhältnisse
zu 1 war 0,00000883. Der Gewichts-Fingerprint blieb unverändert.

Alle drei neuen Diagnosetests und die vollständige **lokale Suite mit 222 Tests**
bestanden (38,6 s). Die lokale Suite enthält auch die geschützten fremden Tests;
das ist keine Aussage über deren Verfügbarkeit im Remote-Repository.
Die anschließend gestartete Suchprüfung steht im nächsten Abschnitt.

Der unabhängige Kerosinvergleich ab 15.000.000 wurde noch NICHT gestartet.
Auch 12.000.000 und 13.000.000 bleiben unbenutzt. Keine neue Modul-KI ist
freigegeben; das Menü zeigt weiter die bisherigen Modelle.

## Gemeinsame Würfelzuordnung und abgeschlossener Suchvergleich

`ai/joint_round.py` berechnet statische Belegungen für hypothetische Hände:
Ruder, Schub, rollenbezogene Aufgaben und gemeinsame Aufgaben verwenden
**verschiedene Würfel**; Kaffee ist ein einziges gemeinsames Budget.
126 gewichtete Viererhände je Rolle decken alle 6^8 gleichverteilten Würfe ab.
Ein ausdrücklich verfügbarer schwarzer Zusatzwürfel wird entweder der Pilotin
oder dem Kopiloten zugeschlagen. Erfolgreiche Handpaare werden über beide
Zuordnungen vereinigt, nicht doppelt gezählt. Besitz der Synchronisationskarte
allein gewährt hier keinen kostenlosen Würfel. Gemeinsame Aufgaben wie Kerosin
werden ebenso genau einmal einer Rolle zugeordnet.

Sieben Tests prüfen unter anderem vollständige unabhängige Zuordnungen,
gemeinsamen Kaffee, konkurrierende Aufgaben, den einzelnen schwarzen Würfel
und eine tatsächlich in der Engine gewonnene konstruierte Landung. Bei drei
Zusatzaufgaben pro Rolle helfen auch neun Gesamtwürfel nicht: vier Kontrollen
plus sechs Aufgaben benötigen zehn. Das ist ein Regel-/Belegungsnachweis,
keine Quote auf offiziellen Routen.

`ai/joint_forecast.py` plant in der vorletzten und drittletzten Runde bis zur
Landung: frühere Vorbereitung, Funkzuordnung, Bewegung, Fluglage, Kaffeeverbrauch
und Kerosin konkurrieren um dieselben acht Zukunftswürfel. Ein Kerosinplatz pro
Zukunftsrunde und das Überlebensreservoir werden mitberechnet. Der bekannte
hypothetische eigene Kerosinverbrauch wird weitergegeben; ein noch nicht
bezahlter Partnerverbrauch bleibt optimistisch bei eins. Zukünftige
Verkehrswürfe werden weiterhin nur über einen öffentlichen Näherungsabschlag
berücksichtigt. Dies ist keine kalibrierte Gewinnwahrscheinlichkeit und keine
vollständige Suche über alle Zugfolgen oder Kartenwirkungen.

`ai/search_teacher.py` ist ein ausdrücklich experimenteller Suchlehrer auf dem
**unveränderten** geführten 500.347-Schritte-Netz. In frühen Runden, in der
Landung und beim Neuwurf entscheidet weiter die Quelle. Nur auf 1.000/2.000 Fuß
kann eine öffentliche Eigenhand-Suche die Auswahl neu ordnen. Drei Varianten
werden verglichen: `model` ohne Zusatzsuche, `legacy` mit der bisherigen
getrennten Zukunftsnäherung, `joint` mit gemeinsamer Zuordnung. Bestehende
Assistenzprofile bleiben semantisch gleich; `plan_actions` erhielt lediglich
einen optionalen, standardmäßig ungenutzten Forecast-Aufruf. Der dadurch neue
Quellcode-Fingerprint markiert ausdrücklich eine Forschungsphase, kein exaktes
Resume alter PPO-Läufe. Keine gespeicherten Fingerprints nachträglich anpassen.

Die neue Suche unterstützt vorerst **Grundspiel/Kerosin ohne Fähigkeitskarten**.
Andere Module/Karten werden ausdrücklich zurückgewiesen. Die Belegungsprimitive
kann einen bereits verfügbaren schwarzen Würfel behandeln; Karten-Auslösung,
Praktikantenketten, Wind, Leck, Eis und Echtzeit sind dadurch noch nicht in der
Zukunftssuche abgedeckt. Der Produktkatalog bleibt unverändert.

16 neue Tests und die gesamte **lokale Suite mit 238 Tests** bestanden
(39,4 s); die Browserquellen wurden neu gebaut. Ein Integrationstest mit zwei
gedrosselten Workern lief über **24 Partien** (2 je Variante und Route), Seed
14.900.000, Beam 32. Bericht `joint-search-smoke-v1.json` enthält keine
Freigabeevidenz. Der Bericht entstand noch vor Ergänzung der zusätzlichen
gepaarten Ausgabe `paired_against_legacy`; Spiel-/Suchcode blieb dabei gleich.

Der erste große Lauf wurde zur Wartung unterbrochen: die neue Suche erzeugte
zu lange CPU-Spitzen innerhalb einzelner Entscheidungen, weil vorher nur
zwischen Spielzügen pausiert wurde. Alle eigenen Prozesse sind beendet worden;
die dauerhafte Nutzer-STOP-Datei wurde weder gesetzt noch gelöscht.
`joint-search-development-v1.json` enthält ausschließlich die abgeschlossenen
Varianten `model` und `legacy`; keine fertige `joint`-Route. Er ist ausdrücklich
als unvollständig markiert. Modell/Legacy-Quoten: OSL 47/56, HND 48/44,
LHR 65/66, YUL 88/91 Siege pro 100 Partien.

Die Drosselung greift nun zusätzlich innerhalb der Eigenhand- und Zukunftssuche
in Zeitabschnitten von ungefähr 20 ms. Die äußere Drosselung bleibt ebenfalls
aktiv; das ist konservativer als 70 % insgesamt und vermeidet lange Volllast.
Ein zusätzlicher Test bestätigt unveränderte Suchwerte mit Kooperationsaufrufen.
Nach Neustart stimmen alle 800 bereits abgeschlossenen Modell-/Legacy-Ergebnisse
mit v1 exakt überein, einschließlich Verlustgründen und Eingriffszählern.
Eine Prozesskontrolle während der langen Joint-Suche zeigte aktive Worker bei
ungefähr 61–63 % CPU; alle acht Worker haben Priorität 15 und einen Torch-Thread.

**Regulär abgeschlossener Suchvergleich:** `ai.search_evaluate`, Log
`/tmp/cockpit-joint-search-development-v2.log`, Ausgabe
`ai/experiments/modules-50pct-2026-10-25/joint-search-development-v2.json`.
Je **100 neue Entwicklungspartien pro Route und Variante**, Seeds ab
14.500.000, OSL/HND/LHR/YUL, Beam 64, acht Worker zu 70 %, ein Torch-Thread,
`nice -n15`. Insgesamt 1.200 Partien; **keine neuen Trainingsentscheidungen**.
Dieselben Entwicklungsseeds wie v1: wiederholte Modell-/Legacy-Partien zählen
nicht als zusätzliche unabhängige Evidenz. Die Wartungsunterbrechung erfolgte
nicht aufgrund eines Ergebnisses der noch unvollständigen Joint-Variante.
Einzelergebnisse werden mit Route/Seed/Status/Grund gespeichert, damit
gepaarte Unterschiede nachvollziehbar bleiben. Die abschließenden Prüfseeds
ab 15.000.000 bleiben unbenutzt. Vor weiteren Läufen Status/STOP/Prozesse prüfen.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt \
  --games 100 --seed 14500000 --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/joint-search-development-v2.json
```

Der vollständige v2-Lauf endete regulär nach **28,9 Minuten**, Exit 0.

| Variante, je 100 Entwicklungspartien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Unverändertes Netz (`model`) | 47 | 48 | 65 | 88 |
| Getrennte Näherung (`legacy`) | 56 | 44 | 66 | 91 |
| Gemeinsame Zuordnung (`joint`) | 55 | 44 | 69 | 91 |

Gepaarte Gewinne/Verluste von Joint gegenüber dem Netz: OSL 17/9,
HND 1/5, LHR 8/4, YUL 5/2. Gegenüber Legacy: OSL 3/4, HND 2/2,
LHR 3/0, YUL 2/2. Die gemeinsame Zuordnung verbessert die schwächste
Route **nicht**. Keine Freigabe und kein Grund, diesen Lehrer unverändert zu
imitieren. Oslo brauchte allein 1.324 s statt 20,4 s bei Legacy: ungefähr
65-fache Laufzeit ohne bessere Quote. Die wiederholten 800 Modell-/Legacy-
Partien zählen weiterhin nicht als zusätzliche unabhängige Evidenz.

## Öffentliche Fehlerdiagnose und letzter eigener Würfel

`ai.search_diagnose` reproduzierte sechs Haneda-Fälle, die das Netz gewinnt und
mindestens eine Suche verliert: 18 Replays, Bericht
`haneda-search-failures-v1.json`, Log `/tmp/cockpit-haneda-search-failures-v1.log`.
Status und Verlustgrund jedes Replays stimmen exakt mit dem v2-Vergleich überein.
Alle schädlichen Eingriffe dieser Beispiele enthielten den ursprünglichen
Netzzug als bewerteten Suchplan. Die Hypothese eines fehlenden Vergleichszugs
im Beam wird dadurch **nicht** gestützt. Profiling misst reine Prozess-CPU-Zeit;
der Hauptaufwand dieser Beispiele liegt in der Zukunftssuche, nicht im Netz.

Eine erweiterte Instrumentierung zeichnet auch eigene Planfolgen und folgende
Netzzüge auf: `haneda-search-sequences-v2.json`, neun Replays der drei Fälle
14.510.008/047/068, Log `/tmp/cockpit-haneda-search-sequences-v2.log`.
Diese ausgewählten Wiederholungen sind **keine neue Quotenstichprobe** und
erzeugen keine Trainingsentscheidungen. Nur der eigene erlaubte Eingang wird
protokolliert; keine private Partnerhand und kein zukünftiger Spielzufall.
Die Instrumentierung verändert weder Pläne noch ausgewählte Aktionen.

Konkrete Grenzen:

- In 14.510.008 bauen beide Suchen vor der Landung Bremse 2 gegen Kaffee.
  Das Netz spart den Kaffee und gewinnt die spätere Landung. Die Suchvariante
  führt ihren Plan hier tatsächlich aus, verliert aber mit zu hohem Schub.
  Statische Aufgabenpunkte sind deshalb kein zuverlässiger Gewinnwert.
- In 14.510.047 priorisieren beide Suchen eine frühe Landeklappe gegen Kaffee;
  nachfolgende Netzzüge erreichen die vollständigen Klappen nicht. Auch hier
  wird die geplante letzte Platzierung ausgeführt. Kein allgemeiner Beleg,
  dass bloß konsequente Planausführung diese Niederlagen verhindert.
- In 14.510.068 plant Joint zuletzt Ruder 5; bei nur einem eigenen Würfel
  übernimmt bisher automatisch das Netz, startet einen Neuwurf und trudelt.
  Diese Inkonsistenz begründet einen **separaten** Versuch `joint-finish`, der
  auch den letzten eigenen Würfel unter der aktuellen erlaubten Maske neu
  plant. Er erzwingt keinen alten Plan nach Partnerzügen. Frühe Runden,
  Landung und offene Neuwürfe bleiben beim Netz; fehlen bewertete erlaubte
  Platzierungen, bleibt ebenfalls die Netzauswahl. `model`, `legacy` und
  `joint` behalten ihre bisherige Semantik.

**Ebenfalls regulär abgeschlossener Versuch:** 100 Haneda-Entwicklungspartien ab 14.510.000,
gleiche Gewichte, Varianten `model`, `joint`, `joint-finish`. Wiederholte
Kontrollen zuerst auf exakte Übereinstimmung mit v2 prüfen. Ein Erfolg auf
diesen bereits untersuchten Seeds erfordert anschließend frische Entwicklung;
die unabhängigen Prüfseeds ab 15.000.000 bleiben unbenutzt. Kein neues Modell
und kein Suchprofil wurde für den Singleplayer freigegeben.

Bericht `joint-finish-haneda-development-v1.json`, Log
`/tmp/cockpit-joint-finish-haneda-development-v1.log`. Alle 300 Partien sind
abgeschlossen: **Netz 48, Joint 44, Joint-Finish 45 Siege**. Modell- und
Joint-Kontrolle stimmen bei allen 200 Einzelresultaten exakt mit v2 überein.
Die letzte-Würfel-Erweiterung liegt weiterhin unter dem Netz: vier neu gewonnene
gegen sieben verlorene Netzsiege. Das begründet weder eine Freigabe noch eine
große frische Bestätigungsserie. Gegenüber Joint sind es vier Gewinne/drei
Verluste. Fall 14.510.008 wird gewonnen, 14.510.047 bleibt verloren und auch
14.510.068 endet weiterhin im Trudeln: die vermutete Ausführungskorrektur
behebt das konkrete Ruder-Gegenbeispiel nicht. Acht Worker zu höchstens 70 %, Torch-Threads 1,
`nice -n15`, verwaltet über `ai.job_control`; reguläres Ende nach 216 s, Exit 0.
Danach lief zunächst kein schwerer Job. Nach dieser Änderung bestanden **241 lokale Tests** (26,3 s),
einschließlich der geschützten fremden Tests. Keine neuen PPO-Entscheidungen.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model joint joint-finish --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/joint-finish-haneda-development-v1.json
```

## Frühe Verkehrs- und Kurvenverluste auf Haneda

`haneda-traffic-curves-diagnosis-v1.json` reproduziert **alle 28** entsprechenden
Netzverluste aus denselben 100 HND-Entwicklungspartien. Die Ausgänge und Gründe
stimmen exakt überein; ausgewählte Wiederholungen sind keine neue Quotenstichprobe.
Log `/tmp/cockpit-haneda-traffic-curves-diagnosis-v1.log`, zwei Worker zu 70 %,
reguläres Ende nach 9,2 s, keine Trainingsentscheidungen. Pro Spiel werden die
letzten acht Entscheidungen mit ausschließlich öffentlichem Kontext, eigener
Hand und erlaubter Aktionsauswahl gespeichert. Der Diagnoseadapter kann jetzt
auch gezielt Netzverluste und bestimmte Gründe auswählen, ohne Suchverluste
oder drei feste Vergleichsmodi vorauszusetzen.

| Verlusthöhe | Kollision | Kurvenkorridor | Summe |
| --- | ---: | ---: | ---: |
| 5.000 Fuß, Runde 2 | 4 | 1 | 5 |
| 4.000 Fuß, Runde 3 | 11 | 5 | 16 |
| 3.000 Fuß, Runde 4 | 1 | 4 | 5 |
| 2.000 Fuß, Runde 5 | 1 | 1 | 2 |

**26/28 entstehen vor dem bisherigen Suchfenster.** Einzelbeispiele zeigen,
dass eine Rolle optionale Aufgaben ausführt, während beide Seiten auf die
Funkarbeit des Partners hoffen. In Fall 14.510.029 verbraucht die Pilotin den
restlichen Kaffee für Schub, während das noch offene Partner-Ruder den Kaffee
für die aktuelle Linkskurve braucht. Dies ist eine nachträgliche Erklärung aus
jeweils erlaubten Eingängen, kein Zugriff des Spielers auf die verdeckte Hand.
Die Beispiele beweisen nicht, dass jede der 28 Partien zu retten gewesen wäre.

**Regulär abgeschlossener Vergleich:** `early-round-haneda-development-v1.json`,
Log `/tmp/cockpit-early-round-haneda-development-v1.log`, 100 HND-Partien ab
14.510.000, dasselbe Netz und dieselbe Assistenzmaske 9. Neue, ausdrücklich
experimentelle Varianten `round-plain` und `round-risk` suchen in **jeder
Nicht-Landerunde**, weiterhin nicht bei offenen Neuwürfen oder weniger als
zwei eigenen Würfeln. Beide verzichten in diesem Vergleich auf eine weitere
Zukunftsprognose. `round-plain` verwendet Planerversion 3; `round-risk` die
bereits vorhandene Version 4 mit gemeinsamem Ruder-/Schubprior über verschiedene
Partnerwürfel, einem Kaffeebudget und zusätzlicher Funk-Kapazitätsstrafe.
Diese Version ist weiterhin **keine vollständige gemeinsame Zuordnung von
Funk, Kontrollen und allen Aufgaben**. Der Versuch trennt die Wirkung früher
Suche von dieser bestehenden Risikoabschätzung. Alle alten Varianten behalten
ihre Semantik; keine Änderung bestehender Produktprofile oder Gewichte.

14 gezielte Tests einschließlich der neuen Varianten und der Diagnoseauswahl
bestanden. Acht Worker zu höchstens 70 %, Torch-Threads 1, `nice -n15`, über
`ai.job_control`. Nach 59,3 s regulär beendet: **Netz 48, frühe einfache Suche 42,
frühe Risiko-Suche 47 Siege**. Gegen das Netz gewinnt Round-Plain 14 andere
Partien und verliert 20 Netzsiege; Round-Risk gewinnt 17 und verliert 18.
Keine Verbesserung gegenüber dem Netz, keine neue Freigabeevidenz.

Ein wichtiger verbleibender Engpass ist in Fall 14.510.029 konkret sichtbar:
bei Schritt 27 lässt Assistenzmaske 9 ausschließlich Kaffee −2 auf den letzten
eigenen Schubwürfel zu. Einfaches Platzieren und Kaffee −1 sind ausgeschlossen.
Der Suchlehrer kann solche Alternativen trotz abweichender Risikobewertung
nicht auswählen. Die breitere Maske 9 erweiterte bisher nur Platzierungsabstände,
nicht alle Kaffee-/Neuwurfentscheidungen. Ein begründeter nächster Versuch
muss gezielt zusätzliche, enginegeprüfte Risiko-Vorschläge zulassen und die
Netzentscheidung weiterhin auf ihrer ursprünglichen Maske berechnen; die rohe
Politik unter einer beliebig weiten Maske war schon früher stark schlechter.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model round-plain round-risk --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/early-round-haneda-development-v1.json
```

## Gezielte legale Risikovorschläge außerhalb der alten Maske

`ai.search_environment.OpenRiskEnv` ist eine **getrennte Forschungsumgebung**.
Sie vereinigt die bisherige Maske 9 mit einer kleinen, aus der rohen
Engine-Regelmaske gewonnenen Risiko-Auswahl (Planerversion 4). Notwendige
Kapazitäts-/Kerosingrenzen bleiben erhalten. Schlechte Vorschläge unter −100
Suchpunkten verdrängen keinen Rettungsneuwurf. Die Netzentscheidung wird
ausdrücklich auf `source_action_mask` berechnet, nicht unter der erweiterten
Auswahl; auch Referenzmaske 7 bleibt exakt erhalten. Nur der separate Suchlehrer
`round-open` darf zusätzliche Vorschläge wählen, einschließlich des letzten
eigenen Würfels. Andere Produktprofile und Gewichte bleiben gleich.

Ein konstruierter, **in der Engine ausgeführter** Engpasstest zeigt: Die alte
Maske erzwingt Kaffee −2 für Schub 2. Die Risiko-Auswahl erlaubt stattdessen
Schub 4, bewahrt zwei Kaffee und ermöglicht danach ein um eins angepasstes
Partner-Ruder. Beide aktuellen Kurven werden mit Fluglage −1 durchflogen;
ein Kaffee bleibt. Dies belegt die einzelne Regelkorrektur, keine Routenquote.
Das versteckte Partner-Ruder in der Testaufstellung wird nicht an den Lehrer
übergeben. Weitere Tests prüfen exakt erhaltene Quell-/Referenzmasken,
Engine-Legalität der zusätzlichen Auswahl, Partnerwürfel-Privatsphäre und die
unveränderte Landemaske. **246 lokale Tests bestanden** (27,0 s); enthalten
sind weiterhin die geschützten fremden Tests. Browser-/Produktcode unverändert.

**Regulär abgeschlossener Vergleich:** `open-risk-haneda-development-v1.json`,
Log `/tmp/cockpit-open-risk-haneda-development-v1.log`, 100 HND-Entwicklungspartien
ab 14.510.000, Varianten `model`, `round-risk`, `round-open`, Beam 64, acht
Worker zu höchstens 70 %, Torch-Threads 1, `nice -n15`, über `ai.job_control`.
Kontrollen zuerst auf exakte Wiederholung prüfen. Die neuen Vorschläge
verwenden weiterhin nur die eigene Hand und öffentliche Daten; auch innerhalb
der zusätzlichen Planung wird ungefähr alle 20 ms freiwillig pausiert.
Keine neuen PPO-Entscheidungen, keine neue Modulfreigabe. Bei Vorteil sind
frische Entwicklungsseeds erforderlich, nicht sofort eine Freigabe. Ergebnis
nach 96,4 s: **Netz 48, Round-Risk 47, Round-Open 45 Siege**. Die 200
Kontrollresultate wiederholen sich exakt. Round-Open gewinnt 20 andere Partien
und verliert 23 Netzsiege. Die Einzelkorrektur beseitigt eine Beschränkung,
aber die feste Risikobewertung liefert keinen insgesamt stärkeren Lehrer.
Keine große Bestätigungsserie oder Nachahmung dieser festen Zugvorgabe.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.search_evaluate \
  --checkpoint runs/guided-residual-stage2/latest.pt --routes LOG_HND_GREEN \
  --modes model round-risk round-open --games 100 --seed 14510000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/open-risk-haneda-development-v1.json
```

## Neues Lernen mit gezielt erweiterten Aktionen

`neural-open-haneda-development-v1.json` prüft die **unveränderten Gewichte**
unter der gezielt erweiterten Maske, ohne festen Suchlehrer. Auf denselben
100 bekannten HND-Partien: **Netz alt 48, Netz mit Zusatzaktionen 45 Siege**,
0 zusätzliche Siege gegen drei verlorene ursprüngliche Siege. Lauf regulär
nach 64,5 s beendet; wiederholte Kontrolle exakt gleich. Die neue Auswahl
liefert also vor Training noch keinen Vorteil. Diese Messung ist keine
zusätzliche unabhängige Stichprobe und keine Freigabe.

Der neue PPO-Weg lernt die Bewertung dieser begrenzten Zusatzaktionen selbst,
anstatt schwächere feste Lehrerzüge zu imitieren. **Keine zusätzliche Schicht,
keine Änderung der eingefrorenen Grundlage oder Kritikergewichtung.** Der
vorhandene trainierbare Detailzweig wird benutzt. `--phase-source` lädt exakt
die geführten 500.347-Schritte-Gewichte und startet ausdrücklich eine **neue
Forschungsphase** mit frischem Adam und Zählern. Quellpfad, Gewichts-SHA,
Quellschritte und alter Planer-Fingerprint werden separat gespeichert; alte
Checkpoints/Hashes werden nicht verändert. Es wird kein exaktes Resume über
geänderten Planungscode behauptet. Ein späteres Resume der neuen Phase verlangt
dieselbe Forschungsumgebung und denselben Such-Fingerprint.

`ParallelGames` führt die neue Umgebung in Training und Bewertung mit. Die
Referenzmaske 7 bleibt in Rollouts, PPO-Wahrscheinlichkeiten und erfolgreichem
Trainingsreplay erhalten. Tests prüfen vor dem Update Wahrscheinlichkeits-
verhältnisse von 1, anschließend echte Änderungen im bestehenden Detailzweig
bei exakt unveränderten eingefrorenen Gewichten. Parallele Bewertung stimmt
mit direkter Bewertung überein. **249 lokale Tests bestanden** (36,3 s),
einschließlich der geschützten fremden Tests. Die bisherigen Standardpfade
verwenden weiterhin ihre bisherigen Umgebungen.

Der komplette Befehl wurde mit dem echten Modell und nur einem kleinen
PPO-Update erfolgreich geprüft: `runs/open-risk-ppo-smoke-v1/`, Log
`/tmp/cockpit-open-risk-ppo-smoke-v1.log`, Ziel 64 neue Entscheidungen mit
möglichem Überschreiten zum Episodenende, tatsächlich **128 neue Entscheidungen
in einem Update**, hier zufällig beide Trainingspartien auf OSL. Zwei Worker
zu 70 %, CPU-Update, regulär nach 33 s beendet. Acht winzige Validierungspartien
pro Messung dienen nur der technischen Prüfung. `open-risk-ppo-smoke-v1.json`
belegt identische Anfangsgewichte und exakt unveränderte eingefrorene Grundlage
nach dem echten PPO-Update. Kein Modell aus dieser technischen Probe
wird freigegeben oder als Gewichtsquelle des eigentlichen Laufs benutzt.

**Regulär abgeschlossene PPO-Phase:** `runs/open-risk-ppo-stage1/`, Log
`/tmp/cockpit-open-risk-ppo-stage1.log`, begrenzte Phase von
**100.000 NEUEN Entscheidungen**:
OSL/HND/LHR/YUL, HND dreifach und OSL zweifach im Curriculum, 100 feste
Entwicklungspartien pro Route (400 insgesamt) ab 14.650.000, Auswahl nach der
schwächsten Route. Anfangsgewichte bleiben als möglicher bester Stand erhalten.
Bewertung etwa alle 50.000 Entscheidungen; bei Plateau kein unbegründetes
Endlos-PPO. Die unabhängige Qualifikation ab 15.000.000 bleibt unbenutzt.
Höchstens acht CPU-Worker zu 70 %, ein Torch-Thread, `nice -n15`; Metal kann die
PPO-Minibatches übernehmen und wurde außerhalb der Sandbox als verfügbar geprüft.
Seed 251039, Lernrate 0,00005, Selbstnachahmung nur erfolgreicher Trainingszüge
mit Gewicht 0,03. Quelle ist wieder der unveränderte 500.347-Stand, nicht die
128-Züge-Probe. Grobe Dauer 20–40 Minuten, abhängig von Episoden und Bewertungen.
Währenddessen keine Such-/Trainingsquellen ändern und keinen zweiten schweren
Job starten. Konkrete Schritte/Einzelquoten immer aus den laufenden Logs lesen.
Die Anfangsprüfung ist abgeschlossen: je 100 Partien auf den **neuen** festen
Entwicklungsseeds ergeben **OSL 48 / HND 36 / LHR 68 / YUL 88 %**. Das ist der
Stand vor dem ersten Update unter der neuen Auswahl, keine Verbesserung und
nicht dieselbe HND-Stichprobe wie die vorherigen 45/48-Vergleiche.
Erster protokollierter PPO-Stand: **2.283 neue Entscheidungen**, davon HND 1.095,
OSL 615, LHR 258, YUL 315. Die eingefrorene Grundlage blieb auch nach diesem
echten Metal-Update exakt unverändert. Weitere Zähler immer aus `training.jsonl`
lesen; sie steigen während des laufenden Jobs weiter.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.train_fuel \
  --phase-source runs/guided-residual-stage2/latest.pt --open-risk-env \
  --run-dir runs/open-risk-ppo-stage1 --steps 100000 --workers 8 --cpu-duty-cycle .7 \
  --seed 251039 --eval-seed 14650000 --eval-games 400 --eval-every 25 \
  --curriculum-airports LOG_HND_GREEN LOG_HND_GREEN LOG_HND_GREEN LOG_OSL_GREEN LOG_OSL_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --eval-airports LOG_OSL_GREEN LOG_HND_GREEN LOG_LHR_GREEN LOG_YUL_GREEN \
  --self-imitation-coef .03 --device mps
```

## Abschluss der neuen PPO-Phase und frischer Vergleich

Die Phase endete regulär nach **23,24 Minuten**, Exit 0, **100.214 NEUEN
Entscheidungen** in 45 Updates/1.758 Trainingspartien. Verteilung: HND 39.057,
OSL/Kerosin 29.668, LHR 14.396, YUL 17.093. Alle Zähler summieren sich korrekt;
kumulative Modulhistorie mit übernommener Quelle: 565.851 Entscheidungen.
Die eingefrorene Grundlage ist in `warm.pt`, `best.pt` und `latest.pt` exakt
gleich geblieben. Vollständiger abgeschlossener Bericht
`open-risk-ppo-stage1.json`, einschließlich Trainings- und Einzelvalidierung.

| Neue Phasenzüge, je 100 feste Entwicklungspartien | OSL | HND | LHR | YUL | Schwächste Route |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0, unveränderte Anfangsgewichte | 48 % | 36 % | 68 % | 88 % | 36 % |
| 56.480, gewähltes `best.pt` | 42 % | 42 % | 65 % | 91 % | 42 % |
| 100.214, `latest.pt` | 40 % | 44 % | 69 % | 91 % | 40 % |

**Best bleibt der 56.480-Stand**, weil die vorher festgelegte Auswahl zuerst
die schwächste Route betrachtet. Der etwas höhere Gesamtwert am Ende ersetzt
dieses Kriterium nicht. Es gibt einen Vorteil für die schwächste Route auf
festen Entwicklungsseeds, aber Oslo gibt nach. Keine Freigabe, kein 50-%-Nachweis
und kein Grund für eine ungeprüfte unbegrenzte Fortsetzung.

Der nächste begrenzte Schritt prüft auf **frischen Entwicklungsseeds ab
14.700.000**, 200 Partien je OSL/HND/LHR/YUL, drei gepaarte Varianten:
ursprüngliche 500.347-Gewichte unter alter Maske 9 (`source`), exakt dieselben
Anfangsgewichte unter der Zusatzmaske (`warm`), gewählter 56.480-Stand unter
Zusatzmaske (`candidate`). Damit wird auch gegen die ursprüngliche KI geprüft,
nicht nur gegen den durch die neue Auswahl zunächst geschwächten Anfang.
Das sind 2.400 Partien, kein unabhängiger Freigabetest. Ergebnisse werden pro
Route und Seed mit gepaarten Gewinnen/Verlusten gegen BEIDE Kontrollen
gespeichert. Außerdem wird gemessen, wie oft die Politik tatsächlich eine
zusätzliche Aktion außerhalb der alten Maske 9 auswählt; Abweichungen von der
engeren Referenzmaske 7 allein beantworten diese Frage nicht.

**Aktueller einziger schwerer Lauf:** Werkzeug `ai.open_risk_compare`, Bericht
`ai/experiments/modules-50pct-2026-10-25/open-risk-ppo-stage1-fresh-v1.json`,
Log `/tmp/cockpit-open-risk-ppo-stage1-fresh-v1.log`. Vor Start zuerst Status,
STOP-Datei und Prozesse prüfen; maximal acht Worker zu 70 %, Torch-Threads 1,
`nice -n15`, ein schwerer Lauf. Die unabhängigen Seeds ab 15.000.000 werden
vom Werkzeug ausdrücklich als Entwicklung abgelehnt. Instrumentierungstests
prüfen unveränderte Kontroll-/Kandidatenaktionen und Gewichte. **251 lokale
Tests bestanden** (37,5 s), einschließlich der geschützten fremden Tests.
Der laufend geschriebene frische Bericht wird erst nach Abschluss committed.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.open_risk_compare \
  --source runs/guided-residual-stage2/latest.pt --warm runs/open-risk-ppo-stage1/warm.pt \
  --candidate runs/open-risk-ppo-stage1/best.pt --games 200 --seed 14700000 \
  --workers 8 --cpu-duty-cycle .7 --beam 64 \
  --output ai/experiments/modules-50pct-2026-10-25/open-risk-ppo-stage1-fresh-v1.json
```

## Nächste Arbeit

### Nutzerauftrag: Crew 2 mit unabhängig bestandenen Routen

Der Nutzer hat ausdrücklich gebeten, das bisher beste verfügbare Modell mit
seinen bestandenen Routen als **Crew 2** hochzuladen. Das hebt das Ziel aller
186 Fälle nicht auf und ist kein Auftrag, schwache Modulrouten freizuschalten.
Vorab ausgewählt ist `runs/guided-residual-stage2/latest.pt`, Profil 9 mit
Referenzmaske 7, 500.347 Phasenentscheidungen, Gewichts-SHA
`1d846e7731d60c9cc84c8204e7b87b5dea643b501b5f59bc2185deb76e8609eb`.
Die Auswahl erfolgte vor dem unabhängigen Test. Keine OpenRisk-Zusatzmaske
und keine Veränderung der veröffentlichten Planungsregeln für diesen Export.

Der frische OpenRisk-Vergleich ist vollständig und regulär abgeschlossen:

| Je 200 Entwicklungspartien | OSL | HND | LHR | YUL |
| --- | ---: | ---: | ---: | ---: |
| Ursprüngliche Quelle | 42,5 % | 38,5 % | 70,5 % | 89,5 % |
| Gleiche Gewichte mit Zusatzmaske | 42 % | 38 % | 71 % | 89 % |
| Trainierter Kandidat | 38,5 % | 39 % | 72 % | 87 % |

Kein konsistenter Vorteil des letzten PPO-Versuchs. Der Kandidat wählt nur
7/14/11/13 echte Zusatzaktionen bei 11.705/10.540/12.164/12.115 Entscheidungen
(OSL/HND/LHR/YUL). Bericht `open-risk-ppo-stage1-fresh-v1.json` bewahrt alle
gepaarten Einzelresultate gegen beide Kontrollen. Die Anfangsgewichte sind
identisch und zählen nicht als zwei unabhängig trainierte Modelle. Die kleine
Erweiterung bietet hier selten andere Aktionen; Auswahl- und Routenkonflikte
sind weiter zu untersuchen, statt ungeprüft dasselbe PPO fortzusetzen.

**Regulär beendet nach 20,81 Minuten, Exit 0:** `ai.route_eval`, Bericht
`ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json`, Log
`/tmp/cockpit-crew2-qualification-v1.log`. Je 500 unabhängige Selbstspielpartien
auf den neun bisherigen Grundspielrouten und OSL/Kerosin, zusätzlich je
100 Partien pro Rolle mit Heuristikpartner: 7.000 Spiele insgesamt. Acht
Worker zu 70 %, Torch-Threads 1, `nice -n15`, über `ai.job_control`.
Nur Routen mit unterer 95-%-Wilson-Grenze mindestens 50 % werden übernommen;
Crew 1 bleibt auswählbar. Alle zehn Strecken sind vollständig geprüft:

| Strecke | Siege / 500 | Selbstspiel | Crew 2 |
| --- | ---: | ---: | --- |
| Montréal, LOG_YUL_GREEN | 433 | 86,6 % | freigegeben |
| Heathrow, LOG_LHR_GREEN | 340 | 68 % | freigegeben |
| Haneda, LOG_HND_GREEN | 179 | 35,8 % | nicht freigegeben |
| Frankfurt, FRA | 404 | 80,8 % | freigegeben |
| Eigene London-Strecke, LHR | 433 | 86,6 % | freigegeben |
| München, MUC | 494 | 98,8 % | freigegeben |
| München Verkehr 1, MUC_T1 | 495 | 99 % | freigegeben |
| München Verkehr 2, MUC_T2 | 495 | 99 % | freigegeben |
| München Verkehr 3, MUC_T3 | 478 | 95,6 % | freigegeben |
| Oslo/Kerosin, LOG_OSL_GREEN | 202 | 40,4 % | nicht freigegeben |

Crew 2 liegt unter `ai/releases/crew2-v1/`, Browserformat 4 mit exakt denselben
Gewichten wie der vorab gewählte Stand. Der Export vereinigt den Katalog mit
den bisherigen Modellen; Crew 1 bleibt die Vorauswahl. Neue Build-Version
für den Service-Worker-Cache. Keine neue Modul-/Kartenstrecke wird dadurch
freigeschaltet. Alle Intervalle und Partnerproben stehen in `evaluation.json`
und der README des Releases; Selbstspiel ist keine menschliche Partnerquote.

**Die unabhängigen Seeds 15.000.000–15.000.499 und die separate Partnerprobe
15.100.000–15.100.099 sind damit erstmals benutzt.** Sie gelten danach als
verbrauchte Qualifikation dieses vorab ausgewählten Standes, nicht als neue
Entwicklungs- oder Modellauswahlseeds. Dies ist noch keine Prüfung aller
Module/Karten; spätere geänderte Kandidaten erhalten gesonderte neue Kohorten.
Ab 15.200.000 ist eine neue abschließende Kohorte reserviert und noch unbenutzt;
auch sie darf nicht zur Modellauswahl oder Lernsteuerung dienen.

`ai.route_eval` dokumentiert jetzt den zur tatsächlichen Schema-Version
gehörenden Planer-Fingerprint, Ressourcen und einen Abschlussmarker.
`ai.publish` lehnt ausdrücklich laufende Berichte ab. **252 lokale Tests
bestanden** (42,8 s, einschließlich der geschützten fremden Tests).
`tests/crew2-ui.cjs` prüfte den echten Browserexport und die Pyodide-Engine:
acht richtige Routen, Crew 1 erhalten, beide menschlichen Rollen, echte
geführte KI-Züge, passende Referenzmasken und verdeckte Partnerwürfel.
Menü und Spiel wurden zusätzlich visuell geprüft. Die tatsächlich exportierten
Gewichte behalten den oben genannten Fingerprint; auf **96 technischen
Spielzuständen** stimmen alle JavaScript-/PyTorch-Entscheidungen überein,
maximaler Logitfehler 0,00000668. Dies sind technische Zustände, keine
zusätzlichen unabhängigen Testpartien.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.route_eval \
  --checkpoint runs/guided-residual-stage2/latest.pt \
  --airports LOG_YUL_GREEN LOG_LHR_GREEN LOG_HND_GREEN FRA LHR MUC MUC_T1 MUC_T2 MUC_T3 LOG_OSL_GREEN \
  --games 500 --partner-games 100 --seed 15000000 --workers 8 --cpu-duty-cycle .7 \
  --minimum-win-rate .5 \
  --output ai/experiments/modules-50pct-2026-10-25/crew2-qualification-v1.json
```

### Passive Diagnose des OpenRisk-Lernens nach Crew 2

`ai.route_policy_probe` isoliert Angebotsänderungen durch die Zusatzmaske und
Lernänderungen durch die Gewichte auf **denselben erlaubten eigenen Zuständen**.
Je Zustand werden die ursprüngliche Politik unter Maske 9, dieselben Gewichte
mit Zusatzmaske und der trainierte Kandidat mit Zusatzmaske verglichen.
Gleichwertige gleichaugige Würfel werden zusätzlich als dieselbe inhaltliche
Aktion gezählt. Nur aggregierte Zähler werden veröffentlicht; weder private
Partnerhände noch zukünftige echte RNG-Werte gehen in diese Berechnungen ein.

Die erste begrenzte Diagnose endete regulär nach **67,46 s**, Exit 0:
**8.369 gesampelte Trainingsentscheidungen in 143 Partien**, kein PPO-Update,
keine neuen trainierten Gewichte und keine Freigabetests. Namensraum
`train:route-policy-probe:251042:...`. Quelle sind die exakt gleichen Crew-2-
Gewichte, Kandidat ist der vorab gewählte 56.480-Stand des OpenRisk-PPO.
Acht Worker zu 70 %, Torch-Threads 1, `nice -n15`, ein verwalteter schwerer
Job; aktive Worker wurden bei 53–70 % beobachtet. Bericht
`ai/experiments/modules-50pct-2026-10-25/route-policy-probe-v1.json`, Log
`/tmp/cockpit-route-policy-probe-v1.log`. Aktuell ist dieser Job beendet.

| Trainingszustände | HND | LHR | OSL/Kerosin | YUL |
| --- | ---: | ---: | ---: | ---: |
| Entscheidungen | 4.056 | 1.410 | 1.718 | 1.185 |
| Zustand bietet eine Zusatzaktion | 168 | 19 | 18 | 18 |
| Zusatzaktion tatsächlich gesampelt | 20 | 3 | 1 | 1 |
| Zusatzaktion bei deterministischer Wahl | 6 | 2 | 0 | 0 |
| Lernbedingt andere deterministische Wahl | 161 | 69 | 87 | 62 |
| Davon beide Aktionen innerhalb alter Maske 9 | 155 | 68 | 87 | 62 |

Insgesamt gibt es nur **223/8.369 = 2,66 %** Gelegenheiten für Zusatzaktionen,
25 tatsächliche Zusatzaktionen (0,30 %) und acht deterministische Zusatzwahlen
(0,096 %). Von 379 lernbedingt geänderten deterministischen Wahlen liegen
**372 = 98,15 %** vollständig innerhalb der alten Maske. 336 Änderungen sind
auch nach Zusammenfassung gleichwertiger Würfel inhaltlich verschieden.
Das Lernen verändert somit überwiegend den alten Strategieraum. Es genügt
nicht, die geringe Nutzung neuer Aktionen nur als fehlende Trainingsdauer zu
deuten: Die zusätzliche Auswahl wird bereits vom Vorschlagsmechanismus selten
angeboten. Besonders Oslo bietet sie nur in 18 von 1.718 Zuständen an.
Dies ist eine Messung auf gesampelten Trainingspfaden, keine neue Spielquote
und kein Kausalitätsbeweis für die beobachteten Entwicklungsverluste.

Die lokale Actor-Gradientenmessung nutzt die tatsächlichen Entscheidungsanteile
des gemischten Curriculums und die PPO-Normalisierung der Vorteile. In keinem
der vier Fälle widerspricht die gemeinsame **vollständige Actor-Richtung** der
routeweisen Richtung. Im gemeinsamen Encoder gibt es einen negativen
YUL-Projektionswert; zugleich sind die Richtungen auf getrennten vollständigen
Episodenhälften **auf derselben Route** sehr instabil: Actor-Kosinus
HND −0,022 / LHR −0,015 / OSL −0,029 / YUL −0,134. Die Encoder-Hälften sind
ebenfalls negativ. Damit sind einzelne negative Winkel zwischen Routen kein
belastbarer Beleg für einen grundsätzlich falschen gemeinsamen Netzaufbau.
Keine getrennten Routennetze oder neue Kritikergewichtung allein daraus ableiten.
Wert-, Entropie- und Nachahmungsgradienten sind in dieser Actor-Diagnose bewusst
nicht enthalten; sie simuliert keinen vollständigen PPO-Update oder Gewinnzuwachs.
Maximaler Fehler des erneut berechneten Rollout-Wahrscheinlichkeitsverhältnisses:
0,00000716. Die Gewichte bleiben unverändert.

**Acht relevante Tests bestanden** (3,6 s): Instrumentierung erhält sämtliche
gesampelten Aktionen, RNG-Folge, Rollout-Tensoren und Endresultate exakt;
Gradientenmessung erhält vorhandene `.grad`-Felder und Gewichte; die synthetische
Gegenrichtung wird erkannt; Referenzmasken und reservierte Prüfpartition bleiben
geschützt. Keine Produktionsprofile, Browsermodelle oder freigegebene Quoten
wurden geändert.

```sh
nice -n15 .venv/bin/python -m ai.job_control run -- .venv/bin/python -m ai.route_policy_probe \
  --source ai/releases/crew2-v1/best.pt --candidate runs/open-risk-ppo-stage1/best.pt \
  --steps 8192 --seed 251042 --workers 8 --cpu-duty-cycle .7 \
  --output ai/experiments/modules-50pct-2026-10-25/route-policy-probe-v1.json
```

### Historischer Forschungsplan vor dem Ausbau um Praktikant und Leck

Die folgenden Punkte dokumentieren den damaligen Stand vor Crew 3/4 und werden
nicht als aktuelle Einschränkung von Karten-Vorschauen oder als neuer Auftrag
über die oben dokumentierten Phasen gelesen. Aktuell gelten die Abschnitte am
Anfang dieses Arbeitsstands und die ausdrückliche Preview-Anweisung.

1. Zuerst Prozessstatus, STOP-Datei und zuletzt dokumentierten Vergleich prüfen;
   keinen zweiten schweren Job. `joint-finish` erreichte nur 45 statt 48
   Netzsiege auf Haneda; keine weitere große Bestätigungsserie dieses Ansatzes.
   Bei schwachem Lehrer nicht wieder dessen Labels endlos imitieren: aktuelle
   gemeinsame Kontrollzuordnung, Annahmen über nachfolgende Partnerzüge,
   Kaffee-/Neuwurfreserven und kalibrierte Fortsetzungswerte bearbeiten.
   Die 17 Kollisionen und elf Kurvenverluste sind inzwischen lokalisiert:
   26/28 entstehen vor 2.000 Fuß. Der oben dokumentierte frühe Suchvergleich
   brachte noch keinen Vorteil. Auch Round-Open (45) und das unverändert
   unter der Zusatzmaske spielende Netz (45) blieben unter dem ursprünglichen
   Netz (48). Die neue PPO-Phase hat 100.214 neue Züge regulär abgeschlossen;
   der frische Vergleich zeigt keinen konsistenten Vorteil gegen beide
   Kontrollen. Die Diagnose oben zeigt: Die zusätzlichen Vorschläge sind selten, Lernänderungen
   betreffen überwiegend alte Aktionen; die Routen-Gradienten sind schon
   innerhalb derselben Route instabil. Kein Beleg, dass getrennte Netze den
   Engpass lösen. Als nächsten begründeten Schritt den öffentlichen
   Vorschlagsraum und seine Bewertung verbessern: zusätzliche enginelegale
   Kaffee-/Platzierungsfolgen aus den bekannten Engpässen systematisch erfassen
   und gegen den unveränderten Spieler prüfen. Eine eng begrenzte statische
   Heuristik nicht wieder unverändert als starken Lehrer behandeln. Für eine
   stärkere Suche wären unabhängige öffentliche Simulationszustände nötig,
   deren Partnerhand und künftige Würfe ausschließlich aus einem getrennten
   Simulations-RNG entstehen; zuerst exakte Rekonstruktion der sichtbaren
   Engine-Zustände und Privatsphäre enginegeprüft herstellen. Keine
   Qualifikationsseeds dafür verwenden. Nicht unterstellen, alle Fehler
   entstehen kurz vor Landung.
   Ein besserer statischer Belegungswert allein ist kein Gewinnnachweis. Die
   Planung für Oslo braucht außerdem eine begründete Laufzeitbegrenzung.
   Die ausdrückliche Crew-2-Veröffentlichung oben ist abgeschlossen; weitere
   neue Modulqualifikationen erst bei ausreichenden Entwicklungsquoten.
2. Assistenzprofil 7 im allgemeinen Adapter und Forschungsprofil 9 unterstützen
   taktisch nur Grundspiel/Kerosin ohne Karten. Für weitere Module/Karten sind
   Modultaktik und Planung noch zu entwickeln; rohe legale Aktionen funktionieren
   bereits. Vor allgemeinem PPO Helferschleifen/Trunkierung als Flucht vor einer
   Niederlage ausschließen. Nicht aus Regelunterstützung Spielstärke ableiten.
3. Den Strategieraum erweitern, falls die bisherige harte Planung bessere
   Aktionen aus der PPO-Auswahl ausschließt. Mehr-Runden-Suche, probabilistische
   eigene/Partner-Zukunft und Suchlehrer mit anschließender Distillation sind
   mögliche nächste Ansätze. Simulations-RNG strikt vom echten Spiel-RNG trennen;
   niemals echte verdeckte Partnerwürfel verwenden.
4. Danach Curriculum über Wind, Leck, Eis, Praktikant und Echtzeit sowie alle
   sechs Karten und 186 Fälle erweitern. Den gemeinsamen schwarzen Würfel auch
   in ZUKÜNFTIGEN Kapazitätsabschätzungen exakt einmal zuordnen. Windvortraining
   braucht bessere Einzelvorhersagen; gute Gesamtfehler genügen nicht.
5. Frontend-Kartenwahl und automatische KI-Abwicklung offener Zusatzwürfel und
   Tauschbestätigungen ergänzen, bevor entsprechende Modelle veröffentlicht
   werden. Aktuell unterstützen die produktiven Singleplayer-Flows nur Grundspiel;
   die neue Kerosin-Schnittstelle ist vorbereitet, aber ohne freigegebene Gewichte.
6. Fallweise unabhängige Qualifikation und Veröffentlichung für Kartenfälle
   ergänzen. `ai.publish` weist Kartenrouten noch ausdrücklich ab. Das nicht
   einfach umgehen: erst passende Einzelberichte und Browserabläufe herstellen.
   Kerosinfreigaben verlangen bereits echte Modulentscheidungen und eine
   Qualitätsgrenze von mindestens 50 %. Neue schwache Modelle bleiben verborgen.
7. Relevante Tests und Browserparität prüfen, geprüfte Fortschritte nach main
   pushen (ausdrücklich autorisiert). Nicht behaupten, das Ziel sei erreicht,
   solange auch nur ein Fall nicht unabhängig besteht.

## Geschützte fremde Änderungen

Nicht anfassen/stagen: `ai/analysis.ipynb`, `ai/tuning/README.md`,
`ai/tuning/analysis.ipynb`, `ai/tuning/transfer.py`, `tests/test_ai_transfer.py`.
