/* Shared module instruments; the Python snapshot supplies rules and legal bonus destinations. */
window.FlightModules = (() => {
  let current = null, choice = null, revealed = null, context = '', timerAnchor = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const name = role => role === 'pilot' ? 'Pilotin' : 'Co-Pilot';
  function render(z, options) {
    current = {z, options};
    const root = document.getElementById('flight-modules');
    const key = `${z.szenario_id}:${z.runde}:${z.kooperation?.wartet_auf || ''}`;
    if (context !== key) { choice = revealed = null; context = key; }
    const modules = z.module || [], cards = z.faehigkeitskarten || [];
    root.classList.toggle('versteckt', !modules.length && !cards.length);
    root.replaceChildren();
    if (!modules.length && !cards.length) return;
    const active = z.status === 'laeuft' && z.phase === 'platzieren';
    const blocked = Boolean(z.zusatzaktion || z.kooperation || options.reroll);
    const roles = options.role ? [options.role] : ['pilot', 'kopilot'];
    const selected = options.selected;
    const canPlace = active && !blocked && selected && selected.besitzer === z.am_zug;
    const section = (title, text = '') => {
      const el = document.createElement('section'); el.className = 'module-instrument';
      el.innerHTML = `<h2>${esc(title)}</h2>${text ? `<p>${esc(text)}</p>` : ''}`;
      root.appendChild(el); return el;
    };
    const button = (parent, label, callback, disabled = false, cls = '') => {
      const b = document.createElement('button'); b.type = 'button'; b.className = `module-button ${cls}`;
      b.textContent = label; b.disabled = disabled; b.addEventListener('click', callback); parent.appendChild(b); return b;
    };
    const action = (role, type, params = {}) => options.onAction(role, type, params);
    const placement = (target, index = null) => options.onPlace(selected.besitzer, selected.index, target, index);
    if (modules.includes('realtime')) {
      const el = section('◷ Echtzeit · 60 Sekunden', z.phase === 'vorbereitung' ? 'Besprecht die nächste Runde. Die Uhr startet mit euren Würfeln.' : 'Nach Ablauf wertet der Host die Runde automatisch aus.');
      const clock = document.createElement('output'); clock.id = 'module-timer'; clock.setAttribute('aria-label', 'Verbleibende Rundenzeit'); el.appendChild(clock);
      if (z.phase === 'vorbereitung') button(el, 'Runde würfeln und Uhr starten', () => action(z.am_zug, 'wuerfeln'), z.status !== 'laeuft' || (options.role && options.role !== z.am_zug));
    }
    if (z.kerosin !== null && z.kerosin !== undefined) {
      const leak = modules.includes('leak');
      const el = section(leak ? '◉ Kerosinleck' : '⛽ Kerosin', leak ? 'Verbrauch: Differenz der Triebwerkswürfel + 1.' : (z.felder.kerosin[0] ? "Kerosinaktion für diese Runde erledigt." : "Ohne Würfel werden am Rundenende 6 Einheiten verbraucht."));
      const gauge = document.createElement('meter'); gauge.min = 0; gauge.max = 20; gauge.value = z.kerosin; gauge.setAttribute('aria-label', `Kerosin ${z.kerosin} von 20`); el.appendChild(gauge);
      const value = document.createElement('strong'); value.textContent = `${z.kerosin} / 20`; el.appendChild(value);
      if (!leak) button(el, z.felder.kerosin[0] ? `Würfel ${z.felder.kerosin[0].wert} liegt` : 'Kerosin regeln', () => placement('kerosin'), !canPlace || Boolean(z.felder.kerosin[0]));
    }
    if (modules.includes('wind')) {
      const el = section('⚑ Wind', 'Die Fluglage dreht den Ring nach jeder Ruderauflösung.');
      el.insertAdjacentHTML('beforeend', `<div class="wind-gauge"><div class="wind-dial" role="img" aria-label="Windring, aktueller Wert ${z.wind_wert}">${z.wind_ring.map((n,i) => `<span class="wind-tick${i === z.wind_position ? ' active' : ''}" style="--wind-angle:${i * 20}deg">${n > 0 ? '+' : ''}${n}</span>`).join('')}<div class="wind-pointer" style="transform:rotate(${z.wind_position * 20}deg)">↑</div></div><div><strong>${z.wind_wert >= 0 ? '+' : ''}${z.wind_wert}</strong><small>zur Triebwerkssumme</small></div></div>`);
      if (z.geschwindigkeit != null) el.insertAdjacentHTML('beforeend', `<p>Aktuelle Geschwindigkeit: <b>${z.geschwindigkeit}</b></p>`);
    }
    if (modules.includes('ice')) {
      const el = section(`❄ Eisbremsen · ${z.eis_fortschritt} / 4`, 'Je ein gleiches Paar oben und unten in derselben Runde. Oben: Pilotin · unten: beide.');
      const grid = document.createElement('div'); grid.className = 'ice-brake-grid';
      for (const row of [0, 1]) for (let col = 0; col < 4; col++) {
        const index = col * 2 + row, field = z.felder.eisbremse[index];
        const b = button(grid, field ? String(field.wert) : `${col + 2}`, () => placement('eisbremse', index), !canPlace || Boolean(field) || col !== z.eis_fortschritt || (row === 0 && selected?.besitzer !== 'pilot'), row ? 'shared' : 'pilot');
        b.setAttribute('aria-label', `Eisbremse ${col + 2} ${row ? 'unten' : 'oben'}${field ? ', belegt' : ''}`);
        if (col < z.eis_fortschritt) b.classList.add('module-complete');
      }
      el.appendChild(grid);
      el.insertAdjacentHTML('beforeend', '<p>Zur Landung müssen alle vier Paare aktiviert sein; die Geschwindigkeit muss unter dem Marker liegen.</p>');
    }
    if (modules.includes('intern')) {
      const el = section('♟ Praktikant', 'Pilotin nimmt von links, Co-Pilot von rechts. Trainingswürfel und nächstes Plättchen müssen verschiedene Zahlen zeigen.');
      el.insertAdjacentHTML('beforeend', `<div class="intern-tokens">${z.praktikant.map(n => `<span>${n}</span>`).join('') || '<b>✓ Ausbildung abgeschlossen</b>'}</div>`);
      button(el, selected ? `${name(selected.besitzer)}: trainieren` : 'Trainingswürfel auswählen', () => placement('training'), !canPlace || !z.praktikant.length || Boolean(z.felder.training[selected?.besitzer]));
    }
    if (z.zusatzaktion) {
      const p = z.zusatzaktion;
      const el = section(`${p.quelle === 'intern' ? 'Praktikant' : 'Synchronisation'} · ${p.wert}`, `${name(p.rolle)} platziert jetzt die Zusatzaktion. ${p.quelle === 'intern' ? 'Kein Kaffee und keine Konzentration.' : 'Die Feldfarbe darf frei gewählt werden.'}`);
      el.classList.add('module-pending');
      (p.kaffee_deltas || []).forEach(delta => button(el, `☕ ${delta > 0 ? '+' : ''}${delta}`, () => action(p.rolle, 'bonus_kaffee', {delta}), !active || (options.role && options.role !== p.rolle)));
      p.ziele.forEach(t => button(el, t.label, () => action(p.rolle, 'zusatz_platzieren', t), !active || (options.role && options.role !== p.rolle)));
      if (!p.ziele.length) el.insertAdjacentHTML('beforeend', '<p>Kein erlaubtes Ziel mehr verfügbar.</p>');
    }
    if (cards.length) {
      const el = section('☆ Fähigkeiten');
      for (const id of cards) {
        const card = window.LANDING_CATALOG.abilities.find(a => a.id === id);
        const info = document.createElement('details'); info.innerHTML = `<summary>${esc(card.name)}</summary><p>${esc(card.description)}</p>`; el.appendChild(info);
        if (id === 'working-together') {
          roles.forEach(r => button(info, `Tausch starten · ${name(r)}`, () => action(r, 'kooperation_start'), !active || blocked || !z.kooperation_verfuegbar));
        } else if (id === 'adaptation' || id === 'anticipation') {
          roles.forEach(r => {
            const available = id === 'adaptation' ? z.anpassung_verfuegbar[r] : z.voraussicht_verfuegbar && r === z.am_zug;
            button(info, `Würfel wählen · ${name(r)}`, () => { choice = {role:r, type:id}; revealed = null; options.conceal(); }, !active || blocked || !available);
          });
        } else {
          info.insertAdjacentHTML('beforeend', '<small>Wird automatisch ausgelöst.</small>');
        }
      }
    }
    const picker = z.kooperation ? {role:z.kooperation.wartet_auf, type:'kooperation_wahl'} : choice;
    if (picker && active) {
      const el = section(z.kooperation ? 'Zusammenarbeit: Würfel wählen' : 'Fähigkeit: Würfel wählen', `${name(picker.role)} wählt einen eigenen freien Würfel.`);
      if (options.role && options.role !== picker.role) {
        el.insertAdjacentHTML('beforeend', `<p>Warte auf ${name(picker.role)} …</p>`);
      } else if (revealed !== picker.role) {
        button(el, `${name(picker.role)}: Würfel anzeigen`, () => { revealed = picker.role; render(z, options); });
      } else {
        z[`${picker.role}_wuerfel`].forEach((v, i) => {
          if (z[`${picker.role}_wuerfel_frei`][i]) button(el, `${i + 1}: ${v}`, () => { choice = revealed = null; action(picker.role, picker.type, {wuerfel_index:i}); }, false, picker.role);
        });
      }
      if (!z.kooperation) button(el, 'Abbrechen', () => { choice = revealed = null; render(z, options); });
    }
    updateTimer();
  }
  function updateTimer() {
    if (!current) return;
    const z = current.z, el = document.getElementById('module-timer');
    if (!el) return;
    const key = `${z.timer_deadline_ms}:${z.server_time_ms}`;
    if (timerAnchor?.key !== key) timerAnchor = {key, remaining:Math.max(0, (z.timer_deadline_ms || z.server_time_ms) - z.server_time_ms), at:performance.now()};
    const seconds = Math.max(0, Math.ceil((timerAnchor.remaining - (performance.now() - timerAnchor.at)) / 1000));
    el.textContent = z.timer_deadline_ms ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}` : '—';
    el.classList.toggle('urgent', Boolean(z.timer_deadline_ms) && seconds <= 10);
  }
  setInterval(() => { updateTimer(); if (current?.z.timer_deadline_ms && current.z.status === 'laeuft') current.options.onTick?.(); }, 200);
  return {render, reset() {choice = revealed = null; current = timerAnchor = null;}};
})();
