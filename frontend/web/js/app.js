/*
 * Cockpit - Web-Frontend (Funktions-Gerüst)
 *
 * Lädt Pyodide, holt sich die ECHTEN Python-Dateien aus backend/ direkt
 * aus dem Repo (per fetch, funktioniert auf GitHub Pages ohne eigenen
 * Server) und ruft darüber dieselbe Spiel-Engine auf, die auch das
 * Terminal-Frontend benutzt. Es gibt also nur EINE Implementierung der
 * Spielregeln (Python) - dieses Skript kümmert sich nur um Anzeige und
 * Klicks.
 *
 * Bewusst noch ohne Feinschliff (Layout/Optik kommt später, siehe
 * README) - aber vollständig spielbar.
 */

const REPO_BASIS = "../../"; // frontend/web/ -> Repo-Wurzel

const PY_DATEIEN = [
  ["backend/__init__.py", "backend/__init__.py"],
  ["backend/regeln.py", "backend/regeln.py"],
  ["backend/wuerfel.py", "backend/wuerfel.py"],
  ["backend/wuerfelfeld.py", "backend/wuerfelfeld.py"],
  ["backend/cockpit.py", "backend/cockpit.py"],
  ["backend/landung.py", "backend/landung.py"],
  ["backend/spielplan.py", "backend/spielplan.py"],
  ["backend/bridge.py", "backend/bridge.py"],
  ["backend/landungen/MUC.yaml", "backend/landungen/MUC.yaml"],
];

let pyodide = null;
let bridge = null;
let ausgewaehlterWuerfel = null; // {besitzer, index}
let kaffeeMenuOffenFuer = null; // {besitzer, index}
let neuwurfOffen = false;
let neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
let aktuellerZustand = null;

async function ladeEngine() {
  pyodide = await loadPyodide();
  await pyodide.loadPackage("pyyaml");

  pyodide.FS.mkdirTree("/skyteam/backend/landungen");
  for (const [quelle, ziel] of PY_DATEIEN) {
    const url = REPO_BASIS + quelle;
    let antwort;
    try {
      antwort = await fetch(url);
    } catch (netzwerkFehler) {
      throw new Error(`Netzwerkfehler beim Laden von ${url}: ${netzwerkFehler.message}`);
    }
    if (!antwort.ok) {
      throw new Error(
        `Konnte ${url} nicht laden (HTTP ${antwort.status}). ` +
        `Aufgerufene Seite: ${window.location.href} - ` +
        "prüfe, ob genau diese URL im Repo existiert (Tippfehler/Groß-Kleinschreibung/" +
        "fehlender Ordner) und ob die Seite über http(s):// läuft, nicht über file://."
      );
    }
    const text = await antwort.text();
    pyodide.FS.writeFile("/skyteam/" + ziel, text);
  }

  pyodide.runPython(`
import sys
sys.path.insert(0, "/skyteam")
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

// ---------------------------------------------------------------------
// Aerodynamik-Skala (Bug #7): "4.5 / 8.5" -> "2 3 4 | 5 6 7 8 | 9 10 11 12"
// ---------------------------------------------------------------------
function aeroSkalaHTML(blau, orange) {
  const bGrenze = Math.floor(blau);
  const oGrenze = Math.floor(orange);
  const teile = [];
  for (let n = 2; n <= 12; n++) {
    teile.push(String(n));
    if ((n === bGrenze || n === oGrenze) && n < 12) teile.push('<span class="trenner">|</span>');
  }
  return teile.join(" ");
}

// ---------------------------------------------------------------------
// Bremsen-Skala (Bug #2): analog zur Aerodynamik-Skala, aber über die
// feste Bremsstärke (0/2/4/6, siehe cockpit.py:bremsstaerke()).
// bremsstaerke < 2  -> "| 2 3 4 5 6"
// bremsstaerke == 2 -> "2 | 3 4 5 6"
// bremsstaerke == 4 -> "2 3 4 | 5 6"
// bremsstaerke == 6 -> "2 3 4 5 6 |"
// ---------------------------------------------------------------------
function bremsSkalaHTML(bremsstaerke) {
  const teile = [];
  if (bremsstaerke < 2) teile.push('<span class="trenner">|</span>');
  for (let n = 2; n <= 6; n++) {
    teile.push(String(n));
    if (n === bremsstaerke) teile.push('<span class="trenner">|</span>');
  }
  return teile.join(" ");
}

// ---------------------------------------------------------------------
// Flugzeuge auf der Entfernungsleiste (Bug #6 der letzten Runde / #6
// hier: Bug-Nummer aus dem Feedback zu Fenster-Ausschnitt): nur der Teil
// der Liste AB der aktuellen Position anzeigen.
// ---------------------------------------------------------------------
function renderFlugzeuge(zustand) {
  const startIndex = Math.max(0, zustand.laenge - zustand.entfernung);
  const sichtbar = zustand.flugzeuge.slice(startIndex);
  const el = document.getElementById("s-flugzeuge");
  el.textContent = sichtbar.length
    ? sichtbar.map(n => (n > 0 ? "✈".repeat(n) : "·")).join(" | ")
    : "(keine Hindernisse mehr voraus)";
}

// ---------------------------------------------------------------------
// Ressourcen als Boxen (Bug #5)
// ---------------------------------------------------------------------
function kaffeeBoxenHTML(anzahl) {
  let html = "";
  for (let i = 0; i < 3; i++) {
    const gefuellt = i < anzahl;
    html += `<span class="ressourcen-box${gefuellt ? " gefuellt" : ""}">${gefuellt ? "☕" : ""}</span>`;
  }
  return html;
}

function neuwurfBoxenHTML(anzahl) {
  if (anzahl <= 0) return '<span class="ressourcen-box"></span>';
  let html = "";
  for (let i = 0; i < anzahl; i++) {
    html += '<span class="ressourcen-box gefuellt">🔄</span>';
  }
  return html;
}

function render(zustand) {
  if (!zustand) return;
  aktuellerZustand = zustand;

  document.getElementById("s-runde").textContent =
    zustand.runde + (zustand.letzte_runde ? " (letzte!)" : "") + (zustand.warteschleife ? " ⟳" : "");
  document.getElementById("s-hoehe").textContent = zustand.hoehe;
  document.getElementById("s-entfernung").textContent = zustand.entfernung;
  document.getElementById("s-fluglage").textContent =
    (zustand.fluglage > 0 ? "+" : "") + zustand.fluglage;
  document.getElementById("s-aero").innerHTML = aeroSkalaHTML(zustand.aerodynamik_blau, zustand.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(zustand.bremsstaerke);
  document.getElementById("s-kaffee").innerHTML = kaffeeBoxenHTML(zustand.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfBoxenHTML(zustand.neuwurf_plaettchen);

  document.getElementById("s-fahrwerk").textContent =
    zustand.fahrwerk_ausgefahren.map(v => v ? "🟢" : "⚪").join(" ");
  document.getElementById("s-klappen").textContent =
    zustand.landeklappen_ausgefahren.map(v => v ? "🟢" : "⚪").join(" ");
  document.getElementById("s-bremsen").textContent =
    zustand.bremsen_aktiviert.map(v => v ? "🟢" : "⚪").join(" ");

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
      (zustand.status === "gewonnen" ? "🎉 Sicher gelandet!" : `💥 Verloren (${grundText(zustand.verlust_grund)})`) +
      "</div>";
    rundenendeBtn.disabled = true;
    neuwurfBtn.disabled = true;
  } else {
    amZugEl.textContent = `Am Zug: ${zustand.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"}`;
    rundenendeBtn.disabled = false;
    neuwurfBtn.disabled = zustand.neuwurf_plaettchen <= 0;
  }
}

// ---------------------------------------------------------------------
// Gemeinsames Cockpit-Board (zeigt jedes gelegte Feld, Wert + Farbe).
// Bug #3: bei Landeklappen/Bremsen (strikte Reihenfolge) wird NUR das
// jeweils nächste fällige Feld als klickbar hervorgehoben.
// ---------------------------------------------------------------------
const ZIEL_BESCHRIFTUNG = {
  ruder: "Ruder",
  triebwerk: "Triebwerke",
  funk: "Funk",
  fahrwerk: "Fahrwerk",
  landeklappe: "Landeklappe",
  bremse: "Bremse",
  konzentration: "Konzentration",
};

function feldZelle(fixierterBesitzer, wertObjekt, slotIndex, eintrag, zustand, gesperrt) {
  const div = document.createElement("div");
  div.className = "feld-zelle";

  if (wertObjekt) {
    div.classList.add("belegt", wertObjekt.besitzer);
    div.textContent = wertObjekt.wert;
    return div;
  }

  if (eintrag.zahlen && slotIndex !== null) {
    div.innerHTML = `<small>${eintrag.zahlen[slotIndex].join("/")}</small>`;
  }

  if (gesperrt) {
    div.title = "Erst die vorherigen Felder in dieser Reihe erledigen.";
    return div;
  }

  const kannHierPlatzieren = fixierterBesitzer
    ? ausgewaehlterWuerfel && ausgewaehlterWuerfel.besitzer === fixierterBesitzer
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

function platziereAusgewaehlten(eintrag, slotIndex) {
  if (!ausgewaehlterWuerfel) return;
  const brauchtIndex = ["fahrwerk", "landeklappe", "bremse", "konzentration"].includes(eintrag.ziel);
  const index = brauchtIndex ? slotIndex : null;
  const funkFeld = eintrag.ziel === "funk" ? slotIndex : 0;
  const antwort = pyToJs(bridge.platziere(
    ausgewaehlterWuerfel.besitzer, ausgewaehlterWuerfel.index, eintrag.ziel, index, funkFeld
  ));
  ausgewaehlterWuerfel = null;
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

    const slots = document.createElement("div");
    slots.className = "feld-slots";

    if (eintrag.art === "farbpaar") {
      const werte = felder[eintrag.snapshot_key];
      slots.appendChild(feldZelle("pilot", werte.pilot, null, eintrag, zustand, false));
      slots.appendChild(feldZelle("kopilot", werte.kopilot, null, eintrag, zustand, false));
    } else {
      const werte = felder[eintrag.snapshot_key];
      // Bug #3: Landeklappen/Bremsen erfordern strikte Reihenfolge -
      // nur das jeweils naechste noch offene Feld darf hervorgehoben werden.
      const statusArray = eintrag.ziel === "landeklappe" ? zustand.landeklappen_ausgefahren
        : eintrag.ziel === "bremse" ? zustand.bremsen_aktiviert
        : null;
      const naechsterIndex = statusArray ? statusArray.indexOf(false) : null;
      for (let i = 0; i < eintrag.slots; i++) {
        const gesperrt = statusArray !== null && naechsterIndex !== -1 && i !== naechsterIndex;
        slots.appendChild(feldZelle(null, werte[i], i, eintrag, zustand, gesperrt));
      }
    }
    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}

// ---------------------------------------------------------------------
// Würfel-Trays + Kaffee (Delta-Buttons statt Texteingabe)
// ---------------------------------------------------------------------
function renderWuerfel(besitzer, zustand) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";
  const werte = zustand[`${besitzer}_wuerfel`];
  const frei = zustand[`${besitzer}_wuerfel_frei`];

  werte.forEach((wert, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "wuerfel-slot";

    const div = document.createElement("div");
    div.className = "wuerfel" + (frei[i] ? "" : " platziert");
    div.textContent = wert;
    const istAusgewaehlt = ausgewaehlterWuerfel &&
      ausgewaehlterWuerfel.besitzer === besitzer && ausgewaehlterWuerfel.index === i;
    if (istAusgewaehlt) div.classList.add("ausgewaehlt");

    const istAmZug = zustand.am_zug === besitzer && zustand.status === "laeuft";
    if (frei[i] && istAmZug) {
      div.title = "Klicken zum Auswählen, dann ein Feld im Cockpit-Board anklicken.";
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istAusgewaehlt ? null : { besitzer, index: i };
        kaffeeMenuOffenFuer = null;
        render(zustand);
      });
    }
    wrapper.appendChild(div);

    if (istAusgewaehlt && frei[i] && zustand.kaffeetassen > 0) {
      const kaffeeBtn = document.createElement("button");
      kaffeeBtn.textContent = "☕";
      kaffeeBtn.title = "Kaffee einsetzen, um diesen Würfel zu verändern";
      kaffeeBtn.addEventListener("click", (ev) => {
        ev.stopPropagation();
        const offenFuerDiesen = kaffeeMenuOffenFuer &&
          kaffeeMenuOffenFuer.besitzer === besitzer && kaffeeMenuOffenFuer.index === i;
        kaffeeMenuOffenFuer = offenFuerDiesen ? null : { besitzer, index: i };
        render(zustand);
      });
      wrapper.appendChild(kaffeeBtn);

      if (kaffeeMenuOffenFuer && kaffeeMenuOffenFuer.besitzer === besitzer && kaffeeMenuOffenFuer.index === i) {
        const deltas = bridge.moegliche_kaffee_deltas(besitzer, i).toJs();
        const menu = document.createElement("div");
        menu.className = "kaffee-auswahl";
        deltas.forEach(d => {
          const btn = document.createElement("button");
          btn.textContent = (d > 0 ? "+" : "") + d;
          btn.addEventListener("click", (ev) => {
            ev.stopPropagation();
            kaffeeMenuOffenFuer = null;
            const antwort = pyToJs(bridge.trinke_kaffee(besitzer, i, d));
            nachAktion(antwort);
          });
          menu.appendChild(btn);
        });
        wrapper.appendChild(menu);
      }
    }

    container.appendChild(wrapper);
  });
}

// ---------------------------------------------------------------------
// Neuwurf-Panel (Bug #4): pro Spieler auswählen, welche NOCH NICHT
// platzierten Würfel neu geworfen werden sollen, dann bestätigen.
// ---------------------------------------------------------------------
function toggleNeuwurfPanel() {
  if (!aktuellerZustand || aktuellerZustand.neuwurf_plaettchen <= 0) return;
  neuwurfOffen = !neuwurfOffen;
  neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
  ausgewaehlterWuerfel = null;
  render(aktuellerZustand);
}

function renderNeuwurfPanel(zustand) {
  const panel = document.getElementById("neuwurf-panel");
  panel.innerHTML = "";

  if (!neuwurfOffen || zustand.status !== "laeuft") {
    panel.classList.add("versteckt");
    return;
  }
  panel.classList.remove("versteckt");

  const intro = document.createElement("p");
  intro.textContent = `Neuwurf-Plättchen einlösen (${zustand.neuwurf_plaettchen} verfügbar): ` +
    "wählt aus, welche noch nicht platzierten Würfel neu geworfen werden sollen, dann bestätigen.";
  panel.appendChild(intro);

  ["pilot", "kopilot"].forEach(besitzer => {
    const gruppe = document.createElement("div");
    gruppe.className = "neuwurf-gruppe";
    const titel = document.createElement("strong");
    titel.textContent = besitzer === "pilot" ? "Pilotin:" : "Co-Pilot:";
    gruppe.appendChild(titel);

    const frei = zustand[`${besitzer}_wuerfel_frei`];
    const werte = zustand[`${besitzer}_wuerfel`];
    let hatFreie = false;
    werte.forEach((wert, i) => {
      if (!frei[i]) return;
      hatFreie = true;
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = neuwurfAuswahl[besitzer].has(i);
      cb.addEventListener("change", () => {
        if (cb.checked) neuwurfAuswahl[besitzer].add(i);
        else neuwurfAuswahl[besitzer].delete(i);
      });
      label.appendChild(cb);
      label.append(` ${wert}`);
      gruppe.appendChild(label);
    });
    if (!hatFreie) {
      const hinweis = document.createElement("span");
      hinweis.textContent = "(keine unplatzierten Würfel mehr)";
      gruppe.appendChild(hinweis);
    }
    panel.appendChild(gruppe);
  });

  const aktionen = document.createElement("div");
  aktionen.className = "neuwurf-aktionen";

  const bestaetigen = document.createElement("button");
  bestaetigen.textContent = "Neu würfeln";
  bestaetigen.addEventListener("click", () => {
    const antwort = pyToJs(bridge.benutze_neuwurf(
      Array.from(neuwurfAuswahl.pilot), Array.from(neuwurfAuswahl.kopilot)
    ));
    neuwurfOffen = false;
    nachAktion(antwort);
  });
  aktionen.appendChild(bestaetigen);

  const abbrechen = document.createElement("button");
  abbrechen.textContent = "Abbrechen";
  abbrechen.addEventListener("click", () => {
    neuwurfOffen = false;
    render(zustand);
  });
  aktionen.appendChild(abbrechen);

  panel.appendChild(aktionen);
}

function nachAktion(antwort) {
  const ergebnis = antwort.ergebnis;
  if (!ergebnis.erfolg) {
    setzeMeldung(`Nicht möglich: ${grundText(ergebnis.grund)}`, "fehler");
  } else {
    setzeMeldung(ergebnis.meldung, "erfolg");
  }
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
  render(antwort.zustand);
  if (antwort.zustand.status === "laeuft") {
    const neuerZustand = pyToJs(bridge.wuerfeln_fuer_runde());
    render(neuerZustand);
  }
}

async function neuesSpiel() {
  const flughafen = document.getElementById("flughafen-auswahl").value;
  ausgewaehlterWuerfel = null;
  kaffeeMenuOffenFuer = null;
  neuwurfOffen = false;
  const zustand = pyToJs(bridge.neues_spiel(flughafen));
  setzeMeldung("Neue Partie gestartet.", "erfolg");
  render(zustand);
}

async function init() {
  document.getElementById("neues-spiel-btn").disabled = true;
  await ladeEngine();
  document.getElementById("lade-hinweis").classList.add("versteckt");
  document.getElementById("spiel-ui").classList.remove("versteckt");
  document.getElementById("neues-spiel-btn").disabled = false;
  document.getElementById("neues-spiel-btn").addEventListener("click", neuesSpiel);
  document.getElementById("rundenende-btn").addEventListener("click", rundenendeKlick);
  document.getElementById("neuwurf-btn").addEventListener("click", toggleNeuwurfPanel);
  await neuesSpiel();
}

init().catch(err => {
  console.error(err);
  document.getElementById("lade-hinweis").textContent =
    "Fehler beim Laden der Engine: " + err.message;
});
