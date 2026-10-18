/* Gemeinsames Neuwurf-Popup für Pass & Play und beide Multiplayer-Geräte. */
const NeuwurfDialog = (() => {
  const rollen = ["pilot", "kopilot"];
  const namen = {pilot: "Pilotin", kopilot: "Co-Pilot"};
  let dialog = null;
  let aktuell = null;

  function neuerZustand() {
    return {
      phase: 0, id: null,
      auswahl: {pilot: [], kopilot: []},
      bestaetigt: {pilot: false, kopilot: false},
      wuerfel: null, vorher: null, meldung: "",
    };
  }

  function schliessen() {
    if (dialog?.open) dialog.close();
    document.body.classList.remove("neuwurf-dialog-offen");
    aktuell = null;
  }

  function render(z, ui, options) {
    if (!ui.phase || z.status !== "laeuft" || z.phase !== "platzieren") {
      schliessen();
      return;
    }
    if (!dialog) {
      dialog = document.createElement("dialog");
      dialog.id = "neuwurf-dialog";
      dialog.setAttribute("aria-labelledby", "neuwurf-titel");
      dialog.setAttribute("aria-describedby", "neuwurf-hinweis");
      dialog.innerHTML = '<header><span class="neuwurf-symbol" aria-hidden="true">↻</span><h2 id="neuwurf-titel">Gemeinsam neu würfeln</h2></header><p id="neuwurf-hinweis"></p><div class="neuwurf-spieler"></div><p class="neuwurf-status" role="status" aria-live="polite"></p><button type="button" class="neuwurf-abbrechen">Abbrechen</button>';
      dialog.addEventListener("cancel", event => {
        event.preventDefault();
        if (aktuell?.ui.phase === 1) aktuell.options.onCancel();
      });
      dialog.querySelector(".neuwurf-abbrechen").addEventListener("click", () => aktuell?.options.onCancel());
      document.body.appendChild(dialog);
    }
    aktuell = {ui, options};
    const ergebnis = ui.phase === 2;
    const fokus = dialog.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    dialog.classList.toggle("neuwurf-ergebnis", ergebnis);
    dialog.querySelector("h2").textContent = ergebnis ? "Neu gewürfelt!" : "Gemeinsam neu würfeln";
    dialog.querySelector("#neuwurf-hinweis").textContent = ergebnis
      ? "Die leuchtend markierten Würfel wurden neu gewürfelt."
      : "Wählt eure Würfel aus und bestätigt jeweils. Sobald beide bereit sind, wird automatisch gewürfelt.";
    const spieler = dialog.querySelector(".neuwurf-spieler");
    spieler.replaceChildren();
    for (const rolle of rollen) {
      const meins = !options.role || options.role === rolle;
      const bereit = ui.bestaetigt[rolle];
      const section = document.createElement("section");
      section.className = `neuwurf-seite ${rolle}`;
      section.dataset.role = rolle;
      const title = document.createElement("h3");
      title.textContent = namen[rolle] + (options.role ? (meins ? " · Du" : " · Partner") : "");
      section.appendChild(title);
      const dice = document.createElement("div");
      dice.className = "neuwurf-wuerfel";
      const werte = ui.wuerfel[rolle];
      werte.forEach((wert, index) => {
        const frei = z[`${rolle}_wuerfel_frei`][index];
        const ausgewaehlt = ui.auswahl[rolle].includes(index);
        const wrap = document.createElement("div");
        wrap.className = "neuwurf-wuerfel-slot";
        const button = document.createElement("button");
        button.type = "button";
        button.className = "wuerfel" + (!frei ? " platziert" : "") + (ausgewaehlt ? (ergebnis ? " neu-gewuerfelt" : " neuwurf-ausgewaehlt") : "");
        button.textContent = wert ?? "?";
        button.dataset.index = index;
        button.dataset.focus = `${rolle}-${index}`;
        button.disabled = ergebnis || !meins || bereit || !frei;
        button.setAttribute("aria-pressed", String(ausgewaehlt));
        button.setAttribute("aria-label", `${namen[rolle]}, Würfel ${index + 1}: ${wert ?? "verdeckt"}${!frei ? ", bereits platziert" : ausgewaehlt ? (ergebnis ? ", neu gewürfelt" : ", zum Neuwurf ausgewählt") : ""}`);
        button.addEventListener("click", () => options.onToggle(rolle, index));
        wrap.appendChild(button);
        const label = document.createElement("span");
        label.className = "neuwurf-wuerfel-label";
        label.textContent = !frei ? "gelegt" : ausgewaehlt ? (ergebnis ? (wert == null ? "neu gewürfelt" : `${ui.vorher[rolle][index]} → ${wert}`) : "↻ gewählt") : "behalten";
        wrap.appendChild(label);
        dice.appendChild(wrap);
      });
      section.appendChild(dice);
      const status = document.createElement("p");
      status.className = "neuwurf-seite-status";
      const anzahl = ui.auswahl[rolle].length;
      status.textContent = ergebnis ? `${anzahl} neu gewürfelt` : bereit ? "✓ Bestätigt" : `${anzahl} ausgewählt`;
      section.appendChild(status);
      if (!ergebnis && meins) {
        const confirm = document.createElement("button");
        confirm.type = "button";
        confirm.className = "neuwurf-bestaetigen" + (bereit ? " bereit" : "");
        confirm.dataset.focus = `${rolle}-confirm`;
        confirm.textContent = bereit ? "Auswahl ändern" : anzahl ? "Auswahl bestätigen" : "Ohne Neuwurf bestätigen";
        confirm.addEventListener("click", () => options.onConfirm(rolle));
        section.appendChild(confirm);
      }
      spieler.appendChild(section);
    }
    dialog.querySelector(".neuwurf-status").textContent = ui.meldung || (ergebnis
      ? "Das Popup schließt gleich automatisch."
      : rollen.some(rolle => ui.bestaetigt[rolle]) ? "Warte auf die zweite Bestätigung …" : "Ein gemeinsamer Neuwurf kostet 1 Plättchen.");
    dialog.querySelector(".neuwurf-abbrechen").hidden = ergebnis;
    if (!dialog.open) dialog.showModal();
    document.body.classList.add("neuwurf-dialog-offen");
    if (fokus) dialog.querySelector(`[data-focus="${fokus}"]:not(:disabled)`)?.focus({preventScroll: true});
  }

  return {neuerZustand, render, schliessen};
})();
