/*
 * Cockpit - Web-Frontend
 *
 * Lädt die Python-Engine aus engine-src.js (eine gebündelte JS-Datei,
 * die alle Backend-.py-Dateien als Strings enthält) und übergibt sie
 * an Pyodide. Kein ../../-Pfad-Traversal mehr, keine einzelnen .py-
 * Fetch-Anfragen - eine einzige Datei, die immer funktioniert.
 *
 * Nach Änderungen am Backend:  python3 build.py  (aus dem Repo-Root)
 */

let pyodide = null;
let bridge = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuOffenFuer = null;
let neuwurfOffen = false;
let neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
let aktuellerZustand = null;

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


// =========================================================
// AERODYNAMIK
// =========================================================

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


// =========================================================
// BREMSEN
// =========================================================

// Bremsen-Marker-Skala: 0 → "| 2 3 4 5 6", 2 → "2 | 3 4 5 6" …
function bremsSkalaHTML(bs) {
  const teile = [];

  if (bs < 2)
    teile.push('<span class="trenner">|</span>');

  for (let n = 2; n <= 6; n++) {
    teile.push(String(n));

    if (n === bs)
      teile.push('<span class="trenner">|</span>');
  }

  return teile.join(" ");
}


// =========================================================
// FLUGBAHNEN: ENTFERNUNG + HÖHE
// =========================================================

/*
 * Erzeugt die beiden vertikalen Leisten dynamisch.
 *
 * Entfernung:
 *
 *     oben
 *     🛬  Landung / 0 km
 *      1
 *      2
 *      3
 *      ...
 *     aktuelle Entfernung
 *     unten
 *
 * Höhe:
 *
 *     oben
 *     🛬  Landung / 0 ft
 *     1.000
 *     2.000
 *     3.000
 *     ...
 *     aktuelle Höhe
 *     unten
 *
 * Die Anzahl der Tiles hängt somit immer direkt vom
 * aktuellen Spielzustand ab.
 */
function renderFlugbahnLeisten(zustand) {
  renderEntfernungsBalken(zustand);
  renderHoehenBalken(zustand);
}


/*
 * =========================================================
 * ENTFERNUNGSBALKEN
 * =========================================================
 */
function renderEntfernungsBalken(zustand) {
  const balken = document.getElementById("entfernungs-balken");

  if (!balken)
    return;

  balken.innerHTML = "";

  const entfernung = Math.max(0, Number(zustand.entfernung) || 0);

  /*
   * Die Landung ist immer ganz oben.
   */
  const landung = document.createElement("div");
  landung.className = "landungs-tile";
  landung.innerHTML = "<span>🛬</span>";
  landung.title = "Landung";
  balken.appendChild(landung);


  /*
   * Die aktuelle Entfernung beginnt bei 1 und reicht
   * bis zur aktuellen Entfernung.
   *
   * Dadurch ist das unterste Feld immer die aktuell
   * noch zurückzulegende Entfernung.
   */
  const startIndex = Math.max(
    0,
    Number(zustand.laenge) - entfernung
  );

  for (let d = 1; d <= entfernung; d++) {

    const tile = document.createElement("div");
    tile.className = "flug-tile";

    /*
     * Das unterste Feld entspricht der aktuellen Entfernung.
     */
    if (d === entfernung) {
      tile.classList.add("aktuell");
    }

    tile.textContent = d;
    tile.title = `${d} km Entfernung bis zur Landung`;


    /*
     * Die Flugzeuge liegen in zustand.flugzeuge
     * entlang der gesamten Flugstrecke.
     *
     * startIndex beschreibt, welches Element von
     * flugzeuge der aktuellen Position entspricht.
     *
     * d = 1 liegt ein Feld vor der aktuellen Position,
     * d = 2 zwei Felder usw.
     *
     * Das +d-1 sorgt dafür, dass das erste sichtbare
     * Entfernungsfeld dem aktuellen Streckenindex entspricht.
     */
    const flugzeugIndex = startIndex + d - 1;

    let anzahlFlugzeuge = 0;

    if (
      Array.isArray(zustand.flugzeuge) &&
      flugzeugIndex >= 0 &&
      flugzeugIndex < zustand.flugzeuge.length
    ) {
      anzahlFlugzeuge = Number(zustand.flugzeuge[flugzeugIndex]) || 0;
    }


    /*
     * Flugzeuge direkt in das Tile setzen.
     */
    if (anzahlFlugzeuge > 0) {

      const flugzeugeContainer = document.createElement("div");
      flugzeugeContainer.className = "flugzeuge-auf-balken";

      if (anzahlFlugzeuge > 1) {
        flugzeugeContainer.classList.add("mehrere");
      }

      for (let i = 0; i < anzahlFlugzeuge; i++) {

        const flugzeug = document.createElement("span");
        flugzeug.className = "flugzeug-auf-balken";
        flugzeug.textContent = "✈";

        flugzeugeContainer.appendChild(flugzeug);
      }

      tile.appendChild(flugzeugeContainer);
    }

    balken.appendChild(tile);
  }
}


/*
 * =========================================================
 * HÖHENBALKEN
 * =========================================================
 */
function renderHoehenBalken(zustand) {
  const balken = document.getElementById("hoehen-balken");

  if (!balken)
    return;

  balken.innerHTML = "";

  const hoehe = Math.max(0, Number(zustand.hoehe) || 0);

  /*
   * Landung immer ganz oben.
   */
  const landung = document.createElement("div");
  landung.className = "landungs-tile";
  landung.innerHTML = "<span>🛬</span>";
  landung.title = "Landung bei 0 ft";
  balken.appendChild(landung);


  /*
   * Ein Tile pro 1.000 ft.
   *
   * ceil sorgt dafür, dass auch eine Höhe, die nicht
   * exakt durch 1000 teilbar ist, noch vollständig
   * dargestellt wird.
   */
  const maxHoehenTile = Math.ceil(hoehe / 1000);

  for (let i = 1; i <= maxHoehenTile; i++) {

    const hoehenWert = i * 1000;

    const tile = document.createElement("div");
    tile.className = "hoehen-tile";

    /*
     * Das unterste Tile entspricht der aktuellen Höhe.
     */
    if (i === maxHoehenTile) {
      tile.classList.add("aktuell");
    }

    tile.textContent =
      hoehenWert.toLocaleString("de-DE");

    tile.title = `${hoehenWert.toLocaleString("de-DE")} ft`;

    balken.appendChild(tile);
  }
}


// =========================================================
// KAFFEE UND NEUWURF
// =========================================================

function kaffeeBoxenHTML(anzahl) {
  let html = "";

  for (let i = 0; i < 3; i++) {
    const voll = i < anzahl;

    html += `<span class="ressourcen-box${voll ? " gefuellt" : ""}">${voll ? "☕" : ""}</span>`;
  }

  return html;
}

function neuwurfBoxenHTML(anzahl) {
  if (anzahl <= 0)
    return '<span class="ressourcen-box"></span>';

  return Array.from(
    { length: anzahl },
    () => '<span class="ressourcen-box gefuellt">🔄</span>'
  ).join("");
}


// =========================================================
// HAUPT-RENDERING
// =========================================================

function render(zustand) {
  if (!zustand)
    return;

  aktuellerZustand = zustand;

  document.getElementById("s-runde").textContent =
    zustand.runde +
    (zustand.letzte_runde ? " (letzte!)" : "") +
    (zustand.warteschleife ? " ⟳" : "");

  /*
   * Diese beiden Werte bleiben intern erhalten.
   * Die sichtbare Darstellung erfolgt jetzt über
   * die beiden vertikalen Leisten.
   */
  document.getElementById("s-hoehe").textContent =
    zustand.hoehe;

  document.getElementById("s-entfernung").textContent =
    zustand.entfernung;

  document.getElementById("s-fluglage").textContent =
    (zustand.fluglage > 0 ? "+" : "") +
    zustand.fluglage;

  document.getElementById("s-aero").innerHTML =
    aeroSkalaHTML(
      zustand.aerodynamik_blau,
      zustand.aerodynamik_orange
    );

  document.getElementById("s-brems").innerHTML =
    bremsSkalaHTML(zustand.bremsstaerke);

  document.getElementById("s-kaffee").innerHTML =
    kaffeeBoxenHTML(zustand.kaffeetassen);

  document.getElementById("s-neuwurf").innerHTML =
    neuwurfBoxenHTML(zustand.neuwurf_plaettchen);


  document.getElementById("s-fahrwerk").textContent =
    zustand.fahrwerk_ausgefahren
      .map(v => v ? "🟢" : "⚪")
      .join(" ");

  document.getElementById("s-klappen").textContent =
    zustand.landeklappen_ausgefahren
      .map(v => v ? "🟢" : "⚪")
      .join(" ");

  document.getElementById("s-bremsen").textContent =
    zustand.bremsen_aktiviert
      .map(v => v ? "🟢" : "⚪")
      .join(" ");


  /*
   * NEU:
   * Die beiden Flug-/Höhenleisten werden bei jedem
   * Spielzustand komplett neu aufgebaut.
   */
  renderFlugbahnLeisten(zustand);


  renderCockpitBoard(zustand);
  renderWuerfel("pilot", zustand);
  renderWuerfel("kopilot", zustand);
  renderNeuwurfPanel(zustand);


  const amZugEl = document.getElementById("am-zug-anzeige");
  const rundenendeBtn = document.getElementById("rundenende-btn");
  const neuwurfBtn = document.getElementById("neuwurf-btn");

  if (zustand.status !== "laeuft") {

    amZugEl.innerHTML =
      `<div class="spiel-ende ${zustand.status}">` +
      (
        zustand.status === "gewonnen"
          ? "🎉 Sicher gelandet!"
          : `💥 Verloren – ${grundText(zustand.verlust_grund)}`
      ) +
      "</div>";

    rundenendeBtn.disabled = true;
    neuwurfBtn.disabled = true;

  } else {

    amZugEl.textContent =
      `Am Zug: ${zustand.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"}`;

    rundenendeBtn.disabled = false;
    neuwurfBtn.disabled =
      zustand.neuwurf_plaettchen <= 0;
  }
}


// =========================================================
// COCKPIT-BOARD
// =========================================================

// --- Cockpit-Board (zeigt jedes gelegte Feld; Bremsen/Klappen: nur nächstes frei) ---

const ZIEL_BESCHRIFTUNG = {
  ruder: "Ruder",
  triebwerk: "Triebwerke",
  funk: "Funk",
  fahrwerk: "Fahrwerk",
  landeklappe: "Landeklappe",
  bremse: "Bremse",
  konzentration: "Konzentration",
};


function feldZelle(
  fixierterBesitzer,
  wertObjekt,
  slotIndex,
  eintrag,
  zustand,
  gesperrt
) {
  const div = document.createElement("div");
  div.className = "feld-zelle";

  if (wertObjekt) {
    div.classList.add(
      "belegt",
      wertObjekt.besitzer
    );

    div.textContent = wertObjekt.wert;
    return div;
  }

  if (eintrag.zahlen && slotIndex !== null) {
    div.innerHTML =
      `<small>${eintrag.zahlen[slotIndex].join("/")}</small>`;
  }

  if (gesperrt) {
    div.title =
      "Erst die vorherigen Felder in dieser Reihe erledigen.";
    return div;
  }

  const kannHierPlatzieren = fixierterBesitzer
    ? ausgewaehlterWuerfel?.besitzer === fixierterBesitzer
    : ausgewaehlterWuerfel &&
      eintrag.zugriff.includes(
        ausgewaehlterWuerfel.besitzer
      );

  const istKlickbar =
    zustand.status === "laeuft" &&
    ausgewaehlterWuerfel &&
    zustand.am_zug === ausgewaehlterWuerfel.besitzer &&
    kannHierPlatzieren;

  if (istKlickbar) {
    div.classList.add("klickbar");

    div.title =
      "Ausgewählten Würfel hier platzieren";

    div.addEventListener(
      "click",
      () => platziereAusgewaehlten(
        eintrag,
        slotIndex
      )
    );
  }

  return div;
}


function platziereAusgewaehlten(
  eintrag,
  slotIndex
) {
  if (!ausgewaehlterWuerfel)
    return;

  const brauchtIndex = [
    "fahrwerk",
    "landeklappe",
    "bremse",
    "konzentration"
  ].includes(eintrag.ziel);

  const antwort = pyToJs(
    bridge.platziere(
      ausgewaehlterWuerfel.besitzer,
      ausgewaehlterWuerfel.index,
      eintrag.ziel,
      brauchtIndex ? slotIndex : null,
      eintrag.ziel === "funk" ? slotIndex : 0
    )
  );

  ausgewaehlterWuerfel = null;

  nachAktion(antwort);
}


function renderCockpitBoard(zustand) {
  const board =
    document.getElementById("cockpit-board");

  board.innerHTML = "";

  const layout =
    pyToJs(bridge.feld_layout());

  const felder =
    zustand.felder;

  layout.forEach(eintrag => {

    const zeile =
      document.createElement("div");

    zeile.className =
      "feld-zeile";


    const label =
      document.createElement("span");

    label.className =
      "feld-label";

    label.textContent =
      ZIEL_BESCHRIFTUNG[eintrag.ziel] +
      (eintrag.pflicht ? " *" : "");

    zeile.appendChild(label);


    const slots =
      document.createElement("div");

    slots.className =
      "feld-slots";


    if (eintrag.art === "farbpaar") {

      const werte =
        felder[eintrag.snapshot_key];

      slots.appendChild(
        feldZelle(
          "pilot",
          werte.pilot,
          null,
          eintrag,
          zustand,
          false
        )
      );

      slots.appendChild(
        feldZelle(
          "kopilot",
          werte.kopilot,
          null,
          eintrag,
          zustand,
          false
        )
      );

    } else {

      const werte =
        felder[eintrag.snapshot_key];

      const statusArray =
        eintrag.ziel === "landeklappe"
          ? zustand.landeklappen_ausgefahren
          : eintrag.ziel === "bremse"
            ? zustand.bremsen_aktiviert
            : null;

      const naechsterIndex =
        statusArray
          ? statusArray.indexOf(false)
          : null;

      for (
        let i = 0;
        i < eintrag.slots;
        i++
      ) {

        const gesperrt =
          statusArray !== null &&
          naechsterIndex !== -1 &&
          i !== naechsterIndex;

        slots.appendChild(
          feldZelle(
            null,
            werte[i],
            i,
            eintrag,
            zustand,
            gesperrt
          )
        );
      }
    }

    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}


// =========================================================
// WÜRFEL-TRAYS + KAFFEE
// =========================================================

function renderWuerfel(
  besitzer,
  zustand
) {
  const container =
    document.getElementById(
      `wuerfel-${besitzer}`
    );

  container.innerHTML = "";

  const werte =
    zustand[`${besitzer}_wuerfel`];

  const frei =
    zustand[`${besitzer}_wuerfel_frei`];


  werte.forEach((wert, i) => {

    const wrapper =
      document.createElement("div");

    wrapper.className =
      "wuerfel-slot";


    const div =
      document.createElement("div");

    div.className =
      "wuerfel" +
      (frei[i] ? "" : " platziert");

    div.textContent =
      wert;


    const istAusgewaehlt =
      ausgewaehlterWuerfel?.besitzer === besitzer &&
      ausgewaehlterWuerfel?.index === i;

    if (istAusgewaehlt)
      div.classList.add("ausgewaehlt");


    const istAmZug =
      zustand.am_zug === besitzer &&
      zustand.status === "laeuft";


    if (frei[i] && istAmZug) {

      div.title =
        "Klicken zum Auswählen, dann ein Feld im Cockpit-Board anklicken.";

      div.addEventListener(
        "click",
        () => {

          ausgewaehlterWuerfel =
            istAusgewaehlt
              ? null
              : {
                  besitzer,
                  index: i
                };

          kaffeeMenuOffenFuer = null;

          render(zustand);
        }
      );
    }

    wrapper.appendChild(div);


    /*
     * Kaffee
     */
    if (
      istAusgewaehlt &&
      frei[i] &&
      zustand.kaffeetassen > 0
    ) {

      const kaffeeBtn =
        document.createElement("button");

      kaffeeBtn.textContent =
        "☕";

      kaffeeBtn.title =
        "Kaffee einsetzen";


      kaffeeBtn.addEventListener(
        "click",
        ev => {

          ev.stopPropagation();

          const offenFuerDiesen =
            kaffeeMenuOffenFuer?.besitzer === besitzer &&
            kaffeeMenuOffenFuer?.index === i;

          kaffeeMenuOffenFuer =
            offenFuerDiesen
              ? null
              : {
                  besitzer,
                  index: i
                };

          render(zustand);
        }
      );

      wrapper.appendChild(kaffeeBtn);


      if (
        kaffeeMenuOffenFuer?.besitzer === besitzer &&
        kaffeeMenuOffenFuer?.index === i
      ) {

        const deltas =
          bridge
            .moegliche_kaffee_deltas(
              besitzer,
              i
            )
            .toJs();

        const menu =
          document.createElement("div");

        menu.className =
          "kaffee-auswahl";


        deltas.forEach(d => {

          const btn =
            document.createElement("button");

          btn.textContent =
            (d > 0 ? "+" : "") + d;


          btn.addEventListener(
            "click",
            ev => {

              ev.stopPropagation();

              kaffeeMenuOffenFuer = null;

              nachAktion(
                pyToJs(
                  bridge.trinke_kaffee(
                    besitzer,
                    i,
                    d
                  )
                )
              );
            }
          );

          menu.appendChild(btn);
        });

        wrapper.appendChild(menu);
      }
    }

    container.appendChild(wrapper);
  });
}


// =========================================================
// NEUWURF-PANEL
// =========================================================

function toggleNeuwurfPanel() {

  if (
    !aktuellerZustand ||
    aktuellerZustand.neuwurf_plaettchen <= 0
  ) {
    return;
  }

  neuwurfOffen = !neuwurfOffen;

  neuwurfAuswahl = {
    pilot: new Set(),
    kopilot: new Set()
  };

  ausgewaehlterWuerfel = null;

  render(aktuellerZustand);
}


function renderNeuwurfPanel(zustand) {

  const panel =
    document.getElementById(
      "neuwurf-panel"
    );

  panel.innerHTML = "";


  if (
    !neuwurfOffen ||
    zustand.status !== "laeuft"
  ) {
    panel.classList.add("versteckt");
    return;
  }

  panel.classList.remove("versteckt");


  const intro =
    document.createElement("p");

  intro.textContent =
    `Neuwurf-Plättchen einlösen (${zustand.neuwurf_plaettchen} verfügbar): ` +
    "Welche noch nicht platzierten Würfel sollen neu geworfen werden?";

  panel.appendChild(intro);


  ["pilot", "kopilot"].forEach(
    besitzer => {

      const gruppe =
        document.createElement("div");

      gruppe.className =
        "neuwurf-gruppe";


      const titel =
        document.createElement("strong");

      titel.textContent =
        besitzer === "pilot"
          ? "Pilotin:"
          : "Co-Pilot:";

      gruppe.appendChild(titel);


      const frei =
        zustand[
          `${besitzer}_wuerfel_frei`
        ];

      const werte =
        zustand[
          `${besitzer}_wuerfel`
        ];

      let hatFreie = false;


      werte.forEach(
        (wert, i) => {

          if (!frei[i])
            return;

          hatFreie = true;


          const label =
            document.createElement("label");

          const cb =
            document.createElement("input");

          cb.type = "checkbox";

          cb.checked =
            neuwurfAuswahl[
              besitzer
            ].has(i);


          cb.addEventListener(
            "change",
            () => {

              if (cb.checked) {
                neuwurfAuswahl[
                  besitzer
                ].add(i);
              } else {
                neuwurfAuswahl[
                  besitzer
                ].delete(i);
              }
            }
          );


          label.appendChild(cb);

          label.append(
            ` Würfel ${i + 1} (${wert})`
          );

          gruppe.appendChild(label);
        }
      );


      if (!hatFreie) {

        const hinweis =
          document.createElement("span");

        hinweis.textContent =
          "(keine unplatzierten Würfel mehr)";

        gruppe.appendChild(hinweis);
      }

      panel.appendChild(gruppe);
    }
  );


  const aktionen =
    document.createElement("div");

  aktionen.className =
    "neuwurf-aktionen";


  const bestaetigen =
    document.createElement("button");

  bestaetigen.textContent =
    "Neu würfeln ✓";


  bestaetigen.addEventListener(
    "click",
    () => {

      const antwort =
        pyToJs(
          bridge.benutze_neuwurf(
            Array.from(
              neuwurfAuswahl.pilot
            ),
            Array.from(
              neuwurfAuswahl.kopilot
            )
          )
        );

      neuwurfOffen = false;

      nachAktion(antwort);
    }
  );

  aktionen.appendChild(bestaetigen);


  const abbrechen =
    document.createElement("button");

  abbrechen.textContent =
    "Abbrechen";

  abbrechen.addEventListener(
    "click",
    () => {
      neuwurfOffen = false;
      render(zustand);
    }
  );

  aktionen.appendChild(abbrechen);

  panel.appendChild(aktionen);
}


// =========================================================
// AKTIONEN
// =========================================================

function nachAktion(antwort) {

  const ergebnis =
    antwort.ergebnis;

  setzeMeldung(
    ergebnis.erfolg
      ? ergebnis.meldung
      : `Nicht möglich: ${grundText(ergebnis.grund)}`,
    ergebnis.erfolg
      ? "erfolg"
      : "fehler"
  );

  render(antwort.zustand);
}


async function rundenendeKlick() {

  const antwort =
    pyToJs(
      bridge.rundenende()
    );


  if (!antwort.ergebnis.erfolg) {

    setzeMeldung(
      `Runde kann noch nicht enden: ${grundText(antwort.ergebnis.grund)}`,
      "fehler"
    );

    render(antwort.zustand);

    return;
  }


  setzeMeldung(
    antwort.ergebnis.meldung,
    "erfolg"
  );

  render(antwort.zustand);


  if (
    antwort.zustand.status === "laeuft"
  ) {
    render(
      pyToJs(
        bridge.wuerfeln_fuer_runde()
      )
    );
  }
}


async function neuesSpiel() {

  const flughafen =
    document.getElementById(
      "flughafen-auswahl"
    ).value;

  ausgewaehlterWuerfel = null;
  kaffeeMenuOffenFuer = null;
  neuwurfOffen = false;

  const zustand =
    pyToJs(
      bridge.neues_spiel(
        flughafen
      )
    );

  setzeMeldung(
    "Neue Partie gestartet.",
    "erfolg"
  );

  render(zustand);
}


// =========================================================
// INITIALISIERUNG
// =========================================================

async function init() {

  document.getElementById(
    "neues-spiel-btn"
  ).disabled = true;


  try {

    await ladeEngine();

  } catch (err) {

    console.error(err);

    document.getElementById(
      "lade-hinweis"
    ).textContent =
      "Fehler beim Laden der Engine: " +
      err.message;

    return;
  }


  document.getElementById(
    "lade-hinweis"
  ).classList.add("versteckt");

  document.getElementById(
    "spiel-ui"
  ).classList.remove("versteckt");

  document.getElementById(
    "neues-spiel-btn"
  ).disabled = false;


  document.getElementById(
    "neues-spiel-btn"
  ).addEventListener(
    "click",
    neuesSpiel
  );


  document.getElementById(
    "rundenende-btn"
  ).addEventListener(
    "click",
    rundenendeKlick
  );


  document.getElementById(
    "neuwurf-btn"
  ).addEventListener(
    "click",
    toggleNeuwurfPanel
  );


  await neuesSpiel();
}


// Expose for the landing menu
window.startPassAndPlay = init;