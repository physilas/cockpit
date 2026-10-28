# Gemeinsamer Rundenplan · Vorschlag vom 28. Oktober 2026

Dies ist ein Bedienungs- und Architekturvorschlag. Der Rundenplan ist noch nicht an das Spiel oder die KI angeschlossen.

## Empfohlener Ablauf

Vor jeder Runde zeigt die KI höchstens drei kombinierbare Ziele: gewünschte Flugweite, einen Schwerpunkt und gegebenenfalls eine besondere Absprache für die aktiven Module/Karten. Beispiel: ein Feld weiterfliegen, Flugzeuge vor uns entfernen, Synchronisation anstreben. Eine kurze Begründung kann bei Bedarf eingeblendet werden.

Ein Daumen hoch übernimmt einen Vorschlag. Ein Daumen runter lehnt diesen Vorschlag ab und bietet passende Alternativen an; beim Flugziel etwa 0 oder 2 statt 1 Feld. Ein gemeinsamer Knopf übernimmt alle aktuellen Vorschläge, sodass nicht jede Runde drei Bestätigungsklicks nötig sind. Anschließend bleibt nur eine kompakte, lesbare Zusammenfassung des gemeinsamen Plans sichtbar. Die schrittweise Dialogvariante ist eine Alternative; das kurze Briefing braucht weniger Interaktionen.

Über **„Meine Ansage“** kann der Mensch unabhängig von den KI-Vorschlägen eine Flugweite, einen Schwerpunkt und eine Absprache auswählen. Danach zeigt die KI die verstandenen Ziele zur Bestätigung. Das ist im beiliegenden Bedienungsentwurf ausprobierbar; im echten Spiel noch nicht angeschlossen. Optionaler Freitext würde später dieselben strukturierten Ziele erzeugen und ebenfalls vor der Übernahme angezeigt werden.

Die KI erzeugt die Vorschläge ausschließlich aus der öffentlichen Lage: Entfernung, Höhe, Verkehr, Fluglage, Wind, Ausbaustand und Karten. Sie benutzt dafür weder ihre verdeckten Würfel noch die des Menschen. Nach der Bestätigung wird der Plan für diese Runde gesperrt. Ein Neuwurf öffnet die Absprache nicht erneut. Die Echtzeituhr startet erst mit den Würfeln, nicht beim Briefing.

## Regeltreue

Die [offizielle Anleitung, Seite 4](https://www.scorpionmasque.com/sites/scorpionmasque.com/files/st_rules01_en_06jun2023.pdf#page=4) erlaubt gemeinsame strategische Ziele vor dem Würfeln. Bereits dort sind konkrete Würfelabsprachen untersagt; nach dem Würfeln gilt Schweigen. Daher gehören Flugweite, Verkehr, Ausbau und gewünschte Fluglage in den Standard. Eine Absprache wie „kleinsten Würfel aufs Ruder“ wäre eine gesondert gekennzeichnete Hausregel. Die bestehende KI-ndergartenbetreuung ist bereits ein Lernmodus mit Eingriffen während der Runde.

## Anbindung ohne zusätzliches Sprachmodell

Die Vorschläge sind benannte Strategiebausteine. Ihre lesbaren Texte und strukturierten IDs werden aus derselben Definition erzeugt. Es wird kein Textmodell heruntergeladen, um bereits bekannte Knopfentscheidungen wieder in IDs zu übersetzen.

Ein möglicher Datenvertrag:

```json
{
  "version": 1,
  "round": 3,
  "movement_preference": 1,
  "focus": "radio",
  "coordination": "synchronisation",
  "source": "public_state",
  "locked": true
}
```

Der Planer berücksichtigt diese Präferenzen bei der Suche nach einem vollständigen Handplan. Pflichtfelder und die Vermeidung unmittelbar nachweisbarer Verluste bleiben geschützt. Ein abgesprochenes Ziel ist eine Präferenz unter unsicheren Würfen. Die KI darf bei einem ungeeigneten Wurf abweichen; nach der Runde wird die Zielerreichung sichtbar. Erklärungen sollen aus tatsächlich protokollierten Einschränkungen entstehen.

Die neue Kontextvariante sollte eine eigene Strategieversion erhalten. Ohne Absprache muss sie exakt auf die eingefrorene Crew-6-Strategie zurückfallen. Die Bestätigung von Crew 6 bewertet das autonome Profil 15; sie wäre kein Wirksamkeitsnachweis für diese neue Kommunikationsfunktion. Dafür braucht es zusätzliche Szenariotests und Vergleiche mit menschlichen oder ausdrücklich bezeichneten simulierten Partnern.

## Daten und spätere Erweiterungen

Strategievorschläge, Annahmen/Ablehnungen, öffentliche Ausgangslage und spätere Zielerreichung werden getrennt von den Bewertungen konkreter Würfelzüge gespeichert. Die bestehenden Zustimmungs- und Speicherregeln gelten weiter. Eine abgelehnte Absprache ist kein negativer Trainingsbeleg für einen beliebigen einzelnen Zug.

Freitext kann später dieselben Strategiebausteine auswählen. Zunächst sind die sichtbaren Auswahlmöglichkeiten auf dem iPhone schneller, verständlicher und vollständig offline nutzbar. Lokales Function Calling ist technisch möglich, etwa mit [FunctionGemma](https://ai.google.dev/gemma/docs/functiongemma); solche Modelle benötigen aber zusätzlichen Speicher, Laufzeitintegration und eine aufgabenspezifische Zuverlässigkeitsprüfung. Für den ersten Rundenplan ist das nicht erforderlich.

## Optionales Sprachpaket: tatsächliche Größen

Die browserfähige [SmolLM2-135M-ONNX-Variante in q4f16](https://huggingface.co/onnx-community/SmolLM2-135M-Instruct-ONNX/blob/main/onnx/model_q4f16.onnx) hat etwa 117 MB Modellgewichte, zuzüglich Tokenizer und Laufzeit. Laut [Original-Modellbeschreibung](https://huggingface.co/HuggingFaceTB/SmolLM2-135M-Instruct) versteht und erzeugt SmolLM2 vor allem Englisch. Damit ist noch keine verlässliche deutsche Strategieübersetzung nachgewiesen. Der aktuelle [FunctionGemma-270M-ONNX-Export](https://huggingface.co/onnx-community/functiongemma-270m-it-ONNX/tree/main/onnx) benötigt bereits rund 426 MB q4f16-Gewichte plus Graph und Zusatzdateien. Eine reine Parameterzahl × 4 Bit unterschätzt solche tatsächlichen Browserdownloads. [Google empfiehlt für FunctionGemma aufgabenspezifisches Fine-Tuning](https://ai.google.dev/gemma/docs/functiongemma).

Empfohlen ist ein unabhängiges, freiwilliges Sprachpaket mit ausgewiesener gemessener Downloadgröße, Abbrechen und Löschen. Vor einer Freigabe sind deutsche Strategieansagen, Verneinungen, widersprüchliche Ziele und unbekannte Wünsche zu testen. Nur gültige Ziel-IDs und im aktuellen Zustand mögliche Parameter dürfen weitergereicht werden; Unklarheiten erscheinen zur Auswahl. Die ursprüngliche App und direkte Zieleingabe bleiben ohne dieses Paket nutzbar. Ein solches Sprachpaket ist noch nicht implementiert oder heruntergeladen.
