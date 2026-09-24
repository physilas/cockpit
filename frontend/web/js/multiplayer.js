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

const GRUND_TEXT_MAP = {
  trudeln:"Trudeln", kollision:"Kollision",
  uebers_ziel_hinaus:"Übers Ziel hinaus", zu_schnell_gelandet:"Zu schnell gelandet",
  notlandung:"Notlandung", pflichtfelder_nicht_erfuellt:"Pflichtfelder nicht erfüllt",
  flugzeuge_uebrig:"Flugzeuge übrig", fahrwerk_unvollstaendig:"Fahrwerk unvollständig",
  landeklappen_unvollstaendig:"Landeklappen unvollständig", nicht_waagerecht:"Nicht waagerecht",
  feld_ungueltig:"Feld ungültig", falsche_reihenfolge:"Falsche Reihenfolge",
  nicht_genug_kaffee:"Nicht genug Kaffee",
  kein_neuwurf_plaettchen:"Kein Neuwurf-Plättchen verfügbar",
  noch_nicht_alle_wuerfel_platziert:"Noch nicht alle Würfel platziert",
  nicht_am_zug:"Nicht am Zug",
};
const FELD_LAYOUT = [
  {ziel:"ruder",       snap:"ruder",       zugriff:["pilot","kopilot"], pflicht:true, art:"farbpaar"},
  {ziel:"triebwerk",   snap:"triebwerk",   zugriff:["pilot","kopilot"], pflicht:true, art:"farbpaar"},
  {ziel:"funk",        snap:"funk_pilot",  zugriff:["pilot"],           slots:1},
  {ziel:"funk",        snap:"funk_kopilot",zugriff:["kopilot"],         slots:2},
  {ziel:"fahrwerk",   snap:"fahrwerk",    zugriff:["pilot"],           slots:3, zahlen:[[1,2],[3,4],[5,6]]},
  {ziel:"landeklappe",snap:"landeklappe", zugriff:["kopilot"],         slots:4, zahlen:[[1,2],[2,3],[4,5],[5,6]]},
  {ziel:"bremse",      snap:"bremse",      zugriff:["pilot"],           slots:3, zahlen:[[2],[4],[6]]},
  {ziel:"konzentration",snap:"konzentration",zugriff:["pilot","kopilot"],slots:3},
];
const LABEL = {ruder:"Ruder",triebwerk:"Trieb.",funk:"Funk",
  fahrwerk:"Fahrw.",landeklappe:"Klappen",bremse:"Bremse",konzentration:"Konz."};

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
  ["screen-menu","screen-host","screen-join"].forEach(s => {
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
  const rawZ = pyToJs(bridge.neues_spiel());
  document.getElementById("screen-host").classList.add("versteckt");
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
function hostAktion(msg) {
  if (!bridge || !pyodideReady) return;
  let raw;
  try {
    if (msg.typ === "platziere") {
      const r = pyToJs(bridge.platziere(
        msg.besitzer, msg.wuerfel_index, msg.ziel,
        msg.index ?? null, msg.funk_feld ?? 0
      ));
      if (conn?.open) conn.send(JSON.stringify({
        typ:"ergebnis", erfolg:r.ergebnis.erfolg,
        meldung: r.ergebnis.erfolg ? r.ergebnis.meldung : grundText(r.ergebnis.grund)
      }));
      raw = r.zustand;
    } else if (msg.typ === "trinke_kaffee") {
      const r = pyToJs(bridge.trinke_kaffee(msg.besitzer, msg.wuerfel_index, msg.delta));
      raw = r.zustand;
    } else if (msg.typ === "rundenende") {
      const r = pyToJs(bridge.rundenende());
      if (r.ergebnis.erfolg && r.zustand.status === "laeuft") {
        bridge.wuerfeln_fuer_runde();
        raw = pyToJs(bridge.zustand());
      } else {
        raw = r.zustand;
      }
    } else if (msg.typ === "neues_spiel") {
      raw = pyToJs(bridge.neues_spiel());
      neuwurfUiReset();

    // ── Neuwurf: zwei-Schritt-Choreografie, siehe Kommentar bei neuwurfUi ──
    } else if (msg.typ === "neuwurf_start") {
      const z = pyToJs(bridge.zustand());
      if (neuwurfUi.phase === 0 && z.neuwurf_plaettchen > 0 && z.status === "laeuft") {
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
  } catch(e) { console.error(e); return; }
  if (raw) sendState(raw);
}

// ── Eigene Aktion (vom aktuellen Gerät ausgelöst) ────────────────────────────
function meineAktion(msg) {
  msg.besitzer = myRole;
  if (myRole === "pilot") {
    hostAktion(msg);
  } else {
    if (conn?.open) conn.send(JSON.stringify(msg));
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
      const msg = JSON.parse(raw);
      hostAktion(msg);
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
      document.getElementById("screen-join").classList.add("versteckt");
      document.getElementById("spiel-header").classList.remove("versteckt");
      document.getElementById("spiel-ui").classList.remove("versteckt");
      document.getElementById("meine-rolle-badge").textContent = "Co-Pilot";
      document.getElementById("meine-rolle-badge").className = "meine-rolle-badge kopilot";
    });
    conn.on("data", raw => {
      const msg = JSON.parse(raw);
      if (msg.typ === "zustand" && msg.zustand) {
        aktuellerZustand = msg.zustand;
        neuwurfUi = msg.neuwurf || { phase: 0, initiator: null, initiatorAuswahl: [], partnerAuswahl: [] };
        render(msg.zustand);
      }
      if (msg.typ === "ergebnis") {
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
function aeroSkalaHTML(b,o) {
  const bg=Math.floor(b),og=Math.floor(o);
  let html = '<div class="skala-leiste">';
  for (let n=2;n<=12;n++) {
    html += `<span class="skala-zahl">${n}</span>`;
    if (n < 12) {
      if (n === bg) html += '<span class="skala-sep skala-sep-blau"></span>';
      if (n === og) html += '<span class="skala-sep skala-sep-orange"></span>';
      if (n !== bg && n !== og) html += '<span class="skala-luecke"></span>';
    }
  }
  html += '</div>';
  return html;
}
// Bremsen-Marker-Skala, gleiches Prinzip, mit einem roten Balken an der
// aktuellen Bremsstärke.
function bremsSkalaHTML(bs) {
  let html = '<div class="skala-leiste">';
  if (bs < 2) html += '<span class="skala-sep skala-sep-rot"></span>';
  for (let n=2;n<=6;n++) {
    html += `<span class="skala-zahl">${n}</span>`;
    if (n < 6) {
      if (n === bs) html += '<span class="skala-sep skala-sep-rot"></span>';
      else html += '<span class="skala-luecke"></span>';
    }
  }
  html += '</div>';
  return html;
}
function kaffeeHTML(n) {
  return Array.from({length:3},(_,i)=>`<span class="ressourcen-box${i<n?" gefuellt":""}">${i<n?"☕":""}</span>`).join("");
}
function neuwurfHTML(n) {
  return n>0?Array.from({length:n},()=>'<span class="ressourcen-box gefuellt">🔄</span>').join("")
           :'<span class="ressourcen-box"></span>';
}

const TRACK_UNIT_PX = 26;
// 7 statt 6 Einheiten: 6 echte 1000-ft-Schritte (6000->0) PLUS ein
// zusätzliches "Bereitschafts"-Feld, damit 0 ft noch als 1 blaues Feld
// angezeigt wird (S.9/S.10: "Perfektes Timing" ist erst erreicht, wenn
// Höhe UND Entfernung gleichzeitig bei ihrem letzten Feld stehen).
const ALTITUDE_MAX_UNITS = 7;

function setzeGauge(prefix, ownMax, remaining, totalHeight, markerY) {
  const used = ownMax - remaining;

  document.getElementById(`${prefix}-track`).style.height = totalHeight + "px";

  const fill = document.getElementById(`${prefix}-fill`);
  fill.style.bottom = (totalHeight - markerY) + "px";
  fill.style.height = (remaining * TRACK_UNIT_PX) + "px";

  // Das unterste ("bereits verbrauchte") Feld unterhalb des Markers wurde
  // entfernt, da es keine zusätzliche Information trägt.
  const usedEl = document.getElementById(`${prefix}-used`);
  if (usedEl) usedEl.classList.remove("sichtbar");

  return used;
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
  const laenge = z.laenge || 1;
  // Auch die Entfernung bekommt das gleiche "+1"-Bereitschaftsfeld wie die
  // Höhe, damit "angekommen" (Entfernung 0) ebenfalls als 1 blaues Feld
  // erscheint - beide Leisten zeigen "1 blaues Feld" exakt im selben
  // Moment: wenn Höhe UND Entfernung beide ihr letztes reales Feld
  // erreicht haben (S.9 "Perfektes Timing").
  const distanzEinheiten = laenge + 1;
  const maxGlobal = Math.max(ALTITUDE_MAX_UNITS, distanzEinheiten);
  const totalHeight = maxGlobal * TRACK_UNIT_PX; // kein zusätzliches Feld mehr für die verbrauchte Spur
  const markerY = totalHeight;

  document.getElementById("tracks-marker").style.top = markerY + "px";

  setzeGauge("altitude", ALTITUDE_MAX_UNITS, z.hoehe / 1000 + 1, totalHeight, markerY);
  document.getElementById("s-hoehe-label").textContent = z.hoehe + " ft";
  renderAltitudeLabels(markerY, z.hoehe);

  const distUsed = setzeGauge("distance", distanzEinheiten, z.entfernung + 1, totalHeight, markerY);
  document.getElementById("s-entfernung-label").textContent = "Entf. " + z.entfernung;

  const obstaclesEl = document.getElementById("distance-obstacles");
  obstaclesEl.innerHTML = "";
  (z.flugzeuge || []).forEach((count, i) => {
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

// Höhen-Zahlen: mitlaufende Skala. Das unterste (Marker-nächste) Feld zeigt
// immer die AKTUELLE Höhe, darüber in 1000-ft-Schritten absteigend bis 0 ft;
// Felder mit negativem Wert bleiben leer ("nichts") - nach jeder Runde
// rutscht so oben ein Feld "aus dem Bild" und unten rückt die neue
// (niedrigere) aktuelle Höhe an den Marker heran. Bei 2000 ft sitzt
// zusätzlich ein Neuwurf-Plättchen-Symbol - die Engine vergibt dort
// automatisch ein Plättchen (siehe backend/spielplan.py: NEUWURF_HOEHEN);
// sobald diese Höhe erreicht/unterschritten ist, verschwindet das Symbol
// wieder (bereits eingesammelt).
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
  document.getElementById("s-runde").textContent = z.runde+(z.letzte_runde?" (l.)":"")+(z.warteschleife?" ⟳":"");
  document.getElementById("s-aero").innerHTML  = aeroSkalaHTML(z.aerodynamik_blau,z.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(z.bremsstaerke);
  document.getElementById("s-kaffee-status").innerHTML = kaffeeHTML(z.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfHTML(z.neuwurf_plaettchen);
  renderAttitude(z.fluglage);
  renderTracks(z);

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
  const nBtn=document.getElementById("neuwurf-btn");
  const imNeuwurf = neuwurfUi.phase !== 0;

  if(z.status!=="laeuft") {
    amZug.innerHTML=`<div class="spiel-ende ${z.status}">`+
      (z.status==="gewonnen"?"🎉 Sicher gelandet!":`💥 Verloren – ${grundText(z.verlust_grund)}`)+
      "</div>";
    if(rBtn)rBtn.disabled=true;
    if(nBtn)nBtn.disabled=true;
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
    if(nBtn) { nBtn.disabled=false; nBtn.textContent="✖"; nBtn.title="Neuwurf abbrechen"; }
  } else {
    const ichDran=myRole&&z.am_zug===myRole;
    amZug.textContent=ichDran?"Du bist am Zug ✦":(z.am_zug==="pilot"?"Pilotin":"Co-Pilot")+" ist am Zug …";
    amZug.style.color=ichDran?"var(--gruen)":"var(--muted)";
    if(rBtn)rBtn.disabled=!ichDran;
    if(nBtn) { nBtn.disabled=z.neuwurf_plaettchen<=0; nBtn.textContent="🔄"; nBtn.title="Neuwurf-Plättchen einlösen"; }
  }
}

// Ordnet jeden Feld-Layout-Eintrag seinem Bereich auf dem neu geordneten
// Board zu: alle Pilot-Aufgaben (Ruder/Triebwerk-Hälfte, Funk, Fahrwerk,
// Bremse) links in einer Spalte, alle Kopilot-Aufgaben (Ruder/Triebwerk-
// Hälfte, Funk, Landeklappen) rechts in einer Spalte, nur die gemeinsame
// Konzentration (beide Farben) unten in der Mitte neben Wheel + Leisten.
function containerFuerEintrag(e, besitzer) {
  if (e.ziel === "konzentration") {
    return document.getElementById("center-bottom-row");
  }
  if (e.ziel === "landeklappe") {
    return document.getElementById("col-kopilot");
  }
  if (e.ziel === "fahrwerk" || e.ziel === "bremse") {
    return document.getElementById("col-pilot");
  }
  if (e.ziel === "funk") {
    return e.zugriff.includes("pilot")
      ? document.getElementById("col-pilot")
      : document.getElementById("col-kopilot");
  }
  // ruder/triebwerk: Farbpaar, je Hälfte in die passende Spalte.
  return besitzer === "pilot"
    ? document.getElementById("col-pilot")
    : document.getElementById("col-kopilot");
}

function renderBoard(z) {
  const bereiche = ["col-pilot", "col-kopilot", "center-bottom-row"]
    .map(id => document.getElementById(id));
  bereiche.forEach(el => { if (el) el.innerHTML = ""; });
  const felder=z.felder||{};

  FELD_LAYOUT.forEach(e=>{
    if (e.art === "farbpaar") {
      const w = felder[e.snap] || {};
      ["pilot", "kopilot"].forEach(besitzer => {
        const zeile = document.createElement("div");
        zeile.className = "feld-zeile";
        const lbl = document.createElement("span");
        lbl.className = "feld-label";
        lbl.textContent = LABEL[e.ziel] + (e.pflicht ? " *" : "");
        zeile.appendChild(lbl);
        const slots = document.createElement("div");
        slots.className = "feld-slots";
        slots.appendChild(zelle(besitzer, w[besitzer], null, e, z));
        zeile.appendChild(slots);
        containerFuerEintrag(e, besitzer).appendChild(zeile);
      });
      return;
    }

    const board = containerFuerEintrag(e);
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
                       e.ziel==="landeklappe"?z.landeklappen_ausgefahren:
                       e.ziel==="bremse"?z.bremsen_aktiviert:null;
      // Nur Landeklappen und Bremsen müssen strikt der Reihe nach ausgefahren
      // werden - beim Fahrwerk ist jede Reihenfolge erlaubt (S.7).
      const reihenfolgeZaehlt = e.ziel==="landeklappe" || e.ziel==="bremse";
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
  if(wertObj){div.classList.add("belegt",wertObj.besitzer);div.textContent=wertObj.wert;return div;}
  if(e.zahlen&&slotIdx!==null)div.innerHTML=`<small>${e.zahlen[slotIdx].join("/")}</small>`;
  if(gesperrt){div.title="Reihenfolge beachten.";return div;}
  const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft";
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

  werte.forEach((wert,i)=>{
    const wrap=document.createElement("div");
    wrap.className="wuerfel-slot";

    const div=document.createElement("div");
    const verborgen=wert===null;
    div.className="wuerfel"+((!frei[i]||verborgen)?" platziert":"");
    if(verborgen)div.classList.add("partner-wuerfel");
    div.textContent=verborgen?"?":String(wert);

    // Markierung: entweder "für's Platzieren ausgewählt" oder (während
    // eines Neuwurfs) "für den Neuwurf markiert" - nie beides gleichzeitig.
    const istPlatzierAus = !imNeuwurf && ausgewaehlterWuerfel?.besitzer===besitzer&&ausgewaehlterWuerfel?.index===i;
    const istNeuwurfMarkiert = istNeuwurfAktiv && istMeins && neuwurfAuswahl?.includes(i);
    if(istPlatzierAus || istNeuwurfMarkiert) div.classList.add("ausgewaehlt");

    const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft";
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

  document.getElementById("btn-host").addEventListener("click", starteHosting);
  document.getElementById("btn-join").addEventListener("click", () => showScreen("screen-join"));
  document.getElementById("btn-do-join").addEventListener("click", () => {
    starte_Beitreten(document.getElementById("join-code-input").value);
  });
  document.getElementById("join-code-input").addEventListener("keydown", e => {
    if (e.key === "Enter") starte_Beitreten(document.getElementById("join-code-input").value);
  });

  document.getElementById("neues-spiel-btn")?.addEventListener("click", () => meineAktion({typ:"neues_spiel"}));
  document.getElementById("rundenende-btn")?.addEventListener("click", () => meineAktion({typ:"rundenende"}));
  document.getElementById("neuwurf-btn")?.addEventListener("click", () => {
    if (!aktuellerZustand) return;
    if (neuwurfUi.phase !== 0) {
      meineAktion({ typ: "neuwurf_cancel" });
      return;
    }
    if (aktuellerZustand.neuwurf_plaettchen <= 0) return;
    ausgewaehlterWuerfel = null;
    meineAktion({ typ: "neuwurf_start" });
  });
  document.getElementById("menue-btn")?.addEventListener("click", () => {
    window.location = "index.html";
  });
});
