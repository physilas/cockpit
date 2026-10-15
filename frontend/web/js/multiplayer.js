/*
 * Cockpit – Multiplayer (PeerJS, kein Server nötig)
 *
 * Host (Pilotin): lädt Pyodide + führt die Spiellogik aus.
 *                 Generiert einen 6-Zeichen-Code und zeigt einen QR-Code.
 * Partner (Co-Pilot): verbindet sich über den Code, braucht kein Pyodide.
 *
 * Kommunikation: WebRTC DataChannel via peerjs.com (kostenloser Relay-Server).
 *
 * Kompaktes Layout: Fahrwerk-/Landeklappen-/Bremsen-Lichter sitzen direkt
 * unter den jeweiligen Würfelfeldern statt in einer eigenen Leiste; die
 * Kaffeetassen-Boxen sitzen direkt neben dem Konzentrations-Feld.
 */

// ── Konstanten ──────────────────────────────────────────────────────────────

const GRUND_TEXT_MAP = COCKPIT_SCHEMA.grund_texte;
const FELD_LAYOUT = COCKPIT_SCHEMA.feld_layout.map(e => ({...e, snap: e.snapshot_key}));
const LABEL = Object.fromEntries(FELD_LAYOUT.map(e => [e.ziel, e.label]));

// ── Zustand ─────────────────────────────────────────────────────────────────
let myRole = null;       // "pilot" | "kopilot"
let peer = null;         // PeerJS eigenes Peer-Objekt
let conn = null;         // DataConnection zur Gegenseite
let bridge = null;       // Pyodide-Bridge (nur Host)
let pyodideReady = false;
let partnerConnected = false;
let aktuellerZustand = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuFuer = null;
let eigeneWuerfelVersteckt = false;

// Neuwurf (Reroll) über zwei Geräte hinweg: die Engine selbst (spielplan.py)
// weiß nichts von "Phasen" - benutze_neuwurf() bekommt einfach beide
// Indexlisten auf einmal. Der Zwei-Schritt-Ablauf (erst Initiator, dann
// Partner) ist reine UI-Choreografie und lebt daher hier als eigenes,
// vom Host verwaltetes Objekt, das bei jedem Zustands-Update mitgeschickt
// wird (siehe sendState()) - so sehen beide Geräte immer denselben
// Neuwurf-Fortschritt, unabhängig davon, wer ihn gestartet hat.
//   phase: 0 = kein Neuwurf | 1 = Initiator wählt | 2 = Partner wählt
//   initiator: "pilot" | "kopilot" | null
//   initiatorAuswahl / partnerAuswahl: Arrays von Würfel-Indizes (0-3)
// WICHTIG: der eigentliche Zug (z.am_zug) wird von alldem nie berührt -
// nach Abschluss des Neuwurfs geht es also automatisch exakt dort weiter,
// wo die Partie vor dem Neuwurf stand.
let neuwurfUi = { phase: 0, initiator: null, initiatorAuswahl: [], partnerAuswahl: [] };

function neuwurfUiReset() {
  neuwurfUi = { phase: 0, initiator: null, initiatorAuswahl: [], partnerAuswahl: [] };
}

// Wessen Würfel gerade ausgewählt werden dürfen (oder null, falls kein
// Neuwurf läuft bzw. gerade niemand dran ist).
function neuwurfAktivBesitzer() {
  if (neuwurfUi.phase === 1) return neuwurfUi.initiator;
  if (neuwurfUi.phase === 2) return neuwurfUi.initiator === "pilot" ? "kopilot" : "pilot";
  return null;
}

// Die Auswahl-Liste für `besitzer`, aber nur wenn `besitzer` gerade aktiv
// dran ist (sonst null - fremde Auswahl wird nie angezeigt/verändert).
function neuwurfAuswahlFuer(besitzer) {
  if (neuwurfUi.phase === 1 && besitzer === neuwurfUi.initiator) return neuwurfUi.initiatorAuswahl;
  if (neuwurfUi.phase === 2 && besitzer !== neuwurfUi.initiator) return neuwurfUi.partnerAuswahl;
  return null;
}

function neuwurfIndexToggle(liste, index) {
  const pos = liste.indexOf(index);
  if (pos === -1) liste.push(index); else liste.splice(pos, 1);
}

// ── Hilfsfunktionen ─────────────────────────────────────────────────────────
function pyToJs(r) { return r.toJs({dict_converter: Object.fromEntries}); }
function grundText(c) {
  if (!c) return "";
  return c.split(",").map(k => GRUND_TEXT_MAP[k.trim()] || k).join(", ");
}
function genCode() {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  return Array.from({length:6}, () => chars[Math.floor(Math.random()*chars.length)]).join("");
}
function joinUrl(code) {
  const p = window.location.pathname;
  return `${window.location.origin}${p}?join=${code}`;
}
function filteredState(rawZ, rolle) {
  const partner = rolle === "pilot" ? "kopilot" : "pilot";
  const z = JSON.parse(JSON.stringify(rawZ));
  const frei = z[`${partner}_wuerfel_frei`];
  z[`${partner}_wuerfel`] = z[`${partner}_wuerfel`].map((v,i) => frei[i] ? null : v);
  return z;
}
function showScreen(id) {
  ["screen-menu","screen-host","screen-join","screen-wait","landing-selection"].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.classList.toggle("versteckt", s !== id);
  });
}
function setMeldung(t, art) {
  const el = document.getElementById("meldung-leiste");
  if (el) { el.textContent = t||""; el.className = art||""; }
}
function setHostStatus(t, cls) {
  const el = document.getElementById("host-status");
  if (el) { el.textContent = t; el.className = "status-pill " + (cls||""); }
}
function setJoinStatus(t, cls) {
  const el = document.getElementById("join-status");
  if (el) { el.textContent = t; el.className = "status-pill " + (cls||""); }
}

// ── Pyodide / Engine (nur Host) ──────────────────────────────────────────────
let gewaehlterFlughafen = "LOG_YUL_GREEN";
let choosingLanding = false;
const landingPicker = Landings.mount(document.getElementById("landing-selection"), {
  mode: "Multiplayer · Host",
  startLabel: "Mit dieser Landung hosten →",
  onBack() {
    if (partnerConnected && aktuellerZustand) {
      choosingLanding = false;
      landingPicker.hide();
      document.getElementById("spiel-header").classList.remove("versteckt");
      document.getElementById("spiel-ui").classList.remove("versteckt");
      sendState();
    } else { showScreen("screen-menu"); }
  },
  onStart(scenario) {
    gewaehlterFlughafen = scenario.engine_code;
    choosingLanding = false;
    document.getElementById("host-landing").textContent = `${scenario.code} · ${scenario.name}${scenario.kind === "logbook" ? (scenario.practice ? " · Originalstrecke, Übungsregeln" : " · Originalstrecke") : " · Eigene Strecke"}`;
    if (partnerConnected && pyodideReady) startGame();
    else starteHosting();
  },
});

function waehleLandung() {
  if (myRole === "kopilot") return;
  choosingLanding = true;
  resetVerkehrUi();
  for (const id of ["spiel-header", "flight-summary", "spiel-ui"]) document.getElementById(id).classList.add("versteckt");
  showScreen("landing-selection");
  landingPicker.show();
  if (conn?.open) conn.send(JSON.stringify({typ:"landung_waehlen"}));
}

async function ladeEngine() {
  const fill = document.getElementById("lade-balken-fill");
  const txt  = document.getElementById("lade-text");
  const setP = p => { if(fill) fill.style.width = p+"%"; };
  try {
    setP(5); txt && (txt.textContent = "Pyodide wird geladen …");
    const pyodide = await loadPyodide({
      indexURL: "https://cdn.jsdelivr.net/pyodide/v0.26.1/full/"
    });
    setP(60); txt && (txt.textContent = "Pakete werden installiert …");
    await pyodide.loadPackage("pyyaml");
    setP(80); txt && (txt.textContent = "Spielregeln werden geladen …");
    pyodide.FS.mkdirTree("/cockpit/backend/landungen");
    for (const [ziel, src] of Object.entries(ENGINE_SRC)) {
      pyodide.FS.writeFile("/cockpit/" + ziel, src);
    }
    pyodide.runPython(`import sys; sys.path.insert(0, "/cockpit")`);
    bridge = pyodide.pyimport("backend.bridge");
    setP(100); txt && (txt.textContent = "Bereit ✓");
    pyodideReady = true;
    if (partnerConnected) startGame();
  } catch(e) {
    console.error(e);
    if (txt) txt.textContent = "Engine-Fehler: " + e.message;
  }
}

// ── Spielstart (Host) ────────────────────────────────────────────────────────
function startGame() {
  resetVerkehrUi();
  const rawZ = pyToJs(bridge.neues_spiel(gewaehlterFlughafen));
  showScreen(null);
  choosingLanding = false;
  neuwurfUiReset();
  ausgewaehlterWuerfel = null;
  kaffeeMenuFuer = null;
  eigeneWuerfelVersteckt = false;
  setMeldung("");
  document.getElementById("spiel-header").classList.remove("versteckt");
  document.getElementById("spiel-ui").classList.remove("versteckt");
  sendState(rawZ);
}

function sendState(rawZ) {
  if (!rawZ) rawZ = pyToJs(bridge.zustand());
  aktuellerZustand = filteredState(rawZ, "pilot");
  render(aktuellerZustand);
  if (conn && conn.open) {
    conn.send(JSON.stringify({
      typ:"zustand",
      zustand: filteredState(rawZ, "kopilot"),
      neuwurf: neuwurfUi,
    }));
  }
}

// ── Host: Aktionen verarbeiten ───────────────────────────────────────────────
function hostAktion(msg, absender) {
  if (!bridge || !pyodideReady || choosingLanding) return false;
  if (absender !== "pilot" && absender !== "kopilot") return;
  // The host assigns the role from the connection. A client-provided role is
  // never authoritative, which keeps this transport usable for future cloud
  // sessions as well.
  msg = {...msg, besitzer: absender};
  let raw;
  const zeigeErgebnis = r => {
    if (!r.erfolg && msg.typ === "wirf_verkehrswuerfel") verkehrWurfFehlgeschlagen();
    const meldung = r.erfolg ? r.meldung : grundText(r.grund);
    if (absender === "pilot") setMeldung(r.erfolg ? meldung : "Nicht möglich: " + meldung, r.erfolg ? "erfolg" : "fehler");
    else if (conn?.open) conn.send(JSON.stringify({typ:"ergebnis", erfolg:r.erfolg, meldung}));
  };
  try {
    if (msg.typ === "platziere") {
      const r = pyToJs(bridge.platziere(
        msg.besitzer, msg.wuerfel_index, msg.ziel,
        msg.index ?? null, msg.funk_feld ?? 0
      ));
      zeigeErgebnis(r.ergebnis);
      raw = r.zustand;
    } else if (msg.typ === "trinke_kaffee") {
      const r = pyToJs(bridge.trinke_kaffee(msg.besitzer, msg.wuerfel_index, msg.delta));
      zeigeErgebnis(r.ergebnis);
      raw = r.zustand;
    } else if (msg.typ === "wirf_verkehrswuerfel") {
      const r = pyToJs(bridge.wirf_verkehrswuerfel(msg.besitzer));
      zeigeErgebnis(r.ergebnis);
      raw = r.zustand;
    } else if (msg.typ === "rundenende") {
      const r = pyToJs(bridge.rundenende());
      zeigeErgebnis(r.ergebnis);
      if (r.ergebnis.erfolg && r.zustand.status === "laeuft") {
        bridge.wuerfeln_fuer_runde();
        raw = pyToJs(bridge.zustand());
      } else {
        raw = r.zustand;
      }
    } else if (msg.typ === "neues_spiel") {
      if (absender !== "pilot") return false;
      resetVerkehrUi();
      raw = pyToJs(bridge.neues_spiel(gewaehlterFlughafen));
      neuwurfUiReset();

    // ── Neuwurf: zwei-Schritt-Choreografie, siehe Kommentar bei neuwurfUi ──
    } else if (msg.typ === "neuwurf_start") {
      const z = pyToJs(bridge.zustand());
      if (neuwurfUi.phase === 0 && z.neuwurf_plaettchen > 0 && z.status === "laeuft" && z.phase === "platzieren") {
        neuwurfUi = { phase: 1, initiator: msg.besitzer, initiatorAuswahl: [], partnerAuswahl: [] };
      }
      raw = pyToJs(bridge.zustand());
    } else if (msg.typ === "neuwurf_toggle") {
      const aktiver = neuwurfAktivBesitzer();
      if (aktiver && msg.besitzer === aktiver) {
        const liste = neuwurfUi.phase === 1 ? neuwurfUi.initiatorAuswahl : neuwurfUi.partnerAuswahl;
        neuwurfIndexToggle(liste, msg.index);
      }
      raw = pyToJs(bridge.zustand());
    } else if (msg.typ === "neuwurf_next") {
      if (neuwurfUi.phase === 1 && msg.besitzer === neuwurfUi.initiator) {
        neuwurfUi.phase = 2;
      }
      raw = pyToJs(bridge.zustand());
    } else if (msg.typ === "neuwurf_confirm") {
      const partner = neuwurfUi.initiator === "pilot" ? "kopilot" : "pilot";
      if (neuwurfUi.phase === 2 && msg.besitzer === partner) {
        const pilotIdx   = neuwurfUi.initiator === "pilot"   ? neuwurfUi.initiatorAuswahl : neuwurfUi.partnerAuswahl;
        const kopilotIdx = neuwurfUi.initiator === "kopilot" ? neuwurfUi.initiatorAuswahl : neuwurfUi.partnerAuswahl;
        bridge.benutze_neuwurf(pilotIdx, kopilotIdx);
        neuwurfUiReset();
      }
      raw = pyToJs(bridge.zustand());
    } else if (msg.typ === "neuwurf_cancel") {
      neuwurfUiReset();
      raw = pyToJs(bridge.zustand());
    }
  } catch(e) { console.error(e); return false; }
  if (raw) sendState(raw);
}

// ── Eigene Aktion (vom aktuellen Gerät ausgelöst) ────────────────────────────
function meineAktion(msg) {
  msg.besitzer = myRole;
  if (myRole === "pilot") {
    return hostAktion(msg, "pilot");
  } else {
    if (!conn?.open) return false;
    conn.send(JSON.stringify(msg));
  }
}

// ── PeerJS: Host aufsetzen ───────────────────────────────────────────────────
function starteHosting() {
  myRole = "pilot";
  showScreen("screen-host");
  const code = genCode();
  document.getElementById("host-code").textContent = code;

  const qrBox = document.getElementById("qr-box");
  qrBox.innerHTML = "";
  if (window.QRCode) {
    new QRCode(qrBox, {
      text: joinUrl(code),
      width: 200, height: 200,
      colorDark: "#e2e8f0", colorLight: "#1e293b",
    });
  }

  peer = new Peer(code, {
    config: {iceServers: [{urls:"stun:stun.l.google.com:19302"}]}
  });

  peer.on("open", () => {
    setHostStatus("Warte auf Co-Pilot … Code: " + code, "");
    ladeEngine();
  });

  peer.on("connection", c => {
    conn = c;
    conn.on("open", () => {
      partnerConnected = true;
      setHostStatus("Co-Pilot verbunden ✓", "ok");
      document.getElementById("verbindungs-status")?.classList.add("ok");
      if (pyodideReady) startGame();
    });
    conn.on("data", raw => {
      try {
        const msg = JSON.parse(raw);
        if (msg && typeof msg === "object") hostAktion(msg, "kopilot");
      } catch (error) {
        console.warn("Ungültige Multiplayer-Nachricht", error);
      }
    });
    conn.on("close", () => {
      setMeldung("Verbindung zum Co-Piloten unterbrochen.", "fehler");
    });
  });

  peer.on("error", e => {
    if (e.type === "unavailable-id") {
      peer.destroy();
      starteHosting();
    } else {
      setHostStatus("Verbindungsfehler: " + e.message, "err");
    }
  });
}

// ── PeerJS: Beitreten ────────────────────────────────────────────────────────
function starte_Beitreten(code) {
  myRole = "kopilot";
  code = code.toUpperCase().trim();
  if (code.length < 6) { setJoinStatus("Code muss 6 Zeichen haben.", "err"); return; }
  setJoinStatus("Verbinde …", "");

  peer = new Peer({
    config: {iceServers: [{urls:"stun:stun.l.google.com:19302"}]}
  });

  peer.on("open", () => {
    conn = peer.connect(code, {reliable: true});
    conn.on("open", () => {
      setJoinStatus("Verbunden ✓ – warte auf Spielstart …", "ok");
      showScreen("screen-wait");
      document.getElementById("neues-spiel-btn").classList.add("versteckt");
      document.getElementById("meine-rolle-badge").textContent = "Co-Pilot";
      document.getElementById("meine-rolle-badge").className = "meine-rolle-badge kopilot";
    });
    conn.on("data", raw => {
      const msg = JSON.parse(raw);
      if (msg.typ === "landung_waehlen") {
        resetVerkehrUi();
        for (const id of ["spiel-header", "flight-summary", "spiel-ui"]) document.getElementById(id).classList.add("versteckt");
        showScreen("screen-wait");
      }
      if (msg.typ === "zustand" && msg.zustand) {
        showScreen(null);
        document.getElementById("spiel-header").classList.remove("versteckt");
        document.getElementById("spiel-ui").classList.remove("versteckt");
        aktuellerZustand = msg.zustand;
        neuwurfUi = msg.neuwurf || { phase: 0, initiator: null, initiatorAuswahl: [], partnerAuswahl: [] };
        render(msg.zustand);
      }
      if (msg.typ === "ergebnis") {
        if (!msg.erfolg) verkehrWurfFehlgeschlagen();
        setMeldung(
          msg.erfolg ? msg.meldung : "Nicht möglich: " + msg.meldung,
          msg.erfolg ? "erfolg" : "fehler"
        );
      }
    });
    conn.on("close", () => setMeldung("Verbindung getrennt.", "fehler"));
  });

  peer.on("error", e => setJoinStatus("Fehler: " + e.message + " – Code korrekt?", "err"));
}

// ── Rendering ────────────────────────────────────────────────────────────
// Aerodynamik-Skala als horizontale Leiste: eine Zahl je Zelle, an den
// beiden Schwellen (blau = Fahrwerk-Marker, orange = Landeklappen-Marker)
// sitzt statt eines simplen "|" ein kleiner, farbiger vertikaler Balken
// in der jeweiligen Spielerfarbe.
function aeroSkalaHTML(blau, orange) {
  // Identische Kreisgeometrie wie im Pass-&-Play-Cockpit.
  const punkt = (index, radius) => {
    const winkel = (146 - index * 11.2) * Math.PI / 180;
    return { x: 125 + radius * Math.cos(winkel), y: -44 + radius * Math.sin(winkel) };
  };
  let html = `<svg class="aero-shell" viewBox="0 0 250 90" role="img" aria-label="Aerodynamik: 2 bis 12, blaue Schwelle ${blau}, orange Schwelle ${orange}">
    <defs><linearGradient id="aero-shell-fill" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#304a50"/><stop offset="1" stop-color="#15282e"/></linearGradient></defs>
    <path d="M 0.549 0 A 132 132 0 0 0 249.451 0 L 210.323 0 A 96 96 0 0 1 39.677 0 Z" fill="url(#aero-shell-fill)" stroke="#678185" stroke-width="1"/>`;
  for (let n = 2; n <= 12; n++) {
    const p = punkt(n - 2, 114);
    html += `<text class="aero-number" x="${p.x}" y="${p.y}" text-anchor="middle" dominant-baseline="central">${n}</text>`;
  }
  for (const [farbe, schwelle] of [["pilot", blau], ["copilot", orange]]) {
    html += `<line class="aero-tick aero-tick-${farbe}" x1="125" y1="56" x2="125" y2="84" style="transform:rotate(${aeroMarkerWinkel(schwelle)}deg)"/>`;
  }
  html += '</svg>';
  return html;
}

function aeroMarkerWinkel(schwelle) {
  const index = Math.max(-0.5, Math.min(10.5, Math.floor(schwelle) - 1.5));
  return 56 - index * 11.2;
}

function renderAeroSkala(blau, orange) {
  const skala = document.getElementById("s-aero");
  if (!skala.querySelector(".aero-shell")) skala.innerHTML = aeroSkalaHTML(blau, orange);
  skala.querySelector(".aero-shell").setAttribute("aria-label", `Aerodynamik: 2 bis 12, blaue Schwelle ${blau}, orange Schwelle ${orange}`);
  skala.querySelector(".aero-tick-pilot").style.transform = `rotate(${aeroMarkerWinkel(blau)}deg)`;
  skala.querySelector(".aero-tick-copilot").style.transform = `rotate(${aeroMarkerWinkel(orange)}deg)`;
}
// Bremsen-Marker-Skala, gleiches Prinzip, mit einem roten Balken an der
// aktuellen Bremsstärke.
function bremsSkalaHTML(bs) {
  let html = '<div class="brems-scale">';
  for (let n = 2; n <= 6; n++) {
    html += `<span class="skala-zahl brems-number">${n}</span>`;
  }
  html += `<span class="brems-marker" aria-hidden="true" style="left:${bremsMarkerPosition(bs)}%"></span></div>`;
  return html;
}

function bremsMarkerPosition(bs) {
  return bs < 2 ? 12 : Math.min(88, 12 + (bs - 1) * 15.2);
}

function renderBremsSkala(bs) {
  const skala = document.getElementById("s-brems");
  if (!skala.querySelector(".brems-marker")) skala.innerHTML = bremsSkalaHTML(bs);
  skala.querySelector(".brems-marker").style.left = bremsMarkerPosition(bs) + "%";
  skala.setAttribute("aria-label", `Bremsstärke ${bs}`);
}
function kaffeeHTML(n) {
  return Array.from({length:3},(_,i)=>`<span class="ressourcen-box${i<n?" gefuellt":""}">${i<n?"☕":""}</span>`).join("");
}
function neuwurfHTML(n) {
  return n>0?Array.from({length:n},()=>'<button type="button" class="ressourcen-box gefuellt reroll-token" title="Neuwurf starten">🔄</button>').join("")
           :'<span class="ressourcen-box"></span>';
}

function bindeNeuwurfTokens(z) {
  document.querySelectorAll("#s-neuwurf .reroll-token").forEach(token => {
    const darfStarten = myRole && z.am_zug === myRole;
    token.disabled = z.status !== "laeuft" || z.phase !== "platzieren" || (neuwurfUi.phase === 0 && !darfStarten);
    token.title = neuwurfUi.phase === 0 ? "Neuwurf starten" : "Neuwurf abbrechen";
    token.addEventListener("click", () => {
      if (neuwurfUi.phase !== 0) {
        meineAktion({ typ: "neuwurf_cancel" });
        return;
      }
      ausgewaehlterWuerfel = null;
      meineAktion({ typ: "neuwurf_start" });
    });
  });
}

// Jede Leiste zeigt nur noch ihre aktuell sichtbaren Felder. So bleiben
// keine leeren Kacheln oberhalb der Entfernung bzw. Höhe zurück.
const TRACK_UNIT_PX = 36;
function setzeGauge(prefix, remaining) {
  const track = document.getElementById(`${prefix}-track`);
  const height = Math.max(0, remaining) * TRACK_UNIT_PX;
  track.style.height = height + "px";
  track.classList.toggle("leer", remaining <= 0);
  const fill = document.getElementById(`${prefix}-fill`);
  fill.style.bottom = "0px";
  fill.style.height = height + "px";
  const usedEl = document.getElementById(`${prefix}-used`);
  if (usedEl) usedEl.classList.remove("sichtbar");
}

const ATTITUDE_DEG_PRO_EINHEIT = 20;

function renderAttitude(fluglage) {
  const needle = document.getElementById("attitude-needle");
  if (!needle) return;
  const deg = fluglage * ATTITUDE_DEG_PRO_EINHEIT;
  needle.style.transform = `rotate(${deg}deg)`;
  needle.style.transformOrigin = "50px 60px";
}

function renderTracks(z) {
  document.getElementById("altitude-track").style.setProperty("--track-unit-px", TRACK_UNIT_PX + "px");
  document.getElementById("distance-track").style.setProperty("--track-unit-px", TRACK_UNIT_PX + "px");

  const laenge = z.laenge || 1;
  const hoehenEinheiten = z.hoehe / 1000 + 1;
  // Auch bei Entfernung 0 bleibt das Flughafen-Feld sichtbar.
  const distanzEinheiten = Math.max(0, z.entfernung + 1);

  setzeGauge("altitude", hoehenEinheiten);
  document.getElementById("altitude-track").setAttribute("aria-label", `Höhenleiste: ${z.hoehe} ft`);
  renderAltitudeLabels(hoehenEinheiten * TRACK_UNIT_PX, z.hoehe, z.neuwurf_hoehen || []);

  setzeGauge("distance", distanzEinheiten);
  document.getElementById("distance-track").setAttribute("aria-label", `Entfernungsleiste: ${z.entfernung} Schritte bis zum Flughafen`);
  renderDistanceLabels(z.entfernung, z.entfernungswerte);

  renderEntfernungsFlugzeuge(z, TRACK_UNIT_PX);
  renderKurven(z.kurven_min, z.kurven_max, laenge, z.entfernung);
}

// Erlaubte Ruderstellung je Entfernungsfeld (kurven_min/kurven_max), wie
// auf den gedruckten Distanz-Modulen: fünf Positionen -2..+2, schwarzes ▼
// = Mitte (0), grüne Dreiecke = erlaubt, rote Kreuze = verboten. Felder
// ohne Einschränkung (-2..+2) bekommen wie auf der Karte kein Symbol.
function kurvenBadgeEl(min, max) {
  const el = document.createElement("span");
  el.className = "vtrack-kurve";
  el.title = `Erlaubte Ruderstellung auf diesem Feld: ${min} bis ${max}`;
  for (let v = -2; v <= 2; v++) {
    const g = document.createElement("span");
    if (v < min || v > max) { g.className = "kurve-verboten"; g.textContent = "✚"; }
    else if (v === 0)       { g.className = "kurve-null";     g.textContent = "▼"; }
    else                    { g.className = "kurve-erlaubt";  g.textContent = v < 0 ? "◁" : "▷"; }
    el.appendChild(g);
  }
  return el;
}

function renderKurven(kmin, kmax, laenge, entfernung) {
  const track = document.getElementById("distance-track");
  let cont = document.getElementById("distance-kurven");
  if (!cont) {
    cont = document.createElement("div");
    cont.id = "distance-kurven";
    track.appendChild(cont);
  }
  cont.innerHTML = "";
  (kmin || []).forEach((min, i) => {
    const max = (kmax || [])[i];
    if (max === undefined || (min <= -2 && max >= 2)) return;   // keine Einschränkung
    const aktuellerIndex = laenge - 1 - entfernung;
    if (i < aktuellerIndex) return;                              // schon überflogen
    const center = (entfernung + 1 - (i - aktuellerIndex) - 0.5) * TRACK_UNIT_PX;
    const badge = kurvenBadgeEl(min, max);
    badge.style.top = (center - TRACK_UNIT_PX / 2) + "px";  // direkt an der Feldgrenze
    cont.appendChild(badge);
  });
}

// Höhen-Zahlen: mitlaufende Skala. Das unterste (Marker-nächste) Feld zeigt
// immer die AKTUELLE Höhe, darüber in 1000-ft-Schritten absteigend bis 0 ft;
// Felder mit negativem Wert bleiben leer ("nichts") - nach jeder Runde
// rutscht so oben ein Feld "aus dem Bild" und unten rückt die neue
// (niedrigere) aktuelle Höhe an den Marker heran. Neuwurf-Symbole sind
// Flughafen-Daten und werden mit dem Zustands-Snapshot geliefert.

function renderDistanceLabels(entfernung, feldwerte) {
  const el = document.getElementById("distance-labels");
  if (!el) return;
  el.replaceChildren();
  const werte = feldwerte || Array.from({ length: entfernung + 1 }, (_, i) => entfernung - i);
  werte.filter(wert => wert >= 0 && wert <= entfernung).forEach(wert => {
    const label = document.createElement("span");
    label.className = "vtrack-distancelabel";
    label.style.top = (wert + 0.5) * TRACK_UNIT_PX + "px";
    label.textContent = String(wert);
    if (wert === 0) label.title = "Flughafen · Entfernung 0";
    el.appendChild(label);
  });
}

function renderAltitudeLabels(markerY, aktuelleHoehe, neuwurfHoehen) {
  const el = document.getElementById("altitude-labels");
  if (!el) return;
  el.innerHTML = "";
  for (let v = 0; v <= aktuelleHoehe / 1000; v++) {
    const hoeheFt = aktuelleHoehe - v * 1000;
    if (hoeheFt <= 0) continue; // Das Landungssymbol ersetzt die 0-ft-Zahl.

    const y = markerY - (v + 0.5) * TRACK_UNIT_PX;
    const label = document.createElement("span");
    label.className = "vtrack-heightlabel";
    label.style.top = y + "px";
    label.textContent = String(hoeheFt);

    if (neuwurfHoehen.includes(hoeheFt) && aktuelleHoehe > hoeheFt) {
      const badge = document.createElement("span");
      badge.className = "reroll-badge";
      badge.textContent = "🔄";
      label.appendChild(badge);
    }
    el.appendChild(label);
  }
}

function render(z) {
  if(!z)return;
  Landings.updateFlight(z);
  document.getElementById("s-runde").textContent = z.letzte_runde
    ? "🛬 Landung"
    : "Runde " + z.runde + (z.warteschleife ? " ⟳" : "");
  renderAeroSkala(z.aerodynamik_blau,z.aerodynamik_orange);
  renderBremsSkala(z.bremsstaerke);
  document.getElementById("s-kaffee-status").innerHTML = kaffeeHTML(z.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfHTML(z.neuwurf_plaettchen);
  bindeNeuwurfTokens(z);
  renderAttitude(z.fluglage);
  renderTracks(z);
  renderVerkehr(z, TRACK_UNIT_PX, myRole === z.am_zug, () => {
    return meineAktion({ typ: "wirf_verkehrswuerfel" });
  });

  if(myRole) {
    const b=document.getElementById("meine-rolle-badge");
    b.textContent=myRole==="pilot"?"Pilotin":"Co-Pilot";
    b.className="meine-rolle-badge "+myRole;
  }

  renderBoard(z);
  renderWuerfel("pilot",z);
  renderWuerfel("kopilot",z);
  renderNeuwurf(z);

  const amZug=document.getElementById("am-zug-anzeige");
  const rBtn=document.getElementById("rundenende-btn");
  const imNeuwurf = neuwurfUi.phase !== 0;

  if(z.status!=="laeuft") {
    amZug.innerHTML=`<div class="spiel-ende ${z.status}">`+
      (z.status==="gewonnen"?"🎉 Sicher gelandet!":`💥 Verloren – ${grundText(z.verlust_grund)}`)+
      "</div>";
    if(rBtn)rBtn.disabled=true;
  } else if (z.phase !== "platzieren") {
    amZug.textContent = myRole === z.am_zug
      ? "Zuerst schwarze Würfel werfen"
      : `${z.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"} wirft die schwarzen Würfel …`;
    amZug.style.color = "var(--muted)";
    if(rBtn)rBtn.disabled=true;
  } else if (imNeuwurf) {
    // Während des Neuwurfs ruht die Platzier-Reihenfolge - der eigentliche
    // Zug (z.am_zug) bleibt dabei unverändert und läuft danach genau dort
    // weiter, wo er stand (siehe neuwurfUi-Kommentar oben).
    const aktiverBesitzer = neuwurfAktivBesitzer();
    const ichBinAktiv = myRole === aktiverBesitzer;
    amZug.textContent = ichBinAktiv
      ? "🔄 Neuwurf: du bist dran ✦"
      : `🔄 Neuwurf: ${aktiverBesitzer === "pilot" ? "Pilotin" : "Co-Pilot"} wählt …`;
    amZug.style.color = ichBinAktiv ? "var(--gruen)" : "var(--muted)";
    if(rBtn)rBtn.disabled=true;
  } else {
    const ichDran=myRole&&z.am_zug===myRole;
    amZug.textContent=ichDran?"Du bist am Zug ✦":(z.am_zug==="pilot"?"Pilotin":"Co-Pilot")+" ist am Zug …";
    amZug.style.color=ichDran?"var(--gruen)":"var(--muted)";
    if(rBtn)rBtn.disabled=!ichDran;
  }
}

// Ordnet Funk/Fahrwerk/Landeklappen ihrer Seitenspalte zu. Ruder, Triebwerk,
// Bremse und Konzentration werden als Sonderfälle behandelt (siehe unten),
// weil sie im physischen Board in der Mitte liegen statt in den Seiten-
// spalten: Ruder flankiert das Fluglage-Rad, Triebwerk/Bremse/Konzentration
// sitzen als eigene Reihen darunter.
function containerFuerEintrag(e) {
  if (e.ziel === "landeklappe") {
    return document.getElementById("col-kopilot-felder");
  }
  if (e.ziel === "fahrwerk") {
    return document.getElementById("col-pilot-felder");
  }
  if (e.ziel === "funk") {
    return e.zugriff.includes("pilot")
      ? document.getElementById("col-pilot-felder")
      : document.getElementById("col-kopilot-felder");
  }
  return null;
}

function renderBoard(z) {
  ["col-pilot-felder", "col-kopilot-felder", "schub-reihe", "bremse-reihe", "konzentration-reihe"]
    .forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ""; });
  const felder=z.felder||{};

  FELD_LAYOUT.forEach(e=>{
    if (e.ziel === "ruder") {
      const w = felder.ruder || {};
      const pilotSlot = document.getElementById("ruder-slot-pilot");
      const kopilotSlot = document.getElementById("ruder-slot-kopilot");
      pilotSlot.innerHTML = "";
      kopilotSlot.innerHTML = "";
      pilotSlot.appendChild(zelle("pilot", w.pilot, null, e, z));
      kopilotSlot.appendChild(zelle("kopilot", w.kopilot, null, e, z));
      return;
    }

    if (e.ziel === "triebwerk") {
      const w = felder.triebwerk || {};
      const reihe = document.getElementById("schub-reihe");
      reihe.appendChild(zelle("pilot", w.pilot, null, e, z));
      const label = document.createElement("span");
      label.className = "inline-label";
      label.textContent = "Schub";
      reihe.appendChild(label);
      reihe.appendChild(zelle("kopilot", w.kopilot, null, e, z));
      return;
    }

    if (e.ziel === "bremse" || e.ziel === "konzentration") {
      const reihe = document.getElementById(e.ziel === "bremse" ? "bremse-reihe" : "konzentration-reihe");
      const werte = felder[e.snap] || Array(e.slots).fill(null);
      const statusArr = e.ziel === "bremse" ? z.bremsen_aktiviert : null;
      const nx = statusArr ? statusArr.indexOf(false) : null;
      for (let i = 0; i < e.slots; i++) {
        const gesperrt = statusArr && nx !== -1 && i !== nx;
        if (statusArr) {
          const wrap = document.createElement("div");
          wrap.className = "feld-slot-mit-licht";
          wrap.appendChild(zelle(null, werte[i], i, e, z, gesperrt));
          const licht = document.createElement("span");
          licht.className = "feld-licht" + (statusArr[i] ? " an" : "");
          wrap.appendChild(licht);
          reihe.appendChild(wrap);
        } else {
          reihe.appendChild(zelle(null, werte[i], i, e, z, gesperrt));
        }
      }
      return;
    }

    // Funk, Fahrwerk, Landeklappen: unverändertes Zeilen-mit-Label-Layout,
    // nur in die jeweilige Seitenspalte einsortiert.
    const board = containerFuerEintrag(e);
    if (!board) return;

    const zeile=document.createElement("div");
    zeile.className="feld-zeile";

    const lbl=document.createElement("span");
    lbl.className="feld-label";
    lbl.textContent=LABEL[e.ziel]+(e.pflicht?" *":"");
    zeile.appendChild(lbl);

    const slots=document.createElement("div");
    slots.className="feld-slots";

    {
      const werte=felder[e.snap]||Array(e.slots).fill(null);
      const statusArr=e.ziel==="fahrwerk"?z.fahrwerk_ausgefahren:
                       e.ziel==="landeklappe"?z.landeklappen_ausgefahren:null;
      // Nur Landeklappen müssen strikt der Reihe nach ausgefahren werden -
      // beim Fahrwerk ist jede Reihenfolge erlaubt (S.7).
      const reihenfolgeZaehlt = e.ziel==="landeklappe";
      const nx=reihenfolgeZaehlt?statusArr.indexOf(false):null;
      for(let i=0;i<e.slots;i++) {
        const gesperrt=reihenfolgeZaehlt&&nx!==-1&&i!==nx;
        if (statusArr) {
          const wrap = document.createElement("div");
          wrap.className = "feld-slot-mit-licht";
          wrap.appendChild(zelle(null,werte[i],i,e,z,gesperrt));
          const licht = document.createElement("span");
          licht.className = "feld-licht" + (statusArr[i] ? " an" : "");
          wrap.appendChild(licht);
          slots.appendChild(wrap);
        } else {
          slots.appendChild(zelle(null,werte[i],i,e,z,gesperrt));
        }
      }
    }
    zeile.appendChild(slots);
    board.appendChild(zeile);
  });
}

function zelle(fixBesitzer,wertObj,slotIdx,e,z,gesperrt=false) {
  const div=document.createElement("div");
  div.className="feld-zelle";
  if(e?.ziel)div.classList.add(`ziel-${e.ziel}`);
  if(wertObj){div.classList.add("belegt",wertObj.besitzer);div.textContent=wertObj.wert;return div;}
  if(e.zahlen&&slotIdx!==null)div.innerHTML=`<small>${e.zahlen[slotIdx].join("/")}</small>`;
  if(gesperrt){div.title="Reihenfolge beachten.";return div;}
  const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft"&&z.phase==="platzieren";
  const kannHier=fixBesitzer?ausgewaehlterWuerfel?.besitzer===fixBesitzer
                            :ausgewaehlterWuerfel&&e.zugriff.includes(ausgewaehlterWuerfel.besitzer);
  if(ichDran&&ausgewaehlterWuerfel&&kannHier){
    div.classList.add("klickbar");
    div.addEventListener("click",()=>platziereAusgewaehlten(e,slotIdx));
  }
  return div;
}

function platziereAusgewaehlten(e,slotIdx) {
  if(!ausgewaehlterWuerfel)return;
  const brauchtIdx=["fahrwerk","landeklappe","bremse","konzentration"].includes(e.ziel);
  meineAktion({
    typ:"platziere",
    wuerfel_index:ausgewaehlterWuerfel.index,
    ziel:e.ziel,
    index:brauchtIdx?slotIdx:null,
    funk_feld:e.ziel==="funk"?slotIdx:0,
  });
  ausgewaehlterWuerfel=null;
}

function renderWuerfel(besitzer,z) {
  const container=document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML="";
  const werte=z[`${besitzer}_wuerfel`];
  const frei =z[`${besitzer}_wuerfel_frei`];
  const istMeins=besitzer===myRole;

  const imNeuwurf = neuwurfUi.phase !== 0;
  const aktiverBesitzer = neuwurfAktivBesitzer();
  const istNeuwurfAktiv = imNeuwurf && besitzer === aktiverBesitzer;
  const neuwurfAuswahl = istNeuwurfAktiv ? neuwurfAuswahlFuer(besitzer) : null;

  if (istMeins && werte.some(wert => wert !== null)) {
    const hideBtn = document.createElement("button");
    hideBtn.className = eigeneWuerfelVersteckt ? "view-btn" : "hide-btn";
    hideBtn.textContent = "◉";
    hideBtn.title = eigeneWuerfelVersteckt ? "Würfel anzeigen" : "Würfel verbergen";
    hideBtn.addEventListener("click", () => {
      eigeneWuerfelVersteckt = !eigeneWuerfelVersteckt;
      ausgewaehlterWuerfel = null;
      kaffeeMenuFuer = null;
      render(z);
    });
    container.appendChild(hideBtn);
  }

  werte.forEach((wert,i)=>{
    const wrap=document.createElement("div");
    wrap.className="wuerfel-slot";

    const div=document.createElement("div");
    const verborgen=wert===null || (istMeins && eigeneWuerfelVersteckt && frei[i]);
    div.className="wuerfel"+((!frei[i]||verborgen)?" platziert":"");
    if(verborgen)div.classList.add("partner-wuerfel");
    div.textContent=verborgen?"?":String(wert);

    // Markierung: entweder "für's Platzieren ausgewählt" oder (während
    // eines Neuwurfs) "für den Neuwurf markiert" - nie beides gleichzeitig.
    const istPlatzierAus = !imNeuwurf && ausgewaehlterWuerfel?.besitzer===besitzer&&ausgewaehlterWuerfel?.index===i;
    const istNeuwurfMarkiert = istNeuwurfAktiv && istMeins && neuwurfAuswahl?.includes(i);
    if(istPlatzierAus || istNeuwurfMarkiert) div.classList.add("ausgewaehlt");

    const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft"&&z.phase==="platzieren";
    if(!imNeuwurf && istMeins&&frei[i]&&!verborgen&&ichDran){
      div.addEventListener("click",()=>{
        ausgewaehlterWuerfel=istPlatzierAus?null:{besitzer,index:i};
        kaffeeMenuFuer=null;
        render(z);
      });
    } else if (imNeuwurf && istNeuwurfAktiv && istMeins && frei[i] && !verborgen) {
      div.title = "Klicken, um diesen Würfel für den Neuwurf zu markieren/abzuwählen.";
      div.addEventListener("click", () => {
        meineAktion({ typ: "neuwurf_toggle", index: i });
      });
    }
    wrap.appendChild(div);

    if(!imNeuwurf && istMeins&&istPlatzierAus&&frei[i]&&!verborgen&&z.kaffeetassen>0){
      const kb=document.createElement("button");
      kb.textContent="☕";
      kb.addEventListener("click",ev=>{
        ev.stopPropagation();
        kaffeeMenuFuer=(kaffeeMenuFuer?.index===i?null:{besitzer,index:i});
        render(z);
      });
      wrap.appendChild(kb);
      if(kaffeeMenuFuer?.index===i&&kaffeeMenuFuer?.besitzer===besitzer){
        const n=z.kaffeetassen;
        const menu=document.createElement("div");
        menu.className="kaffee-auswahl";
        for(let d=-n;d<=n;d++){
          if(d===0||wert+d<1||wert+d>6)continue;
          const b=document.createElement("button");
          b.textContent=(d>0?"+":"")+d;
          b.addEventListener("click",ev=>{
            ev.stopPropagation();
            kaffeeMenuFuer=null;
            meineAktion({typ:"trinke_kaffee",wuerfel_index:i,delta:d});
          });
          menu.appendChild(b);
        }
        wrap.appendChild(menu);
      }
    }
    container.appendChild(wrap);
  });
}

// Neuwurf-Panel: zeigt nur noch die Anweisung + Aktions-Buttons - die
// Auswahl selbst passiert direkt an den (eigenen) Würfeln oben, siehe
// renderWuerfel(). Beide Geräte sehen dank neuwurfUi (vom Host verteilt)
// jederzeit denselben Fortschritt.
function renderNeuwurf(z) {
  const panel=document.getElementById("neuwurf-panel");
  panel.innerHTML="";
  if(neuwurfUi.phase===0||z.status!=="laeuft"){panel.classList.add("versteckt");return;}
  panel.classList.remove("versteckt");

  const partnerRolle = neuwurfUi.initiator === "pilot" ? "kopilot" : "pilot";
  const initiatorName = neuwurfUi.initiator === "pilot" ? "Pilotin" : "Co-Pilot";
  const partnerName   = partnerRolle === "pilot" ? "Pilotin" : "Co-Pilot";
  const aktiverBesitzer = neuwurfAktivBesitzer();
  const ichBinAktiv = myRole === aktiverBesitzer;

  const intro=document.createElement("p");
  if (neuwurfUi.phase === 1) {
    intro.innerHTML = ichBinAktiv
      ? "Tippe oben deine Würfel an, die neu geworfen werden sollen."
      : `<strong>${initiatorName}</strong> wählt gerade Würfel zum Neuwerfen aus …`;
  } else {
    intro.innerHTML = ichBinAktiv
      ? "Jetzt du: tippe oben deine Würfel an, die neu geworfen werden sollen."
      : `Warte auf <strong>${partnerName}</strong> …`;
  }
  panel.appendChild(intro);

  if (ichBinAktiv) {
    const frei = z[`${myRole}_wuerfel_frei`];
    if (!frei.some(Boolean)) {
      const s = document.createElement("p");
      s.textContent = "(keine unplatzierten Würfel verfügbar)";
      panel.appendChild(s);
    }
  }

  const ak=document.createElement("div");
  ak.className="neuwurf-aktionen";

  if (neuwurfUi.phase === 1 && ichBinAktiv) {
    const weiter=document.createElement("button");
    weiter.textContent=`Weiter → ${partnerName}`;
    weiter.addEventListener("click", () => meineAktion({typ:"neuwurf_next"}));
    ak.appendChild(weiter);
  }
  if (neuwurfUi.phase === 2 && ichBinAktiv) {
    const ok=document.createElement("button");
    ok.textContent="🎲 Neu würfeln";
    ok.addEventListener("click", () => meineAktion({typ:"neuwurf_confirm"}));
    ak.appendChild(ok);
  }
  const ab=document.createElement("button");
  ab.textContent="Abbrechen";
  ab.addEventListener("click", () => meineAktion({typ:"neuwurf_cancel"}));
  ak.appendChild(ab);
  panel.appendChild(ak);
}

// ── Init ─────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  const params = new URLSearchParams(window.location.search);
  const joinCode = params.get("join");
  if (joinCode) {
    showScreen("screen-join");
    document.getElementById("join-code-input").value = joinCode;
    starte_Beitreten(joinCode);
    return;
  }

  document.getElementById("btn-host").addEventListener("click", waehleLandung);
  document.getElementById("btn-join").addEventListener("click", () => showScreen("screen-join"));
  document.getElementById("btn-do-join").addEventListener("click", () => {
    starte_Beitreten(document.getElementById("join-code-input").value);
  });
  document.getElementById("join-code-input").addEventListener("keydown", e => {
    if (e.key === "Enter") starte_Beitreten(document.getElementById("join-code-input").value);
  });

  document.getElementById("neues-spiel-btn")?.addEventListener("click", waehleLandung);
  document.getElementById("rundenende-btn")?.addEventListener("click", () => meineAktion({typ:"rundenende"}));
  document.getElementById("menue-btn")?.addEventListener("click", () => {
    window.location = "index.html";
  });
});
