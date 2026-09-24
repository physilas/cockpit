/*
 * Cockpit - Web-Frontend (Pass & Play)
 *
 * Lädt die Python-Engine aus engine-src.js (eine gebündelte JS-Datei,
 * die alle Backend-.py-Dateien als Strings enthält) und übergibt sie
 * an Pyodide. Kein ../../-Pfad-Traversal mehr, keine einzelnen .py-
 * Fetch-Anfragen - eine einzige Datei, die immer funktioniert.
 *
 * Nach Änderungen am Backend:  python3 build.py  (aus dem Repo-Root)
 *
 * Kompaktes Layout (iPhone, keine Scrollbar): Fahrwerk-/Landeklappen-/
 * Bremsen-Lichter sitzen direkt unter den jeweiligen Würfelfeldern statt
 * in einer eigenen Leiste; die Kaffeetassen-Boxen sitzen direkt neben
 * dem Konzentrations-Feld statt in der Statusleiste.
 */

let pyodide = null;
let bridge = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuOffenFuer = null;
let neuwurfOffen = false;
let neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
let aktuellerZustand = null;

// Pass-&-Play Würfelsichtbarkeit
// null = alle verborgen; "pilot" / "kopilot" = nur diese Seite sichtbar
let diceVisible = null;

// Neuwurf-Zweiphasen (Pass & Play)
// 0 = geschlossen, 1 = Initiator wählt, 2 = Partner wählt
let neuwurfPhase = 0;
let neuwurfInitiatorRolle = null;   // wer hat Neuwurf gestartet?
let neuwurfPhase1Indizes = new Set(); // Würfel-Indizes des Initiators

async function ladeEngine() {
  pyodide = await loadPyodide();
  await pyodide.loadPackage("pyyaml");

  // ENGINE_SRC wird von engine-src.js bereitgestellt (auto-generiert durch build.py)
  pyodide.FS.mkdirTree("/cockpit/backend/landungen");
  for (const [ziel, src] of Object.entries(ENGINE_SRC)) {
    pyodide.FS.writeFile("/cockpit/" + ziel, src);
  }

  pyodide.runPython(`
import sys
sys.path.insert(0, "/cockpit")
`);
  bridge = pyodide.pyimport("backend.bridge");
}

function pyToJs(pyResult) {
  return pyResult.toJs({ dict_converter: Object.fromEntries });
}

function grundText(code) {
  if (!code) return "";
  return bridge.grund_text(code);
}

function setzeMeldung(text, art) {
  const el = document.getElementById("meldung-leiste");
  el.textContent = text || "";
  el.className = art || "";
}

// Aerodynamik-Skala als horizontale Leiste: eine Zahl je Zelle, an den
// beiden Schwellen (blau = Fahrwerk-Marker, orange = Landeklappen-Marker)
// sitzt statt eines simplen "|" ein kleiner, farbiger vertikaler Balken
// in der jeweiligen Spielerfarbe (S.6/S.7/S.8).
function aeroSkalaHTML(blau, orange) {
  const bGrenze = Math.floor(blau);
  const oGrenze = Math.floor(orange);
  let html = '<div class="skala-leiste">';
  for (let n = 2; n <= 12; n++) {
    html += `<span class="skala-zahl">${n}</span>`;
    if (n < 12) {
      if (n === bGrenze) html += '<span class="skala-sep skala-sep-blau"></span>';
      if (n === oGrenze) html += '<span class="skala-sep skala-sep-orange"></span>';
      if (n !== bGrenze && n !== oGrenze) html += '<span class="skala-luecke"></span>';
    }
  }
  html += '</div>';
  return html;
}

// Bremsen-Marker-Skala, gleiches Prinzip wie oben, aber mit einem roten
// Balken an der aktuellen Bremsstärke (S.9-S.11).
function bremsSkalaHTML(bs) {
  let html = '<div class="skala-leiste">';
  if (bs < 2) html += '<span class="skala-sep skala-sep-rot"></span>';
  for (let n = 2; n <= 6; n++) {
    html += `<span class="skala-zahl">${n}</span>`;
    if (n < 6) {
      if (n === bs) html += '<span class="skala-sep skala-sep-rot"></span>';
      else html += '<span class="skala-luecke"></span>';
    }
  }
  html += '</div>';
  return html;
}

// Höhen-/Entfernungs-Gauges (Sky-Team-artig): das Flugzeug-Symbol sitzt
// NICHT in den Leisten selbst, sondern in einer eigenen, gemeinsamen
// Spalte dazwischen (siehe HTML: .tracks-marker-col) - so bleiben die
// Höhen- und Entfernungs-Flugzeuge IMMER exakt auf derselben Höhe,
// unabhängig davon, wie lang die jeweilige Leiste ist (ALTITUDE_MAX_UNITS
// vs. `laenge` können unterschiedlich groß sein).
//
// Jede Leiste hat oberhalb der (gemeinsamen) Marker-Linie Platz für ihre
// eigene maximale Länge (`ownMax` Felder), und darunter genau EIN
// zusätzliches Feld für das zuletzt verbrauchte ("gerade hinter uns") -
// alles, was weiter zurückliegt, ist strategisch nicht mehr relevant und
// wird gar nicht erst gezeichnet. Beide Leisten werden an der Marker-
// Linie ausgerichtet, indem die kürzere Leiste oben etwas eingerückt
// wird (`topPad`).
const TRACK_UNIT_PX = 26;
// 7 statt 6 Einheiten: 6 echte 1000-ft-Schritte (6000->0) PLUS ein
// zusätzliches "Bereitschafts"-Feld, damit 0 ft noch als 1 blaues Feld
// angezeigt wird (S.9/S.10: "Perfektes Timing" ist erst erreicht, wenn
// Höhe UND Entfernung gleichzeitig bei ihrem letzten Feld stehen - nicht
// erst, wenn beide Leisten schon leer sind).
const ALTITUDE_MAX_UNITS = 7;

function setzeGauge(prefix, ownMax, remaining, totalHeight, markerY) {
  const used = ownMax - remaining;

  document.getElementById(`${prefix}-track`).style.height = totalHeight + "px";

  // Beide Leisten haben dieselbe Gesamthöhe und denselben Marker (siehe
  // renderTracks), also reicht ein einfaches "bottom", damit die
  // Füllung direkt oberhalb des Markers beginnt.
  const fill = document.getElementById(`${prefix}-fill`);
  fill.style.bottom = (totalHeight - markerY) + "px";
  fill.style.height = (remaining * TRACK_UNIT_PX) + "px";

  // Das unterste ("bereits verbrauchte") Feld unterhalb des Markers wurde
  // entfernt, da es keine zusätzliche Information trägt - der Marker
  // selbst sitzt jetzt direkt am unteren Rand der Leiste.
  const usedEl = document.getElementById(`${prefix}-used`);
  if (usedEl) usedEl.classList.remove("sichtbar");

  return used;
}

// Fluglage als künstlicher Horizont (S.5): der Himmel/Boden-Hintergrund
// steht fest, nur der weiße Zeiger dreht sich - wie bei einem echten
// Fluglage-Instrument. 20°/Einheit, damit der Zeiger bei jedem der 5
// festen Marker (-2/-1/0/+1/+2) sichtbar exakt einrastet; RUDER_STALL_
// SCHWELLE (Trudeln) liegt bei ±3, der Zeiger kann also auch noch etwas
// darüber hinauszeigen, kurz bevor die Partie endet.
const ATTITUDE_DEG_PRO_EINHEIT = 20;

function renderAttitude(fluglage) {
  const needle = document.getElementById("attitude-needle");
  if (!needle) return;
  const deg = fluglage * ATTITUDE_DEG_PRO_EINHEIT;
  needle.style.transform = `rotate(${deg}deg)`;
  needle.style.transformOrigin = "50px 60px";
}

function renderTracks(zustand) {
  const laenge = zustand.laenge || 1;
  // Auch die Entfernung bekommt das gleiche "+1"-Bereitschaftsfeld wie die
  // Höhe (siehe ALTITUDE_MAX_UNITS), damit "angekommen" (Entfernung 0)
  // ebenfalls als 1 blaues Feld erscheint - beide Leisten zeigen "1 blaues
  // Feld" also exakt im selben Moment: wenn Höhe UND Entfernung beide ihr
  // letztes reales Feld erreicht haben (S.9 "Perfektes Timing").
  const distanzEinheiten = laenge + 1;
  const maxGlobal = Math.max(ALTITUDE_MAX_UNITS, distanzEinheiten);
  const totalHeight = maxGlobal * TRACK_UNIT_PX; // kein zusätzliches Feld mehr für die verbrauchte Spur
  const markerY = totalHeight;

  // Gemeinsamer Flugzeug-Marker zwischen den beiden Leisten.
  document.getElementById("tracks-marker").style.top = markerY + "px";

  // Höhe: 7 Einheiten (6 reale 1000-ft-Schritte + 1 Bereitschaftsfeld bei 0 ft).
  setzeGauge("altitude", ALTITUDE_MAX_UNITS, zustand.hoehe / 1000 + 1, totalHeight, markerY);
  document.getElementById("s-hoehe-label").textContent = zustand.hoehe + " ft";
  renderAltitudeLabels(markerY, zustand.hoehe);

  // Entfernung: `laenge` Einheiten (variiert je Flughafen) + 1 Bereitschaftsfeld.
  const distUsed = setzeGauge("distance", distanzEinheiten, zustand.entfernung + 1, totalHeight, markerY);
  document.getElementById("s-entfernung-label").textContent = "Entf. " + zustand.entfernung;

  // Hindernis-Flugzeuge: Index i (0 = am weitesten weg/Start) sitzt an
  // einer FESTEN Position auf der Leiste. y = (maxGlobal - i + verbraucht)
  // * UNIT_PX, gemessen vom oberen Rand der Leiste. Alles, was mehr als
  // ein Feld hinter dem Marker liegt, wird nicht mehr gezeichnet (nicht
  // mehr relevant für die Entscheidungsfindung).
  const obstaclesEl = document.getElementById("distance-obstacles");
  obstaclesEl.innerHTML = "";
  (zustand.flugzeuge || []).forEach((count, i) => {
    if (count <= 0) return;
    // -0.5 Einheiten, damit das Flugzeug-Symbol in der Mitte seines
    // Feldes sitzt statt auf der Trennlinie zum nächsten Feld.
    const y = (maxGlobal - i + distUsed - 0.5) * TRACK_UNIT_PX;
    if (y > markerY) return;
    const el = document.createElement("span");
    el.className = "vtrack-obstacle";
    el.style.top = y + "px";
    // Einzelne Flugzeug-Symbole statt "✈×n" - eines je Flugzeug auf diesem Feld.
    for (let k = 0; k < count; k++) {
      const plane = document.createElement("span");
      plane.textContent = "✈";
      el.appendChild(plane);
    }
    obstaclesEl.appendChild(el);
  });
}

// Höhen-Zahlen auf der Höhenleiste: KEINE festen Positionen, sondern eine
// "mitlaufende" Skala - das unterste (dem Flugzeug-Marker nächste) Feld
// zeigt immer die AKTUELLE Höhe, darüber in 1000-ft-Schritten absteigend
// bis 0 ft. Sobald ein Feld einen negativen Wert hätte (weil die Partie
// schon weiter fortgeschritten ist als dieses Feld "vorschauen" kann),
// bleibt es leer ("nichts") statt einer Zahl - so rutscht nach jeder Runde
// ein Feld oben "aus dem Bild" und ein neues (niedrigeres) rückt nach unten
// an den Marker heran. Bei 2000 ft sitzt zusätzlich ein Neuwurf-Plättchen-
// Symbol - die Engine vergibt dort automatisch ein Plättchen (siehe
// backend/spielplan.py: NEUWURF_HOEHEN); sobald diese Höhe tatsächlich
// erreicht/unterschritten ist, verschwindet das Symbol wieder (bereits
// eingesammelt).
const NEUWURF_HOEHEN_FT = 2000;

function renderAltitudeLabels(markerY, aktuelleHoehe) {
  const el = document.getElementById("altitude-labels");
  if (!el) return;
  el.innerHTML = "";
  for (let v = 0; v < ALTITUDE_MAX_UNITS; v++) {
    const hoeheFt = aktuelleHoehe - v * 1000;
    if (hoeheFt < 0) continue; // "nichts" - Feld bleibt leer/unbeschriftet

    const y = markerY - (v + 0.5) * TRACK_UNIT_PX;
    const label = document.createElement("span");
    label.className = "vtrack-heightlabel";
    label.style.top = y + "px";
    label.textContent = String(hoeheFt);

    if (hoeheFt === NEUWURF_HOEHEN_FT && aktuelleHoehe > NEUWURF_HOEHEN_FT) {
      // Eigenes, absolut positioniertes Element statt Teil des Zahlentexts -
      // so bleibt die "2000" exakt so zentriert wie alle anderen Zahlen,
      // unabhängig davon, ob das Plättchen-Symbol daneben sichtbar ist.
      const badge = document.createElement("span");
      badge.className = "reroll-badge";
      badge.textContent = "🔄";
      label.appendChild(badge);
    }
    el.appendChild(label);
  }
}

// Kaffee und Neuwurf als kompakte Boxen
function kaffeeBoxenHTML(anzahl) {
  let html = "";
  for (let i = 0; i < 3; i++) {
    const voll = i < anzahl;
    html += `<span class="ressourcen-box${voll ? " gefuellt" : ""}">${voll ? "☕" : ""}</span>`;
  }
  return html;
}

function neuwurfBoxenHTML(anzahl) {
  if (anzahl <= 0) return '<span class="ressourcen-box"></span>';
  return Array.from({ length: anzahl }, () => '<span class="ressourcen-box gefuellt">🔄</span>').join("");
}

function render(zustand) {
  if (!zustand) return;
  aktuellerZustand = zustand;

  document.getElementById("s-runde").textContent =
    zustand.runde + (zustand.letzte_runde ? " (l.)" : "") + (zustand.warteschleife ? " ⟳" : "");
  document.getElementById("s-aero").innerHTML = aeroSkalaHTML(zustand.aerodynamik_blau, zustand.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(zustand.bremsstaerke);
  document.getElementById("s-kaffee-status").innerHTML = kaffeeBoxenHTML(zustand.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfBoxenHTML(zustand.neuwurf_plaettchen);

  renderAttitude(zustand.fluglage);
  renderTracks(zustand);
  renderCockpitBoard(zustand);
  renderWuerfel("pilot", zustand);
  renderWuerfel("kopilot", zustand);
  renderNeuwurfPanel(zustand);

  const amZugEl = document.getElementById("am-zug-anzeige");
  const rundenendeBtn = document.getElementById("rundenende-btn");
  const neuwurfBtn = document.getElementById("neuwurf-btn");

  if (zustand.status !== "laeuft") {
    amZugEl.innerHTML = `<div class="spiel-ende ${zustand.status}">` +
      (zustand.status === "gewonnen"
        ? "🎉 Sicher gelandet!"
        : `💥 Verloren – ${grundText(zustand.verlust_grund)}`) +
      "</div>";
    rundenendeBtn.disabled = true;
    neuwurfBtn.disabled = true;
  } else {
    amZugEl.textContent = `Am Zug: ${zustand.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"}`;
    rundenendeBtn.disabled = false;
    neuwurfBtn.disabled = zustand.neuwurf_plaettchen <= 0;
  }
}

// --- Cockpit-Board (zeigt jedes gelegte Feld; Bremsen/Klappen: nur nächstes frei) ---
const ZIEL_BESCHRIFTUNG = {
  ruder: "Ruder", triebwerk: "Trieb.", funk: "Funk",
  fahrwerk: "Fahrw.", landeklappe: "Klappen",
  bremse: "Bremse", konzentration: "Konz.",
};

function feldZelle(fixierterBesitzer, wertObjekt, slotIndex, eintrag, zustand, gesperrt) {
  const div = document.createElement("div");
  div.className = "feld-zelle";

  if (wertObjekt) {
    div.classList.add("belegt", wertObjekt.besitzer);
    div.textContent = wertObjekt.wert;
    return div;
  }
  if (eintrag.zahlen && slotIndex !== null)
    div.innerHTML = `<small>${eintrag.zahlen[slotIndex].join("/")}</small>`;

  if (gesperrt) {
    div.title = "Erst die vorherigen Felder in dieser Reihe erledigen.";
    return div;
  }

  const kannHierPlatzieren = fixierterBesitzer
    ? ausgewaehlterWuerfel?.besitzer === fixierterBesitzer
    : ausgewaehlterWuerfel && eintrag.zugriff.includes(ausgewaehlterWuerfel.besitzer);

  const istKlickbar = zustand.status === "laeuft" && ausgewaehlterWuerfel &&
    zustand.am_zug === ausgewaehlterWuerfel.besitzer && kannHierPlatzieren;

  if (istKlickbar) {
    div.classList.add("klickbar");
    div.title = "Ausgewählten Würfel hier platzieren";
    div.addEventListener("click", () => platziereAusgewaehlten(eintrag, slotIndex));
  }
  return div;
}

// Baut eine Zelle plus optionalem kleinen Licht-Indikator darunter (statt
// einer eigenen Fortschritts-Leiste - kompakter fürs iPhone).
function feldZelleMitLicht(wertObjekt, slotIndex, eintrag, zustand, gesperrt, statusArray) {
  const wrap = document.createElement("div");
  wrap.className = "feld-slot-mit-licht";
  wrap.appendChild(feldZelle(null, wertObjekt, slotIndex, eintrag, zustand, gesperrt));
  if (statusArray) {
    const licht = document.createElement("span");
    licht.className = "feld-licht" + (statusArray[slotIndex] ? " an" : "");
    wrap.appendChild(licht);
  }
  return wrap;
}

function keinEffektWarnung(eintrag, slotIndex, zustand) {
  if (!zustand) return null;
  const z = zustand;
  if (eintrag.ziel === "fahrwerk" && z.fahrwerk_ausgefahren[slotIndex])
    return "Dieses Fahrwerk-Teil ist bereits ausgefahren – kein Effekt.";
  if (eintrag.ziel === "landeklappe" && z.landeklappen_ausgefahren[slotIndex])
    return "Diese Landeklappe ist bereits ausgefahren – kein Effekt.";
  if (eintrag.ziel === "bremse" && z.bremsen_aktiviert[slotIndex])
    return "Diese Bremse ist bereits aktiviert – kein Effekt.";
  if (eintrag.ziel === "konzentration" && z.kaffeetassen >= 3)
    return "Der Kaffeevorrat ist bereits voll (3 Tassen) – kein Effekt.";
  return null;
}

function platziereAusgewaehlten(eintrag, slotIndex) {
  if (!ausgewaehlterWuerfel) return;

  const warnung = keinEffektWarnung(eintrag, slotIndex, aktuellerZustand);
  if (warnung && !window.confirm(`⚠️ ${warnung}\n\nTrotzdem platzieren?`)) return;

  const brauchtIndex = ["fahrwerk", "landeklappe", "bremse", "konzentration"].includes(eintrag.ziel);
  const antwort = pyToJs(bridge.platziere(
    ausgewaehlterWuerfel.besitzer, ausgewaehlterWuerfel.index, eintrag.ziel,
    brauchtIndex ? slotIndex : null,
    eintrag.ziel === "funk" ? slotIndex : 0
  ));
  ausgewaehlterWuerfel = null;
  diceVisible = null;   // Würfel sofort wieder verbergen
  nachAktion(antwort);
}

// Ordnet jeden Feld-Layout-Eintrag seinem Bereich auf dem neu geordneten
// Board zu: alle Pilot-Aufgaben (Ruder/Triebwerk-Hälfte, Funk, Fahrwerk,
// Bremse) links in einer Spalte, alle Kopilot-Aufgaben (Ruder/Triebwerk-
// Hälfte, Funk, Landeklappen) rechts in einer Spalte, nur die gemeinsame
// Konzentration (beide Farben) unten in der Mitte neben Wheel + Leisten.
function containerFuerEintrag(eintrag, besitzer) {
  if (eintrag.ziel === "konzentration") {
    return document.getElementById("center-bottom-row");
  }
  if (eintrag.ziel === "landeklappe") {
    return document.getElementById("col-kopilot");
  }
  if (eintrag.ziel === "fahrwerk" || eintrag.ziel === "bremse") {
    return document.getElementById("col-pilot");
  }
  if (eintrag.ziel === "funk") {
    return eintrag.zugriff.includes("pilot")
      ? document.getElementById("col-pilot")
      : document.getElementById("col-kopilot");
  }
  // ruder/triebwerk: Farbpaar, je Hälfte in die passende Spalte.
  return besitzer === "pilot"
    ? document.getElementById("col-pilot")
    : document.getElementById("col-kopilot");
}

function renderCockpitBoard(zustand) {
  const bereiche = ["col-pilot", "col-kopilot", "center-bottom-row"]
    .map(id => document.getElementById(id));
  bereiche.forEach(el => { if (el) el.innerHTML = ""; });

  const layout = pyToJs(bridge.feld_layout());
  const felder = zustand.felder;

  layout.forEach(eintrag => {
    if (eintrag.art === "farbpaar") {
      // Ruder/Triebwerk: statt einer gemeinsamen Zeile mit 2 Zellen, je
      // eine einzellige Zeile pro Farbe - eine für die Pilot-, eine für
      // die Kopilot-Spalte (S.5/S.6 bleiben pro Spieler eigene Würfel).
      const werte = felder[eintrag.snapshot_key];
      ["pilot", "kopilot"].forEach(besitzer => {
        const zeile = document.createElement("div");
        zeile.className = "feld-zeile";
        const label = document.createElement("span");
        label.className = "feld-label";
        label.textContent = ZIEL_BESCHRIFTUNG[eintrag.ziel] + (eintrag.pflicht ? " *" : "");
        zeile.appendChild(label);
        const slots = document.createElement("div");
        slots.className = "feld-slots";
        slots.appendChild(feldZelle(besitzer, werte[besitzer], null, eintrag, zustand, false));
        zeile.appendChild(slots);
        containerFuerEintrag(eintrag, besitzer).appendChild(zeile);
      });
      return;
    }

    const board = containerFuerEintrag(eintrag);
    const zeile = document.createElement("div");
    zeile.className = "feld-zeile";

    const label = document.createElement("span");
    label.className = "feld-label";
    label.textContent = ZIEL_BESCHRIFTUNG[eintrag.ziel] + (eintrag.pflicht ? " *" : "");
    zeile.appendChild(label);

    const slots = document.createElement("div");
    slots.className = "feld-slots";

    const werte = felder[eintrag.snapshot_key];
    const statusArray =
      eintrag.ziel === "fahrwerk"     ? zustand.fahrwerk_ausgefahren :
      eintrag.ziel === "landeklappe"  ? zustand.landeklappen_ausgefahren :
      eintrag.ziel === "bremse"       ? zustand.bremsen_aktiviert : null;
    // Nur Landeklappen und Bremsen müssen strikt der Reihe nach ausgefahren
    // werden (S.8/S.9) - beim Fahrwerk ist laut Regelheft jede Reihenfolge
    // erlaubt (S.7), daher hier keine Sperre über die anderen Felder.
    const reihenfolgeZaehlt = eintrag.ziel === "landeklappe" || eintrag.ziel === "bremse";
    const naechsterIndex = reihenfolgeZaehlt ? statusArray.indexOf(false) : null;
    for (let i = 0; i < eintrag.slots; i++) {
      const gesperrt = reihenfolgeZaehlt && naechsterIndex !== -1 && i !== naechsterIndex;
      if (statusArray) {
        slots.appendChild(feldZelleMitLicht(werte[i], i, eintrag, zustand, gesperrt, statusArray));
      } else {
        slots.appendChild(feldZelle(null, werte[i], i, eintrag, zustand, gesperrt));
      }
    }
    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}

// --- Würfel-Trays + Kaffee ---
//
// Neuwurf-Auswahl (Reroll): läuft nicht mehr über eine separate Liste mit
// Checkboxen ("1:4", "2:2", ...), sondern direkt über Klicks auf die
// bereits angezeigten Würfel - genau wie beim normalen Platzieren, nur
// dass hier mehrere Würfel gleichzeitig markiert werden können (Toggle),
// bis "Weiter"/"Neu würfeln" bestätigt wird.
function neuwurfAktivBesitzer() {
  if (neuwurfPhase === 1) return neuwurfInitiatorRolle;
  if (neuwurfPhase === 2) return neuwurfInitiatorRolle === "pilot" ? "kopilot" : "pilot";
  return null;
}

function neuwurfAuswahlSetFuer(besitzer) {
  if (neuwurfPhase === 1) return neuwurfPhase1Indizes;
  if (neuwurfPhase === 2) return neuwurfAuswahl[besitzer];
  return null;
}

function renderWuerfel(besitzer, zustand) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";

  const werte = zustand[`${besitzer}_wuerfel`];
  const frei  = zustand[`${besitzer}_wuerfel_frei`];
  const istAmZug  = zustand.am_zug === besitzer && zustand.status === "laeuft";
  const sichtbar  = diceVisible === besitzer;

  const imNeuwurf = neuwurfPhase !== 0;
  const aktiverNeuwurfBesitzer = neuwurfAktivBesitzer();
  const istNeuwurfAktiv = imNeuwurf && besitzer === aktiverNeuwurfBesitzer;
  const neuwurfAuswahlSet = istNeuwurfAktiv ? neuwurfAuswahlSetFuer(besitzer) : null;

  // "Würfel anzeigen"-Button (nur Auge, kompakt).
  //
  // WICHTIG (Privatsphäre): Solange der Neuwurf-Dialog offen ist, gilt
  // ausschließlich die Neuwurf-Phase, NICHT "wer ist am Zug" - sonst
  // bliebe der Knopf für die Würfel des Initiators während Phase 2 aktiv
  // (er/sie ist ja weiterhin "am Zug"), und der Partner könnte am
  // gemeinsamen Gerät versehentlich fremde Würfel aufdecken. Außerhalb
  // eines Neuwurfs gilt wie gewohnt: nur der aktive Spieler sieht seine
  // eigenen, noch nicht platzierten Würfel.
  let zeigeViewBtn;
  if (imNeuwurf) {
    zeigeViewBtn = !sichtbar && istNeuwurfAktiv;
  } else {
    zeigeViewBtn = !sichtbar && istAmZug;
  }
  if (zeigeViewBtn) {
    const viewBtn = document.createElement("button");
    viewBtn.className = "view-btn";
    viewBtn.textContent = "👁";
    viewBtn.title = "Würfel anzeigen";
    viewBtn.addEventListener("click", () => {
      diceVisible = besitzer;
      render(aktuellerZustand);
    });
    container.appendChild(viewBtn);
  }

  werte.forEach((wert, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "wuerfel-slot";

    const div = document.createElement("div");
    const verberge = frei[i] && !sichtbar;
    div.className = "wuerfel" + (frei[i] ? "" : " platziert") + (verberge ? " verborgen" : "");
    div.textContent = verberge ? "?" : (wert ?? "");

    // Markierung: entweder "für's Platzieren ausgewählt" (normaler Modus)
    // oder "für den Neuwurf ausgewählt" (Reroll-Modus) - nie beides.
    const istPlatzierAusgewaehlt = !imNeuwurf && sichtbar &&
      ausgewaehlterWuerfel?.besitzer === besitzer && ausgewaehlterWuerfel?.index === i;
    const istNeuwurfMarkiert = istNeuwurfAktiv && sichtbar && neuwurfAuswahlSet?.has(i);
    if (istPlatzierAusgewaehlt || istNeuwurfMarkiert) div.classList.add("ausgewaehlt");

    if (!imNeuwurf && sichtbar && frei[i] && istAmZug) {
      div.title = "Klicken zum Auswählen, dann ein Feld im Board anklicken.";
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istPlatzierAusgewaehlt ? null : { besitzer, index: i };
        kaffeeMenuOffenFuer = null;
        render(zustand);
      });
    } else if (istNeuwurfAktiv && sichtbar && frei[i]) {
      div.title = "Klicken, um diesen Würfel für den Neuwurf zu markieren/abzuwählen.";
      div.addEventListener("click", () => {
        if (neuwurfAuswahlSet.has(i)) neuwurfAuswahlSet.delete(i);
        else neuwurfAuswahlSet.add(i);
        render(zustand);
      });
    }
    wrapper.appendChild(div);

    if (!imNeuwurf && istPlatzierAusgewaehlt && frei[i] && zustand.kaffeetassen > 0) {
      const kaffeeBtn = document.createElement("button");
      kaffeeBtn.textContent = "☕";
      kaffeeBtn.title = "Kaffee einsetzen";
      kaffeeBtn.addEventListener("click", ev => {
        ev.stopPropagation();
        const offenFuerDiesen = kaffeeMenuOffenFuer?.besitzer === besitzer && kaffeeMenuOffenFuer?.index === i;
        kaffeeMenuOffenFuer = offenFuerDiesen ? null : { besitzer, index: i };
        render(zustand);
      });
      wrapper.appendChild(kaffeeBtn);

      if (kaffeeMenuOffenFuer?.besitzer === besitzer && kaffeeMenuOffenFuer?.index === i) {
        const deltas = bridge.moegliche_kaffee_deltas(besitzer, i).toJs();
        const menu = document.createElement("div");
        menu.className = "kaffee-auswahl";
        deltas.forEach(d => {
          const btn = document.createElement("button");
          btn.textContent = (d > 0 ? "+" : "") + d;
          btn.addEventListener("click", ev => {
            ev.stopPropagation();
            kaffeeMenuOffenFuer = null;
            // Anders als beim Platzieren bleibt hier derselbe Spieler am Zug -
            // die eigenen Würfel sollen daher sichtbar bleiben, damit der neue
            // Wert direkt gesehen und der Würfel weiter platziert werden kann.
            nachAktion(pyToJs(bridge.trinke_kaffee(besitzer, i, d)), { verbirgWuerfel: false });
          });
          menu.appendChild(btn);
        });
        wrapper.appendChild(menu);
      }
    }
    container.appendChild(wrapper);
  });
}

// --- Neuwurf-Panel (zwei Phasen für Pass & Play) ---
//
// Statt einer eigenen Checkbox-Liste ("1:4", "2:2", ...) wird direkt auf
// den ohnehin sichtbaren Würfeln oben ausgewählt (siehe renderWuerfel) -
// das Panel zeigt hier nur noch die Anweisung sowie die Aktions-Buttons.
function neuwurfReset() {
  neuwurfPhase = 0;
  neuwurfInitiatorRolle = null;
  neuwurfPhase1Indizes = new Set();
  neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
  diceVisible = null;
}

function neuwurfAbbrechen() {
  neuwurfReset();
  render(aktuellerZustand);
}

function toggleNeuwurfPanel() {
  if (!aktuellerZustand || aktuellerZustand.neuwurf_plaettchen <= 0) return;
  if (neuwurfPhase !== 0) {
    neuwurfAbbrechen();
    return;
  }
  neuwurfPhase = 1;
  neuwurfInitiatorRolle = aktuellerZustand.am_zug;
  neuwurfPhase1Indizes = new Set();
  neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
  ausgewaehlterWuerfel = null;
  diceVisible = null;
  render(aktuellerZustand);
}

function renderNeuwurfPanel(zustand) {
  const panel = document.getElementById("neuwurf-panel");
  panel.innerHTML = "";

  if (neuwurfPhase === 0 || zustand.status !== "laeuft") {
    panel.classList.add("versteckt");
    return;
  }
  panel.classList.remove("versteckt");

  const partnerRolle = neuwurfInitiatorRolle === "pilot" ? "kopilot" : "pilot";
  const initiatorName = neuwurfInitiatorRolle === "pilot" ? "Pilotin" : "Co-Pilot";
  const partnerName   = partnerRolle === "pilot" ? "Pilotin" : "Co-Pilot";

  if (neuwurfPhase === 1) {
    const hinweis = document.createElement("p");
    hinweis.innerHTML = `<strong>${initiatorName}</strong>: oben die Würfel antippen, die neu geworfen werden sollen.`;
    panel.appendChild(hinweis);

    if (diceVisible !== neuwurfInitiatorRolle) {
      const viewBtn = document.createElement("button");
      viewBtn.className = "view-btn";
      viewBtn.textContent = "👁";
      viewBtn.title = "Würfel anzeigen";
      viewBtn.addEventListener("click", () => { diceVisible = neuwurfInitiatorRolle; render(aktuellerZustand); });
      panel.appendChild(viewBtn);
    } else {
      const frei = zustand[`${neuwurfInitiatorRolle}_wuerfel_frei`];
      if (!frei.some(Boolean)) {
        const s = document.createElement("p");
        s.textContent = "(keine unplatzierten Würfel verfügbar)";
        panel.appendChild(s);
      }

      const ak = document.createElement("div");
      ak.className = "neuwurf-aktionen";

      const weiter = document.createElement("button");
      weiter.textContent = `Weiter → ${partnerName}`;
      weiter.addEventListener("click", () => {
        neuwurfPhase = 2;
        diceVisible = null;
        render(aktuellerZustand);
      });
      ak.appendChild(weiter);

      const ab = document.createElement("button");
      ab.textContent = "Abbrechen";
      ab.addEventListener("click", () => neuwurfAbbrechen());
      ak.appendChild(ab);
      panel.appendChild(ak);
    }
  }

  if (neuwurfPhase === 2) {
    const hinweis = document.createElement("p");
    hinweis.innerHTML = `<strong>${partnerName}</strong>: oben die Würfel antippen, die neu geworfen werden sollen.`;
    panel.appendChild(hinweis);

    if (diceVisible !== partnerRolle) {
      const viewBtn = document.createElement("button");
      viewBtn.className = "view-btn";
      viewBtn.textContent = "👁";
      viewBtn.title = "Würfel anzeigen";
      viewBtn.addEventListener("click", () => { diceVisible = partnerRolle; render(aktuellerZustand); });
      panel.appendChild(viewBtn);
    } else {
      const frei = zustand[`${partnerRolle}_wuerfel_frei`];
      if (!frei.some(Boolean)) {
        const s = document.createElement("p");
        s.textContent = "(keine unplatzierten Würfel verfügbar)";
        panel.appendChild(s);
      }

      const ak = document.createElement("div");
      ak.className = "neuwurf-aktionen";

      const neuwerfen = document.createElement("button");
      neuwerfen.textContent = "🎲 Neu würfeln";
      neuwerfen.addEventListener("click", () => {
        const pilotIdx   = neuwurfInitiatorRolle === "pilot"
          ? Array.from(neuwurfPhase1Indizes)
          : Array.from(neuwurfAuswahl[partnerRolle]);
        const kopilotIdx = neuwurfInitiatorRolle === "kopilot"
          ? Array.from(neuwurfPhase1Indizes)
          : Array.from(neuwurfAuswahl[partnerRolle]);

        const antwort = pyToJs(bridge.benutze_neuwurf(pilotIdx, kopilotIdx));
        neuwurfReset();
        nachAktion(antwort);
      });
      ak.appendChild(neuwerfen);

      const ab = document.createElement("button");
      ab.textContent = "Abbrechen";
      ab.addEventListener("click", () => neuwurfAbbrechen());
      ak.appendChild(ab);
      panel.appendChild(ak);
    }
  }
}

function nachAktion(antwort, { verbirgWuerfel = true } = {}) {
  const ergebnis = antwort.ergebnis;
  setzeMeldung(
    ergebnis.erfolg ? ergebnis.meldung : `Nicht möglich: ${grundText(ergebnis.grund)}`,
    ergebnis.erfolg ? "erfolg" : "fehler"
  );
  if (verbirgWuerfel) diceVisible = null;
  render(antwort.zustand);
}

async function rundenendeKlick() {
  const antwort = pyToJs(bridge.rundenende());
  if (!antwort.ergebnis.erfolg) {
    setzeMeldung(`Runde kann noch nicht enden: ${grundText(antwort.ergebnis.grund)}`, "fehler");
    render(antwort.zustand);
    return;
  }
  setzeMeldung(antwort.ergebnis.meldung, "erfolg");
  diceVisible = null;
  render(antwort.zustand);
  if (antwort.zustand.status === "laeuft") {
    render(pyToJs(bridge.wuerfeln_fuer_runde()));
  }
}

async function neuesSpiel() {
  const flughafen = document.getElementById("flughafen-auswahl").value;
  ausgewaehlterWuerfel = null;
  kaffeeMenuOffenFuer = null;
  neuwurfOffen = false;
  neuwurfPhase = 0;
  neuwurfInitiatorRolle = null;
  neuwurfPhase1Indizes = new Set();
  neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
  diceVisible = null;
  const zustand = pyToJs(bridge.neues_spiel(flughafen));
  setzeMeldung("Neue Partie gestartet.", "erfolg");
  render(zustand);
}

// Zurück zum Startmenü (Pass & Play <-> Multiplayer Auswahl)
function zurueckZumMenue() {
  document.getElementById("game-header").classList.add("versteckt");
  document.getElementById("spiel-ui").classList.add("versteckt");
  document.getElementById("lade-hinweis").classList.add("versteckt");
  document.getElementById("start-menu").classList.remove("versteckt");
}

async function init() {
  document.getElementById("neues-spiel-btn").disabled = true;
  try {
    await ladeEngine();
  } catch (err) {
    console.error(err);
    document.getElementById("lade-hinweis").textContent = "Fehler beim Laden der Engine: " + err.message;
    return;
  }
  document.getElementById("lade-hinweis").classList.add("versteckt");
  document.getElementById("game-header").classList.remove("versteckt");
  document.getElementById("spiel-ui").classList.remove("versteckt");
  document.getElementById("neues-spiel-btn").disabled = false;
  document.getElementById("neues-spiel-btn").addEventListener("click", neuesSpiel);
  document.getElementById("rundenende-btn").addEventListener("click", rundenendeKlick);
  document.getElementById("neuwurf-btn").addEventListener("click", toggleNeuwurfPanel);
  const menuBtn = document.getElementById("menue-btn");
  if (menuBtn) menuBtn.addEventListener("click", zurueckZumMenue);
  await neuesSpiel();
}

// Called by the start-menu button
window.startPassAndPlay = function() {
  document.getElementById("start-menu").classList.add("versteckt");
  document.getElementById("lade-hinweis").classList.remove("versteckt");
  if (bridge) {
    // Engine schon geladen (z.B. nach Rückkehr vom Menü) - direkt weiter.
    document.getElementById("lade-hinweis").classList.add("versteckt");
    document.getElementById("game-header").classList.remove("versteckt");
    document.getElementById("spiel-ui").classList.remove("versteckt");
    neuesSpiel();
  } else {
    init();
  }
};
