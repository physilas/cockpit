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
let isHost=false, guestProtocolReady=false;
let lobby=MultiplayerLobby.create();
let myRole = null;       // "pilot" | "kopilot"
let peer = null;         // PeerJS eigenes Peer-Objekt
let conn = null;         // DataConnection zur Gegenseite
let bridge = null;       // Pyodide-Bridge (nur Host)
let pyodideReady = false;
let partnerConnected = false;
let aktuellerZustand = null;
let rueckgaengigId = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuFuer = null;
let eigeneWuerfelVersteckt = false;

// Der Host sammelt beide Auswahlen und Bestätigungen unabhängig voneinander.
// phase: 0 = geschlossen, 1 = Auswahl, 2 = Ergebnis mit Hervorhebung.
// Nur das Popup erhält während des Neuwurfs beide Würfelpools.
let neuwurfUi = NeuwurfDialog.neuerZustand();
let neuwurfSequence = 0;
let neuwurfTimer = null;

function neuwurfUiReset() {
  clearTimeout(neuwurfTimer);
  neuwurfTimer = null;
  neuwurfUi = NeuwurfDialog.neuerZustand();
  NeuwurfDialog.schliessen();
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
  ["screen-menu","screen-host","screen-join","screen-wait","screen-lobby","landing-selection"].forEach(s => {
    const el = document.getElementById(s);
    if (el) el.classList.toggle("versteckt", s !== id);
  });
}
function setMeldung(t, art) {
  const el = document.getElementById("meldung-leiste");
  if (el) { el.textContent = t||""; el.className = art||""; }
  window.GameExperience?.record(t,art);
}
function setHostStatus(t, cls) {
  const el = document.getElementById("host-status");
  if (el) { el.textContent = t; el.className = "status-pill " + (cls||""); }
}
function setJoinStatus(t, cls) {
  const el = document.getElementById("join-status");
  if (el) { el.textContent = t; el.className = "status-pill " + (cls||""); }
}

function updateRoleBadge(){
  const badge=document.getElementById("meine-rolle-badge");
  badge.textContent=myRole==="pilot"?"Pilotin":myRole==="kopilot"?"Co-Pilot":"";
  badge.className=`meine-rolle-badge ${myRole||""}`;
  document.getElementById("neues-spiel-btn")?.classList.toggle("versteckt",!isHost);
}
function showLobby(){
  choosingLanding=true;neuwurfUiReset();resetVerkehrUi();
  for(const id of ["spiel-header","flight-summary","spiel-ui"])document.getElementById(id).classList.add("versteckt");
  showScreen("screen-lobby");updateRoleBadge();
  const scenario=LANDING_CATALOG.scenarios.find(s=>s.id===lobby.route);
  document.getElementById("lobby-route").textContent=scenario?`${scenario.code} · ${scenario.name}${scenario.modules.includes("realtime") && lobby.timed === false ? " · Ohne Zeitlimit" : ""}${lobby.cards.length?" · "+lobby.cards.map(id=>LANDING_CATALOG.abilities.find(c=>c.id===id)?.name||id).join(", "):""}`:"Wählt gemeinsam eure Landung.";
  document.getElementById("lobby-roles").hidden=!scenario;
  document.getElementById("lobby-connection").textContent=partnerConnected?"Ihr seid verbunden. Beide können Strecke und Rollen auswählen.":"Warte auf Mitspieler …";
  const role=isHost?lobby.hostRole:lobby.guestRole,ready=isHost?lobby.hostReady:lobby.guestReady;
  for(const value of ["pilot","kopilot"])document.getElementById(`lobby-${value}`).setAttribute("aria-pressed",String(role===value));
  document.getElementById("lobby-assignment").textContent=role?`Du: ${role==="pilot"?"Pilotin":"Co-Pilot"} · Mitspieler: ${role==="pilot"?"Co-Pilot":"Pilotin"}`:"Wählt eure Rollen.";
  const button=document.getElementById("lobby-ready");button.disabled=!role;button.textContent=ready?"✓ Bereit – Auswahl zurücknehmen":"Bereit zum Start";
  document.getElementById("lobby-ready-status").textContent=!pyodideReady&&isHost?"Spielregeln werden noch geladen …":lobby.hostReady&&lobby.guestReady?"Start wird vorbereitet …":(isHost?lobby.guestReady:lobby.hostReady)?"Dein Mitspieler ist bereit.":"Der Flug startet erst, wenn ihr beide bereit seid.";
}
function sendLobby(){if(isHost&&conn?.open)conn.send(JSON.stringify({typ:"lobby",lobby}));}
function maybeStartLobby(){
  if(!isHost||!guestProtocolReady||!partnerConnected||!pyodideReady||!MultiplayerLobby.canStart(lobby))return;
  const scenario=LANDING_CATALOG.scenarios.find(s=>s.id===lobby.route);if(!scenario)return;
  lobby.started=true;myRole=lobby.hostRole;gewaehlterFlughafen=scenario.engine_code;gewaehlteKarten=[...lobby.cards];zeitlimit=lobby.timed !== false;
  updateRoleBadge();startGame();
}
function handleLobby(msg,who){
  if(!isHost)return;
  if(msg.typ==="lobby_hello"){guestProtocolReady=msg.version===3;sendLobby();return;}
  if(who==="guest"&&!guestProtocolReady||lobby.started)return;
  try{
    if(msg.typ==="lobby_route"){
      const scenario=LANDING_CATALOG.scenarios.find(s=>s.id===msg.route),cards=msg.cards;
      if(!scenario||!Array.isArray(cards)||new Set(cards).size!==cards.length||cards.length!==scenario.ability_count||!cards.every(id=>LANDING_CATALOG.abilities.some(c=>c.id===id)))return;
      lobby=MultiplayerLobby.route(lobby,scenario.id,cards,msg.timed !== false);
    }else if(msg.typ==="lobby_role")lobby=MultiplayerLobby.role(lobby,who,msg.role);
    else if(msg.typ==="lobby_ready")lobby=MultiplayerLobby.ready(lobby,who,msg.ready,msg.revision);
    else return;
    myRole=lobby.hostRole;showLobby();sendLobby();maybeStartLobby();
  }catch(error){document.getElementById("lobby-ready-status").textContent=error.message;sendLobby();}
}
function lobbyAction(message){if(isHost)handleLobby(message,"host");else if(conn?.open)conn.send(JSON.stringify(message));}

// ── Pyodide / Engine (nur Host) ──────────────────────────────────────────────
let gewaehlterFlughafen = "LOG_YUL_GREEN";
let choosingLanding = false;
let gewaehlteKarten = [];
let playOptions = null, zeitlimit = true;
const landingPicker = Landings.mount(document.getElementById("landing-selection"), {
  mode: "Multiplayer · Lobby",
  startLabel: "Diese Strecke gemeinsam wählen →",
  onBack(){landingPicker.hide();showLobby();},
  onStart(scenario){
    const message={typ:"lobby_route",route:scenario.id,cards:scenario.ability_ids||[],timed:scenario.timed !== false};
    landingPicker.hide();
    if(isHost)handleLobby(message,"host");else conn?.send(JSON.stringify(message));
    showLobby();
  },
});

function waehleLandung() {
  if(!partnerConnected)return;
  if(!choosingLanding){lobby={...lobby,started:false,hostReady:false,guestReady:false};if(isHost)sendLobby();}
  choosingLanding = true;
  neuwurfUiReset();
  resetVerkehrUi();
  for (const id of ["spiel-header", "flight-summary", "spiel-ui"]) document.getElementById(id).classList.add("versteckt");
  showScreen("landing-selection");
  landingPicker.show();

}

async function ladeEngine() {
  const fill = document.getElementById("lade-balken-fill");
  const txt  = document.getElementById("lade-text");
  const setP = p => { if(fill) fill.style.width = p+"%"; };
  try {
    setP(5); txt && (txt.textContent = "Pyodide wird geladen …");
    const pyodide = await loadPyodide({
      indexURL: new URL("vendor/pyodide/0.26.1/",document.baseURI).href
    });
    setP(60); txt && (txt.textContent = "Pakete werden installiert …");
    await pyodide.loadPackage("pyyaml");
    setP(80); txt && (txt.textContent = "Spielregeln werden geladen …");
    pyodide.FS.mkdirTree("/cockpit/backend/landungen");
    for (const [ziel, src] of Object.entries(ENGINE_SRC)) {
      pyodide.FS.mkdirTree("/cockpit/" + ziel.substring(0, ziel.lastIndexOf("/")));
      pyodide.FS.writeFile("/cockpit/" + ziel, src);
    }
    pyodide.runPython(`import sys; sys.path.insert(0, "/cockpit")`);
    bridge = pyodide.pyimport("backend.bridge");
    playOptions = pyodide.pyimport("play_options");
    setP(100); txt && (txt.textContent = "Bereit ✓");
    pyodideReady = true;
    if(partnerConnected){sendLobby();maybeStartLobby();}
  } catch(e) {
    console.error(e);
    if (txt) txt.textContent = "Engine-Fehler: " + e.message;
  }
}

// ── Spielstart (Host) ────────────────────────────────────────────────────────
let initialEngine = null; // Host-local state/RNG; never sent to the partner.
function newEngineGame(sameSeed=false) {
  window.GameExperience?.reset();CockpitLayout.reset();
  const z=sameSeed && initialEngine ? pyToJs(bridge.spiel_laden(initialEngine))
    : pyToJs(playOptions.neues_spiel(gewaehlterFlughafen,JSON.stringify(gewaehlteKarten),zeitlimit));
  initialEngine=String(bridge.spiel_speichern());
  return z;
}
function startGame() {
  resetVerkehrUi();
  const rawZ = newEngineGame();
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
  aktuellerZustand = filteredState(rawZ, myRole);
  render(aktuellerZustand);
  if (conn && conn.open) {
    conn.send(JSON.stringify({
      typ:"zustand",
      role:lobby.guestRole,
      zustand: filteredState(rawZ, lobby.guestRole),
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
  if (pyToJs(bridge.tick()).ergebnis.erfolg) { neuwurfUiReset(); sendState(); return false; }
  if (neuwurfUi.phase !== 0 && !msg.typ?.startsWith('neuwurf_')) return false;
  msg = {...msg, besitzer: absender};
  let raw;
  const zeigeErgebnis = r => {
    if (!r.erfolg && msg.typ === "wirf_verkehrswuerfel") verkehrWurfFehlgeschlagen();
    const meldung = r.erfolg ? r.meldung : grundText(r.grund);
    if (absender === myRole) setMeldung(r.erfolg ? meldung : "Nicht möglich: " + meldung, r.erfolg ? "erfolg" : "fehler");
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
    } else if (msg.typ === "rueckgaengig") {
      const r = pyToJs(bridge.rueckgaengig(msg.besitzer, msg.version));
      zeigeErgebnis(r.ergebnis);
      raw = r.zustand;
    } else if (msg.typ === "verkehr_start") {
      const z = pyToJs(bridge.zustand());
      if (msg.besitzer !== z.am_zug || msg.version !== z.rueckgaengig_version || z.phase !== "vorbereitung" || !z.verkehrswuerfe.length || z.verkehrswuerfel_offen) return false;
      raw = pyToJs(bridge.wuerfeln_fuer_runde());
    } else if (msg.typ === "modul_aktion") {
      const r = pyToJs(bridge.modul_aktion(msg.besitzer, msg.aktion, JSON.stringify(msg.parameter || {})));
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
      if (r.ergebnis.erfolg && r.zustand.status === "laeuft" && !r.zustand.module.includes("realtime")) {
        bridge.wuerfeln_fuer_runde();
        raw = pyToJs(bridge.zustand());
      } else {
        raw = r.zustand;
      }
    } else if (msg.typ === "neues_spiel") {
      if (absender !== myRole) return false;
      resetVerkehrUi();
      raw = newEngineGame(msg.sameSeed === true);
      neuwurfUiReset();

    // ── Gemeinsamer Neuwurf, vom Host einmalig ausgeführt ──
    } else if (msg.typ === "neuwurf_start") {
      const z = pyToJs(bridge.zustand());
      if (neuwurfUi.phase || z.am_zug !== absender || msg.version !== z.rueckgaengig_version || z.neuwurf_plaettchen <= 0 || z.status !== "laeuft" || z.phase !== "platzieren" || z.zusatzaktion || z.kooperation) return false;
      neuwurfUi = NeuwurfDialog.neuerZustand();
      neuwurfUi.phase = 1;
      neuwurfUi.id = ++neuwurfSequence;
      neuwurfUi.wuerfel = {pilot: [...z.pilot_wuerfel], kopilot: [...z.kopilot_wuerfel]};
      NeuwurfDialog.ohneWuerfelBestaetigen(z, neuwurfUi);
      ausgewaehlterWuerfel = kaffeeMenuFuer = null;
      raw = z;
    } else if (["neuwurf_toggle", "neuwurf_confirm", "neuwurf_cancel"].includes(msg.typ)) {
      if (neuwurfUi.phase !== 1 || msg.id !== neuwurfUi.id) return false;
      const z = pyToJs(bridge.zustand());
      if (msg.typ === "neuwurf_toggle") {
        if (neuwurfUi.bestaetigt[absender] || !Number.isInteger(msg.index) || !z[`${absender}_wuerfel_frei`][msg.index]) return false;
        const liste = neuwurfUi.auswahl[absender];
        const pos = liste.indexOf(msg.index);
        if (pos === -1) liste.push(msg.index); else liste.splice(pos, 1);
        neuwurfUi.meldung = "";
      } else if (msg.typ === "neuwurf_cancel") {
        neuwurfUiReset();
      } else {
        if (typeof msg.confirmed !== "boolean") return false;
        neuwurfUi.bestaetigt[absender] = msg.confirmed;
        neuwurfUi.meldung = "";
        if (neuwurfUi.bestaetigt.pilot && neuwurfUi.bestaetigt.kopilot) {
          if (!neuwurfUi.auswahl.pilot.length && !neuwurfUi.auswahl.kopilot.length) {
            neuwurfUiReset();
          } else {
            const r = pyToJs(bridge.benutze_neuwurf(neuwurfUi.auswahl.pilot, neuwurfUi.auswahl.kopilot));
            zeigeErgebnis(r.ergebnis);
            raw = r.zustand;
            if (r.ergebnis.erfolg) {
              neuwurfUi.phase = 2;
              neuwurfUi.vorher = neuwurfUi.wuerfel;
              neuwurfUi.wuerfel = {pilot: [...raw.pilot_wuerfel], kopilot: [...raw.kopilot_wuerfel]};
              const id = neuwurfUi.id;
              neuwurfTimer = setTimeout(() => {
                if (neuwurfUi.id !== id) return;
                neuwurfUiReset();
                sendState();
              }, 2400);
            } else {
              neuwurfUi.bestaetigt = {pilot: false, kopilot: false};
              NeuwurfDialog.ohneWuerfelBestaetigen(z, neuwurfUi);
              neuwurfUi.meldung = grundText(r.ergebnis.grund);
            }
          }
        }
      }
      if (!raw) raw = z;
    }
  } catch(e) { console.error(e); return false; }
  if (raw) sendState(raw);
}

// ── Eigene Aktion (vom aktuellen Gerät ausgelöst) ────────────────────────────
function meineAktion(msg) {
  msg.besitzer = myRole;
  if (isHost) {
    return hostAktion(msg, myRole);
  } else {
    if (!conn?.open) return false;
    conn.send(JSON.stringify(msg));
  }
}

// ── PeerJS: Host aufsetzen ───────────────────────────────────────────────────
function starteHosting() {
  isHost=true;myRole=null;lobby=MultiplayerLobby.create();guestProtocolReady=false;choosingLanding=true;
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
    setHostStatus("Warte auf Mitspieler … Code: " + code, "");
    ladeEngine();
  });

  peer.on("connection", c => {
    if(partnerConnected&&conn?.open){c.close();return;}
    conn = c;
    conn.on("open", () => {
      partnerConnected = true;
      setHostStatus("Mitspieler verbunden ✓", "ok");
      document.getElementById("verbindungs-status")?.classList.add("ok");
      showLobby();sendLobby();
    });
    conn.on("data", raw => {
      try {
        const msg = JSON.parse(raw);
        if(msg&&typeof msg==="object"){
          if(msg.typ?.startsWith("lobby_"))handleLobby(msg,"guest");
          else if(guestProtocolReady)hostAktion(msg,lobby.guestRole);
        }
      } catch (error) {
        console.warn("Ungültige Multiplayer-Nachricht", error);
      }
    });
    conn.on("close", () => {
      partnerConnected=false;guestProtocolReady=false;lobby.guestReady=false;setMeldung("Verbindung zum Mitspieler unterbrochen.", "fehler");
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
  isHost=false;myRole=null;choosingLanding=true;
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
      partnerConnected=true;
      conn.send(JSON.stringify({typ:"lobby_hello",version:3}));
    });
    conn.on("data", raw => {
      let msg;try{msg=JSON.parse(raw);}catch{return;}
      if(msg.typ==="lobby"&&msg.lobby?.version===3){lobby=msg.lobby;myRole=lobby.guestRole;choosingLanding=true;showLobby();return;}
      if (msg.typ === "landung_waehlen") {
        neuwurfUiReset();
        resetVerkehrUi();
        for (const id of ["spiel-header", "flight-summary", "spiel-ui"]) document.getElementById(id).classList.add("versteckt");
        showScreen("screen-wait");
      }
      if (msg.typ === "zustand" && msg.zustand && ["pilot","kopilot"].includes(msg.role)) {
        myRole=msg.role;choosingLanding=false;updateRoleBadge();
        showScreen(null);
        document.getElementById("spiel-header").classList.remove("versteckt");
        document.getElementById("spiel-ui").classList.remove("versteckt");
        aktuellerZustand = msg.zustand;
        neuwurfUi = msg.neuwurf || NeuwurfDialog.neuerZustand();
        if (neuwurfUi.phase) ausgewaehlterWuerfel = kaffeeMenuFuer = null;
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
function kaffeeHTML(n) {
  return Array.from({length:3},(_,i)=>`<span class="ressourcen-box${i<n?" gefuellt":""}">${i<n?"☕":""}</span>`).join("");
}

function bindeNeuwurfTokens(z) {
  document.querySelectorAll("#s-neuwurf .reroll-token").forEach(token => {
    const darfStarten = myRole && z.am_zug === myRole;
    token.disabled = z.neuwurf_plaettchen <= 0 || z.status !== "laeuft" || z.phase !== "platzieren" || Boolean(z.zusatzaktion || z.kooperation) || (neuwurfUi.phase === 0 && !darfStarten);
    token.title = neuwurfUi.phase === 0 ? "Neuwurf starten" : "Neuwurf abbrechen";
    token.setAttribute("aria-label", `${token.title} · ${z.neuwurf_plaettchen} Plättchen`);
    token.addEventListener("click", () => {
      if (neuwurfUi.phase !== 0) {
        meineAktion({ typ: "neuwurf_cancel", id: neuwurfUi.id });
        return;
      }
      ausgewaehlterWuerfel = null;
      meineAktion({ typ: "neuwurf_start", version: z.rueckgaengig_version });
    });
  });
}

// Jede Leiste zeigt nur noch ihre aktuell sichtbaren Felder. So bleiben
// keine leeren Kacheln oberhalb der Entfernung bzw. Höhe zurück.
let TRACK_UNIT_PX = 36;
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
  TRACK_UNIT_PX = CockpitLayout.unit(z);
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
  const motion=window.GameExperience?.begin(z);
  if (rueckgaengigId !== z.rueckgaengig_id) {
    if (rueckgaengigId !== null) eigeneWuerfelVersteckt = true;
    rueckgaengigId = z.rueckgaengig_id;
    ausgewaehlterWuerfel = kaffeeMenuFuer = null;
    neuwurfUiReset(); FlightModules.reset(); resetVerkehrUi();
  }
  document.getElementById("rueckgaengig-btn").disabled = !z.rueckgaengig_moeglich || neuwurfUi.phase !== 0;
  Landings.updateFlight(z);
  document.getElementById("s-runde").textContent = z.letzte_runde
    ? "🛬 Landung"
    : "Runde " + z.runde + (z.warteschleife ? " ⟳" : "");
  renderAeroSkala(z.aerodynamik_blau,z.aerodynamik_orange);
  FlightModules.renderBrakes(z.bremsstaerke);
  document.getElementById("s-kaffee-status").innerHTML = kaffeeHTML(z.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = FlightModules.rerollHTML(z.neuwurf_plaettchen);
  bindeNeuwurfTokens(z);
  renderAttitude(z.fluglage);
  renderTracks(z);
  renderVerkehr(z, TRACK_UNIT_PX, myRole === z.am_zug, () => {
    return meineAktion({ typ: "wirf_verkehrswuerfel" });
  }, () => meineAktion({typ:"verkehr_start",version:z.rueckgaengig_version}));

  if(myRole) {
    const b=document.getElementById("meine-rolle-badge");
    b.textContent=myRole==="pilot"?"Pilotin":"Co-Pilot";
    b.className="meine-rolle-badge "+myRole;
  }

  renderBoard(z);
  renderWuerfel("pilot",z);
  renderWuerfel("kopilot",z);
  renderNeuwurf(z);
  FlightModules.render(z, {
    role:myRole, selected:eigeneWuerfelVersteckt ? null : ausgewaehlterWuerfel, reroll:neuwurfUi.phase !== 0,
    conceal() {eigeneWuerfelVersteckt = true; ausgewaehlterWuerfel = null; render(aktuellerZustand);},
    onPlace(role, die, target, index) {ausgewaehlterWuerfel = null; meineAktion({typ:'platziere', wuerfel_index:die, ziel:target, index});},
    onAction(role, action, params) {ausgewaehlterWuerfel = null; meineAktion({typ:'modul_aktion', aktion:action, parameter:params});},
    onTick:isHost ? () => {if (!choosingLanding) {const r = pyToJs(bridge.tick()); if (r.ergebnis.erfolg) {neuwurfUiReset(); sendState(r.zustand);}}} : null,
  });

  const amZug=document.getElementById("am-zug-anzeige");
  const rBtn=document.getElementById("rundenende-btn");
  const imNeuwurf = neuwurfUi.phase !== 0;

  if(z.status!=="laeuft") {
    GameDialogs.result(z,z.status==="gewonnen"?"Eure Crew hat die Landung geschafft.":grundText(z.verlust_grund));
    amZug.innerHTML=`<div class="spiel-ende ${z.status}">`+
      (z.status==="gewonnen"?"🎉 Sicher gelandet!":`💥 Verloren – ${grundText(z.verlust_grund)}`)+
      "</div>";
    if(rBtn)rBtn.disabled=true;
  } else if (z.phase !== "platzieren") {
    amZug.textContent = z.phase === "vorbereitung" ? "Bereit zum Würfeln" : myRole === z.am_zug
      ? "Zuerst schwarze Würfel werfen"
      : `${z.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"} wirft die schwarzen Würfel …`;
    amZug.style.color = "var(--muted)";
    if(rBtn)rBtn.disabled=true;
  } else if (z.zusatzaktion || z.kooperation) {
    const role = z.zusatzaktion?.rolle || z.kooperation.wartet_auf;
    amZug.textContent = `Zusatzaktion: ${role === 'pilot' ? 'Pilotin' : 'Co-Pilot'}`;
    if (rBtn) rBtn.disabled = true;
  } else if (imNeuwurf) {
    amZug.textContent = neuwurfUi.phase === 2 ? "↻ Neu gewürfelt!" : neuwurfUi.bestaetigt[myRole] ? "↻ Warte auf die zweite Bestätigung …" : "↻ Wähle deine Würfel im Popup";
    amZug.style.color = "var(--muted)";
    if(rBtn)rBtn.disabled=true;
  } else {
    const ichDran=myRole&&z.am_zug===myRole;
    amZug.textContent=ichDran?"Du bist am Zug ✦":(z.am_zug==="pilot"?"Pilotin":"Co-Pilot")+" ist am Zug …";
    amZug.style.color=ichDran?"var(--gruen)":"var(--muted)";
    if(rBtn)rBtn.disabled=!ichDran;
  }
  window.GameExperience?.finish(z,motion,{reroll:neuwurfUi.phase!==0});
  CockpitLayout.fit(z, () => render(aktuellerZustand));
  if(z.status==="laeuft")GameDialogs.result(z,"");
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
  document.getElementById("bremse-reihe").classList.toggle("versteckt", z.module.includes("ice"));
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
  FlightModules.identifyField(div,e,slotIdx,fixBesitzer);
  if(wertObj){CockpitControls.placedDie(div,wertObj);return div;}
  if(e.zahlen&&slotIdx!==null)div.innerHTML=`<small>${e.zahlen[slotIdx].join("/")}</small>`;
  if(gesperrt){div.title="Reihenfolge beachten.";return div;}
  const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft"&&z.phase==="platzieren"&&!z.zusatzaktion&&!z.kooperation;
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

    const istPlatzierAus = !imNeuwurf && ausgewaehlterWuerfel?.besitzer===besitzer&&ausgewaehlterWuerfel?.index===i;
    if(istPlatzierAus) div.classList.add("ausgewaehlt");

    const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft"&&z.phase==="platzieren"&&!z.zusatzaktion&&!z.kooperation;
    if(!imNeuwurf && istMeins&&frei[i]&&!verborgen&&ichDran){
      div.addEventListener("click",()=>{
        ausgewaehlterWuerfel=istPlatzierAus?null:{besitzer,index:i};
        kaffeeMenuFuer=null;
        render(z);
      });
    }
    wrap.appendChild(div);

    if(!imNeuwurf && istMeins&&istPlatzierAus&&frei[i]&&!verborgen&&z.kaffeetassen>0){
      const kb=document.createElement("button");
      kb.textContent="☕";
      kb.className="coffee-open";kb.setAttribute("aria-label",`Würfel ${wert} mit Kaffee ändern`);
      kb.addEventListener("click",ev=>{
        ev.stopPropagation();
        const deltas=Array.from({length:7},(_,i)=>i-3).filter(delta=>delta&&Math.abs(delta)<=z.kaffeetassen&&wert+delta>=1&&wert+delta<=6);
        CockpitControls.coffee({value:wert,deltas,owner:besitzer,onApply:delta=>meineAktion({typ:"trinke_kaffee",wuerfel_index:i,delta})});
      });wrap.appendChild(kb);
    }
    container.appendChild(wrap);
  });
}

function renderNeuwurf(z) {
  NeuwurfDialog.render(z, neuwurfUi, {
    role: myRole,
    onToggle(rolle, index) { meineAktion({typ: "neuwurf_toggle", id: neuwurfUi.id, index}); },
    onConfirm(rolle) { meineAktion({typ: "neuwurf_confirm", id: neuwurfUi.id, confirmed: !neuwurfUi.bestaetigt[myRole]}); },
    onCancel() { meineAktion({typ: "neuwurf_cancel", id: neuwurfUi.id}); },
  });
}

// ── Init ─────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  document.getElementById("lobby-route-change").onclick=waehleLandung;
  for(const role of ["pilot","kopilot"])document.getElementById(`lobby-${role}`).onclick=()=>lobbyAction({typ:"lobby_role",role});
  document.getElementById("lobby-ready").onclick=()=>lobbyAction({typ:"lobby_ready",ready:!(isHost?lobby.hostReady:lobby.guestReady),revision:lobby.revision});
  const params = new URLSearchParams(window.location.search);
  const joinCode = params.get("join");

  document.getElementById("btn-host").addEventListener("click", starteHosting);
  document.getElementById("btn-join").addEventListener("click", () => showScreen("screen-join"));
  document.getElementById("btn-do-join").addEventListener("click", () => {
    starte_Beitreten(document.getElementById("join-code-input").value);
  });
  document.getElementById("join-code-input").addEventListener("keydown", e => {
    if (e.key === "Enter") starte_Beitreten(document.getElementById("join-code-input").value);
  });

  GameDialogs.connect({
    canRestart:()=>isHost,
    confirmMainText:'Die Verbindung zur gemeinsamen Partie wird beendet.',
    onRestart(options){GameDialogs.reset();meineAktion({typ:'neues_spiel',sameSeed:options.sameSeed===true});},
    onMainMenu(){window.location='index.html';},
    onResume(){if(aktuellerZustand)render(aktuellerZustand);},
  });
  document.getElementById("neues-spiel-btn")?.addEventListener("click",()=>GameDialogs.menu());
  document.getElementById("rundenende-btn")?.addEventListener("click", () => meineAktion({typ:"rundenende"}));
  document.getElementById("rueckgaengig-btn")?.addEventListener("click", () => document.dispatchEvent(new Event("cockpit-undo")));
  document.addEventListener("cockpit-undo", () => {
    if (neuwurfUi.phase !== 0 || !aktuellerZustand?.rueckgaengig_moeglich) return;
    meineAktion({typ:"rueckgaengig",version:aktuellerZustand.rueckgaengig_version});
  });
  document.getElementById("menue-btn")?.addEventListener("click", () => {
    GameDialogs.menu();
  });
  if (joinCode) {
    showScreen("screen-join");
    document.getElementById("join-code-input").value = joinCode;
    starte_Beitreten(joinCode);
  }
});

window.CockpitUpdateHooks={canApply:()=>!aktuellerZustand&&!conn?.open,async prepare(){if(aktuellerZustand||conn?.open)throw new Error("Bitte zuerst die Multiplayer-Partie verlassen.");}};
