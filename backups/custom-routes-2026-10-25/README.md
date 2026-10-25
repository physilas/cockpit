# Eigene Routen – Backup vom 25.10.2026

Gesichert sind FRA, LHR, MUC, MUC_T1, MUC_T2 und MUC_T3: sechs unveränderte YAML-Dateien, ihre vollständigen bisherigen Katalogeinträge in `catalog.json` und Prüfsummen in `sha256.json`.

Auf Nutzerwunsch zeigt das Spiel vorerst ausschließlich die 21 Standardrouten. `build.py` entfernt eigene Routen aus dem gemeinsamen Browserkatalog. Dadurch erscheinen sie weder im Einzelspieler noch bei Pass & Play oder in der Mehrspieler-Auswahl. Der Filter „Eigene Strecken“ ist entfernt.

Die Originaldateien unter `backend/landungen/` bleiben zusätzlich erhalten, damit historische KI-Modelle, Trainingsberichte und Engineübungen reproduzierbar bleiben. Sie werden im Spiel nicht angeboten. Gespeicherte historische Partien und Modelle werden nicht gelöscht.

Für eine spätere Wiederherstellung sind alle Routendaten hier gesichert. Die Einschränkung des Browserkatalogs wird zentral in `build.py` zurückgenommen. In `frontend/web/js/landings.js` auch den Galerieknopf samt Filterverhalten für eigene Strecken wiederherstellen (vorheriger Stand: Commit `eb829dd`), anschließend `python build.py` ausführen. Historische Trainings-/Release-Daten brauchen keine Änderung.
