/* Real-DOM smoke tests for the shared traffic UI. No engine/network needed;
 * deterministic snapshots mimic both local and multiplayer updates. */
document.getElementById("run-tests").addEventListener("click", async event => {
  event.target.disabled = true;
  const output = document.getElementById("test-results");
  output.textContent = "Tests laufen …\n";
  let passed = 0;
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const report = message => { passed++; output.textContent += `✓ ${message}\n`; };
  const find = selector => document.querySelector(selector);
  const waitForRoll = () => new Promise(resolve => setTimeout(resolve, 650));
  const base = () => ({
    runde: 1, hoehe: 6000, entfernung: 6, laenge: 7, status: "laeuft",
    flugzeuge: [0, 1, 3, 0, 1, 1, 0], flugzeugwuerfel: [1, 0, 2, 0, 1, 0, 0],
    verkehrswuerfel_offen: 2, verkehrswuerfe: [],
  });
  let z = base();
  let calls = 0;
  const render = (allowed = true, roll = mockRoll) => {
    renderEntfernungsFlugzeuge(z, 36);
    renderVerkehr(z, 36, allowed, roll);
  };
  function mockRoll() {
    calls++;
    const result = calls === 1 ? { wert: 3, ziel_entfernung: 4 } : { wert: 5, ziel_entfernung: null };
    const flugzeuge = [...z.flugzeuge];
    if (result.ziel_entfernung !== null) flugzeuge[z.laenge - 1 - result.ziel_entfernung]++;
    z = { ...z, flugzeuge, verkehrswuerfel_offen: z.verkehrswuerfel_offen - 1,
      verkehrswuerfe: [...z.verkehrswuerfe, result] };
    render();
    return true;
  }
  const clickRoll = () => find(".traffic-roll-button").click();
  const isBlocked = () => find(".board-grid").inert && !find(".traffic-fog").hidden;
  try {
    resetVerkehrUi();
    renderEntfernungsFlugzeuge(z, 36);
    assert(find('.vtrack-aircraft[aria-label="3 Flugzeuge auf Entfernung 4"]').querySelectorAll(".aircraft-icon").length === 3, "Nicht jedes Flugzeug dargestellt");
    assert(!find(".aircraft-count"), "Flugzeugzähler noch vorhanden");
    assert(find('.vtrack-aircraft[aria-label="3 Flugzeuge auf Entfernung 4"]').classList.contains("with-traffic"), "Würfelspur nicht freigehalten");
    const formation = find('.vtrack-aircraft[aria-label="3 Flugzeuge auf Entfernung 4"]');
    const bereich = formation.getBoundingClientRect();
    assert([...formation.querySelectorAll(".aircraft-icon")].every(el => {
      const icon = el.getBoundingClientRect();
      return icon.left >= bereich.left - .5 && icon.right <= bereich.right + .5;
    }), "Enge Formation ragt in Zahlen oder Würfelspur");
    report("Jedes Flugzeug erscheint einzeln in einer kompakten Formation ohne Zahl");

    render();
    assert(find("dialog").open && isBlocked(), "Dialog/Sperre fehlt");
    assert(find(".dice-tray").inert && find("#aktionen-leiste").inert, "Spielaktionen nicht gesperrt");
    assert(find('.vtrack-traffic[aria-label="2 schwarze Verkehrswürfel auf Entfernung 4"]').children.length === 2, "Mehrfachmarker fehlt");
    report("Fällige Würfel öffnen automatisch den Dialog und sperren Aktionen");

    await new Promise(requestAnimationFrame);
    assert(!find("dialog p, dialog small, #verkehr-panel strong"), "Überflüssige Erklärungstexte sichtbar");
    assert(getComputedStyle(find(".traffic-roll-result")).position === "absolute", "Statuskommentar noch sichtbar");
    assert(parseFloat(find(".traffic-fog").style.top) >= find("#distance-track").getBoundingClientRect().bottom, "Nebel überdeckt Entfernungsleiste");
    assert(getComputedStyle(find(".traffic-fog")).maskImage.includes("gradient"), "Weicher Nebelübergang fehlt");
    report("Kompakter Dialog; Nebel blendet erst unter der gesamten Strecke ein");

    clickRoll(); clickRoll();
    await waitForRoll();
    assert(calls === 1 && z.verkehrswuerfel_offen === 1, "Doppelter/verlorener Wurf");
    assert(find("dialog").open && isBlocked() && find(".traffic-roll-die").textContent === "3", "Erstes Ergebnis fehlt");
    assert(!find(".traffic-roll-button").disabled, "Nächster Wurf gesperrt");
    report("Doppelklick würfelt nur einmal; weitere Würfe bleiben möglich");

    assert(find('.aircraft-arriving[data-distance="4"]').querySelectorAll(".aircraft-icon").length === 4, "Neues Flugzeug auf belegtem Feld nicht animiert");
    assert(find('.aircraft-arriving[data-distance="4"]').querySelectorAll(".aircraft-row").length === 2, "Große Formation nicht in Reihen angeordnet");
    render();
    assert(!find(".aircraft-arriving"), "Dasselbe Ergebnis startet die Animation nochmals");
    report("Nur ein neuer Wurf animiert das Zielfeld, auch bei Mehrfachbelegung");

    find(".traffic-peek-button").click();
    render();
    assert(!find("dialog").open && isBlocked(), "Streckenansicht hebt Sperre auf/öffnet sofort erneut");
    find("#verkehr-panel button").click();
    assert(find("dialog").open && calls === 1, "Wiederöffnen würfelt erneut");
    report("Strecke ansehen und Dialog wieder öffnen verändern keine Würfe");

    clickRoll();
    await waitForRoll();
    assert(calls === 2 && z.verkehrswuerfel_offen === 0 && isBlocked(), "Letztes Ergebnis gibt Cockpit zu früh frei");
    assert(find(".traffic-roll-result").textContent.includes("Glück gehabt"), "Zu kurze Strecke falsch angezeigt");
    assert(!find(".aircraft-arriving"), "Fehlendes Flugzeug wird trotzdem animiert");
    clickRoll(); render();
    assert(!find("dialog").open && !find(".board-grid").inert && find(".traffic-fog").hidden, "Bestätigung gibt Cockpit nicht frei");
    assert(find("#verkehr-panel").classList.contains("versteckt") && !find("#verkehr-panel").children.length, "Unnötige Ergebnisbox bleibt sichtbar");
    report("Letzter Wurf bleibt sichtbar; Runde beginnen entfernt Nebel und Sperre");

    z = { ...base(), runde: 2, hoehe: 5000 };
    render(false);
    assert(find("dialog").open && find(".traffic-roll-button").disabled, "Wartende Person darf würfeln");
    clickRoll();
    assert(calls === 2, "Falsche Rolle hat gewürfelt");
    z = { ...z, verkehrswuerfel_offen: 0, verkehrswuerfe: [{ wert: 4, ziel_entfernung: 3 }] };
    render(false);
    assert(find(".traffic-roll-die").textContent === "4" && !find(".traffic-roll-button").disabled, "Remote-Ergebnis nicht übernommen");
    report("Neue Runde am selben Feld öffnet erneut; andere Rolle wartet auf das Ergebnis");

    resetVerkehrUi(); z = base();
    render(true, () => false);
    clickRoll(); await waitForRoll();
    assert(!find(".traffic-roll-button").disabled && find(".traffic-roll-result").textContent.includes("erneut versuchen"), "Fehlgeschlagener Wurf blockiert Wiederholung");
    report("Ein fehlgeschlagener Wurf kann wiederholt werden");

    render(); clickRoll(); resetVerkehrUi();
    await waitForRoll();
    assert(calls === 2 && !find("dialog").open && find(".traffic-fog").hidden, "Abgebrochene Animation würfelt nach Spielwechsel");
    z = { ...base(), verkehrswuerfel_offen: 0 }; render();
    assert(!find("dialog").open && !find(".board-grid").inert, "Normale Runde wird gesperrt");
    report("Spielwechsel bricht Animation ab; ohne fällige Würfel bleibt alles frei");
    output.textContent += `\n${passed}/10 Tests bestanden.`;
  } catch (error) {
    output.textContent += `✗ ${error.message}\n${passed}/10 Tests bestanden.`;
  } finally {
    resetVerkehrUi();
    event.target.disabled = false;
  }
});
