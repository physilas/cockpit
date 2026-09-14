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

// Aerodynamik-Skala: "4.5 / 8.5" → "2 3 4 | 5 6 7 8 | 9 10 11 12"
function aeroSkalaHTML(blau, orange) {
  const bGrenze = Math.floor(blau);
  const oGrenze = Math.floor(orange);
  const teile = [];
  for (let n = 2; n <= 12; n++) {
    teile.push(String(n));
    if ((n === bGrenze || n === oGrenze) && n < 12)
      teile.push('<span class="trenner">|</span>');
  }
  return teile.join(" ");
}

// Bremsen-Marker-Skala: 0 → "| 2 3 4 5 6", 2 → "2 | 3 4 5 6" …
function bremsSkalaHTML(bs) {
  const teile = [];
  if (bs < 2) teile.push('<span class="trenner">|</span>');
  for (let n = 2; n <= 6; n++) {
    teile.push(String(n));
    if (n === bs) teile.push('<span class="trenner">|</span>');
  }
  return teile.join(" ");
}

// Flugzeuge: nur Felder ab aktueller Position anzeigen
function renderFlugzeuge(zustand) {
  const startIndex = Math.max(0, zustand.laenge - zustand.entfernung);
  const sichtbar = zustand.flugzeuge.slice(startIndex);
  document.getElementById("s-flugzeuge").textContent = sichtbar.length
    ? sichtbar.map(n => n > 0 ? "✈".repeat(n) : "·").join(" | ")
    : "(frei)";
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
  document.getElementById("s-hoehe").textContent = zustand.hoehe;
  document.getElementById("s-entfernung").textContent = zustand.entfernung;
  document.getElementById("s-fluglage").textContent = (zustand.fluglage > 0 ? "+" : "") + zustand.fluglage;
  document.getElementById("s-aero").innerHTML = aeroSkalaHTML(zustand.aerodynamik_blau, zustand.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(zustand.bremsstaerke);
  document.getElementById("s-neuwurf").innerHTML = neuwurfBoxenHTML(zustand.neuwurf_plaettchen);

  renderFlugzeuge(zustand);
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

function renderCockpitBoard(zustand) {
  const board = document.getElementById("cockpit-board");
  board.innerHTML = "";
  const layout = pyToJs(bridge.feld_layout());
  const felder = zustand.felder;

  layout.forEach(eintrag => {
    const zeile = document.createElement("div");
    zeile.className = "feld-zeile";

    const label = document.createElement("span");
    label.className = "feld-label";
    label.textContent = ZIEL_BESCHRIFTUNG[eintrag.ziel] + (eintrag.pflicht ? " *" : "");
    zeile.appendChild(label);

    // Kaffee/Neuwurf-Ressourcen direkt neben das Konzentrations-Label hängen
    if (eintrag.ziel === "konzentration") {
      const res = document.createElement("span");
      res.className = "ressourcen-inline";
      res.innerHTML = kaffeeBoxenHTML(zustand.kaffeetassen);
      zeile.appendChild(res);
    }

    const slots = document.createElement("div");
    slots.className = "feld-slots";

    if (eintrag.art === "farbpaar") {
      const werte = felder[eintrag.snapshot_key];
      slots.appendChild(feldZelle("pilot",   werte.pilot,   null, eintrag, zustand, false));
      slots.appendChild(feldZelle("kopilot", werte.kopilot, null, eintrag, zustand, false));
    } else {
      const werte = felder[eintrag.snapshot_key];
      const statusArray =
        eintrag.ziel === "fahrwerk"     ? zustand.fahrwerk_ausgefahren :
        eintrag.ziel === "landeklappe"  ? zustand.landeklappen_ausgefahren :
        eintrag.ziel === "bremse"       ? zustand.bremsen_aktiviert : null;
      const naechsterIndex = statusArray ? statusArray.indexOf(false) : null;
      for (let i = 0; i < eintrag.slots; i++) {
        const gesperrt = statusArray !== null && naechsterIndex !== -1 && i !== naechsterIndex;
        if (statusArray) {
          slots.appendChild(feldZelleMitLicht(werte[i], i, eintrag, zustand, gesperrt, statusArray));
        } else {
          slots.appendChild(feldZelle(null, werte[i], i, eintrag, zustand, gesperrt));
        }
      }
    }
    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}

// --- Würfel-Trays + Kaffee ---
function renderWuerfel(besitzer, zustand) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";

  const werte = zustand[`${besitzer}_wuerfel`];
  const frei  = zustand[`${besitzer}_wuerfel_frei`];
  const istAmZug  = zustand.am_zug === besitzer && zustand.status === "laeuft";
  const sichtbar  = diceVisible === besitzer;

  // "Würfel anzeigen"-Button (nur Auge, kompakt): erscheint für den aktiven
  // Spieler (und in Neuwurf Phase 2 auch für den Partner), solange die
  // Würfel noch verborgen sind.
  const zeigeViewBtn = !sichtbar && (
    istAmZug ||
    (neuwurfPhase === 2 && besitzer !== neuwurfInitiatorRolle)
  );
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

    const istAusgewaehlt = sichtbar && ausgewaehlterWuerfel?.besitzer === besitzer && ausgewaehlterWuerfel?.index === i;
    if (istAusgewaehlt) div.classList.add("ausgewaehlt");

    if (sichtbar && frei[i] && istAmZug) {
      div.title = "Klicken zum Auswählen, dann ein Feld im Board anklicken.";
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istAusgewaehlt ? null : { besitzer, index: i };
        kaffeeMenuOffenFuer = null;
        render(zustand);
      });
    }
    wrapper.appendChild(div);

    if (sichtbar && istAusgewaehlt && frei[i] && zustand.kaffeetassen > 0) {
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
            nachAktion(pyToJs(bridge.trinke_kaffee(besitzer, i, d)));
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
function toggleNeuwurfPanel() {
  if (!aktuellerZustand || aktuellerZustand.neuwurf_plaettchen <= 0) return;
  if (neuwurfPhase !== 0) {
    neuwurfPhase = 0;
    neuwurfInitiatorRolle = null;
    neuwurfPhase1Indizes = new Set();
    neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
    render(aktuellerZustand);
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
    hinweis.innerHTML = `<strong>${initiatorName}</strong>: Würfel wählen, die neu geworfen werden.`;
    panel.appendChild(hinweis);

    if (diceVisible !== neuwurfInitiatorRolle) {
      const viewBtn = document.createElement("button");
      viewBtn.className = "view-btn";
      viewBtn.textContent = "👁";
      viewBtn.title = "Würfel anzeigen";
      viewBtn.addEventListener("click", () => { diceVisible = neuwurfInitiatorRolle; render(aktuellerZustand); });
      panel.appendChild(viewBtn);
    } else {
      const gruppe = document.createElement("div");
      gruppe.className = "neuwurf-gruppe";
      const frei  = zustand[`${neuwurfInitiatorRolle}_wuerfel_frei`];
      const werte = zustand[`${neuwurfInitiatorRolle}_wuerfel`];
      let hat = false;
      werte.forEach((wert, i) => {
        if (!frei[i]) return;
        hat = true;
        const lbl = document.createElement("label");
        const cb  = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = neuwurfPhase1Indizes.has(i);
        cb.addEventListener("change", () => {
          if (cb.checked) neuwurfPhase1Indizes.add(i);
          else            neuwurfPhase1Indizes.delete(i);
        });
        lbl.appendChild(cb);
        lbl.append(` ${i + 1}:${wert}`);
        gruppe.appendChild(lbl);
      });
      if (!hat) {
        const s = document.createElement("span");
        s.textContent = "(keine unplatzierten Würfel)";
        gruppe.appendChild(s);
      }
      panel.appendChild(gruppe);

      const ak = document.createElement("div");
      ak.className = "neuwurf-aktionen";

      const weiter = document.createElement("button");
      weiter.textContent = `Weiter → ${partnerName}`;
      weiter.addEventListener("click", () => {
        neuwurfPhase1Indizes = new Set(neuwurfPhase1Indizes);
        neuwurfPhase = 2;
        diceVisible = null;
        render(aktuellerZustand);
      });
      ak.appendChild(weiter);

      const ab = document.createElement("button");
      ab.textContent = "Abbrechen";
      ab.addEventListener("click", () => {
        neuwurfPhase = 0; neuwurfInitiatorRolle = null;
        neuwurfPhase1Indizes = new Set();
        diceVisible = null;
        render(aktuellerZustand);
      });
      ak.appendChild(ab);
      panel.appendChild(ak);
    }
  }

  if (neuwurfPhase === 2) {
    const hinweis = document.createElement("p");
    hinweis.innerHTML = `<strong>${partnerName}</strong>: Würfel wählen, die neu geworfen werden.`;
    panel.appendChild(hinweis);

    if (diceVisible !== partnerRolle) {
      const viewBtn = document.createElement("button");
      viewBtn.className = "view-btn";
      viewBtn.textContent = "👁";
      viewBtn.title = "Würfel anzeigen";
      viewBtn.addEventListener("click", () => { diceVisible = partnerRolle; render(aktuellerZustand); });
      panel.appendChild(viewBtn);
    } else {
      const gruppe = document.createElement("div");
      gruppe.className = "neuwurf-gruppe";
      const frei  = zustand[`${partnerRolle}_wuerfel_frei`];
      const werte = zustand[`${partnerRolle}_wuerfel`];
      let hat = false;
      werte.forEach((wert, i) => {
        if (!frei[i]) return;
        hat = true;
        const lbl = document.createElement("label");
        const cb  = document.createElement("input");
        cb.type = "checkbox";
        cb.checked = neuwurfAuswahl[partnerRolle].has(i);
        cb.addEventListener("change", () => {
          if (cb.checked) neuwurfAuswahl[partnerRolle].add(i);
          else            neuwurfAuswahl[partnerRolle].delete(i);
        });
        lbl.appendChild(cb);
        lbl.append(` ${i + 1}:${wert}`);
        gruppe.appendChild(lbl);
      });
      if (!hat) {
        const s = document.createElement("span");
        s.textContent = "(keine unplatzierten Würfel)";
        gruppe.appendChild(s);
      }
      panel.appendChild(gruppe);

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
        neuwurfPhase = 0;
        neuwurfInitiatorRolle = null;
        neuwurfPhase1Indizes = new Set();
        neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
        diceVisible = null;
        nachAktion(antwort);
      });
      ak.appendChild(neuwerfen);

      const ab = document.createElement("button");
      ab.textContent = "Abbrechen";
      ab.addEventListener("click", () => {
        neuwurfPhase = 0; neuwurfInitiatorRolle = null;
        neuwurfPhase1Indizes = new Set();
        diceVisible = null;
        render(aktuellerZustand);
      });
      ak.appendChild(ab);
      panel.appendChild(ak);
    }
  }
}

function nachAktion(antwort) {
  const ergebnis = antwort.ergebnis;
  setzeMeldung(
    ergebnis.erfolg ? ergebnis.meldung : `Nicht möglich: ${grundText(ergebnis.grund)}`,
    ergebnis.erfolg ? "erfolg" : "fehler"
  );
  diceVisible = null;
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
