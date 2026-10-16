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
  const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
  const base = () => ({
    runde: 1, hoehe: 6000, entfernung: 6, laenge: 7, status: "laeuft", phase: "verkehr",
    rueckgaengig_moeglich: true,
    flugzeuge: [0, 1, 3, 0, 1, 1, 0], flugzeugwuerfel: [1, 0, 2, 0, 1, 0, 0],
    verkehrswuerfel_offen: 2, verkehrswuerfe: [],
  });
  let z = base();
  let calls = 0, starts = 0, undos = 0;
  const undo = () => undos++;
  document.addEventListener("cockpit-undo", undo);
  const render = (allowed = true, roll = mockRoll) => {
    renderEntfernungsFlugzeuge(z, 36);
    renderVerkehr(z, 36, allowed, roll, () => { starts++; z.phase = "platzieren"; render(allowed, roll); });
  };
  function mockRoll() {
    calls++;
    const result = calls === 1 ? { wert: 3, ziel_entfernung: 4 } : { wert: 5, ziel_entfernung: undefined };
    const flugzeuge = [...z.flugzeuge];
    if (result.ziel_entfernung != null) flugzeuge[z.laenge - 1 - result.ziel_entfernung]++;
    z = { ...z, flugzeuge, verkehrswuerfel_offen: z.verkehrswuerfel_offen - 1,
      verkehrswuerfe: [...z.verkehrswuerfe, result] };
    if (!z.verkehrswuerfel_offen) z.phase = "vorbereitung";
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
    report("Jedes Flugzeug erscheint einzeln ohne Zahl, innerhalb der freien Spur");

    const positionen = () => [...find("#distance-obstacles").querySelectorAll(".aircraft-pose")].map(el => el.getAttribute("style"));
    const fontSizes = [...find("#distance-obstacles").querySelectorAll(".aircraft-icon")].map(el => getComputedStyle(el).fontSize);
    assert(new Set(fontSizes).size === 1, "Flugzeuge auf verschiedenen Tiles haben unterschiedliche Größen");
    const vorher = positionen();
    renderEntfernungsFlugzeuge({ ...z, runde: 9 }, 36);
    assert(JSON.stringify(positionen()) === JSON.stringify(vorher), "Flugzeuge springen beim erneuten Rendern");
    const posen = [...find('.vtrack-aircraft[data-distance="4"]').querySelectorAll(".aircraft-pose")];
    for (const eigenschaft of ["--plane-x", "--plane-angle"]) {
      assert(new Set(posen.map(el => el.style.getPropertyValue(eigenschaft))).size > 1, `Gleiche Position/Drehung: ${eigenschaft}`);
    }
    report("Feste Abstände und kleine Drehungen bleiben über Spielzüge hinweg stabil");

    const track = find("#distance-track");
    const alteBreite = track.style.width;
    for (const breite of [80, 90, 140, 200]) {
      track.style.width = `${breite}px`;
      for (const entfernung of [4, 6]) {
        for (let anzahl = 1; anzahl <= 9; anzahl++) {
          const flugzeuge = Array(7).fill(0);
          flugzeuge[6 - entfernung] = anzahl;
          renderEntfernungsFlugzeuge({ ...z, flugzeuge }, 36);
          const feld = find(".vtrack-aircraft").getBoundingClientRect();
          assert(find(".vtrack-aircraft").querySelectorAll(".aircraft-icon").length === anzahl, "Flugzeuge fehlen bei hoher Belegung");
          const boxes = [...find(".vtrack-aircraft").querySelectorAll(".aircraft-pose")].map(el => el.getBoundingClientRect());
          for (let a = 0; a < boxes.length; a++) for (let b = a + 1; b < boxes.length; b++) {
            assert(!(boxes[a].left < boxes[b].right && boxes[b].left < boxes[a].right && boxes[a].top < boxes[b].bottom && boxes[b].top < boxes[a].bottom), `Flugzeuge überlappen (${breite}px, ${anzahl})`);
          }
          assert([...find(".vtrack-aircraft").querySelectorAll(".aircraft-pose")].every(el => {
            const icon = el.getBoundingClientRect();
            return icon.left >= feld.left - .5 && icon.right <= feld.right + .5
              && icon.top >= feld.top - .5 && icon.bottom <= feld.bottom + .5;
          }), `Gedrehte Flugzeuge verlassen sichere Fläche (${breite}px, Entfernung ${entfernung}, ${anzahl} Flugzeuge)`);
        }
      }
    }
    track.style.width = alteBreite;
    renderEntfernungsFlugzeuge(z, 36);
    report("Gedrehte Hüllflächen bleiben bei 1–9 Flugzeugen und 80–200px breiten Leisten frei");

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
    await wait(1050);
    assert(starts === 0 && isBlocked(), "Runde beginnt vor dem letzten Würfel");
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

    find(".traffic-undo-button").click();
    assert(undos === 1, "Rückgängig im Dialog nicht erreichbar");
    report("Rückgängig ist auch im modalen Würfeldialog erreichbar");

    clickRoll();
    await waitForRoll();
    assert(calls === 2 && z.verkehrswuerfel_offen === 0 && isBlocked(), "Letztes Ergebnis gibt Cockpit zu früh frei");
    assert(find(".traffic-roll-result").textContent.includes("Glück gehabt"), "Zu kurze Strecke (Pyodide undefined) falsch angezeigt");
    assert(verkehrErgebnisText({wert:5,ziel_entfernung:null}).includes("Glück gehabt"), "Remote null falsch angezeigt");
    assert(!find(".aircraft-arriving"), "Fehlendes Flugzeug wird trotzdem animiert");
    assert(find(".traffic-roll-button").disabled, "Manueller Start überspringt den Cooldown");
    clickRoll(); render();
    await wait(450); render();
    assert(starts === 0 && isBlocked(), "Cooldown kürzer als eine Sekunde");
    await wait(600);
    assert(starts === 1 && z.phase === "platzieren", "Automatischer Rundenstart fehlt/ist doppelt");
    assert(!find("dialog").open && !find(".board-grid").inert && find(".traffic-fog").hidden, "Automatischer Start gibt Cockpit nicht frei");
    assert(find("#verkehr-panel").classList.contains("versteckt") && !find("#verkehr-panel").children.length, "Unnötige Ergebnisbox bleibt sichtbar");
    report("Eine Sekunde nach dem letzten Wurf startet die Runde automatisch; Rendern verlängert die Pause nicht");

    z = { ...base(), runde: 2, hoehe: 5000 };
    render(false);
    assert(find("dialog").open && find(".traffic-roll-button").disabled, "Wartende Person darf würfeln");
    clickRoll();
    assert(calls === 2, "Falsche Rolle hat gewürfelt");
    z = { ...z, phase: "vorbereitung", verkehrswuerfel_offen: 0, verkehrswuerfe: [{ wert: 4, ziel_entfernung: 3 }] };
    render(false);
    assert(find(".traffic-roll-die").textContent === "4" && find(".traffic-roll-button").disabled, "Remote-Ergebnis nicht übernommen");
    await wait(1100);
    assert(starts === 1 && !isBlocked(), "Wartendes Gerät startet eigenständig die Runde");
    report("Neue Runde am selben Feld öffnet erneut; andere Rolle wartet auf das Ergebnis");

    resetVerkehrUi(); render();
    assert(find("dialog").open && isBlocked(), "Abschluss-Snapshot nach Neuverbindung startet keinen Cooldown");
    resetVerkehrUi();
    await wait(1100);
    assert(starts === 1 && !isBlocked(), "Spielwechsel lässt einen alten Cooldown weiterlaufen");
    report("Neuverbindung erkennt den Abschluss; Spielwechsel bricht den Cooldown ab");

    render();
    z = { ...z, phase: "verkehr", verkehrswuerfel_offen: 1, verkehrswuerfe: [] };
    render();
    await wait(1100);
    assert(starts === 1 && isBlocked() && find(".traffic-roll-die").textContent === "?", "Rückgängig lässt alten Rundenstart oder Würfelwert stehen");
    report("Rückgängig während des Cooldowns verwirft den ausstehenden Rundenstart");

    resetVerkehrUi(); z = base();
    render(true, () => false);
    clickRoll(); await waitForRoll();
    assert(!find(".traffic-roll-button").disabled && find(".traffic-roll-result").textContent.includes("erneut versuchen"), "Fehlgeschlagener Wurf blockiert Wiederholung");
    report("Ein fehlgeschlagener Wurf kann wiederholt werden");

    render(); clickRoll(); resetVerkehrUi();
    await waitForRoll();
    assert(calls === 2 && !find("dialog").open && find(".traffic-fog").hidden, "Abgebrochene Animation würfelt nach Spielwechsel");
    z = { ...base(), phase: "platzieren", verkehrswuerfel_offen: 0 }; render();
    assert(!find("dialog").open && !find(".board-grid").inert, "Normale Runde wird gesperrt");
    report("Spielwechsel bricht Animation ab; ohne fällige Würfel bleibt alles frei");
    output.textContent += `\n${passed}/15 Tests bestanden.`;
  } catch (error) {
    output.textContent += `✗ ${error.message}\n${passed}/15 Tests bestanden.`;
  } finally {
    resetVerkehrUi();
    document.removeEventListener("cockpit-undo", undo);
    event.target.disabled = false;
  }
});
