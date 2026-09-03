/*
 * Cockpit – Multiplayer (PeerJS, kein Server nötig)
 *
 * Host (Pilotin): lädt Pyodide + führt die Spiellogik aus.
 *                 Generiert einen 6-Zeichen-Code und zeigt einen QR-Code.
 * Partner (Co-Pilot): verbindet sich über den Code, braucht kein Pyodide.
 *
 * Kommunikation: WebRTC DataChannel via peerjs.com (kostenloser Relay-Server).
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
const LABEL = {ruder:"Ruder",triebwerk:"Triebwerke",funk:"Funk",
  fahrwerk:"Fahrwerk",landeklappe:"Landeklappe",bremse:"Bremse",konzentration:"Konzentration"};

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
let neuwurfOffen = false;
let neuwurfAuswahl = {pilot: new Set(), kopilot: new Set()};

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
    conn.send(JSON.stringify({typ:"zustand", zustand: filteredState(rawZ, "kopilot")}));
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
    } else if (msg.typ === "benutze_neuwurf") {
      const r = pyToJs(bridge.benutze_neuwurf(msg.pilot_indizes||[], msg.kopilot_indizes||[]));
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
    // Partner sendet an Host
    if (conn?.open) conn.send(JSON.stringify(msg));
  }
}

// ── PeerJS: Host aufsetzen ───────────────────────────────────────────────────
function starteHosting() {
  myRole = "pilot";
  showScreen("screen-host");
  const code = genCode();
  document.getElementById("host-code").textContent = code;

  // QR-Code generieren
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
    ladeEngine();  // parallel laden
  });

  peer.on("connection", c => {
    conn = c;
    conn.on("open", () => {
      partnerConnected = true;
      setHostStatus("Co-Pilot verbunden ✓", "ok");
      document.getElementById("verbindungs-status")?.classList.add("ok");
      if (pyodideReady) startGame();
      // else: startGame() called from ladeEngine() when ready
    });
    conn.on("data", raw => {
      const msg = JSON.parse(raw);
      hostAktion(msg);  // Host verarbeitet Partner-Aktionen
    });
    conn.on("close", () => {
      setMeldung("Verbindung zum Co-Piloten unterbrochen.", "fehler");
    });
  });

  peer.on("error", e => {
    if (e.type === "unavailable-id") {
      // Code bereits vergeben – neuen generieren
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

// ── Rendering (identisch mit app.js) ────────────────────────────────────────
function aeroSkalaHTML(b,o) {
  const bg=Math.floor(b),og=Math.floor(o),t=[];
  for(let n=2;n<=12;n++){t.push(n);if((n===bg||n===og)&&n<12)t.push('<span class="trenner">|</span>');}
  return t.join(" ");
}
function bremsSkalaHTML(bs) {
  const t=[];
  if(bs<2)t.push('<span class="trenner">|</span>');
  for(let n=2;n<=6;n++){t.push(n);if(n===bs)t.push('<span class="trenner">|</span>');}
  return t.join(" ");
}
function kaffeeHTML(n) {
  return Array.from({length:3},(_,i)=>`<span class="ressourcen-box${i<n?" gefuellt":""}">${i<n?"☕":""}</span>`).join("");
}
function neuwurfHTML(n) {
  return n>0?Array.from({length:n},()=>'<span class="ressourcen-box gefuellt">🔄</span>').join("")
           :'<span class="ressourcen-box"></span>';
}

function render(z) {
  if(!z)return;
  document.getElementById("s-runde").textContent = z.runde+(z.letzte_runde?" (letzte!)":"")+(z.warteschleife?" ⟳":"");
  document.getElementById("s-hoehe").textContent = z.hoehe;
  document.getElementById("s-entfernung").textContent = z.entfernung;
  document.getElementById("s-fluglage").textContent = (z.fluglage>0?"+":"")+z.fluglage;
  document.getElementById("s-aero").innerHTML  = aeroSkalaHTML(z.aerodynamik_blau,z.aerodynamik_orange);
  document.getElementById("s-brems").innerHTML = bremsSkalaHTML(z.bremsstaerke);
  document.getElementById("s-kaffee").innerHTML  = kaffeeHTML(z.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = neuwurfHTML(z.neuwurf_plaettchen);
  document.getElementById("s-fahrwerk").textContent = z.fahrwerk_ausgefahren.map(v=>v?"🟢":"⚪").join(" ");
  document.getElementById("s-klappen").textContent  = z.landeklappen_ausgefahren.map(v=>v?"🟢":"⚪").join(" ");
  document.getElementById("s-bremsen").textContent  = z.bremsen_aktiviert.map(v=>v?"🟢":"⚪").join(" ");
  const si=Math.max(0,z.laenge-z.entfernung);
  document.getElementById("s-flugzeuge").textContent = z.flugzeuge.slice(si).map(n=>n>0?"✈".repeat(n):"·").join(" | ")||"(frei)";

  // Meine-Rolle-Badge
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

  if(z.status!=="laeuft") {
    amZug.innerHTML=`<div class="spiel-ende ${z.status}">`+
      (z.status==="gewonnen"?"🎉 Sicher gelandet!":`💥 Verloren – ${grundText(z.verlust_grund)}`)+
      "</div>";
    if(rBtn)rBtn.disabled=true;
    if(nBtn)nBtn.disabled=true;
  } else {
    const ichDran=myRole&&z.am_zug===myRole;
    amZug.textContent=ichDran?"Du bist am Zug ✦":(z.am_zug==="pilot"?"Pilotin":"Co-Pilot")+" ist am Zug …";
    amZug.style.color=ichDran?"var(--gruen)":"var(--muted)";
    if(rBtn)rBtn.disabled=!ichDran;
    if(nBtn)nBtn.disabled=z.neuwurf_plaettchen<=0;
  }
}

function renderBoard(z) {
  const board=document.getElementById("cockpit-board");
  board.innerHTML="";
  const felder=z.felder||{};

  FELD_LAYOUT.forEach(e=>{
    const zeile=document.createElement("div");
    zeile.className="feld-zeile";

    const lbl=document.createElement("span");
    lbl.className="feld-label";
    lbl.textContent=LABEL[e.ziel]+(e.pflicht?" *":"");
    zeile.appendChild(lbl);

    const slots=document.createElement("div");
    slots.className="feld-slots";

    if(e.art==="farbpaar") {
      const w=felder[e.snap]||{};
      slots.appendChild(zelle("pilot",  w.pilot,  null,e,z));
      slots.appendChild(zelle("kopilot",w.kopilot,null,e,z));
    } else {
      const werte=felder[e.snap]||Array(e.slots).fill(null);
      const statusArr=e.ziel==="landeklappe"?z.landeklappen_ausgefahren:e.ziel==="bremse"?z.bremsen_aktiviert:null;
      const nx=statusArr?statusArr.indexOf(false):null;
      for(let i=0;i<e.slots;i++) {
        const gesperrt=statusArr!==null&&nx!==-1&&i!==nx;
        slots.appendChild(zelle(null,werte[i],i,e,z,gesperrt));
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

  werte.forEach((wert,i)=>{
    const wrap=document.createElement("div");
    wrap.className="wuerfel-slot";

    const div=document.createElement("div");
    const verborgen=wert===null;
    div.className="wuerfel"+((!frei[i]||verborgen)?" platziert":"");
    if(verborgen)div.classList.add("partner-wuerfel");
    div.textContent=verborgen?"?":String(wert);

    const istAus=ausgewaehlterWuerfel?.besitzer===besitzer&&ausgewaehlterWuerfel?.index===i;
    if(istAus)div.classList.add("ausgewaehlt");

    const ichDran=myRole&&z.am_zug===myRole&&z.status==="laeuft";
    if(istMeins&&frei[i]&&!verborgen&&ichDran){
      div.addEventListener("click",()=>{
        ausgewaehlterWuerfel=istAus?null:{besitzer,index:i};
        kaffeeMenuFuer=null;
        render(z);
      });
    }
    wrap.appendChild(div);

    if(istMeins&&istAus&&frei[i]&&!verborgen&&z.kaffeetassen>0){
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

function renderNeuwurf(z) {
  const panel=document.getElementById("neuwurf-panel");
  panel.innerHTML="";
  if(!neuwurfOffen||z.status!=="laeuft"){panel.classList.add("versteckt");return;}
  panel.classList.remove("versteckt");

  const intro=document.createElement("p");
  intro.textContent=`Neuwurf (${z.neuwurf_plaettchen} Plättchen): wähle deine Würfel zum Neuwerfen:`;
  panel.appendChild(intro);

  // Nur eigene Würfel auswählen
  const g=document.createElement("div");
  g.className="neuwurf-gruppe";
  const werte=z[`${myRole}_wuerfel`];
  const frei =z[`${myRole}_wuerfel_frei`];
  let hat=false;
  werte.forEach((w,i)=>{
    if(!frei[i]||w===null)return;
    hat=true;
    const lbl=document.createElement("label");
    const cb=document.createElement("input");
    cb.type="checkbox";
    cb.checked=neuwurfAuswahl[myRole].has(i);
    cb.addEventListener("change",()=>{if(cb.checked)neuwurfAuswahl[myRole].add(i);else neuwurfAuswahl[myRole].delete(i);});
    lbl.appendChild(cb);
    lbl.append(` Würfel ${i+1} (${w})`);
    g.appendChild(lbl);
  });
  if(!hat){const s=document.createElement("span");s.textContent="(keine unplatzierten Würfel)";g.appendChild(s);}
  panel.appendChild(g);

  const ak=document.createElement("div");
  ak.className="neuwurf-aktionen";
  const ok=document.createElement("button");
  ok.textContent="Neu würfeln ✓";
  ok.addEventListener("click",()=>{
    const pi=[...neuwurfAuswahl.pilot];
    const ki=[...neuwurfAuswahl.kopilot];
    meineAktion({typ:"benutze_neuwurf",pilot_indizes:pi,kopilot_indizes:ki});
    neuwurfOffen=false;
    neuwurfAuswahl={pilot:new Set(),kopilot:new Set()};
  });
  ak.appendChild(ok);
  const ab=document.createElement("button");
  ab.textContent="Abbrechen";
  ab.addEventListener("click",()=>{neuwurfOffen=false;if(aktuellerZustand)render(aktuellerZustand);});
  ak.appendChild(ab);
  panel.appendChild(ak);
}

// ── Init ─────────────────────────────────────────────────────────────────────
window.addEventListener("DOMContentLoaded", () => {
  // Auto-Join aus URL-Parameter ?join=CODE
  const params = new URLSearchParams(window.location.search);
  const joinCode = params.get("join");
  if (joinCode) {
    showScreen("screen-join");
    document.getElementById("join-code-input").value = joinCode;
    starte_Beitreten(joinCode);
    return;
  }

  // Buttons verdrahten
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
    if(!aktuellerZustand||aktuellerZustand.neuwurf_plaettchen<=0)return;
    neuwurfOffen=!neuwurfOffen;
    neuwurfAuswahl={pilot:new Set(),kopilot:new Set()};
    ausgewaehlterWuerfel=null;
    if(aktuellerZustand)render(aktuellerZustand);
  });
});