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

function setzeMeldung(text, art) {
  const el = document.getElementById("meldung-leiste");
  el.textContent = text || "";
  el.className = art || "";
}

function render(zustand) {
  if (!zustand) return;

  document.getElementById("s-runde").textContent =
    zustand.runde + (zustand.letzte_runde ? " (letzte!)" : "") + (zustand.warteschleife ? " ⟳" : "");
  document.getElementById("s-hoehe").textContent = zustand.hoehe;
  document.getElementById("s-entfernung").textContent = zustand.entfernung;
  document.getElementById("s-fluglage").textContent =
    (zustand.fluglage > 0 ? "+" : "") + zustand.fluglage;
  document.getElementById("s-aero").textContent =
    `${zustand.aerodynamik_blau} / ${zustand.aerodynamik_orange}`;
  document.getElementById("s-brems").textContent = zustand.bremsstaerke;
  document.getElementById("s-kaffee").textContent = `${zustand.kaffeetassen} / 3`;
  document.getElementById("s-neuwurf").textContent = zustand.neuwurf_plaettchen;

  document.getElementById("s-fahrwerk").textContent =
    zustand.fahrwerk_ausgefahren.map(v => v ? "🟢" : "⚪").join(" ");
  document.getElementById("s-klappen").textContent =
    zustand.landeklappen_ausgefahren.map(v => v ? "🟢" : "⚪").join(" ");
  document.getElementById("s-bremsen").textContent =
    zustand.bremsen_aktiviert.map(v => v ? "🟢" : "⚪").join(" ");

  document.getElementById("s-flugzeuge").textContent =
    zustand.flugzeuge.map(n => "✈".repeat(n) || "–").join(" | ");

  renderWuerfel("pilot", zustand);
  renderWuerfel("kopilot", zustand);
  renderZiele("pilot", zustand);
  renderZiele("kopilot", zustand);

  const amZugEl = document.getElementById("am-zug-anzeige");
  const rundenendeBtn = document.getElementById("rundenende-btn");
  if (zustand.status !== "laeuft") {
    amZugEl.innerHTML = `<div class="spiel-ende ${zustand.status}">` +
      (zustand.status === "gewonnen" ? "🎉 Sicher gelandet!" : `💥 Verloren (${zustand.verlust_grund})`) +
      "</div>";
    rundenendeBtn.disabled = true;
  } else {
    amZugEl.textContent = `Am Zug: ${zustand.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"}`;
    rundenendeBtn.disabled = false;
  }
}

function renderWuerfel(besitzer, zustand) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";
  const werte = zustand[`${besitzer}_wuerfel`];
  const frei = zustand[`${besitzer}_wuerfel_frei`];

  werte.forEach((wert, i) => {
    const div = document.createElement("div");
    div.className = "wuerfel" + (frei[i] ? "" : " platziert");
    div.textContent = wert;
    const istAusgewaehlt = ausgewaehlterWuerfel &&
      ausgewaehlterWuerfel.besitzer === besitzer && ausgewaehlterWuerfel.index === i;
    if (istAusgewaehlt) div.classList.add("ausgewaehlt");

    if (frei[i] && zustand.am_zug === besitzer && zustand.status === "laeuft") {
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istAusgewaehlt ? null : { besitzer, index: i };
        render(zustand);
      });
      div.title = "Klicken zum Auswählen, dann ein Ziel wählen.";

      if (istAusgewaehlt && zustand.kaffeetassen > 0) {
        const kaffeeBtn = document.createElement("button");
        kaffeeBtn.textContent = "☕";
        kaffeeBtn.title = "Kaffee einsetzen, um diesen Würfel zu verändern";
        kaffeeBtn.style.marginLeft = "2px";
        kaffeeBtn.addEventListener("click", async (ev) => {
          ev.stopPropagation();
          const delta = window.prompt(
            `Wert um wie viel verändern? (max. ±${zustand.kaffeetassen}, Bereich bleibt 1-6)`, "1");
          if (delta === null) return;
          const d = parseInt(delta, 10);
          if (!Number.isInteger(d) || d === 0) return;
          const antwort = bridge.trinke_kaffee(besitzer, i, d).toJs({ dict_converter: Object.fromEntries });
          nachAktion(antwort);
        });
        container.appendChild(div);
        container.appendChild(kaffeeBtn);
        return;
      }
    }
    container.appendChild(div);
  });
}

// Statisches Layout (siehe backend/bridge.py:feld_layout) - hier nur
// einmal geholt und mit dem Frontend-Text angereichert.
const ZIEL_BESCHRIFTUNG = {
  ruder: "Ruder (Pflicht)",
  triebwerk: "Triebwerke (Pflicht)",
  funk: "Funk",
  fahrwerk: "Fahrwerk",
  landeklappe: "Landeklappe",
  bremse: "Bremse",
  konzentration: "Konzentration (Kaffee)",
};

function renderZiele(besitzer, zustand) {
  const container = document.getElementById(`ziele-${besitzer}`);
  container.innerHTML = "";

  const layout = bridge.feld_layout().toJs({ dict_converter: Object.fromEntries })
    .filter(eintrag => eintrag.zugriff.includes(besitzer));

  const istAmZug = zustand.am_zug === besitzer && zustand.status === "laeuft";
  const aktiverWuerfel = ausgewaehlterWuerfel && ausgewaehlterWuerfel.besitzer === besitzer
    ? ausgewaehlterWuerfel.index : null;

  layout.forEach(eintrag => {
    const slots = eintrag.slots || 1;
    for (let slot = 0; slot < slots; slot++) {
      const btn = document.createElement("button");
      btn.className = "ziel-btn";
      let beschriftung = ZIEL_BESCHRIFTUNG[eintrag.ziel];
      if (eintrag.zahlen) beschriftung += ` [${eintrag.zahlen[slot].join("/")}]`;
      if (eintrag.ziel === "funk" && slots > 1) beschriftung += ` #${slot + 1}`;
      if ((eintrag.ziel === "fahrwerk" || eintrag.ziel === "landeklappe" ||
           eintrag.ziel === "bremse" || eintrag.ziel === "konzentration") && slots > 1) {
        beschriftung += ` #${slot + 1}`;
      }
      btn.textContent = beschriftung;
      btn.disabled = !istAmZug || aktiverWuerfel === null;

      btn.addEventListener("click", () => {
        const index = (eintrag.ziel === "fahrwerk" || eintrag.ziel === "landeklappe" ||
          eintrag.ziel === "bremse" || eintrag.ziel === "konzentration") ? slot : null;
        const funkFeld = eintrag.ziel === "funk" ? slot : 0;
        const antwort = bridge.platziere(
          besitzer, aktiverWuerfel, eintrag.ziel, index, funkFeld
        ).toJs({ dict_converter: Object.fromEntries });
        ausgewaehlterWuerfel = null;
        nachAktion(antwort);
      });
      container.appendChild(btn);
    }
  });
}

function nachAktion(antwort) {
  const ergebnis = antwort.ergebnis;
  if (!ergebnis.erfolg) {
    setzeMeldung(`Nicht möglich: ${ergebnis.grund}`, "fehler");
  } else {
    setzeMeldung(ergebnis.meldung, "erfolg");
  }
  render(antwort.zustand);
}

async function rundenendeKlick() {
  const antwort = bridge.rundenende().toJs({ dict_converter: Object.fromEntries });
  if (!antwort.ergebnis.erfolg) {
    setzeMeldung(`Runde kann noch nicht enden: ${antwort.ergebnis.grund}`, "fehler");
    render(antwort.zustand);
    return;
  }
  setzeMeldung(antwort.ergebnis.meldung, "erfolg");
  render(antwort.zustand);
  if (antwort.zustand.status === "laeuft") {
    const neuerZustand = bridge.wuerfeln_fuer_runde().toJs({ dict_converter: Object.fromEntries });
    render(neuerZustand);
  }
}

async function neuesSpiel() {
  const flughafen = document.getElementById("flughafen-auswahl").value;
  ausgewaehlterWuerfel = null;
  const zustand = bridge.neues_spiel(flughafen).toJs({ dict_converter: Object.fromEntries });
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
  await neuesSpiel();
}

init().catch(err => {
  console.error(err);
  document.getElementById("lade-hinweis").textContent =
    "Fehler beim Laden der Engine: " + err.message;
});
