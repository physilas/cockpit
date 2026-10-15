/* Gemeinsame Anzeige der schwarzen Verkehrswürfel für beide Spielmodi.
 * Die Engine liefert Würfe und Zielpositionen; hier werden nur Symbole
 * und die vom jeweiligen Client angebundene Wurfaktion dargestellt. */
function verkehrswuerfelSymbol(wert = null) {
  const el = document.createElement("span");
  el.className = "traffic-die";
  el.setAttribute("aria-hidden", "true");
  if (wert !== null) {
    el.textContent = wert;
    el.removeAttribute("aria-hidden");
  } else {
    el.classList.add("traffic-cube");
    el.innerHTML = '<svg viewBox="0 0 16 16"><path fill="#050607" stroke="#f2f8f4" stroke-width=".8" stroke-linejoin="round" d="M8 1 15 4.5V11.5L8 15 1 11.5V4.5Z M1 4.5 8 8 15 4.5 M8 8V15"/></svg>';
  }
  return el;
}

// Enge, gleichmäßige Formationen statt zufälliger Stapel oder Zähler.
// Links bleiben die Entfernungszahlen, rechts eine eigene Würfelspur frei.
function renderEntfernungsFlugzeuge(z, trackUnit) {
  const container = document.getElementById("distance-obstacles");
  container.replaceChildren();
  (z.flugzeuge || []).forEach((anzahl, i) => {
    const entfernung = z.laenge - 1 - i;
    if (anzahl <= 0 || entfernung > z.entfernung) return;
    const feld = document.createElement("span");
    feld.className = "vtrack-aircraft";
    feld.dataset.distance = entfernung;
    feld.style.top = (entfernung * trackUnit + 8) + "px";
    if (z.flugzeugwuerfel?.[i]) feld.classList.add("with-traffic");
    const label = `${anzahl} ${anzahl === 1 ? "Flugzeug" : "Flugzeuge"} auf Entfernung ${entfernung}`;
    feld.title = label;
    feld.setAttribute("role", "img");
    feld.setAttribute("aria-label", label);
    const gruppe = document.createElement("span");
    gruppe.className = "aircraft-group";
    const zeilen = Math.ceil(anzahl / 3);
    const spalten = Math.ceil(anzahl / zeilen);
    const groesse = Math.min(21, 24 / zeilen);
    gruppe.style.setProperty("--plane-size", `${groesse}px`);
    gruppe.style.setProperty("--formation-factor", 1 + (spalten - 1) * .7);
    gruppe.style.setProperty("--formation-width", `${groesse * (1 + (spalten - 1) * .7)}px`);
    for (let k = 0; k < anzahl; k += spalten) {
      const zeile = document.createElement("span");
      zeile.className = "aircraft-row";
      for (let n = k; n < Math.min(k + spalten, anzahl); n++) {
        const flugzeug = document.createElement("span");
        flugzeug.className = "aircraft-icon";
        flugzeug.textContent = "✈";
        flugzeug.setAttribute("aria-hidden", "true");
        zeile.appendChild(flugzeug);
      }
      gruppe.appendChild(zeile);
    }
    feld.appendChild(gruppe);
    container.appendChild(feld);
  });
}

function animiereVerkehrsFlugzeuge(wuerfe) {
  wuerfe.forEach(wurf => {
    if (wurf.ziel_entfernung === null) return;
    const feld = document.querySelector(`.vtrack-aircraft[data-distance="${wurf.ziel_entfernung}"]`);
    if (!feld) return;
    feld.classList.add("aircraft-arriving");
    const neu = [...feld.querySelectorAll(".aircraft-icon")].at(-1);
    neu.classList.add("aircraft-new");
    feld.querySelector(".aircraft-group").addEventListener("animationend", () => {
      feld.classList.remove("aircraft-arriving");
      neu.classList.remove("aircraft-new");
    }, { once: true });
  });
}

const verkehrDialogUi = {
  key: null, zustand: null, darfWerfen: false, werfen: null,
  aktiv: false, bestaetigt: false, streckeAnsehen: false,
  gesehen: 0, busy: false, timer: null, dialog: null, nebel: null,
};

function resetVerkehrUi() {
  clearTimeout(verkehrDialogUi.timer);
  Object.assign(verkehrDialogUi, {
    key: null, zustand: null, aktiv: false, bestaetigt: false,
    streckeAnsehen: false, gesehen: 0, busy: false, timer: null,
  });
  if (verkehrDialogUi.dialog?.open) verkehrDialogUi.dialog.close();
  setzeVerkehrSperre(false);
}

function setzeVerkehrSperre(aktiv) {
  document.body.classList.toggle("verkehr-aktiv", aktiv);
  document.body.classList.toggle("verkehr-dialog-offen", aktiv && !!verkehrDialogUi.dialog?.open);
  document.querySelectorAll(".board-grid, .dice-tray, #aktionen-leiste, #neuwurf-panel")
    .forEach(el => { el.inert = aktiv; });
  if (verkehrDialogUi.nebel) verkehrDialogUi.nebel.hidden = !aktiv;
}

function positioniereVerkehrDialog() {
  const ui = verkehrDialogUi;
  if (!ui.aktiv || !ui.nebel) return;
  const hoehe = window.visualViewport?.height || window.innerHeight;
  const header = document.querySelector("#game-header:not(.versteckt), #spiel-header:not(.versteckt)");
  const rand = header?.getBoundingClientRect().bottom || 0;
  // Das Cockpit überlappt die Leisten im Layout. Seine Oberkante ist deshalb
  // kein sicherer Nebelbeginn; niemals in die vollständige Leiste hineinragen.
  const strecke = document.getElementById("distance-track");
  const streckenRand = (document.getElementById("tracks-leiste") || strecke)?.getBoundingClientRect().bottom || rand;
  const top = Math.ceil(Math.max(rand, streckenRand, strecke?.getBoundingClientRect().bottom || 0));
  ui.nebel.style.top = `${top}px`;
  if (ui.dialog?.open) {
    ui.dialog.style.maxHeight = `${Math.max(120, hoehe - top - 24)}px`;
    const halb = ui.dialog.getBoundingClientRect().height / 2;
    const mitte = Math.max(top + halb + 12, Math.min(hoehe - halb - 12, (top + hoehe) / 2));
    ui.dialog.style.top = `${mitte}px`;
  }
}

function richteVerkehrStreckeAus() {
  const strecke = document.getElementById("distance-track");
  if (!strecke) return;
  const header = document.querySelector("#game-header:not(.versteckt), #spiel-header:not(.versteckt)");
  const rand = header?.getBoundingClientRect().bottom || 0;
  const leiste = (strecke.closest(".vtrack-wrap") || strecke).getBoundingClientRect();
  if (leiste.top < rand || leiste.bottom > (window.visualViewport?.height || window.innerHeight)) {
    window.scrollBy({ top: leiste.top - rand - 8, behavior: "auto" });
  }
  positioniereVerkehrDialog();
}

function erstelleVerkehrDialog() {
  const ui = verkehrDialogUi;
  if (ui.dialog) return ui.dialog;
  ui.nebel = document.createElement("div");
  ui.nebel.className = "traffic-fog";
  ui.nebel.hidden = true;
  ui.nebel.setAttribute("aria-hidden", "true");
  document.body.appendChild(ui.nebel);
  const dialog = document.createElement("dialog");
  dialog.id = "verkehr-dialog";
  dialog.setAttribute("aria-labelledby", "verkehr-dialog-titel");
  dialog.innerHTML = `<h2 id="verkehr-dialog-titel">Schwarzer Würfel</h2>
    <div class="traffic-roll-stage"><span class="traffic-roll-die" aria-label="Noch nicht geworfen">?</span></div>
    <span class="traffic-roll-result sr-only" role="status" aria-live="polite"></span>
    <button type="button" class="traffic-roll-button" autofocus>Werfen</button>
    <button type="button" class="traffic-peek-button">Strecke ansehen</button>`;
  dialog.querySelector(".traffic-roll-button").addEventListener("click", () => {
    if (!ui.zustand?.verkehrswuerfel_offen) {
      ui.bestaetigt = true;
      ui.aktiv = false;
      dialog.close();
      setzeVerkehrSperre(false);
      const panel = document.getElementById("verkehr-panel");
      panel.replaceChildren();
      panel.classList.add("versteckt");
      document.querySelector(".view-btn:not(:disabled), #rundenende-btn:not(:disabled)")?.focus();
    } else {
      starteVerkehrAnimation();
    }
  });
  const ansehen = () => {
    ui.streckeAnsehen = true;
    dialog.close();
    document.body.classList.remove("verkehr-dialog-offen");
    document.querySelector("#verkehr-panel button")?.focus();
  };
  dialog.querySelector(".traffic-peek-button").addEventListener("click", ansehen);
  dialog.addEventListener("cancel", event => {
    event.preventDefault();
    ansehen();
  });
  document.body.appendChild(dialog);
  ui.dialog = dialog;
  window.addEventListener("resize", positioniereVerkehrDialog);
  window.addEventListener("scroll", positioniereVerkehrDialog, { passive: true });
  window.visualViewport?.addEventListener("resize", positioniereVerkehrDialog);
  return dialog;
}

function oeffneVerkehrDialog() {
  const ui = verkehrDialogUi;
  if (!ui.aktiv) return;
  ui.streckeAnsehen = false;
  const dialog = erstelleVerkehrDialog();
  aktualisiereVerkehrDialog();
  if (!dialog.open) {
    richteVerkehrStreckeAus();
    dialog.showModal();
  }
  setzeVerkehrSperre(true);
  positioniereVerkehrDialog();
  requestAnimationFrame(positioniereVerkehrDialog);
}

function verkehrWurfFehlgeschlagen() {
  const ui = verkehrDialogUi;
  clearTimeout(ui.timer);
  ui.timer = null;
  ui.busy = false;
  if (ui.dialog) {
    aktualisiereVerkehrDialog();
    ui.dialog.querySelector(".traffic-roll-result").textContent = "Wurf nicht ausgeführt. Bitte erneut versuchen.";
    if (ui.darfWerfen && ui.zustand?.verkehrswuerfel_offen) {
      ui.dialog.querySelector(".traffic-roll-button").textContent = "Erneut werfen";
    }
  }
}

function starteVerkehrAnimation() {
  const ui = verkehrDialogUi;
  if (ui.busy || !ui.darfWerfen || !ui.zustand?.verkehrswuerfel_offen) return;
  ui.busy = true;
  aktualisiereVerkehrDialog();
  const key = ui.key;
  const dauer = window.matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 550;
  ui.timer = window.setTimeout(async () => {
    ui.timer = null;
    if (ui.key !== key || !ui.aktiv || !ui.zustand?.verkehrswuerfel_offen) return;
    try {
      if (await ui.werfen() === false) verkehrWurfFehlgeschlagen();
    } catch (error) {
      console.error(error);
      verkehrWurfFehlgeschlagen();
    }
  }, dauer);
}

function aktualisiereVerkehrDialog() {
  const ui = verkehrDialogUi;
  if (!ui.dialog || !ui.zustand) return;
  const z = ui.zustand;
  const offen = z.verkehrswuerfel_offen || 0;
  const letzter = (z.verkehrswuerfe || []).at(-1);
  const die = ui.dialog.querySelector(".traffic-roll-die");
  die.textContent = ui.busy ? "?" : (letzter?.wert ?? "?");
  die.setAttribute("aria-label", ui.busy ? "Würfel wird geworfen" : (letzter ? `Gewürfelt: ${letzter.wert}` : "Noch nicht geworfen"));
  die.classList.toggle("rolling", ui.busy);
  ui.dialog.querySelector(".traffic-roll-result").textContent = ui.busy
    ? "Würfel wird geworfen …"
    : letzter ? verkehrErgebnisText(letzter)
    : ui.darfWerfen ? "Würfle zuerst den schwarzen Würfel." : "Warte auf den schwarzen Würfel.";
  const button = ui.dialog.querySelector(".traffic-roll-button");
  button.textContent = !offen ? "Runde beginnen"
    : ui.busy ? "Würfelt …"
    : !ui.darfWerfen ? "Warte …"
    : offen > 1 ? `Werfen (${offen})` : "Werfen";
  button.disabled = ui.busy || (offen > 0 && !ui.darfWerfen);
}

function verkehrErgebnisText(wurf) {
  return wurf.ziel_entfernung === null
    ? "Glück gehabt – kein neues Flugzeug!"
    : `+1 ✈ auf Entfernung ${wurf.ziel_entfernung}`;
}

function renderVerkehr(z, trackUnit, darfWerfen, werfen) {
  const track = document.getElementById("distance-track");
  let symbole = document.getElementById("distance-traffic");
  if (!symbole) {
    symbole = document.createElement("div");
    symbole.id = "distance-traffic";
    track.appendChild(symbole);
  }
  symbole.replaceChildren();
  (z.flugzeugwuerfel || []).forEach((anzahl, i) => {
    const entfernung = z.laenge - 1 - i;
    if (anzahl <= 0 || entfernung > z.entfernung) return;
    const gruppe = document.createElement("span");
    gruppe.className = "vtrack-traffic";
    // Die Track-Höhe enthält auch den Rahmen; am untersten Feld Luft lassen.
    gruppe.style.top = ((entfernung + 1) * trackUnit - 22) + "px";
    const label = `${anzahl} ${anzahl === 1 ? "schwarzer Verkehrswürfel" : "schwarze Verkehrswürfel"} auf Entfernung ${entfernung}`;
    gruppe.title = label;
    gruppe.setAttribute("role", "img");
    gruppe.setAttribute("aria-label", label);
    for (let n = 0; n < Math.min(anzahl, 2); n++) gruppe.appendChild(verkehrswuerfelSymbol());
    if (anzahl > 2) {
      gruppe.replaceChildren(verkehrswuerfelSymbol());
      const zaehler = document.createElement("small");
      zaehler.textContent = `×${anzahl}`;
      gruppe.appendChild(zaehler);
    }
    symbole.appendChild(gruppe);
  });

  const ui = verkehrDialogUi;
  const key = `${z.runde}:${z.hoehe}:${z.entfernung}`;
  const wuerfe = z.verkehrswuerfe || [];
  const offen = z.status === "laeuft" && z.verkehrswuerfel_offen > 0;
  const neueWuerfe = ui.key === key ? wuerfe.slice(ui.gesehen) : [];
  if (ui.key !== key || wuerfe.length < ui.gesehen) resetVerkehrUi();
  ui.key = key;
  ui.zustand = z;
  ui.darfWerfen = darfWerfen;
  ui.werfen = werfen;
  if (wuerfe.length > ui.gesehen) {
    clearTimeout(ui.timer);
    ui.timer = null;
    ui.busy = false;
    animiereVerkehrsFlugzeuge(neueWuerfe);
    document.getElementById("meldung-leiste")?.replaceChildren();
  }
  ui.gesehen = wuerfe.length;
  if (offen) ui.aktiv = true;
  if (z.status !== "laeuft" || ui.bestaetigt) ui.aktiv = false;

  const panel = document.getElementById("verkehr-panel");
  panel.replaceChildren();
  panel.classList.toggle("versteckt", !ui.aktiv);
  if (!offen && wuerfe.length === 0) {
    setzeVerkehrSperre(false);
    if (ui.dialog?.open) ui.dialog.close();
    return;
  }

  if (ui.aktiv) {
    const button = document.createElement("button");
    button.type = "button";
    button.appendChild(verkehrswuerfelSymbol());
    button.append(offen ? " Würfeldialog öffnen" : " Wurfergebnis ansehen");
    button.addEventListener("click", oeffneVerkehrDialog);
    panel.appendChild(button);
  }
  setzeVerkehrSperre(ui.aktiv);
  aktualisiereVerkehrDialog();
  if (ui.aktiv && !ui.streckeAnsehen) oeffneVerkehrDialog();
  else if (!ui.aktiv && ui.dialog?.open) ui.dialog.close();
}
