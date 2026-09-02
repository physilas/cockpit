/*
 * Cockpit – Multiplayer Client
 *
 * Verbindet sich über WebSocket mit server.py.
 * Hosting-Flow: Spieler 1 klickt "Hosten" → QR-Code erscheint.
 * Join-Flow:    Spieler 2 klickt "Beitreten" → Kamera öffnet sich → QR scannen.
 *              Oder: Spieler 2 scannt QR mit nativer Kamera-App → URL öffnet sich.
 */

const WS_PORT = 8765;

// --- Grund-Text-Map (entspricht backend/regeln.py:GRUND_TEXT) ---
const GRUND_TEXT_MAP = {
  trudeln:                        "Trudeln",
  kollision:                      "Kollision",
  uebers_ziel_hinaus:             "Übers Ziel hinaus",
  zu_schnell_gelandet:            "Zu schnell gelandet",
  notlandung:                     "Notlandung",
  pflichtfelder_nicht_erfuellt:   "Pflichtfelder nicht erfüllt",
  flugzeuge_uebrig:               "Flugzeuge übrig",
  fahrwerk_unvollstaendig:        "Fahrwerk unvollständig",
  landeklappen_unvollstaendig:    "Landeklappen unvollständig",
  nicht_waagerecht:               "Nicht waagerecht",
  feld_ungueltig:                 "Feld ungültig",
  falsche_reihenfolge:            "Falsche Reihenfolge",
  nicht_genug_kaffee:             "Nicht genug Kaffee",
  kein_neuwurf_plaettchen:        "Kein Neuwurf-Plättchen verfügbar",
  noch_nicht_alle_wuerfel_platziert: "Noch nicht alle Würfel platziert",
  nicht_am_zug:                   "Nicht am Zug",
};
function grundText(code) {
  if (!code) return "";
  return code.split(",").map(c => GRUND_TEXT_MAP[c.trim()] || c).join(", ");
}

// --- Statisches Feld-Layout (entspricht backend/bridge.py:feld_layout()) ---
const FELD_LAYOUT = [
  { ziel:"ruder",       snapshot_key:"ruder",      zugriff:["pilot","kopilot"], pflicht:true, art:"farbpaar" },
  { ziel:"triebwerk",   snapshot_key:"triebwerk",   zugriff:["pilot","kopilot"], pflicht:true, art:"farbpaar" },
  { ziel:"funk",        snapshot_key:"funk_pilot",  zugriff:["pilot"],   slots:1 },
  { ziel:"funk",        snapshot_key:"funk_kopilot",zugriff:["kopilot"], slots:2 },
  { ziel:"fahrwerk",    snapshot_key:"fahrwerk",    zugriff:["pilot"],   slots:3, zahlen:[[1,2],[3,4],[5,6]] },
  { ziel:"landeklappe", snapshot_key:"landeklappe", zugriff:["kopilot"], slots:4, zahlen:[[1,2],[2,3],[4,5],[5,6]] },
  { ziel:"bremse",      snapshot_key:"bremse",      zugriff:["pilot"],   slots:3, zahlen:[[2],[4],[6]] },
  { ziel:"konzentration",snapshot_key:"konzentration",zugriff:["pilot","kopilot"],slots:3 },
];

const ZIEL_BESCHRIFTUNG = {
  ruder:"Ruder", triebwerk:"Triebwerke", funk:"Funk",
  fahrwerk:"Fahrwerk", landeklappe:"Landeklappe",
  bremse:"Bremse", konzentration:"Konzentration",
};

// --- Zustand ---
let ws = null;
let meineRolle = null;
let aktuellerZustand = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuOffenFuer = null;
let neuwurfOffen = false;
let neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
let qrScanner = null;

// ============================================================
// WebSocket
// ============================================================
function wsUrl(host) {
  return `ws://${host}:${WS_PORT}`;
}

function joinUrl(host) {
  const base = `${window.location.protocol}//${window.location.hostname}:${window.location.port}`;
  return `${base}/frontend/web/multiplayer.html?join=ws://${host}:${WS_PORT}`;
}

function verbinde(rolle, url) {
  setStatus("Verbinde …", "");
  ws = new WebSocket(url);

  ws.onopen = () => {
    ws.send(JSON.stringify({ typ: "rolle_anmelden", rolle }));
    setStatus("Verbunden ✓", "verbunden");
  };

  ws.onmessage = ({ data }) => {
    let msg;
    try { msg = JSON.parse(data); } catch { return; }

    if (msg.typ === "rolle") {
      meineRolle = msg.rolle;
      document.getElementById("meine-rolle-badge").textContent =
        meineRolle === "pilot" ? "Pilotin" : "Co-Pilot";
      document.getElementById("meine-rolle-badge").className =
        `meine-rolle-badge ${meineRolle}`;
      document.getElementById("verbindungs-screen").classList.add("versteckt");
      document.getElementById("spiel-header").classList.remove("versteckt");
      document.getElementById("spiel-ui").classList.remove("versteckt");
    }

    if (msg.typ === "zustand" && msg.zustand) {
      aktuellerZustand = msg.zustand;
      render(msg.zustand);
    }

    if (msg.typ === "ergebnis") {
      setzeMeldung(
        msg.erfolg ? msg.meldung : `Nicht möglich: ${msg.grund || msg.meldung}`,
        msg.erfolg ? "erfolg" : "fehler"
      );
    }

    if (msg.typ === "fehler") {
      setzeMeldung(msg.meldung, "fehler");
    }
  };

  ws.onerror = () => setStatus("Verbindungsfehler – läuft server.py?", "fehler");
  ws.onclose = () => {
    setStatus("Verbindung getrennt", "fehler");
    setzeMeldung("Verbindung zum Server verloren. Bitte Seite neu laden.", "fehler");
  };
}

function sende(daten) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(daten));
}

// ============================================================
// Hosting-Screen (QR-Code generieren)
// ============================================================
function starteHosting() {
  const host = window.location.hostname;
  const url  = wsUrl(host);

  // Als Pilot verbinden
  verbinde("pilot", url);

  // QR-Code für den Kopiloten generieren
  const qrTarget = document.getElementById("qr-container");
  qrTarget.innerHTML = "";
  document.getElementById("hosting-screen").classList.remove("versteckt");
  document.getElementById("landing-screen").classList.add("versteckt");

  const joinLink = joinUrl(host);
  document.getElementById("join-link-text").textContent = joinLink;

  if (window.QRCode) {
    new QRCode(qrTarget, {
      text: joinLink,
      width: 220,
      height: 220,
      colorDark: "#e2e8f0",
      colorLight: "#1e293b",
    });
  } else {
    qrTarget.textContent = "QR-Code-Bibliothek nicht geladen.";
  }
}

// ============================================================
// Scan-Screen (Kamera-QR-Scanner)
// ============================================================
function starteScan() {
  document.getElementById("landing-screen").classList.add("versteckt");
  document.getElementById("scan-screen").classList.remove("versteckt");

  if (!window.Html5Qrcode) {
    document.getElementById("scan-status").textContent =
      "Scanner-Bibliothek nicht geladen. Bitte QR-Code-URL manuell eingeben.";
    return;
  }

  qrScanner = new Html5Qrcode("qr-reader");
  qrScanner.start(
    { facingMode: "environment" },
    { fps: 10, qrbox: { width: 220, height: 220 } },
    (decodedText) => {
      qrScanner.stop().catch(() => {});
      verarbeiteGescannteUrl(decodedText);
    },
    () => {}   // Fehler ignorieren (kein QR gefunden ist normal)
  ).catch(err => {
    document.getElementById("scan-status").textContent =
      "Kamera konnte nicht geöffnet werden: " + err;
  });
}

function verarbeiteGescannteUrl(url) {
  try {
    const params = new URLSearchParams(new URL(url).search);
    const wsAddr = params.get("join");
    if (!wsAddr) throw new Error("Kein 'join'-Parameter in der URL.");
    document.getElementById("scan-screen").classList.add("versteckt");
    verbinde("kopilot", wsAddr);
  } catch (e) {
    document.getElementById("scan-status").textContent = "Ungültiger QR-Code: " + e.message;
  }
}

// ============================================================
// Skalen (identisch mit app.js)
// ============================================================
function aeroSkalaHTML(blau, orange) {
  const bG = Math.floor(blau), oG = Math.floor(orange);
  const t = [];
  for (let n = 2; n <= 12; n++) {
    t.push(String(n));
    if ((n === bG || n === oG) && n < 12) t.push('<span class="trenner">|</span>');
  }
  return t.join(" ");
}

function bremsSkalaHTML(bs) {
  const t = [];
  if (bs < 2) t.push('<span class="trenner">|</span>');
  for (let n = 2; n <= 6; n++) {
    t.push(String(n));
    if (n === bs) t.push('<span class="trenner">|</span>');
  }
  return t.join(" ");
}

function kaffeeBoxenHTML(n) {
  let h = "";
  for (let i = 0; i < 3; i++)
    h += `<span class="ressourcen-box${i < n ? " gefuellt" : ""}">${i < n ? "☕" : ""}</span>`;
  return h;
}

function neuwurfBoxenHTML(n) {
  if (!n) return '<span class="ressourcen-box"></span>';
  return Array.from({length:n}, () => '<span class="ressourcen-box gefuellt">🔄</span>').join("");
}

// ============================================================
// Hauptrender
// ============================================================
function render(z) {
  aktuellerZustand = z;

  document.getElementById("s-runde").textContent =
    z.runde + (z.letzte_runde ? " (letzte!)" : "") + (z.warteschleife ? " ⟳" : "");
  document.getElementById("s-hoehe").textContent = z.hoehe;
  document.getElementById("s-entfernung").textContent = z.entfernung;
  document.getElementById("s-fluglage").textContent = (z.fluglage > 0 ? "+" : "") + z.fluglage;
  document.getElementById("s-aero").innerHTML  = aeroSkalaHTML(z.aerodynamik_blau, z.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(z.bremsstaerke);
  document.getElementById("s-kaffee").innerHTML  = kaffeeBoxenHTML(z.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfBoxenHTML(z.neuwurf_plaettchen);

  document.getElementById("s-fahrwerk").textContent = z.fahrwerk_ausgefahren.map(v => v?"🟢":"⚪").join(" ");
  document.getElementById("s-klappen").textContent  = z.landeklappen_ausgefahren.map(v => v?"🟢":"⚪").join(" ");
  document.getElementById("s-bremsen").textContent  = z.bremsen_aktiviert.map(v => v?"🟢":"⚪").join(" ");

  // Flugzeuge (nur ab aktueller Position)
  const si = Math.max(0, z.laenge - z.entfernung);
  document.getElementById("s-flugzeuge").textContent =
    z.flugzeuge.slice(si).map(n => n > 0 ? "✈".repeat(n) : "·").join(" | ") || "(frei)";

  renderCockpitBoard(z);
  renderWuerfel("pilot", z);
  renderWuerfel("kopilot", z);
  renderNeuwurfPanel(z);

  const amZugEl = document.getElementById("am-zug-anzeige");
  const rBtn    = document.getElementById("rundenende-btn");
  const nBtn    = document.getElementById("neuwurf-btn");

  if (z.status !== "laeuft") {
    amZugEl.innerHTML = `<div class="spiel-ende ${z.status}">` +
      (z.status === "gewonnen" ? "🎉 Sicher gelandet!" : `💥 Verloren – ${grundText(z.verlust_grund)}`) +
      "</div>";
    rBtn.disabled = nBtn.disabled = true;
  } else {
    const ichBinDran = meineRolle && z.am_zug === meineRolle;
    amZugEl.textContent = z.am_zug === meineRolle
      ? "Du bist am Zug ✦"
      : `${z.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"} ist am Zug …`;
    amZugEl.style.color = ichBinDran ? "var(--gruen)" : "var(--muted)";
    rBtn.disabled = !ichBinDran;
    nBtn.disabled = z.neuwurf_plaettchen <= 0;
  }
}

// ============================================================
// Cockpit-Board (identisch mit app.js, aber ohne Pyodide)
// ============================================================
function feldZelle(fixierterBesitzer, wertObjekt, slotIndex, eintrag, z, gesperrt) {
  const div = document.createElement("div");
  div.className = "feld-zelle";

  if (wertObjekt) {
    div.classList.add("belegt", wertObjekt.besitzer);
    div.textContent = wertObjekt.wert;
    return div;
  }
  if (eintrag.zahlen && slotIndex !== null)
    div.innerHTML = `<small>${eintrag.zahlen[slotIndex].join("/")}</small>`;

  if (gesperrt) { div.title = "Reihenfolge beachten."; return div; }

  const ichBinDran = meineRolle && z.am_zug === meineRolle && z.status === "laeuft";
  const kannHier = fixierterBesitzer
    ? ausgewaehlterWuerfel?.besitzer === fixierterBesitzer
    : ausgewaehlterWuerfel && eintrag.zugriff.includes(ausgewaehlterWuerfel.besitzer);

  if (ichBinDran && ausgewaehlterWuerfel && kannHier) {
    div.classList.add("klickbar");
    div.title = "Ausgewählten Würfel hier platzieren";
    div.addEventListener("click", () => platziereAusgewaehlten(eintrag, slotIndex));
  }
  return div;
}

function renderCockpitBoard(z) {
  const board = document.getElementById("cockpit-board");
  board.innerHTML = "";

  FELD_LAYOUT.forEach(e => {
    const zeile = document.createElement("div");
    zeile.className = "feld-zeile";

    const label = document.createElement("span");
    label.className = "feld-label";
    label.textContent = ZIEL_BESCHRIFTUNG[e.ziel] + (e.pflicht ? " *" : "");
    zeile.appendChild(label);

    const slots = document.createElement("div");
    slots.className = "feld-slots";

    const felder = z.felder || {};

    if (e.art === "farbpaar") {
      const w = felder[e.snapshot_key] || {};
      slots.appendChild(feldZelle("pilot",   w.pilot,   null, e, z, false));
      slots.appendChild(feldZelle("kopilot", w.kopilot, null, e, z, false));
    } else {
      const werte = felder[e.snapshot_key] || Array(e.slots).fill(null);
      const statusArr =
        e.ziel === "landeklappe" ? z.landeklappen_ausgefahren :
        e.ziel === "bremse"      ? z.bremsen_aktiviert : null;
      const naechster = statusArr ? statusArr.indexOf(false) : null;
      for (let i = 0; i < e.slots; i++) {
        const gesperrt = statusArr !== null && naechster !== -1 && i !== naechster;
        slots.appendChild(feldZelle(null, werte[i], i, e, z, gesperrt));
      }
    }
    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}

// ============================================================
// Würfel-Trays (Partner-Würfel als "?" wenn noch nicht gespielt)
// ============================================================
function renderWuerfel(besitzer, z) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";
  const werte = z[`${besitzer}_wuerfel`];
  const frei  = z[`${besitzer}_wuerfel_frei`];
  const istMeins = besitzer === meineRolle;

  werte.forEach((wert, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "wuerfel-slot";

    const div = document.createElement("div");
    const istPlatziert = !frei[i];
    const verborgen    = wert === null; // vom Server versteckt (Partnerwürfel)

    div.className = "wuerfel" + (istPlatziert || verborgen ? " platziert" : "");
    if (verborgen) div.classList.add("partner-wuerfel");
    div.textContent = verborgen ? "?" : String(wert);

    const istAusgewaehlt = ausgewaehlterWuerfel?.besitzer === besitzer && ausgewaehlterWuerfel?.index === i;
    if (istAusgewaehlt) div.classList.add("ausgewaehlt");

    const ichBinDran = meineRolle && z.am_zug === meineRolle && z.status === "laeuft";
    if (istMeins && frei[i] && !verborgen && ichBinDran) {
      div.title = "Klicken zum Auswählen.";
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istAusgewaehlt ? null : { besitzer, index: i };
        kaffeeMenuOffenFuer = null;
        render(z);
      });
    }
    wrapper.appendChild(div);

    // Kaffee-Buttons (nur eigene, verfügbare Würfel)
    if (istMeins && istAusgewaehlt && frei[i] && z.kaffeetassen > 0) {
      const kBtn = document.createElement("button");
      kBtn.textContent = "☕";
      kBtn.title = "Kaffee einsetzen";
      kBtn.addEventListener("click", ev => {
        ev.stopPropagation();
        const offen = kaffeeMenuOffenFuer?.besitzer === besitzer && kaffeeMenuOffenFuer?.index === i;
        kaffeeMenuOffenFuer = offen ? null : { besitzer, index: i };
        render(z);
      });
      wrapper.appendChild(kBtn);

      if (kaffeeMenuOffenFuer?.besitzer === besitzer && kaffeeMenuOffenFuer?.index === i) {
        const deltas = moeglicheKaffeeDeltas(wert, z.kaffeetassen);
        const menu = document.createElement("div");
        menu.className = "kaffee-auswahl";
        deltas.forEach(d => {
          const b = document.createElement("button");
          b.textContent = (d > 0 ? "+" : "") + d;
          b.addEventListener("click", ev => {
            ev.stopPropagation();
            kaffeeMenuOffenFuer = null;
            sende({ typ: "trinke_kaffee", wuerfel_index: i, delta: d });
          });
          menu.appendChild(b);
        });
        wrapper.appendChild(menu);
      }
    }
    container.appendChild(wrapper);
  });
}

function moeglicheKaffeeDeltas(augenzahl, tassen) {
  const d = [];
  for (let delta = -tassen; delta <= tassen; delta++) {
    if (delta !== 0 && augenzahl + delta >= 1 && augenzahl + delta <= 6)
      d.push(delta);
  }
  return d;
}

// ============================================================
// Neuwurf-Panel
// ============================================================
function renderNeuwurfPanel(z) {
  const panel = document.getElementById("neuwurf-panel");
  panel.innerHTML = "";
  if (!neuwurfOffen || z.status !== "laeuft") { panel.classList.add("versteckt"); return; }
  panel.classList.remove("versteckt");

  const intro = document.createElement("p");
  intro.textContent = `Neuwurf einlösen (${z.neuwurf_plaettchen} Plättchen): welche nicht platzierten Würfel neu werfen?`;
  panel.appendChild(intro);

  ["pilot", "kopilot"].forEach(b => {
    const g = document.createElement("div");
    g.className = "neuwurf-gruppe";
    const t = document.createElement("strong");
    t.textContent = b === "pilot" ? "Pilotin:" : "Co-Pilot:";
    g.appendChild(t);
    const frei = z[`${b}_wuerfel_frei`];
    const werte = z[`${b}_wuerfel`];
    let hatFreie = false;
    werte.forEach((wert, i) => {
      if (!frei[i] || wert === null) return;
      hatFreie = true;
      const label = document.createElement("label");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = neuwurfAuswahl[b].has(i);
      cb.addEventListener("change", () => {
        if (cb.checked) neuwurfAuswahl[b].add(i); else neuwurfAuswahl[b].delete(i);
      });
      label.appendChild(cb);
      label.append(` Würfel ${i+1} (${wert})`);
      g.appendChild(label);
    });
    if (!hatFreie) { const s = document.createElement("span"); s.textContent = "(keine)"; g.appendChild(s); }
    panel.appendChild(g);
  });

  const aktionen = document.createElement("div");
  aktionen.className = "neuwurf-aktionen";

  const ok = document.createElement("button");
  ok.textContent = "Neu würfeln ✓";
  ok.addEventListener("click", () => {
    sende({ typ: "benutze_neuwurf",
      pilot_indizes:   Array.from(neuwurfAuswahl.pilot),
      kopilot_indizes: Array.from(neuwurfAuswahl.kopilot) });
    neuwurfOffen = false;
    neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
  });
  aktionen.appendChild(ok);

  const ab = document.createElement("button");
  ab.textContent = "Abbrechen";
  ab.addEventListener("click", () => { neuwurfOffen = false; render(aktuellerZustand); });
  aktionen.appendChild(ab);
  panel.appendChild(aktionen);
}

// ============================================================
// Aktionen
// ============================================================
function platziereAusgewaehlten(eintrag, slotIndex) {
  if (!ausgewaehlterWuerfel) return;
  const brauchtIndex = ["fahrwerk","landeklappe","bremse","konzentration"].includes(eintrag.ziel);
  sende({
    typ: "platziere",
    wuerfel_index: ausgewaehlterWuerfel.index,
    ziel: eintrag.ziel,
    index: brauchtIndex ? slotIndex : null,
    funk_feld: eintrag.ziel === "funk" ? slotIndex : 0,
  });
  ausgewaehlterWuerfel = null;
}

// ============================================================
// UI-Hilfsfunktionen
// ============================================================
function setStatus(text, cls) {
  const el = document.getElementById("ws-status");
  if (el) { el.textContent = text; el.className = cls; }
}

function setzeMeldung(text, art) {
  const el = document.getElementById("meldung-leiste");
  if (el) { el.textContent = text || ""; el.className = art || ""; }
}

// ============================================================
// Init
// ============================================================
window.addEventListener("DOMContentLoaded", () => {
  // Auto-join wenn ?join=... in der URL
  const params = new URLSearchParams(window.location.search);
  const joinParam = params.get("join");
  if (joinParam) {
    document.getElementById("landing-screen").classList.add("versteckt");
    document.getElementById("verbindungs-screen").classList.remove("versteckt");
    setStatus("Verbinde als Co-Pilot …", "");
    verbinde("kopilot", joinParam);
    return;
  }

  // Buttons verdrahten
  document.getElementById("btn-hosten").addEventListener("click", starteHosting);
  document.getElementById("btn-beitreten").addEventListener("click", starteScan);
  document.getElementById("btn-manuell").addEventListener("click", () => {
    const ip = prompt("IP-Adresse des Host-Geräts (z.B. 192.168.1.5):");
    if (ip) verbinde("kopilot", `ws://${ip.trim()}:${WS_PORT}`);
  });
  document.getElementById("neues-spiel-btn")?.addEventListener("click", () => {
    sende({ typ: "neues_spiel" });
  });
  document.getElementById("rundenende-btn")?.addEventListener("click", () => {
    sende({ typ: "rundenende" });
  });
  document.getElementById("neuwurf-btn")?.addEventListener("click", () => {
    if (!aktuellerZustand || aktuellerZustand.neuwurf_plaettchen <= 0) return;
    neuwurfOffen = !neuwurfOffen;
    neuwurfAuswahl = { pilot: new Set(), kopilot: new Set() };
    ausgewaehlterWuerfel = null;
    if (aktuellerZustand) render(aktuellerZustand);
  });
});
