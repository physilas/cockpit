/* Gemeinsame Anzeige der schwarzen Verkehrswürfel für beide Spielmodi.
 * Die Engine liefert Würfe und Zielpositionen; hier werden nur Symbole
 * und die vom jeweiligen Client angebundene Wurfaktion dargestellt. */
function verkehrswuerfelSymbol(wert = null) {
  const el = document.createElement("span");
  el.className = "traffic-die";
  el.setAttribute("aria-hidden", "true");
  if (wert !== null) {
    el.textContent = wert;
  } else {
    el.classList.add("traffic-cube");
    el.innerHTML = '<svg viewBox="0 0 16 16"><path fill="#050607" stroke="#f2f8f4" stroke-width=".8" stroke-linejoin="round" d="M8 1 15 4.5V11.5L8 15 1 11.5V4.5Z M1 4.5 8 8 15 4.5 M8 8V15"/></svg>';
  }
  return el;
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

  const panel = document.getElementById("verkehr-panel");
  panel.replaceChildren();
  const offen = z.status === "laeuft" && z.verkehrswuerfel_offen > 0;
  const wuerfe = z.verkehrswuerfe || [];
  panel.classList.toggle("versteckt", !offen && wuerfe.length === 0);
  if (!offen && wuerfe.length === 0) return;

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
      text.textContent = wurf.ziel_entfernung === null
        ? "Glück gehabt – kein neues Flugzeug!"
        : `+1 ✈ auf Entfernung ${wurf.ziel_entfernung}`;
      ergebnis.appendChild(text);
      ergebnisse.appendChild(ergebnis);
    });
    panel.appendChild(ergebnisse);
  }
  if (offen) {
    const button = document.createElement("button");
    button.type = "button";
    button.appendChild(verkehrswuerfelSymbol());
    button.append(" Schwarzen Würfel werfen");
    button.disabled = !darfWerfen;
    button.addEventListener("click", () => {
      button.disabled = true;
      werfen();
    });
    panel.appendChild(button);
  }
}
