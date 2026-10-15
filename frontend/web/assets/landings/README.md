# Stadtpanoramen und Bildnachweise

Die 13 Dateien `*-city.webp` sind Fotos von Wikimedia Commons, ausgewählt und
anhand der konkreten Dateiseiten und ihrer Lizenzmetadaten am 15.10.2026 geprüft.
Sie zeigen die Städte und Landschaften der Reiseziele im Panorama-Stil und
ersetzen die bisherigen Flughafenfotos. KEF zeigt Reykjavík; PBH zeigt Paro mit
Fluss, Tal und Rinpung Dzong. Die Spiel-Illustrationen gehören nicht zu den Assets.

Die verbindlichen Bildnachweise stehen in `backend/bildnachweise.json`: Originaltitel,
Autor, Quelldateiseite, Originaldatei, Lizenz mit URL, Bearbeitungshinweis und
Prüfdatum. SHA-256-Werte dokumentieren heruntergeladene und verwendete Fassungen.
Die Fotos sind unter CC0 1.0, CC BY 2.0/4.0 oder CC BY-SA 2.0/3.0/3.0 DE/4.0 verfügbar;
die konkrete Lizenz je Bild ist maßgeblich. Die verwendeten Bildfassungen behalten
ihre jeweils dokumentierte Lizenz.

Bearbeitung: längste Kante auf maximal 1280 Pixel verkleinert und als WebP gespeichert.
Das Layout zeigt abhängig von der Ansicht einen Ausschnitt. Keine inhaltliche
Retusche. Die Rechteangaben beziehen sich auf die Fotos.

`build.py` erzeugt die öffentliche Seite `frontend/web/bildnachweise.html` aus
denselben Metadaten. Die App zeigt den Fotocredit auf jeder Auswahlkarte und
verlinkt Autor/Quelle, Lizenz und vollständigen Nachweis in der Detailansicht.
Die Bildnachweise und die lokalen Fotodateien gehören zum PWA-Cache.

Neue Fotos nur mit dokumentierter passender Lizenz und vollständigem Nachweis
hinzufügen. Hinweise zur Wiederverwendung:
https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia
