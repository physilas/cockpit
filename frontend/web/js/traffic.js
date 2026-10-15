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

// Ein gut sichtbares Symbol mit Anzahl ersetzt überlappende Flugzeugstapel.
// Links bleiben die Entfernungszahlen, rechts eine eigene Würfelspur frei.
function renderEntfernungsFlugzeuge(z, trackUnit) {
  const container = document.getElementById("distance-obstacles");
  container.replaceChildren();
  (z.flugzeuge || []).forEach((anzahl, i) => {
    const entfernung = z.laenge - 1 - i;
    if (anzahl <= 0 || entfernung > z.entfernung) return;
    const feld = document.createElement("span");
    feld.className = "vtrack-aircraft";
    feld.style.top = (entfernung * trackUnit + 8) + "px";
    if (z.flugzeugwuerfel?.[i]) feld.classList.add("with-traffic");
    const label = `${anzahl} ${anzahl === 1 ? "Flugzeug" : "Flugzeuge"} auf Entfernung ${entfernung}`;
    feld.title = label;
    feld.setAttribute("role", "img");
    feld.setAttribute("aria-label", label);
    const gruppe = document.createElement("span");
    gruppe.className = "aircraft-group";
    const flugzeug = document.createElement("span");
    flugzeug.className = "aircraft-icon";
    flugzeug.textContent = "✈";
    flugzeug.setAttribute("aria-hidden", "true");
    gruppe.appendChild(flugzeug);
    if (anzahl > 1) {
      const zaehler = document.createElement("span");
      zaehler.className = "aircraft-count";
      zaehler.textContent = anzahl;
      zaehler.setAttribute("aria-hidden", "true");
      gruppe.appendChild(zaehler);
    }
    feld.appendChild(gruppe);
    container.appendChild(feld);
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
  const cockpitTop = document.querySelector(".board-grid")?.getBoundingClientRect().top || rand;
  const top = Math.max(rand, Math.min(cockpitTop, hoehe - 80));
  ui.nebel.style.top = `${top}px`;
  if (ui.dialog?.open) {
    const halb = ui.dialog.getBoundingClientRect().height / 2;
    const mitte = Math.max(halb + 12, Math.min(hoehe - halb - 12, (top + hoehe) / 2));
    ui.dialog.style.top = `${mitte}px`;
  }
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
  dialog.setAttribute("aria-describedby", "verkehr-dialog-hinweis");
  dialog.innerHTML = `<h2 id="verkehr-dialog-titel">Schwarzer Verkehrswürfel</h2>
    <p id="verkehr-dialog-hinweis"></p>
    <div class="traffic-roll-stage"><span class="traffic-roll-die" aria-label="Noch nicht geworfen">?</span></div>
    <p class="traffic-roll-result" role="status" aria-live="polite"></p>
    <p class="traffic-roll-remaining"></p>
    <button type="button" class="traffic-roll-button" autofocus>Schwarzen Würfel werfen</button>
    <button type="button" class="traffic-peek-button">Strecke ansehen</button>
    <small>Seiten: 2, 3, 3, 4, 4, 5 · Aktuelles Feld zählt als 1.</small>`;
  dialog.querySelector(".traffic-roll-button").addEventListener("click", () => {
    if (!ui.zustand?.verkehrswuerfel_offen) {
      ui.bestaetigt = true;
      ui.aktiv = false;
      dialog.close();
      setzeVerkehrSperre(false);
      document.querySelector("#verkehr-panel button")?.remove();
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
  if (!dialog.open) dialog.showModal();
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
  ui.dialog.querySelector("#verkehr-dialog-hinweis").textContent = offen
    ? (ui.darfWerfen ? "Vor Rundenbeginn kommt neuer Flugverkehr hinzu." : "Die Person am Zug wirft. Das Ergebnis erscheint auch hier.")
    : "Alle schwarzen Würfel sind geworfen. Die Runde ist bereit.";
  ui.dialog.querySelector(".traffic-roll-result").textContent = ui.busy
    ? "Würfel wird geworfen …"
    : letzter ? verkehrErgebnisText(letzter)
    : ui.darfWerfen ? "Würfle zuerst den schwarzen Würfel." : "Warte auf den schwarzen Würfel.";
  ui.dialog.querySelector(".traffic-roll-remaining").textContent = offen
    ? `Noch ${offen} ${offen === 1 ? "Wurf" : "Würfe"} offen`
    : "Jetzt können die Spielerwürfel verwendet werden.";
  const button = ui.dialog.querySelector(".traffic-roll-button");
  button.textContent = !offen ? "Runde beginnen"
    : ui.busy ? "Würfelt …"
    : !ui.darfWerfen ? "Warte auf den Wurf …"
    : letzter ? "Nächsten schwarzen Würfel werfen" : "Schwarzen Würfel werfen";
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
    gruppe.title = `${label} – vor jeder Runde werfen (2, 3, 3, 4, 4, 5)`;
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
  if (ui.key !== key || wuerfe.length < ui.gesehen) resetVerkehrUi();
  ui.key = key;
  ui.zustand = z;
  ui.darfWerfen = darfWerfen;
  ui.werfen = werfen;
  if (wuerfe.length > ui.gesehen) {
    clearTimeout(ui.timer);
    ui.timer = null;
    ui.busy = false;
  }
  ui.gesehen = wuerfe.length;
  if (offen) ui.aktiv = true;
  if (z.status !== "laeuft" || ui.bestaetigt) ui.aktiv = false;

  const panel = document.getElementById("verkehr-panel");
  panel.replaceChildren();
  panel.classList.toggle("versteckt", !offen && wuerfe.length === 0);
  if (!offen && wuerfe.length === 0) {
    setzeVerkehrSperre(false);
    if (ui.dialog?.open) ui.dialog.close();
    return;
  }

  const titel = document.createElement("strong");
  titel.textContent = offen
    ? `Vor Rundenbeginn: ${z.verkehrswuerfel_offen} ${z.verkehrswuerfel_offen === 1 ? "schwarzer Würfel" : "schwarze Würfel"} offen`
    : "Schwarze Würfel dieser Runde";
  panel.appendChild(titel);
  if (offen) {
    const hinweis = document.createElement("span");
    hinweis.textContent = "Seiten: 2, 3, 3, 4, 4, 5 · Aktuelles Feld zählt als 1.";
    panel.appendChild(hinweis);
  }
  if (wuerfe.length) {
    const ergebnisse = document.createElement("div");
    ergebnisse.className = "traffic-results";
    wuerfe.forEach(wurf => {
      const ergebnis = document.createElement("span");
      ergebnis.className = "traffic-result";
      ergebnis.appendChild(verkehrswuerfelSymbol(wurf.wert));
      const text = document.createElement("span");
      text.textContent = verkehrErgebnisText(wurf);
      ergebnis.appendChild(text);
      ergebnisse.appendChild(ergebnis);
    });
    panel.appendChild(ergebnisse);
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
