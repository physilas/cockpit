/* Shared cockpit instruments. The Python snapshot remains the source of rules. */
window.FlightModules = (() => {
  let current = null, choice = null, revealed = null, context = '', detail = null, timerAnchor = null;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const name = role => role === 'pilot' ? 'Pilotin' : 'Co-Pilot';
  const signed = n => `${n > 0 ? '+' : ''}${n}`;
  const cardIcons = {'control':'◎', 'adaptation':'⇄', 'anticipation':'↻', 'mastery':'✦', 'working-together':'⇆', 'synchronisation':'⬡'};
  const bonusBoards = new WeakSet();
  let bonusTargets = new Map();
  const syncUi = {dialog:null,key:null,peek:false,busy:false,timer:null};

  const tradeUi = {dialog:null,key:null,revealed:null,closed:new Set()};
  function resetTrade() {
    if (tradeUi.dialog?.open) tradeUi.dialog.close();
    tradeUi.key = tradeUi.revealed = null; tradeUi.closed.clear();
  }
  function renderTrade(z, options) {
    const k = z.kooperation, result = k ? null : z.kooperation_ergebnis;
    const key = `${z.szenario_id}:${z.runde}:${(k || result)?.id}:${z.rueckgaengig_id || 0}`;
    if ((!k && !result) || z.status !== 'laeuft' || z.zusatzaktion || (result && tradeUi.closed.has(key))) {
      if (tradeUi.dialog?.open) tradeUi.dialog.close();
      return;
    }
    if (tradeUi.key !== key) {tradeUi.key = key; tradeUi.revealed = null; closeDetail();}
    let d = tradeUi.dialog;
    if (!d) {
      d = document.createElement('dialog'); d.id = 'trade-dialog';
      d.setAttribute('aria-labelledby','trade-title');
      d.setAttribute('aria-describedby','trade-hint');
      d.addEventListener('cancel', event => {
        event.preventDefault();
        if (current.z.kooperation) act(current.options.role || current.z.kooperation.wartet_auf,'kooperation_abbrechen',{kooperation_id:current.z.kooperation.id});
        else {tradeUi.closed.add(tradeUi.key); d.close();}
      });
      document.body.appendChild(d); tradeUi.dialog = d;
    }
    if (result && d.dataset.phase === 'result' && d.dataset.resultKey === key) return;
    const focused = d.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    d.dataset.phase = result ? 'result' : 'choice'; d.dataset.resultKey = result ? key : '';
    d.replaceChildren();
    d.insertAdjacentHTML('beforeend', `<h2 id="trade-title">${result ? 'Würfel getauscht!' : 'Zusammenarbeit'}</h2><p id="trade-hint">${result ? 'Beide haben bestätigt. Diese beiden Würfel werden offen getauscht.' : options.role ? 'Wähle einen eigenen freien Würfel und bestätige. Die andere Seite zeigt, sobald dein Partner gewählt hat.' : 'Seht eure Würfel nacheinander an und bestätigt jeweils. Es ist immer nur eine Hand aufgedeckt.'}</p>`);
    if (result) {
      const stage = document.createElement('div'); stage.className = 'trade-result-stage';
      stage.innerHTML = `<span class="trade-crossing" aria-hidden="true">⇄</span>${['pilot','kopilot'].map(r => `<span class="trade-flying ${r}" aria-label="${name(r)} gibt ${result.vorher[r]}">${result.vorher[r]}</span>`).join('')}`;
      d.appendChild(stage);
      const receipt = document.createElement('div'); receipt.className = 'trade-receipts';
      receipt.innerHTML = ['pilot','kopilot'].map(r => `<div class="${r}"><span>${name(r)} erhält</span><strong>${result.nachher[r]}</strong></div>`).join('');
      d.appendChild(receipt);
      button(d,'Weiter', () => {tradeUi.closed.add(key); d.close();},false,'trade-continue');
    } else {
      const sides = document.createElement('div'); sides.className = 'trade-sides'; d.appendChild(sides);
      for (const role of ['pilot','kopilot']) {
        const own = !options.role || options.role === role;
        const visible = own && tradeUi.revealed === role;
        const index = k.auswahl?.[role], confirmed = Boolean(k.bestaetigt?.[role]);
        const side = document.createElement('section'); side.className = `trade-side ${role}`;
        side.dataset.role = role;
        side.innerHTML = `<h3>${name(role)}${options.role ? (own ? ' · Du' : ' · Partner') : ''}</h3>`;
        if (own) {
          const reveal = button(side,visible ? 'Verdecken' : 'Würfel ansehen', () => {
            tradeUi.revealed = visible ? null : role;
            options.conceal();
          },confirmed && !options.role,'trade-reveal');
          reveal.dataset.focus = `${role}-reveal`;
        } else side.insertAdjacentHTML('beforeend','<p class="trade-private">Eigene Würfel bleiben privat</p>');
        const hand = document.createElement('div'); hand.className = 'trade-hand'; side.appendChild(hand);
        z[`${role}_wuerfel`].forEach((value,i) => {
          const free = z[`${role}_wuerfel_frei`][i], selected = i === index;
          const shown = !free || visible ? value : '?';
          const die = button(hand,shown ?? '?', () => act(role,'kooperation_wahl',{wuerfel_index:i,kooperation_id:k.id}), !own || !visible || !free || confirmed, `trade-die${selected ? ' selected' : ''}${!free ? ' placed' : ''}`);
          die.setAttribute('aria-label',`${name(role)}, Würfel ${i + 1}: ${shown ?? '?'}${selected ? ', gewählt' : ''}${!free ? ', bereits gelegt' : ''}`);
          die.setAttribute('aria-pressed',String(selected)); die.dataset.focus = `${role}-${i}`;
        });
        const selected = index != null;
        const status = document.createElement('div'); status.className = 'trade-selection'; status.setAttribute('role','status');
        const value = selected && visible ? z[`${role}_wuerfel`][index] : '?';
        status.innerHTML = selected ? `<span class="trade-picked">${value}</span><span class="trade-direction" aria-hidden="true">${role === 'pilot' ? '→' : '←'}</span><small>${confirmed ? '✓ Bestätigt' : 'Gewählt'}</small>` : '<small>Noch nicht gewählt</small>';
        side.appendChild(status);
        if (own) {
          const confirm = button(side,confirmed ? 'Auswahl ändern' : 'Bestätigen', () => {
            if (!options.role) tradeUi.revealed = null;
            act(role,confirmed ? 'kooperation_freigeben' : 'kooperation_bestaetigen',{kooperation_id:k.id});
          },!selected,`trade-confirm${confirmed ? ' ready' : ''}`);
          confirm.dataset.focus = `${role}-confirm`;
          confirm.setAttribute('aria-label',`${name(role)}: ${confirmed ? 'Auswahl ändern' : 'Tausch bestätigen'}`);
        }
        sides.appendChild(side);
      }
      const status = document.createElement('p'); status.className = 'trade-status'; status.setAttribute('role','status');
      status.textContent = Object.values(k.bestaetigt || {}).some(Boolean) ? 'Warte auf die zweite Bestätigung …' : 'Die Werte bleiben unverändert, bis beide bestätigen.';
      d.appendChild(status);
      button(d,'Abbrechen', () => act(options.role || k.wartet_auf,'kooperation_abbrechen',{kooperation_id:k.id}),false,'trade-cancel');
    }
    if (z.rueckgaengig_moeglich) button(d,'↶ Rückgängig', () => document.dispatchEvent(new Event('cockpit-undo')),false,'trade-undo');
    if (!d.open) d.showModal();
    if (focused) [...d.querySelectorAll('[data-focus]')].find(b => b.dataset.focus === focused && !b.disabled)?.focus({preventScroll:true});
  }

  function resetSync() {
    clearTimeout(syncUi.timer);
    syncUi.timer = null; syncUi.key = null; syncUi.peek = syncUi.busy = false;
    if (syncUi.dialog?.open) syncUi.dialog.close();
    document.getElementById('sync-reminder')?.remove();
    document.querySelectorAll('header.has-sync-reminder').forEach(el => el.classList.remove('has-sync-reminder'));
  }
  function showSync() {
    syncUi.peek = false;
    renderSync(current.z,current.options);
  }
  function renderSync(z, options) {
    const p = z.zusatzaktion;
    if (p?.quelle !== 'synchronisation' || z.status !== 'laeuft') {resetSync(); return;}
    const key = `${z.szenario_id}:${z.runde}`;
    if (syncUi.key !== key) {resetSync(); syncUi.key = key; closeDetail();}
    if (!syncUi.dialog) {
      const d = document.createElement('dialog'); d.id = 'sync-dialog';
      d.setAttribute('aria-labelledby','sync-dialog-title');
      d.innerHTML = '<h2 id="sync-dialog-title">Synchronisation</h2><div class="traffic-roll-stage"><span class="traffic-roll-die">?</span></div><p class="sync-role" role="status"></p><button type="button" class="sync-roll-button">Werfen</button><button type="button" class="sync-peek-button">Cockpit ansehen</button><button type="button" class="sync-undo-button">↶ Rückgängig</button>';
      document.body.appendChild(d); syncUi.dialog = d;
      const peek = () => {syncUi.peek = true; d.close();};
      d.querySelector('.sync-peek-button').addEventListener('click',peek);
      d.querySelector('.sync-undo-button').addEventListener('click', () => document.dispatchEvent(new Event('cockpit-undo')));
      d.addEventListener('cancel', e => {e.preventDefault(); peek();});
      d.querySelector('.sync-roll-button').addEventListener('click', () => {
        const pending = current?.z.zusatzaktion;
        if (pending?.quelle !== 'synchronisation') return;
        if (pending.wert != null) {peek(); document.querySelector('.bonus-target')?.focus(); return;}
        if (!allowed(pending.rolle) || syncUi.busy) return;
        syncUi.busy = true; renderSync(current.z,current.options);
        const rollKey = syncUi.key;
        syncUi.timer = setTimeout(() => {
          if (syncUi.key !== rollKey || current?.z.zusatzaktion?.quelle !== 'synchronisation') return;
          syncUi.timer = null; syncUi.busy = false;
          act(pending.rolle,'synchronisation_wuerfeln');
        },400);
      });
    }
    const d = syncUi.dialog, rolled = p.wert != null;
    if (rolled) {clearTimeout(syncUi.timer); syncUi.timer = null; syncUi.busy = false;}
    const die = d.querySelector('.traffic-roll-die');
    die.textContent = rolled ? p.wert : '?'; die.classList.toggle('rolling',syncUi.busy);
    die.setAttribute('aria-label',rolled ? `Zusatzwürfel: ${p.wert}` : 'Schwarzer Zusatzwürfel, noch nicht geworfen');
    d.querySelector('.sync-role').textContent = `${name(p.rolle)} ${rolled ? 'platziert den Zusatzwürfel.' : 'würfelt den Zusatzwürfel.'}`;
    const b = d.querySelector('.sync-roll-button');
    b.textContent = rolled ? 'Im Cockpit platzieren' : syncUi.busy ? 'Würfelt …' : allowed(p.rolle) ? 'Werfen' : `Warte auf ${name(p.rolle)} …`;
    b.disabled = !allowed(p.rolle) || syncUi.busy || options.reroll;
    d.querySelector('.sync-undo-button').disabled = !z.rueckgaengig_moeglich || syncUi.busy || options.reroll;
    let reminder = document.getElementById('sync-reminder');
    if (!reminder) {
      reminder = document.createElement('button'); reminder.id = 'sync-reminder'; reminder.type = 'button';
      reminder.addEventListener('click',showSync);
      document.body.appendChild(reminder);
    }
    reminder.innerHTML = `<span class="traffic-die" aria-hidden="true">${rolled ? p.wert : '?'}</span><span>Synchronisation · ${name(p.rolle)}<small>${rolled ? 'Im Cockpit platzieren' : 'Schwarzen Würfel werfen'}</small></span>`;
    reminder.setAttribute('aria-label', rolled ? `Synchronisation: schwarzer Würfel ${p.wert}. ${name(p.rolle)} muss ihn im Cockpit platzieren.` : `Synchronisation: ${name(p.rolle)} würfelt den schwarzen Würfel.`);
    const header = document.querySelector('#game-header:not(.versteckt), #spiel-header:not(.versteckt)');
    if (header) {header.appendChild(reminder); header.classList.add('has-sync-reminder');}
    if (!syncUi.peek && !d.open) d.showModal();
  }

  // Give both cockpit renderers the same physical field identity. Legal
  // destinations, values and target colours still come exclusively from Python.
  function identifyField(el, entry, index = null, owner = null) {
    el.dataset.ziel = entry.ziel;
    el.dataset.index = ['fahrwerk','landeklappe','bremse','konzentration','eisbremse'].includes(entry.ziel) ? String(index) : '';
    el.dataset.funkFeld = String(entry.ziel === 'funk' ? (entry.funk_feld_basis || 0) + index : 0);
    el.dataset.besitzer = owner || (entry.zugriff.length === 1 ? entry.zugriff[0] : '');
    return el;
  }
  function clearBonusTargets() {
    for (const [el, previous] of bonusTargets) {
      el.classList.remove('bonus-target');
      delete el.dataset.bonusSource;
      for (const attr of ['role','tabindex','aria-label','title']) {
        if (previous[attr] === null) el.removeAttribute(attr);
        else el.setAttribute(attr,previous[attr]);
      }
      if (el.tagName === 'BUTTON') el.disabled = previous.disabled;
    }
    bonusTargets.clear();
  }
  function renderBonusTargets(z, options) {
    clearBonusTargets();
    const board = document.querySelector('.board-grid');
    if (!bonusBoards.has(board)) {
      board.addEventListener('click', event => {
        const el = event.target.closest('.bonus-target'), p = current?.z.zusatzaktion;
        if (!p || !bonusTargets.has(el) || !allowed(p.rolle) || current.options.reroll || current.z.status !== 'laeuft' || current.z.phase !== 'platzieren') return;
        act(p.rolle,'zusatz_platzieren',bonusTargets.get(el).target);
      });
      board.addEventListener('keydown', event => {
        if ((event.key === 'Enter' || event.key === ' ') && event.target.classList.contains('bonus-target')) {
          event.preventDefault(); event.target.click();
        }
      });
      bonusBoards.add(board);
    }
    const p = z.zusatzaktion;
    if (!p || z.status !== 'laeuft' || z.phase !== 'platzieren' || options.reroll || !allowed(p.rolle)) return;
    board.querySelectorAll('.feld-zelle[data-ziel]:not(.belegt)').forEach(el => {
      const target = p.ziele.find(t => t.ziel === el.dataset.ziel && String(t.index ?? '') === el.dataset.index &&
        String(t.funk_feld) === el.dataset.funkFeld && (!el.dataset.besitzer || t.ziel_besitzer === el.dataset.besitzer));
      if (!target) return;
      const previous = {target,disabled:el.disabled};
      for (const attr of ['role','tabindex','aria-label','title']) previous[attr] = el.getAttribute(attr);
      bonusTargets.set(el,previous);
      el.classList.add('bonus-target'); el.dataset.bonusSource = p.quelle;
      el.setAttribute('role','button'); el.tabIndex = 0;
      const label = `${p.quelle === 'intern' ? 'Praktikant' : 'Synchronisation'} ${p.wert} auf ${target.label} platzieren`;
      el.setAttribute('aria-label',label); el.title = label;
      if (el.tagName === 'BUTTON') el.disabled = false;
    });
  }

  function button(parent, label, callback, disabled = false, cls = '') {
    const b = document.createElement('button');
    b.type = 'button'; b.className = cls || 'module-button'; b.textContent = label; b.disabled = disabled;
    b.addEventListener('click', callback); parent.appendChild(b); return b;
  }
  function mount(id, visible) {
    const el = document.getElementById(id);
    el.replaceChildren(); el.classList.toggle('versteckt', !visible); return el;
  }
  function act(role, type, params = {}) {
    closeDetail(); current.options.onAction(role, type, params);
  }
  function place(target, index = null) {
    const selected = current.options.selected;
    if (selected) current.options.onPlace(selected.besitzer, selected.index, target, index);
  }
  function allowed(role) { return !current.options.role || current.options.role === role; }
  function canPlace() {
    const {z, options} = current, s = options.selected;
    return z.status === 'laeuft' && z.phase === 'platzieren' && !z.zusatzaktion && !z.kooperation && !options.reroll &&
      Boolean(s && s.besitzer === z.am_zug && allowed(s.besitzer));
  }
  function slot(parent, field, label, callback, enabled, cls, ariaLabel) {
    const b = button(parent, field ? String(field.wert) : label, () => {if (canPlace()) callback();}, !enabled || Boolean(field), `feld-zelle ${cls}${field ? ` belegt ${field.besitzer}` : ''}${enabled && !field ? ' klickbar' : ''}`);
    if (field?.quelle) b.classList.add(`source-${field.quelle}`);
    b.setAttribute('aria-label', `${ariaLabel}${field ? `, Würfel ${field.wert}` : ''}`); return b;
  }

  // Numbers occupy five equal cells inside the 12% margins. A marker always
  // sits on a cell boundary, including half-step strengths from the ice module.
  function rerollHTML(count) {
    return `<button type="button" class="reroll-token reroll-count" aria-label="Neuwurf starten · ${count} Plättchen" title="Neuwurf starten"${count <= 0 ? ' disabled' : ''}><span aria-hidden="true">↻</span><strong>${count}</strong></button>`;
  }

  function renderBrakes(strength) {
    const el = document.getElementById('s-brems');
    if (!el.querySelector('.brems-marker')) {
      el.innerHTML = `<div class="brems-scale">${[2,3,4,5,6].map(n => `<span class="skala-zahl brems-number">${n}</span>`).join('')}<span class="brems-marker" aria-hidden="true"></span></div>`;
    }
    const safe = Math.floor(strength);
    el.querySelector('.brems-marker').style.left = `${Math.max(12, Math.min(88, 12 + (safe - 1) * 15.2))}%`;
    el.setAttribute('aria-label', `Bremsstärke ${String(strength).replace('.', ',')}`);
  }

  function windDial(z) {
    return `<div class="wind-dial" role="img" aria-label="Windring, aktueller Wert ${signed(z.wind_wert)}">${z.wind_ring.map((n,i) => `<span class="wind-tick${i === z.wind_position ? ' active' : ''}" style="--wind-angle:${i * 20}deg">${signed(n)}</span>`).join('')}<div class="wind-pointer" style="transform:rotate(${z.wind_position * 20}deg)">↑</div></div>`;
  }
  function renderFuel(z) {
    const present = z.kerosin != null, leak = z.module.includes('leak');
    document.querySelector('.board-grid').classList.toggle('has-fuel', present);
    const gauge = mount('fuel-gauge', present), action = mount('fuel-action', present);
    if (!present) return;
    gauge.classList.toggle('low-fuel', z.kerosin <= 6);
    gauge.innerHTML = `<button type="button" class="fuel-info" aria-label="${leak ? 'Kerosinleck' : 'Kerosin'}: ${z.kerosin} von 20. Details anzeigen"><span class="fuel-value">${z.kerosin}</span><span class="fuel-rail" role="meter" aria-label="Kerosin" aria-valuemin="0" aria-valuemax="20" aria-valuenow="${z.kerosin}"><span class="fuel-fill" style="--fuel-percent:${Math.max(0, Math.min(100,z.kerosin * 5))}%"></span><span class="fuel-graduations"></span></span><span class="fuel-icon" aria-hidden="true">⛽</span></button>`;
    gauge.querySelector('button').addEventListener('click', () => openDetail('fuel'));
    action.innerHTML = `<span class="feld-label">${leak ? '◉ Leck' : 'Kerosin'}</span>`;
    if (leak) {
      button(action, 'Δ + 1', () => openDetail('fuel'), false, 'leak-indicator').setAttribute('aria-label', 'Kerosinleck: Verbrauch und Details');
    } else {
      identifyField(slot(action, z.felder.kerosin[0], '⛽', () => place('kerosin'), canPlace(), 'shared-slot', 'Kerosin regeln'), {ziel:'kerosin',zugriff:['pilot','kopilot']});
    }
  }
  function renderWind(z) {
    const present = z.module.includes('wind'), el = mount('wind-instrument', present);
    document.querySelector('.thrust-instruments').classList.toggle('has-wind', present);
    const label = document.querySelector('#schub-reihe .inline-label');
    label?.querySelector('.wind-modifier')?.remove();
    if (!present) return;
    label?.insertAdjacentHTML('beforeend', `<span class="wind-modifier" aria-label="Wind ${signed(z.wind_wert)}">${signed(z.wind_wert)}</span>`);
    const b = button(el, '', () => openDetail('wind'), false, 'wind-mini');
    b.setAttribute('aria-label', `Wind ${signed(z.wind_wert)}. Windrad vergrößern`);
    b.setAttribute('aria-haspopup', 'dialog');
    b.innerHTML = `<span class="wind-mini-arrow" style="transform:rotate(${z.wind_position * 20}deg)" aria-hidden="true">↑</span>`;
  }
  function renderIce(z) {
    const present = z.module.includes('ice'), el = mount('ice-brakes', present);
    document.getElementById('bremse-reihe').classList.toggle('versteckt', present);
    if (!present) return;
    el.innerHTML = `<div class="ice-heading"><span>❄ Eisbremsen</span><button type="button" class="instrument-help" aria-label="Eisbremsen erklären">${z.eis_fortschritt}/4 ⓘ</button></div><div class="ice-brake-grid"></div>`;
    el.querySelector('.instrument-help').addEventListener('click', () => openDetail('ice'));
    const grid = el.querySelector('.ice-brake-grid');
    for (let col = 0; col < 4; col++) {
      const pair = document.createElement('div'); pair.className = 'ice-pair';
      if (col < z.eis_fortschritt) pair.classList.add('module-complete');
      if (col === z.eis_fortschritt) pair.classList.add('current-pair');
      for (const row of [0,1]) {
        const index = col * 2 + row, field = z.felder.eisbremse[index];
        identifyField(slot(pair, field, String(col + 2), () => place('eisbremse', index), canPlace() && col === z.eis_fortschritt && (row === 1 || current.options.selected?.besitzer === 'pilot'), row ? 'shared-slot' : 'pilot-slot', `Eisbremse ${col + 2} ${row ? 'unten, beide' : 'oben, Pilotin'}`), {ziel:'eisbremse',zugriff:row ? ['pilot','kopilot'] : ['pilot']},index);
      }
      pair.insertAdjacentHTML('beforeend', `<span class="feld-licht${col < z.eis_fortschritt ? ' an' : ''}" aria-label="Paar ${col + 2} ${col < z.eis_fortschritt ? 'aktiviert' : 'offen'}"></span>`);
      grid.appendChild(pair);
    }
  }
  function renderIntern(z) {
    const el = mount('intern-strip', z.module.includes('intern'));
    if (!z.module.includes('intern')) return;
    el.innerHTML = `<div class="intern-heading"><span>♟ Praktikant <strong>${6 - z.praktikant.length}/6</strong></span><button type="button" class="instrument-help" aria-label="Praktikant erklären">ⓘ</button></div><div class="intern-training"><div class="intern-end pilot"></div><div class="intern-tokens"></div><div class="intern-end kopilot"></div></div>`;
    el.querySelector('.instrument-help').addEventListener('click', () => openDetail('intern'));
    for (const role of ['pilot','kopilot']) {
      const end = el.querySelector(`.intern-end.${role}`);
      slot(end, z.felder.training[role], role === 'pilot' ? '→' : '←', () => place('training'), canPlace() && current.options.selected?.besitzer === role && z.praktikant.length > 0, `${role}-slot`, `Praktikant trainieren · ${name(role)}`);
    }
    el.querySelector('.intern-tokens').innerHTML = z.praktikant.map((n,i) => `<span class="intern-token${i === 0 ? ' next-pilot' : ''}${i === z.praktikant.length - 1 ? ' next-kopilot' : ''}">${n}</span>`).join('') || '<span class="intern-complete">✓ Ausgebildet</span>';
    if (z.zusatzaktion?.quelle === 'intern') {
      const p = z.zusatzaktion;
      el.insertAdjacentHTML('beforeend', `<div class="intern-placement-hint" role="status"><span class="intern-token">${p.wert}</span><span>${allowed(p.rolle) ? `${name(p.rolle)}: hervorgehobenes Feld antippen.` : `${name(p.rolle)} platziert das Plättchen …`}</span></div>`);
    }
  }
  function cardState(id, z) {
    const role = current.options.role || z.am_zug;
    if (id === 'adaptation') return z.anpassung_verfuegbar[role] ? 'Bereit' : 'Verbraucht';
    if (id === 'anticipation') return z.voraussicht_verfuegbar && role === z.am_zug ? 'Bereit' : 'Später';
    if (id === 'working-together') return z.kooperation_verfuegbar ? 'Bereit' : 'Später';
    return 'Auto';
  }
  function renderCards(z) {
    const el = mount('ability-strip', z.faehigkeitskarten.length > 0);
    for (const id of z.faehigkeitskarten) {
      const card = window.LANDING_CATALOG.abilities.find(a => a.id === id), state = cardState(id,z);
      const b = button(el, '', () => openDetail(`card:${id}`), false, `ability-chip${state === 'Verbraucht' ? ' spent' : ''}`);
      b.setAttribute('aria-haspopup','dialog'); b.setAttribute('aria-label', `${card.name}. ${state}. Details und Aktionen`);
      b.innerHTML = `<span class="ability-icon" aria-hidden="true">${cardIcons[id]}</span><span>${esc(card.name)}<small>${state}</small></span>`;
    }
  }
  function renderRealtime(z) {
    const present = z.module.includes('realtime'), el = mount('realtime-instrument', present);
    if (!present) return;
    el.innerHTML = '<output id="module-timer" aria-label="Verbleibende Rundenzeit"></output>';
    if (z.phase === 'vorbereitung') {
      button(el, '◷ Würfeln', () => act(z.am_zug, 'wuerfeln'), z.status !== 'laeuft' || !allowed(z.am_zug), 'timer-start').title = 'Würfel werfen und 60 Sekunden starten';
    } else {
      button(el, '◷', () => openDetail('realtime'), false, 'timer-help').setAttribute('aria-label','Echtzeit erklären');
    }
  }

  function detailDialog() {
    let d = document.getElementById('module-detail');
    if (!d) {
      d = document.createElement('dialog'); d.id = 'module-detail';
      d.setAttribute('aria-labelledby','module-detail-title'); document.body.appendChild(d);
      d.addEventListener('close', () => { detail = null; });
      d.addEventListener('click', e => { if (e.target === d) closeDetail(); });
    }
    return d;
  }
  function closeDetail() {
    detail = null;
    const d = document.getElementById('module-detail'); if (d?.open) d.close();
  }
  function openDetail(type) {
    detail = type; renderDetail(); const d = detailDialog(); if (!d.open) d.showModal();
  }
  function renderDetail() {
    if (!detail || !current) return;
    const {z, options} = current, d = detailDialog();
    const focused = d.contains(document.activeElement) ? document.activeElement.dataset.focus : null;
    d.innerHTML = '<div class="module-detail-head"><h2 id="module-detail-title"></h2><button type="button" class="module-close" aria-label="Details schließen" data-focus="close">×</button></div><div class="module-detail-body"></div>';
    d.querySelector('.module-close').addEventListener('click', closeDetail);
    const body = d.querySelector('.module-detail-body');
    const title = t => {d.querySelector('h2').textContent = t;};
    const para = text => {const p = document.createElement('p'); p.textContent = text; body.appendChild(p);};
    if (detail === 'wind') {
      title('⚑ Wind'); body.innerHTML = `<div class="wind-gauge">${windDial(z)}<strong>${signed(z.wind_wert)}</strong></div>`;
      para('Der Wind wird zur Summe der beiden Triebwerkswürfel addiert – auch bei der Landung. Nach jeder Ruderauflösung dreht die aktuelle Fluglage den Ring weiter.');
      if (z.geschwindigkeit != null) para(`Aktuelle Geschwindigkeit: ${z.geschwindigkeit}`);
    } else if (detail === 'fuel') {
      title(z.module.includes('leak') ? '◉ Kerosinleck' : '⛽ Kerosin');
      para(`Treibstoffvorrat: ${z.kerosin} von 20. Bei 0 ist die Partie sofort verloren.`);
      para(z.module.includes('leak') ? 'Sobald beide Triebwerke belegt sind, verbraucht ihr die Differenz der Würfelwerte + 1. Das Kerosinfeld entfällt.' : 'Ein Würfel auf dem Kerosinfeld verbraucht sofort so viele Einheiten wie sein Wert. Ohne Kerosinaktion verbraucht ihr am Rundenende 6 Einheiten.');
    } else if (detail === 'ice') {
      title(`❄ Eisbremsen · ${z.eis_fortschritt}/4`);
      para('Aktiviert die Paare 2, 3, 4 und 5 von links nach rechts. Oben legt nur die Pilotin, unten dürfen beide legen. Beide gleichen Würfel müssen in derselben Runde liegen.');
      para('Zur Landung müssen alle vier Paare aktiviert sein. Die Geschwindigkeit muss unter dem roten Marker liegen.');
    } else if (detail === 'intern') {
      title('♟ Praktikant');
      para('Die Pilotin nimmt das linke, der Co-Pilot das rechte Plättchen. Wählt einen eigenen Würfel und tippt auf euer Trainingsfeld. Sein Wert muss sich vom nächsten Plättchen unterscheiden. Ein Training pro Person und Runde.');
      para('Platziert anschließend das Plättchen auf einem erlaubten Feld. Dafür sind weder Kaffee noch Konzentration erlaubt. Zur Landung müssen alle sechs Plättchen ausgebildet sein.');
    } else if (detail === 'realtime') {
      title('◷ Echtzeit');
      para('Nach dem Würfeln habt ihr 60 Sekunden. Danach wird die Runde automatisch ausgewertet, auch mit ungenutzten Würfeln. Besprecht euch vor der nächsten Runde in Ruhe; die Uhr startet erst beim Würfeln.');
    } else if (detail.startsWith('card:')) {
      const id = detail.slice(5), card = window.LANDING_CATALOG.abilities.find(a => a.id === id);
      title(`${cardIcons[id]} ${card.name}`); para(card.description);
      const active = z.status === 'laeuft' && z.phase === 'platzieren' && !z.zusatzaktion && !z.kooperation && !options.reroll;
      const roles = options.role ? [options.role] : ['pilot','kopilot'];
      if (id === 'working-together') {
        roles.forEach(r => button(body, `Tausch starten · ${name(r)}`, () => act(r,'kooperation_start'), !active || !z.kooperation_verfuegbar).dataset.focus = r);
      } else if (id === 'adaptation' || id === 'anticipation') {
        roles.forEach(r => {
          const available = id === 'adaptation' ? z.anpassung_verfuegbar[r] : z.voraussicht_verfuegbar && r === z.am_zug;
          button(body, `${name(r)} · ${available ? 'Würfel wählen' : 'Zurzeit nicht verfügbar'}`, () => {choice = {role:r,type:id}; revealed = null; closeDetail(); options.conceal();}, !active || !available).dataset.focus = r;
        });
      } else para('Diese Fähigkeit wird automatisch ausgelöst.');
    }
    if (focused) [...d.querySelectorAll('[data-focus]')].find(b => b.dataset.focus === focused)?.focus();
  }

  function renderPending(z, options) {
    const root = document.getElementById('flight-modules'); root.replaceChildren();
    const active = z.status === 'laeuft' && z.phase === 'platzieren';
    const section = (title, text) => {
      const el = document.createElement('section'); el.className = 'module-pending';
      el.innerHTML = `<h2>${esc(title)}</h2><p>${esc(text)}</p>`; root.appendChild(el); return el;
    };
    if (z.zusatzaktion && z.zusatzaktion.quelle !== 'intern') {
      const p = z.zusatzaktion;
      const el = section(`Synchronisation${p.wert != null ? ` · ${p.wert}` : ''}`, p.wert == null ? `${name(p.rolle)} würfelt zuerst den schwarzen Zusatzwürfel.` : allowed(p.rolle) ? `${name(p.rolle)}: hervorgehobenes Feld im Cockpit antippen.` : `${name(p.rolle)} platziert den Zusatzwürfel …`);
      button(el,p.wert == null ? 'Würfeldialog öffnen' : 'Zusatzwürfel ansehen',showSync);
      (p.kaffee_deltas || []).forEach(delta => button(el, `☕ ${signed(delta)}`, () => act(p.rolle, 'bonus_kaffee', {delta}), !active || !allowed(p.rolle)));
      if (p.wert != null && !p.ziele.length) el.insertAdjacentHTML('beforeend','<p>Kein erlaubtes Ziel mehr verfügbar.</p>');
    }
    const picker = choice;
    if (picker && active) {
      const el = section('Fähigkeit: Würfel wählen', `${name(picker.role)} wählt einen eigenen freien Würfel.`);
      if (!allowed(picker.role)) {
        el.insertAdjacentHTML('beforeend', `<p>Warte auf ${name(picker.role)} …</p>`);
      } else if (revealed !== picker.role) {
        button(el, `${name(picker.role)}: Würfel anzeigen`, () => {revealed = picker.role; render(z,options);});
      } else {
        z[`${picker.role}_wuerfel`].forEach((v,i) => {
          if (z[`${picker.role}_wuerfel_frei`][i]) button(el, `${i + 1}: ${v}`, () => {choice = revealed = null; act(picker.role,picker.type,{wuerfel_index:i});}, false, `module-button ${picker.role}`);
        });
      }
      if (!z.kooperation) button(el,'Abbrechen', () => {choice = revealed = null; render(z,options);});
    }
    root.classList.toggle('versteckt', !root.childElementCount);
  }
  function render(z, options) {
    const scenarioChanged = current?.z.szenario_id !== z.szenario_id;
    if (current?.z.rueckgaengig_id !== z.rueckgaengig_id) {resetTrade(); resetSync(); choice = revealed = null; closeDetail();}
    current = {z,options};
    if (scenarioChanged) {resetTrade(); closeDetail();}
    const key = `${z.szenario_id}:${z.runde}:${z.kooperation?.wartet_auf || ''}`;
    if (context !== key) {choice = revealed = null; context = key;}
    renderFuel(z); renderWind(z); renderIce(z); renderIntern(z); renderCards(z); renderRealtime(z);
    renderBonusTargets(z,options);
    renderPending(z,options); renderDetail(); renderSync(z,options); renderTrade(z,options); updateTimer();
  }
  function updateTimer() {
    if (!current) return;
    const z = current.z, el = document.getElementById('module-timer');
    if (!el) return;
    const key = `${z.timer_deadline_ms}:${z.server_time_ms}`;
    if (timerAnchor?.key !== key) timerAnchor = {key, remaining:Math.max(0,(z.timer_deadline_ms || z.server_time_ms) - z.server_time_ms), at:performance.now()};
    const seconds = Math.max(0,Math.ceil((timerAnchor.remaining - (performance.now() - timerAnchor.at)) / 1000));
    el.textContent = z.timer_deadline_ms ? `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2,'0')}` : '—';
    el.classList.toggle('urgent', Boolean(z.timer_deadline_ms) && seconds <= 10);
  }
  setInterval(() => {updateTimer(); if (current?.z.timer_deadline_ms && current.z.status === 'laeuft') current.options.onTick?.();}, 200);
  return {render, renderBrakes, rerollHTML, identifyField, reset() {resetTrade(); resetSync(); clearBonusTargets(); closeDetail(); choice = revealed = null; context = ''; current = timerAnchor = null;}};
})();
