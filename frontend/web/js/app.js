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
let aiBridge = null;
let playOptions = null;
let ausgewaehlterWuerfel = null;
let kaffeeMenuOffenFuer = null;
let aktuellerZustand = null;
let rueckgaengigId = null;
let gameActive = false, activeScenario = null, menuPausedAt = null, lastSavedKey = "";
// Private, local-only initial state + RNG. Never put this in AI/cloud records.
let pendingResumeSnapshot=null, lastResumeSaveSucceeded=true;
let initialEngine = null;
const resumeKey = "flyteam-resume-v1";

// Pass-&-Play Würfelsichtbarkeit
// null = alle verborgen; "pilot" / "kopilot" = nur diese Seite sichtbar
let diceVisible = null;

// Beide Rollen wählen und bestätigen im gemeinsamen Popup.
let neuwurfUi = NeuwurfDialog.neuerZustand();
let neuwurfTimer = null;

async function ladeEngine() {
  pyodide = await loadPyodide({indexURL: new URL("vendor/pyodide/0.26.1/", document.baseURI).href});
  await pyodide.loadPackage("pyyaml");

  // ENGINE_SRC wird von engine-src.js bereitgestellt (auto-generiert durch build.py)
  pyodide.FS.mkdirTree("/cockpit/backend/landungen");
  for (const [ziel, src] of Object.entries(ENGINE_SRC)) {
    pyodide.FS.mkdirTree("/cockpit/" + ziel.substring(0, ziel.lastIndexOf("/")));
    pyodide.FS.writeFile("/cockpit/" + ziel, src);
  }

  pyodide.runPython(`
import sys
sys.path.insert(0, "/cockpit")
`);
  bridge = pyodide.pyimport("backend.bridge");
  playOptions = pyodide.pyimport("play_options");
  aiBridge = pyodide.pyimport("ai.browser_bridge");
}

function pyToJs(pyResult) {
  return pyResult.toJs({ dict_converter: Object.fromEntries });
}

function syncTeachingClock() {
  if(!Singleplayer.isTeaching()||menuPausedAt===null||!bridge)return;
  const now=Date.now();bridge.uhr_verschieben(Math.max(0,(now-menuPausedAt)/1000));menuPausedAt=now;
}

function spielAktion(action, actor = "human", suppliedDecision = null) {
  syncTeachingClock();
  if (actor === "human" && action.role && !Singleplayer.canControl(action.role)) {
    return {ergebnis: {erfolg: false, grund: "nicht_am_zug"}, zustand: aktuellerZustand};
  }
  const context = Singleplayer.beforeAction(action, actor, suppliedDecision);
  let result;
  if (action.kind === "place") result = bridge.platziere(action.role, action.die, action.target, action.index ?? null, action.radio_index || 0);
  else if (action.kind === "coffee") result = bridge.trinke_kaffee(action.role, action.die, action.delta);
  else if (action.kind === "bonus_place") result = bridge.modul_aktion(action.role, "zusatz_platzieren", JSON.stringify({
    ziel:action.target,index:action.index ?? null,funk_feld:action.radio_index || 0,ziel_besitzer:action.target_owner || action.role}));
  else if (action.kind === "bonus_roll") result = bridge.modul_aktion(action.role, "synchronisation_wuerfeln", "{}");
  else if (action.kind === "bonus_coffee") result = bridge.modul_aktion(action.role, "bonus_kaffee", JSON.stringify({delta:action.delta}));
  else if (["adaptation", "anticipation"].includes(action.kind)) result = bridge.modul_aktion(action.role, action.kind, JSON.stringify({wuerfel_index:action.die}));
  else if (action.kind === "swap_start") result = bridge.modul_aktion(action.role, "kooperation_start", "{}");
  else if (action.kind === "swap_choose") result = bridge.kooperation_waehlen_bestaetigen(action.role, action.die, action.cooperation_id ?? null);
  else if (action.kind === "swap_cancel") result = bridge.modul_aktion(action.role, "kooperation_abbrechen", JSON.stringify({kooperation_id:action.cooperation_id}));
  else if (action.kind === "module_action") result = bridge.modul_aktion(action.role, action.module_action, JSON.stringify(action.parameters));
  else if (action.kind === "round_end") result = bridge.rundenende();
  else throw new Error("Unbekannte Spielaktion.");
  const answer = pyToJs(result);
  Singleplayer.afterAction(context, answer);
  return answer;
}

function spielModulAktion(role, type, params = {}) {
  let action;
  const logicalRole = aktuellerZustand.zusatzaktion?.rolle || aktuellerZustand.kooperation?.wartet_auf || aktuellerZustand.am_zug;
  // Some human card effects are engine-legal off turn. Preserve those moves,
  // while avoiding a fabricated observation/action for the current AI actor.
  const administrative = Singleplayer.active() && role !== logicalRole;
  if (type === "zusatz_platzieren") action = {kind:"bonus_place",role,target:params.ziel,index:params.index,
    radio_index:params.funk_feld,target_owner:params.ziel_besitzer};
  else if (type === "synchronisation_wuerfeln") action = {kind:"bonus_roll",role};
  else if (type === "bonus_kaffee") action = {kind:"bonus_coffee",role,delta:params.delta};
  else if (["adaptation", "anticipation"].includes(type)) action = {kind:type,role,die:params.wuerfel_index};
  else if (type === "kooperation_start") action = {kind:"swap_start",role};
  else if (type === "kooperation_abbrechen") action = {kind:"swap_cancel",role,cooperation_id:params.kooperation_id};
  else if (type === "kooperation_bestaetigen" && aktuellerZustand.kooperation?.auswahl[role] != null)
    action = {kind:"swap_choose",role,die:aktuellerZustand.kooperation.auswahl[role],cooperation_id:params.kooperation_id ?? aktuellerZustand.kooperation.id};
  // Card dialogs can contain several engine steps for one training action.
  // Record those administrative steps without inventing a policy action ID.
  if (!action || administrative) action = {kind:"module_action",role,module_action:type,parameters:params};
  return spielAktion(action);
}

function grundText(code) {
  if (!code) return "";
  return code.split(",").map(k => COCKPIT_SCHEMA.grund_texte[k.trim()] || k.trim()).join(", ");
}

function setzeMeldung(text, art) {
  const el = document.getElementById("meldung-leiste");
  el.textContent = text || "";
  el.className = art || "";
  window.GameExperience?.record(text,art);
}

// Aerodynamik-Skala als horizontale Leiste: eine Zahl je Zelle, an den
// beiden Schwellen (blau = Fahrwerk-Marker, orange = Landeklappen-Marker)
// sitzt statt eines simplen "|" ein kleiner, farbiger vertikaler Balken
// in der jeweiligen Spielerfarbe (S.6/S.7/S.8).
function aeroSkalaHTML(blau, orange) {
  // Schale, Zahlen und Marker teilen denselben Kreismittelpunkt (125, -44).
  // Eine gemeinsame SVG-Geometrie bleibt auf jeder Displaybreite symmetrisch.
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

// Jede Leiste ist nur so hoch wie ihre aktuell sichtbaren Felder. Dadurch
// entstehen weder beim Start noch nach einer Bewegung leere Felder oben.
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
  TRACK_UNIT_PX = CockpitLayout.unit(zustand);
  document.getElementById("altitude-track").style.setProperty("--track-unit-px", TRACK_UNIT_PX + "px");
  document.getElementById("distance-track").style.setProperty("--track-unit-px", TRACK_UNIT_PX + "px");

  const laenge = zustand.laenge || 1;
  const hoehenEinheiten = zustand.hoehe / 1000 + 1; // inklusive des beschrifteten 0-ft-Felds
  // Auch bei Entfernung 0 bleibt das Flughafen-Feld sichtbar.
  const distanzEinheiten = Math.max(0, zustand.entfernung + 1);

  setzeGauge("altitude", hoehenEinheiten);
  document.getElementById("altitude-track").setAttribute("aria-label", `Höhenleiste: ${zustand.hoehe} ft`);
  renderAltitudeLabels(hoehenEinheiten * TRACK_UNIT_PX, zustand.hoehe, zustand.neuwurf_hoehen || []);

  setzeGauge("distance", distanzEinheiten);
  document.getElementById("distance-track").setAttribute("aria-label", `Entfernungsleiste: ${zustand.entfernung} Schritte bis zum Flughafen`);
  renderDistanceLabels(zustand.entfernung, zustand.entfernungswerte);

  renderEntfernungsFlugzeuge(zustand, TRACK_UNIT_PX);
  renderKurven(zustand.kurven_min, zustand.kurven_max, laenge, zustand.entfernung);
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

// Höhen-Zahlen auf der Höhenleiste: KEINE festen Positionen, sondern eine
// "mitlaufende" Skala - das unterste (dem Flugzeug-Marker nächste) Feld
// zeigt immer die AKTUELLE Höhe, darüber in 1000-ft-Schritten absteigend
// bis 0 ft. Sobald ein Feld einen negativen Wert hätte (weil die Partie
// schon weiter fortgeschritten ist als dieses Feld "vorschauen" kann),
// bleibt es leer ("nichts") statt einer Zahl - so rutscht nach jeder Runde
// ein Feld oben "aus dem Bild" und ein neues (niedrigeres) rückt nach unten
// an den Marker heran. Neuwurf-Symbole stammen aus der Flughafen-Konfiguration
// im Zustands-Snapshot; neue Szenarien brauchen keine JS-Änderung.

function renderDistanceLabels(entfernung, feldwerte) {
  const el = document.getElementById("distance-labels");
  if (!el) return;
  el.replaceChildren();
  // Werte kommen aus dem Backend; Fallback für einen älteren Multiplayer-Host.
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


function bindeNeuwurfTokens(zustand) {
  document.querySelectorAll("#s-neuwurf .reroll-token").forEach(token => {
    token.disabled = zustand.neuwurf_plaettchen <= 0 || zustand.status !== "laeuft" || zustand.phase !== "platzieren" || Boolean(zustand.zusatzaktion || zustand.kooperation);
    token.title = neuwurfUi.phase === 0 ? "Neuwurf starten" : "Neuwurf abbrechen";
    token.setAttribute("aria-label", `${token.title} · ${zustand.neuwurf_plaettchen} Plättchen`);
    token.addEventListener("click", toggleNeuwurfPanel);
  });
}

function render(zustand) {
  if (!zustand) return;
  const motion=window.GameExperience?.begin(zustand);
  if (rueckgaengigId !== zustand.rueckgaengig_id) {
    rueckgaengigId = zustand.rueckgaengig_id;
    ausgewaehlterWuerfel = kaffeeMenuOffenFuer = null;
    neuwurfReset(); FlightModules.reset(); resetVerkehrUi();
  }
  aktuellerZustand = zustand;
  document.getElementById("spiel-ui").classList.toggle("has-intern",zustand.module.includes("intern"));
  if (Singleplayer.hasAI()) diceVisible = Singleplayer.visibleRole();
  const feedbackUndo = Singleplayer.canUndoFeedback();
  document.getElementById("rueckgaengig-btn").disabled =
    !(feedbackUndo || zustand.rueckgaengig_moeglich) || neuwurfUi.phase !== 0;
  document.getElementById("rueckgaengig-btn").title = feedbackUndo
    ? "Letzte Bewertung rückgängig machen" : "Letzten Spielschritt rückgängig machen";
  Landings.updateFlight(zustand);

  document.getElementById("s-runde").textContent = zustand.letzte_runde
    ? "🛬 Landung"
    : "Runde " + zustand.runde + (zustand.warteschleife ? " ⟳" : "");
  renderAeroSkala(zustand.aerodynamik_blau, zustand.aerodynamik_orange);
  FlightModules.renderBrakes(zustand.bremsstaerke);
  document.getElementById("s-kaffee-status").innerHTML = kaffeeBoxenHTML(zustand.kaffeetassen);
  document.getElementById("s-neuwurf").innerHTML = FlightModules.rerollHTML(zustand.neuwurf_plaettchen);
  bindeNeuwurfTokens(zustand);

  renderAttitude(zustand.fluglage);
  renderTracks(zustand);
  renderVerkehr(zustand, TRACK_UNIT_PX, true, () => {
    const antwort = pyToJs(bridge.wirf_verkehrswuerfel());
    nachAktion(antwort);
    return antwort.ergebnis.erfolg;
  }, () => render(pyToJs(bridge.wuerfeln_fuer_runde())));
  renderCockpitBoard(zustand);
  renderWuerfel("pilot", zustand);
  renderWuerfel("kopilot", zustand);
  renderNeuwurfPanel(zustand);
  FlightModules.render(zustand, {
    role:Singleplayer.hasAI() ? Singleplayer.visibleRole() : null, selected:diceVisible ? ausgewaehlterWuerfel : null, reroll:neuwurfUi.phase !== 0,
    conceal() {diceVisible = null; ausgewaehlterWuerfel = null; render(aktuellerZustand);},
    onPlace(role, die, target, index) {ausgewaehlterWuerfel = null; nachAktion(spielAktion({kind:"place",role,die,target,index}));},
    onAction(role, action, params) {ausgewaehlterWuerfel = null; nachAktion(spielModulAktion(role, action, params));},
    timerPaused:()=>menuPausedAt!==null,
    onTick() {if (!gameActive || menuPausedAt !== null) return; const r = pyToJs(bridge.tick()); if (r.ergebnis.erfolg) {ausgewaehlterWuerfel = null; neuwurfReset(); nachAktion(r);}},
  });

  const amZugEl = document.getElementById("am-zug-anzeige");
  const rundenendeBtn = document.getElementById("rundenende-btn");

  if (zustand.status !== "laeuft") {
    amZugEl.innerHTML = `<div class="spiel-ende ${zustand.status}">` +
      (zustand.status === "gewonnen"
        ? "🎉 Sicher gelandet!"
        : `💥 Verloren – ${grundText(zustand.verlust_grund)}`) +
      "</div>";
    rundenendeBtn.disabled = true;
  } else if (zustand.phase !== "platzieren") {
    amZugEl.textContent = zustand.phase === "vorbereitung" ? "Bereit zum Würfeln" : "Zuerst schwarze Würfel werfen";
    rundenendeBtn.disabled = true;
  } else if (zustand.zusatzaktion || zustand.kooperation) {
    const role = zustand.zusatzaktion?.rolle || zustand.kooperation.wartet_auf;
    amZugEl.textContent = `Zusatzaktion: ${role === 'pilot' ? 'Pilotin' : 'Co-Pilot'}`;
    rundenendeBtn.disabled = true;
  } else if (neuwurfUi.phase) {
    amZugEl.textContent = "↻ Gemeinsamer Neuwurf";
    rundenendeBtn.disabled = true;
  } else {
    amZugEl.textContent = `Am Zug: ${zustand.am_zug === "pilot" ? "Pilotin" : "Co-Pilot"}`;
    rundenendeBtn.disabled = false;
  }
  window.GameExperience?.finish(zustand,motion,{reroll:neuwurfUi.phase!==0});
  CockpitLayout.fit(zustand, () => render(aktuellerZustand));
  Singleplayer.afterRender(zustand);
  if (gameActive) {
    GameDialogs.result(zustand, zustand.status === "gewonnen" ? "Eure Crew hat die Landung geschafft." : grundText(zustand.verlust_grund));
    persistLastGame();
  }
}

// --- Cockpit-Board (zeigt jedes gelegte Feld; Bremsen/Klappen: nur nächstes frei) ---
const ZIEL_BESCHRIFTUNG = {
  ...Object.fromEntries(COCKPIT_SCHEMA.feld_layout.map(e => [e.ziel, e.label])),
};

function feldZelle(fixierterBesitzer, wertObjekt, slotIndex, eintrag, zustand, gesperrt) {
  const div = document.createElement("div");
  div.className = "feld-zelle";
  if (eintrag?.ziel) div.classList.add(`ziel-${eintrag.ziel}`);
  FlightModules.identifyField(div, eintrag, slotIndex, fixierterBesitzer);

  if (wertObjekt) {
    CockpitControls.placedDie(div, wertObjekt);
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

  const istKlickbar = zustand.status === "laeuft" && zustand.phase === "platzieren" && !zustand.zusatzaktion && !zustand.kooperation && ausgewaehlterWuerfel &&
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
  const antwort = spielAktion({kind: "place", role: ausgewaehlterWuerfel.besitzer,
    die: ausgewaehlterWuerfel.index, target: eintrag.ziel,
    index: brauchtIndex ? slotIndex : null, radio_index: eintrag.ziel === "funk" ? slotIndex : 0});
  ausgewaehlterWuerfel = null;
  diceVisible = null;   // Würfel sofort wieder verbergen
  nachAktion(antwort);
}

// Ordnet Funk/Fahrwerk/Landeklappen (die weiterhin als beschriftete Zeile
// mit Slots dargestellt werden) ihrer Seitenspalte zu. Ruder, Triebwerk,
// Bremse und Konzentration werden weiter unten als Sonderfälle behandelt,
// weil sie im physischen Board nicht in den Seitenspalten liegen, sondern
// in der Mitte (Ruder flankiert das Fluglage-Rad, Triebwerk/Bremse/
// Konzentration sitzen als eigene Reihen darunter).
function containerFuerEintrag(eintrag) {
  if (eintrag.ziel === "landeklappe") {
    return document.getElementById("col-kopilot-felder");
  }
  if (eintrag.ziel === "fahrwerk") {
    return document.getElementById("col-pilot-felder");
  }
  if (eintrag.ziel === "funk") {
    return eintrag.zugriff.includes("pilot")
      ? document.getElementById("col-pilot-felder")
      : document.getElementById("col-kopilot-felder");
  }
  return null;
}

function renderCockpitBoard(zustand) {
  ["col-pilot-felder", "col-kopilot-felder", "schub-reihe", "bremse-reihe", "konzentration-reihe"]
    .forEach(id => { const el = document.getElementById(id); if (el) el.innerHTML = ""; });

  document.getElementById("bremse-reihe").classList.toggle("versteckt", zustand.module.includes("ice"));
  const layout = COCKPIT_SCHEMA.feld_layout;
  const felder = zustand.felder;

  layout.forEach(eintrag => {
    // Ruder: je eine Zelle direkt links/rechts vom Fluglage-Rad, ohne
    // eigenes Label (die Position an sich zeigt schon, wessen Würfel
    // dort hingehört - genau wie auf dem physischen Board).
    if (eintrag.ziel === "ruder") {
      const werte = felder.ruder;
      const pilotSlot = document.getElementById("ruder-slot-pilot");
      const kopilotSlot = document.getElementById("ruder-slot-kopilot");
      pilotSlot.innerHTML = "";
      kopilotSlot.innerHTML = "";
      pilotSlot.appendChild(feldZelle("pilot", werte.pilot, null, eintrag, zustand, false));
      kopilotSlot.appendChild(feldZelle("kopilot", werte.kopilot, null, eintrag, zustand, false));
      return;
    }

    // Triebwerk (Schub): beide Farben nebeneinander in einer eigenen
    // Reihe unterhalb der Aerodynamik-Skala.
    if (eintrag.ziel === "triebwerk") {
      const werte = felder.triebwerk;
      const reihe = document.getElementById("schub-reihe");
      reihe.appendChild(feldZelle("pilot", werte.pilot, null, eintrag, zustand, false));
      const label = document.createElement("span");
      label.className = "inline-label";
      label.textContent = "Schub";
      reihe.appendChild(label);
      reihe.appendChild(feldZelle("kopilot", werte.kopilot, null, eintrag, zustand, false));
      return;
    }

    // Bremse (nur Pilotin) und Konzentration (beide): eigene Reihen unter
    // der Bremsen-Skala, ebenfalls ohne Textlabel.
    if (eintrag.ziel === "bremse" || eintrag.ziel === "konzentration") {
      const reihe = document.getElementById(eintrag.ziel === "bremse" ? "bremse-reihe" : "konzentration-reihe");
      const werte = felder[eintrag.snapshot_key];
      const statusArray = eintrag.ziel === "bremse" ? zustand.bremsen_aktiviert : null;
      const naechsterIndex = statusArray ? statusArray.indexOf(false) : null;
      for (let i = 0; i < eintrag.slots; i++) {
        const gesperrt = statusArray && naechsterIndex !== -1 && i !== naechsterIndex;
        if (statusArray) {
          reihe.appendChild(feldZelleMitLicht(werte[i], i, eintrag, zustand, gesperrt, statusArray));
        } else {
          reihe.appendChild(feldZelle(null, werte[i], i, eintrag, zustand, gesperrt));
        }
      }
      return;
    }

    // Funk, Fahrwerk, Landeklappen: unverändertes Zeilen-mit-Label-Layout,
    // nur in die jeweilige Seitenspalte einsortiert (siehe containerFuerEintrag).
    const board = containerFuerEintrag(eintrag);
    if (!board) return;

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
      eintrag.ziel === "landeklappe"  ? zustand.landeklappen_ausgefahren : null;
    // Nur Landeklappen müssen strikt der Reihe nach ausgefahren werden
    // (S.8) - beim Fahrwerk ist laut Regelheft jede Reihenfolge erlaubt (S.7).
    const reihenfolgeZaehlt = eintrag.ziel === "landeklappe";
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

function renderWuerfel(besitzer, zustand) {
  const container = document.getElementById(`wuerfel-${besitzer}`);
  container.innerHTML = "";

  const werte = zustand[`${besitzer}_wuerfel`];
  const frei  = zustand[`${besitzer}_wuerfel_frei`];
  const istAmZug  = Singleplayer.canControl(besitzer) && zustand.am_zug === besitzer && zustand.status === "laeuft" && zustand.phase === "platzieren" && !zustand.zusatzaktion && !zustand.kooperation;
  const sichtbar  = diceVisible === besitzer;

  const imNeuwurf = neuwurfUi.phase !== 0;
  const zeigeViewBtn = !imNeuwurf && !sichtbar && istAmZug;
  if (zeigeViewBtn) {
    const viewBtn = document.createElement("button");
    viewBtn.className = "view-btn";
    viewBtn.textContent = "◉";
    viewBtn.title = "Würfel anzeigen";
    viewBtn.addEventListener("click", () => {
      diceVisible = besitzer;
      render(aktuellerZustand);
    });
    container.appendChild(viewBtn);
  }

  // Aktive Spielerin bzw. aktiver Spieler kann die offenen Würfel vor dem
  // Weitergeben des Geräts jederzeit wieder verdecken.
  const darfVerbergen = !imNeuwurf && sichtbar && istAmZug;
  if (darfVerbergen) {
    const hideBtn = document.createElement("button");
    hideBtn.className = "hide-btn";
    hideBtn.textContent = "◉";
    hideBtn.title = "Würfel verbergen";
    hideBtn.addEventListener("click", () => {
      diceVisible = null;
      ausgewaehlterWuerfel = null;
      kaffeeMenuOffenFuer = null;
      render(aktuellerZustand);
    });
    container.appendChild(hideBtn);
  }

  werte.forEach((wert, i) => {
    const wrapper = document.createElement("div");
    wrapper.className = "wuerfel-slot";

    const div = document.createElement("div");
    const verberge = frei[i] && !sichtbar;
    div.className = "wuerfel" + (frei[i] ? "" : " platziert") + (verberge ? " verborgen" : "");
    div.textContent = verberge ? "?" : (wert ?? "");

    const istPlatzierAusgewaehlt = !imNeuwurf && sichtbar &&
      ausgewaehlterWuerfel?.besitzer === besitzer && ausgewaehlterWuerfel?.index === i;
    if (istPlatzierAusgewaehlt) div.classList.add("ausgewaehlt");

    if (!imNeuwurf && sichtbar && frei[i] && istAmZug) {
      div.title = "Klicken zum Auswählen, dann ein Feld im Board anklicken.";
      div.addEventListener("click", () => {
        ausgewaehlterWuerfel = istPlatzierAusgewaehlt ? null : { besitzer, index: i };
        kaffeeMenuOffenFuer = null;
        render(zustand);
      });
    }
    wrapper.appendChild(div);

    if (!imNeuwurf && istPlatzierAusgewaehlt && frei[i] && zustand.kaffeetassen > 0) {
      const kaffeeBtn = document.createElement("button");
      kaffeeBtn.textContent = "☕";
      kaffeeBtn.title = "Kaffee einsetzen";
      kaffeeBtn.className="coffee-open";
      kaffeeBtn.setAttribute("aria-label", `Würfel ${wert} mit Kaffee ändern`);
      kaffeeBtn.addEventListener("click", ev => {
        ev.stopPropagation();
        const deltas=bridge.moegliche_kaffee_deltas(besitzer,i).toJs();
        CockpitControls.coffee({value:wert,deltas,owner:besitzer,onApply(delta){
          const answer=spielAktion({kind:"coffee",role:besitzer,die:i,delta});
          nachAktion(answer,{verbirgWuerfel:false});
          if(answer.ergebnis.erfolg){ausgewaehlterWuerfel={besitzer,index:i};render(aktuellerZustand);}
        }});
      });
      wrapper.appendChild(kaffeeBtn);
    }
    container.appendChild(wrapper);
  });
}

// --- Gemeinsames Neuwurf-Popup ---
function neuwurfReset() {
  clearTimeout(neuwurfTimer);
  neuwurfTimer = null;
  neuwurfUi = NeuwurfDialog.neuerZustand();
  NeuwurfDialog.schliessen();
  diceVisible = null;
}

function neuwurfAbbrechen() {
  if (neuwurfUi.phase === 2) return;
  if (Singleplayer.rerollPending()) { Singleplayer.cancelReroll(); return; }
  neuwurfReset();
  render(aktuellerZustand);
}

function toggleNeuwurfPanel() {
  const z = aktuellerZustand;
  if (!z || z.status !== "laeuft" || z.phase !== "platzieren" || z.zusatzaktion || z.kooperation || z.neuwurf_plaettchen <= 0) return;
  if (neuwurfUi.phase) { neuwurfAbbrechen(); return; }
  if (Singleplayer.beginReroll(z.am_zug)) return;
  neuwurfUi = NeuwurfDialog.neuerZustand();
  neuwurfUi.phase = 1;
  neuwurfUi.wuerfel = {pilot: [...z.pilot_wuerfel], kopilot: [...z.kopilot_wuerfel]};
  NeuwurfDialog.ohneWuerfelBestaetigen(z, neuwurfUi);
  ausgewaehlterWuerfel = kaffeeMenuOffenFuer = null;
  diceVisible = null;
  render(z);
}

function neuwurfBestaetigen(rolle) {
  if (neuwurfUi.phase !== 1) return;
  if (Singleplayer.confirmReroll(rolle, neuwurfUi.auswahl[rolle])) return;
  neuwurfUi.bestaetigt[rolle] = !neuwurfUi.bestaetigt[rolle];
  neuwurfUi.meldung = "";
  if (neuwurfUi.bestaetigt.pilot && neuwurfUi.bestaetigt.kopilot) {
    if (!neuwurfUi.auswahl.pilot.length && !neuwurfUi.auswahl.kopilot.length) {
      neuwurfReset();
      setzeMeldung("Alle Würfel behalten. Das Neuwurf-Plättchen bleibt erhalten.", "erfolg");
    } else {
      const antwort = pyToJs(bridge.benutze_neuwurf(neuwurfUi.auswahl.pilot, neuwurfUi.auswahl.kopilot));
      if (antwort.ergebnis.erfolg) {
        neuwurfUi.phase = 2;
        neuwurfUi.vorher = neuwurfUi.wuerfel;
        neuwurfUi.wuerfel = {pilot: [...antwort.zustand.pilot_wuerfel], kopilot: [...antwort.zustand.kopilot_wuerfel]};
        neuwurfTimer = setTimeout(() => { neuwurfReset(); render(aktuellerZustand); }, 2400);
      } else {
        neuwurfUi.bestaetigt = {pilot: false, kopilot: false};
        NeuwurfDialog.ohneWuerfelBestaetigen(aktuellerZustand, neuwurfUi);
        neuwurfUi.meldung = grundText(antwort.ergebnis.grund);
      }
      nachAktion(antwort);
      return;
    }
  }
  render(aktuellerZustand);
}

function renderNeuwurfPanel(zustand) {
  const ui = Singleplayer.hasAI() && neuwurfUi.wuerfel ? {
    ...neuwurfUi,
    wuerfel: {...neuwurfUi.wuerfel, [Singleplayer.aiRole()]: neuwurfUi.wuerfel[Singleplayer.aiRole()].map((v,i) => zustand[`${Singleplayer.aiRole()}_wuerfel_frei`][i] ? null : v)},
    vorher: neuwurfUi.vorher ? {...neuwurfUi.vorher, [Singleplayer.aiRole()]: [null,null,null,null]} : null,
  } : neuwurfUi;
  NeuwurfDialog.render(zustand, ui, {
    role: Singleplayer.rerollRole(),
    onToggle(rolle, index) {
      if (neuwurfUi.phase !== 1 || neuwurfUi.bestaetigt[rolle] || !aktuellerZustand[`${rolle}_wuerfel_frei`][index]) return;
      const liste = neuwurfUi.auswahl[rolle];
      const pos = liste.indexOf(index);
      if (pos === -1) liste.push(index); else liste.splice(pos, 1);
      neuwurfUi.meldung = "";
      render(aktuellerZustand);
    },
    onConfirm: neuwurfBestaetigen,
    onCancel: neuwurfAbbrechen,
  });
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
  if (neuwurfUi.phase) return;
  const antwort = spielAktion({kind: "round_end"});
  if (!antwort.ergebnis.erfolg) {
    setzeMeldung(`Runde kann noch nicht enden: ${grundText(antwort.ergebnis.grund)}`, "fehler");
    render(antwort.zustand);
    return;
  }
  setzeMeldung(antwort.ergebnis.meldung, "erfolg");
  diceVisible = null;
  render(antwort.zustand);
  if (antwort.zustand.status === "laeuft" && !antwort.zustand.module.includes("realtime")) {
    render(pyToJs(bridge.wuerfeln_fuer_runde()));
  }
}

// Start with the whole fitted board visible. Small windows can scroll inside
// the cockpit while the header remains outside the scrolling area.
function spielfeldUntenAusrichten() {
  requestAnimationFrame(() => {
    const main = document.getElementById("spiel-ui");
    if (!main || main.classList.contains("versteckt")) return;
    if (verkehrDialogUi.aktiv) richteVerkehrStreckeAus();
    else if (matchMedia('(max-width: 600px)').matches) main.scrollTop = 0;
    else main.scrollIntoView({block: "start", inline: "nearest", behavior: "auto"});
  });
}

let enginePromise = null;
let navigationVersion = 0;
const landingPicker = Landings.mount(document.getElementById("landing-selection"), {
  mode: "Pass & Play",
  onBack: zurueckZumMenue,
  onStart: neuesSpiel,
});

async function neuesSpiel(scenario, options = {}) {
  if(options.sameSeed && !initialEngine)throw new Error('Der ursprüngliche Zufallszustand ist für diesen Spielstand nicht verfügbar.');
  const version = ++navigationVersion;
  if (!bridge) {
    if (!enginePromise) enginePromise = ladeEngine().catch(error => { enginePromise = null; throw error; });
    await enginePromise;
  }
  if (version !== navigationVersion) return;
  GameDialogs.reset(); menuPausedAt = null; window.GameExperience?.reset();
  resetVerkehrUi();
  ausgewaehlterWuerfel = null;
  kaffeeMenuOffenFuer = null;
  neuwurfReset();
  const zustand = options.sameSeed && initialEngine
    ? pyToJs(bridge.spiel_laden(initialEngine))
    : pyToJs(playOptions.neues_spiel(scenario.engine_code, JSON.stringify(scenario.ability_ids || []), scenario.timed !== false));
  initialEngine = String(bridge.spiel_speichern());
  activeScenario = {...scenario}; gameActive = true; lastSavedKey = "";
  landingPicker.hide();
  document.getElementById("game-header").classList.remove("versteckt");
  document.getElementById("spiel-ui").classList.remove("versteckt");
  setzeMeldung(scenario.practice ? "Übungsflug gestartet. Zusatzmodule und Karteneffekte sind noch inaktiv." : "Neue Partie gestartet.", "erfolg");
  render(zustand);
  spielfeldUntenAusrichten();
}

function zurueckZumMenue() {
  persistLastGame(true);
  gameActive = false; menuPausedAt = null; GameDialogs.reset();
  Singleplayer.stop();
  Singleplayer.hideMenu();
  navigationVersion++;
  neuwurfReset();
  FlightModules.reset();
  resetVerkehrUi();
  landingPicker.hide();
  for (const id of ["game-header", "flight-summary", "spiel-ui", "lade-hinweis"]) document.getElementById(id).classList.add("versteckt");
  document.getElementById("start-menu").classList.remove("versteckt");
  updateResumeButton();
}

window.startPassAndPlay = function() {
  Singleplayer.stop();
  Singleplayer.hideMenu();
  navigationVersion++;
  neuwurfReset();
  FlightModules.reset();
  resetVerkehrUi();
  for (const id of ["start-menu", "game-header", "flight-summary", "spiel-ui", "lade-hinweis"]) document.getElementById(id).classList.add("versteckt");
  landingPicker.show();
};

document.getElementById("neues-spiel-btn").addEventListener("click", () => GameDialogs.menu());
document.getElementById("rundenende-btn").addEventListener("click", rundenendeKlick);
document.getElementById("rueckgaengig-btn").addEventListener("click", () => document.dispatchEvent(new Event("cockpit-undo")));
document.addEventListener("cockpit-undo", () => {
  if (!bridge || neuwurfUi.phase !== 0) return;
  if (Singleplayer.undoFeedback()) return;
  if (!aktuellerZustand?.rueckgaengig_moeglich) return;
  const answer = pyToJs(bridge.rueckgaengig(null, aktuellerZustand.rueckgaengig_version));
  Singleplayer.undo(answer);
  nachAktion(answer);
});
document.getElementById("menue-btn").addEventListener("click", () => GameDialogs.menu());

Singleplayer.connect({
  state: () => aktuellerZustand,
  start: neuesSpiel, execute: spielAktion, showAnswer: nachAktion,
  decision(role, reroll, steps, maxSteps, assistanceVersion = 0, schemaVersion = 1) { syncTeachingClock();return pyToJs(aiBridge.decision(role, JSON.stringify(reroll), steps, maxSteps, assistanceVersion, schemaVersion)); },
  refresh() { render(aktuellerZustand); },
  undoLast() { return pyToJs(bridge.rueckgaengig(null, aktuellerZustand.rueckgaengig_version)); },
  checkpoint() { return String(bridge.spiel_speichern()); },
  pauseTeaching(){if(menuPausedAt===null)menuPausedAt=Date.now();},
  resumeTeaching({restored=false}={}){if(!restored&&menuPausedAt!==null&&bridge)bridge.uhr_verschieben(Math.max(0,(Date.now()-menuPausedAt)/1000));menuPausedAt=null;},
  restoreCheckpoint(raw) { const z=pyToJs(bridge.spiel_laden(raw)); render(z); return z; },
  notify(text) { setzeMeldung(text, "erfolg"); },
  roundComplete() { return ["pilot", "kopilot"].every(role => aktuellerZustand[`${role}_wuerfel_frei`].every(free => !free)); },
  rerollAnimating() { return neuwurfUi.phase === 2; },
  openReroll() {
    neuwurfUi = NeuwurfDialog.neuerZustand(); neuwurfUi.phase = 1;
    neuwurfUi.wuerfel = {pilot: [...aktuellerZustand.pilot_wuerfel], kopilot: [...aktuellerZustand.kopilot_wuerfel]};
    NeuwurfDialog.ohneWuerfelBestaetigen(aktuellerZustand, neuwurfUi);
    ausgewaehlterWuerfel = kaffeeMenuOffenFuer = null; diceVisible = null;
  },
  closeReroll: neuwurfReset,
  rerollMessage(text) { neuwurfUi.meldung = text; render(aktuellerZustand); },
  rerollSelection(role, indices) { neuwurfUi.auswahl[role] = indices; neuwurfUi.bestaetigt[role] = true; },
  applyReroll(selections) { return pyToJs(bridge.benutze_neuwurf(selections.pilot, selections.kopilot)); },
  rerollResult(answer) {
    neuwurfUi.phase = 2; neuwurfUi.vorher = neuwurfUi.wuerfel;
    neuwurfUi.wuerfel = {pilot: [...answer.zustand.pilot_wuerfel], kopilot: [...answer.zustand.kopilot_wuerfel]};
    neuwurfTimer = setTimeout(() => { neuwurfReset(); render(aktuellerZustand); }, 2400);
  },
  mainMenu: zurueckZumMenue,
  hideGame() {
    persistLastGame(true); gameActive = false;
    navigationVersion++; neuwurfReset(); FlightModules.reset(); resetVerkehrUi(); landingPicker.hide();
    for (const id of ["game-header", "flight-summary", "spiel-ui", "lade-hinweis"]) document.getElementById(id).classList.add("versteckt");
  },
});

function updateResumeButton() {
  const button=document.getElementById("resume-last-game");
  try {
    const saved=JSON.parse(localStorage.getItem(resumeKey));
    const route=LANDING_CATALOG.scenarios.find(s=>s.id===saved?.scenario?.id);
    button.hidden=!(saved?.format===1&&route&&saved.engine);
    if(!button.hidden)document.getElementById("resume-last-label").textContent=`${route.code} · Runde ${saved.round}`;
  } catch { button.hidden=true; }
}

function persistLastGame(force=false) {
  if(!gameActive||!bridge||!activeScenario)return;
  if(menuPausedAt!==null){
    if(!Singleplayer.isTeaching())return;
    syncTeachingClock();
  }
  try {
    const state=pyToJs(bridge.zustand());
    if(state.status!=="laeuft") {localStorage.removeItem(resumeKey);updateResumeButton();return;}
    const singleplayer=Singleplayer.backup();
    const key=`${state.rueckgaengig_version}|${state.phase}|${state.am_zug}|${singleplayer?.session?.data_revision}|${JSON.stringify(neuwurfUi)}`;
    if(!force&&key===lastSavedKey)return;
    pendingResumeSnapshot=JSON.stringify({format:1,scenario:activeScenario,round:state.runde,
      engine:String(bridge.spiel_speichern()),initialEngine,singleplayer,reroll:neuwurfUi});
    localStorage.setItem(resumeKey,pendingResumeSnapshot);pendingResumeSnapshot=null;lastResumeSaveSucceeded=true;
    lastSavedKey=key;updateResumeButton();
  } catch(error) { lastResumeSaveSucceeded=false;console.warn("Lokaler Spielstand konnte nicht gesichert werden.",error); }
}

async function resumeLastGame() {
  const button=document.getElementById("resume-last-game");button.disabled=true;
  try {
    const saved=JSON.parse(localStorage.getItem(resumeKey));
    const scenario=LANDING_CATALOG.scenarios.find(s=>s.id===saved?.scenario?.id);
    if(!scenario||saved.format!==1)throw new Error("Dieser Spielstand ist nicht mehr verfügbar.");
    if(!bridge){if(!enginePromise)enginePromise=ladeEngine().catch(e=>{enginePromise=null;throw e;});await enginePromise;}
    gameActive=false;Singleplayer.stop("resume");GameDialogs.reset();menuPausedAt=null;
    window.GameExperience?.reset();
    const state=pyToJs(bridge.spiel_laden(saved.engine));
    initialEngine=typeof saved.initialEngine==='string'?saved.initialEngine:null;
    aktuellerZustand=state;rueckgaengigId=state.rueckgaengig_id;
    await Singleplayer.restore(saved.singleplayer);
    activeScenario=saved.scenario;gameActive=true;lastSavedKey="";
    neuwurfUi=saved.reroll?.phase===1?saved.reroll:NeuwurfDialog.neuerZustand();
    document.getElementById("start-menu").classList.add("versteckt");
    Singleplayer.hideMenu();landingPicker.hide();
    for(const id of ["game-header","spiel-ui"])document.getElementById(id).classList.remove("versteckt");
    render(state);spielfeldUntenAusrichten();
  } catch(error) {document.getElementById("resume-last-label").textContent=error.message;}
  finally {button.disabled=false;}
}

GameDialogs.connect({
  canReplay:()=>Boolean(initialEngine),
  onPause(){Singleplayer.suspend();persistLastGame(true);menuPausedAt=Date.now();},
  onResume(){
    if(menuPausedAt!==null&&bridge)bridge.uhr_verschieben((Date.now()-menuPausedAt)/1000);
    menuPausedAt=Singleplayer.isTeaching()?Date.now():null;lastSavedKey="";Singleplayer.resume();
    if(gameActive&&bridge)render(pyToJs(bridge.zustand()));
  },
  async onRestart(options){
    if(Singleplayer.active())await Singleplayer.restart(options);
    else if(activeScenario)await neuesSpiel(activeScenario,options);
  },
  onMainMenu:zurueckZumMenue,
});
document.getElementById("resume-last-game").onclick=resumeLastGame;
window.addEventListener("pagehide",()=>persistLastGame(true));
window.addEventListener("resize",()=>{if(gameActive&&aktuellerZustand)render(aktuellerZustand);});
updateResumeButton();

if (new URLSearchParams(window.location.search).get("view") === "landings") {
  window.startPassAndPlay();
}

window.CockpitUpdateHooks={
  canApply:()=>!gameActive,
  async prepare(){
    if(gameActive)throw new Error("Bitte zuerst zum Hauptmenü zurückkehren. Dein Spiel wird dabei gesichert.");
    if(pendingResumeSnapshot){localStorage.setItem(resumeKey,pendingResumeSnapshot);pendingResumeSnapshot=null;lastResumeSaveSucceeded=true;}
    if(!lastResumeSaveSucceeded)throw new Error("Der Spielstand konnte nicht gespeichert werden. Bitte zuerst Speicher freigeben oder deine Aufzeichnungen sichern.");
    await Singleplayer.flushForUpdate();
  }
};
