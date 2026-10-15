/* Shared pre-flight selection. Browsing and draft loadouts need no Python/CDN. */
(() => {
  const catalog = window.LANDING_CATALOG;
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const difficulty = s => catalog.difficulties.find(d => d.id === s.difficulty) || { label: "Eigene Strecke", color: "#507780" };
  const read = (key, fallback) => {
    try { const value = JSON.parse(localStorage.getItem(key)); return value && typeof value === "object" && !Array.isArray(value) ? value : fallback; }
    catch { return fallback; }
  };
  const write = (key, value) => { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* Private browsing: selection still works. */ } };
  const progressKey = s => `${s.practice ? "practice" : "route"}:${s.id}`;
  const photo = s => catalog.photos?.[s.code];
  const imageHTML = s => s.image
    ? `<img src="${esc(s.image)}" alt="${esc(photo(s)?.alt || `Stadtansicht von ${s.city}`)}" loading="lazy" width="340" height="240" style="object-position:${esc(photo(s)?.position || '50% 50%')}">`
    : `<div class="landing-placeholder" aria-hidden="true"><span>✈</span><b>${esc(s.code)}</b></div>`;
  const photoCredit = s => photo(s)
    ? `<p class="landing-photo-credit">${esc(photo(s).location)} · Foto: <a href="${esc(photo(s).source_url)}" target="_blank" rel="noopener">${esc(photo(s).author)}</a> · <a href="${esc(photo(s).license_url)}" target="_blank" rel="noopener">${esc(photo(s).license)}</a> · <a href="bildnachweise.html#${esc(s.code)}" target="_blank" rel="noopener">Bildnachweis ↗</a></p>`
    : '';
  const moduleHTML = s => s.modules.map(id => `<span class="landing-chip">${esc(catalog.modules[id].icon)} ${esc(catalog.modules[id].name)}</span>`).join("");

  function mount(root, options) {
    let filter = "all", query = "", selected = null, detail = false, busy = false;
    let drafts = read("flyteam-loadout-drafts-v1", {});
    const stored = read("flyteam-selection-v1", {});
    selected = catalog.scenarios.find(s => s.id === stored.id) || catalog.scenarios[0];
    root.innerHTML = `
      <div class="landing-shell">
        <nav class="landing-nav" aria-label="Navigation"><button type="button" class="landing-back" data-action="back">← Menü</button><span>✈ FLY TEAM <span class="landing-mode">${esc(options.mode || "Pass & Play")}</span></span></nav>
        <div data-view="gallery">
          <div class="landing-hero"><span class="landing-eyebrow">FLUGVORBEREITUNG</span><h1>Wähle deine Landung.</h1><p>Von Montréal bis Paro. Ein neuer Anflug wartet auf euch.</p><div class="landing-stats"><span>21 Landungen</span><span>11 Flughäfen</span><span>4 Schwierigkeitsstufen</span></div></div>
          <div class="landing-notice"><b>Bereit für die Landung.</b> Die Szenariovorgaben stammen aus dem Logbuch; die Fotos sind frei lizenzierte Stadt- und Landschaftspanoramen der Reiseziele. Alle 21 Originalstrecken sind aus deinen Fotos übernommen. Alle Zusatzmodule und die sechs Fähigkeiten sind aktiv. Wählt vor dem Start das für eure Landung vorgesehene Kartenset.</div>
          <div class="landing-controls"><div class="landing-filters" role="group" aria-label="Landungen filtern"><button type="button" data-filter="all">Alle 21</button>${catalog.difficulties.map(d => `<button type="button" data-filter="${d.id}" style="--level:${d.color}"><i></i>${esc(d.label)}</button>`).join("")}<button type="button" data-filter="custom">Eigene Strecken</button></div><label class="landing-search">Flughafen suchen<input type="search" placeholder="Stadt, Flughafen oder Code …" autocomplete="off"></label></div>
          <p class="landing-result-count" role="status" aria-live="polite"></p><div class="landing-grid"></div><p class="landing-credit">Fotos: Wikimedia Commons · <a href="bildnachweise.html" target="_blank" rel="noopener">Bildnachweise und Lizenzen ↗</a> · <a href="${esc(catalog.source.rules_url)}" target="_blank" rel="noopener">Spielregeln bei Dized ↗</a></p>
        </div>
        <div data-view="detail" class="versteckt"></div>
      </div>`;
    const gallery = root.querySelector('[data-view="gallery"]');
    const details = root.querySelector('[data-view="detail"]');
    const grid = root.querySelector('.landing-grid');
    const normalize = text => text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("de");
    function renderGrid() {
      const victories = read("flyteam-landings-v1", {});
      const matches = catalog.scenarios.filter(s => (filter === "custom" ? s.kind === "custom" : s.kind === "logbook" && (filter === "all" || s.difficulty === filter))
        && normalize(`${s.code} ${s.name} ${s.city} ${s.country}`).includes(normalize(query.trim())));
      root.querySelectorAll('[data-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.filter === filter)));
      root.querySelector('.landing-result-count').textContent = `${matches.length} ${matches.length === 1 ? "Landung" : "Landungen"}${filter === "custom" ? " · eigene Strecken" : " · Logbuch"}`;
      grid.innerHTML = matches.length ? matches.map(s => {
        const d = difficulty(s), won = Boolean(victories[progressKey(s)]);
        return `<button type="button" class="landing-card" style="--level:${d.color}" data-scenario="${esc(s.id)}" aria-label="${esc(s.code)} ${esc(s.name)}, ${esc(d.label)}, ${s.kind === 'logbook' ? (s.practice ? 'Originalstrecke mit Übungsregeln' : 'Originalstrecke') : 'eigene Strecke'}">
          <div class="landing-card-image">${imageHTML(s)}${photo(s) ? `<span class="landing-photo-label" title="Foto: ${esc(photo(s).author)} · ${esc(photo(s).license)}">${esc(photo(s).author)} · ${esc(photo(s).license)}</span>` : ''}<span class="landing-level">${esc(d.label)}</span>${won ? `<span class="landing-completed">✓ ${s.practice ? 'Übung geschafft' : 'Gelandet'}</span>` : ''}</div>
          <div class="landing-card-body"><div class="landing-destination"><strong>${esc(s.code)}</strong><span>${esc(s.city)} · ${esc(s.country)}</span></div><h2>${esc(s.name)}</h2><p>${esc(s.description)}</p><div class="landing-card-modules">${moduleHTML(s)}${s.ability_count ? `<span class="landing-chip">☆ ${s.ability_count} ${s.ability_count === 1 ? "Karte" : "Karten"}</span>` : ''}${!s.modules.length && !s.ability_count ? '<span class="landing-chip">Grundspiel</span>' : ''}</div><div class="landing-card-footer"><span>${s.kind === 'logbook' ? (s.practice ? 'Original · Übungsregeln' : 'Originalstrecke') : 'Eigene Strecke'}</span><b>Vorbereiten →</b></div></div></button>`;
      }).join('') : '<div class="landing-empty">Keine Landung gefunden. Versuche einen anderen Suchbegriff.</div>';
    }
    function selectedCards() {
      const saved = drafts[selected.id];
      return Array.isArray(saved) ? [...new Set(saved)].filter(id => catalog.abilities.some(a => a.id === id)).slice(0, selected.ability_count) : [];
    }
    function renderDetail(focus = false) {
      const s = selected, d = difficulty(s), cards = selectedCards();
      details.innerHTML = `<button type="button" class="landing-back" data-action="gallery">← Alle Landungen</button>
        <div class="landing-detail-top" style="--level:${d.color}"><div class="landing-detail-visual"><div class="landing-detail-image">${imageHTML(s)}<span class="landing-level">${esc(d.label)}</span></div>${photoCredit(s)}</div><div class="landing-detail-intro"><span class="landing-eyebrow">${esc(s.country)} · ${s.kind === 'logbook' ? 'ORIGINALSTRECKE' : 'EIGENE STRECKE'}</span><h1 tabindex="-1">${esc(s.code)} <span>${esc(s.name)}</span></h1><p>${esc(s.description)}</p><div class="landing-card-modules">${moduleHTML(s)}${s.ability_count ? `<span class="landing-chip">☆ ${s.ability_count} ${s.ability_count === 1 ? "Fähigkeitskarte" : "Fähigkeitskarten"}</span>` : ''}</div>${s.kind === "logbook" ? `<p class="landing-detail-note">Originalstrecke aus deinem Spielmaterial. ${s.practice ? `<b>Übungsregeln: noch ohne ${s.modules.map(id => esc(catalog.modules[id].name)).join(", ")}${s.ability_count ? " und Karteneffekte" : ""}.</b>` : (s.modules.length || s.ability_count ? "Alle vorgesehenen Module und euer Kartenset sind aktiv." : "Diese Landung benötigt keine Zusatzmodule oder Fähigkeitskarten.")}</p>${s.source_note ? `<p class="landing-detail-note">${esc(s.source_note)}</p>` : ""}` : ""}</div></div>
        <section class="landing-route"><h2>Deine ${s.practice ? 'Übungsstrecke' : 'Strecke'}</h2><p>${s.track.length} Felder · Grundregeln${s.track.some(r => Number(r.split(' ')[1])) ? ' · Verkehrswürfel' : ''}${s.track.some(r => r.split(' ').slice(2).join(' ') !== '-2 2') ? ' · Kurven' : ''}</p><ol class="landing-route-strip">${s.track.map((row,i) => { const [planes,traffic,lo,hi] = row.split(' ').map(Number); return `<li><b>${i === s.track.length - 1 ? '⚑' : s.track.length - 1 - i}</b><span aria-label="${planes} Flugzeuge">${'✈'.repeat(planes) || '·'}</span><small>${traffic ? `⚄ ×${traffic}` : '—'}</small><small>${lo !== -2 || hi !== 2 ? `${lo} … ${hi}` : 'frei'}</small></li>`; }).join('')}</ol></section>
        <section class="landing-loadout"><div class="landing-section-title"><h2>Fähigkeitskarten</h2><span>${cards.length} / ${s.ability_count} ausgewählt</span></div><p>${s.ability_count ? 'Wählt genau die angegebene Zahl unterschiedlicher Fähigkeiten. Euer Set wird auf diesem Gerät gespeichert und ist während des Flugs aktiv.' : 'Für diese Landung sieht das Logbuch keine Fähigkeitskarten vor.'}</p>${s.ability_count ? `<div class="landing-abilities">${catalog.abilities.map(a => `<button type="button" class="landing-ability" data-ability="${a.id}" aria-pressed="${cards.includes(a.id)}" ${!cards.includes(a.id) && cards.length >= s.ability_count ? 'disabled' : ''}><span class="landing-ability-mark">${cards.includes(a.id) ? '✓' : '+'}</span><strong>${esc(a.name)}</strong><small>${esc(a.original_name)}</small><p>${esc(a.description)}</p></button>`).join('')}</div><p class="landing-detail-note">Die Fähigkeiten dieses Sets sind im Spiel aktiv. Die deutschen Namen sind Arbeitsübersetzungen.</p>` : ''}</section>
        <div class="landing-launch"><div><b>${esc(s.code)} · ${esc(d.label)}</b><span>${s.kind === 'logbook' ? (s.practice ? 'Originalstrecke · Übungsregeln' : (s.modules.length ? `Originalstrecke · ${s.modules.map(id => catalog.modules[id].name).join(' · ')}` : 'Originalstrecke · Grundspiel')) : 'Partie mit eigener Strecke'}</span></div><button type="button" class="landing-start" data-action="start" ${busy || cards.length !== s.ability_count ? 'disabled' : ''}>${busy ? 'Wird vorbereitet …' : esc(options.startLabel || (s.practice ? 'Übungsflug starten →' : 'Spiel starten →'))}</button><p class="landing-launch-status" role="status" aria-live="polite"></p></div>`;
      gallery.classList.add('versteckt'); details.classList.remove('versteckt');
      if (focus) { window.scrollTo(0,0); details.querySelector('h1').focus({preventScroll:true}); }
    }
    root.addEventListener('input', event => {
      if (event.target.matches('input[type="search"]')) { query = event.target.value; renderGrid(); }
    });
    root.addEventListener('click', async event => {
      const button = event.target.closest('button');
      if (!button || !root.contains(button) || button.disabled) return;
      if (busy && button.dataset.action !== 'back') return;
      if (button.dataset.filter) { filter = button.dataset.filter; renderGrid(); }
      if (button.dataset.scenario) {
        selected = catalog.scenarios.find(s => s.id === button.dataset.scenario);
        write('flyteam-selection-v1', {id:selected.id}); detail = true; renderDetail(true);
      }
      if (button.dataset.ability) {
        const cards = selectedCards(), id = button.dataset.ability;
        drafts[selected.id] = cards.includes(id) ? cards.filter(c => c !== id) : [...cards,id].slice(0,selected.ability_count);
        write('flyteam-loadout-drafts-v1', drafts); renderDetail();
        details.querySelector(`[data-ability="${id}"]`)?.focus({preventScroll:true});
      }
      if (button.dataset.action === 'back') options.onBack();
      if (button.dataset.action === 'gallery') {
        detail = false; details.classList.add('versteckt'); gallery.classList.remove('versteckt'); renderGrid();
        grid.querySelector(`[data-scenario="${selected.id}"]`)?.focus({preventScroll:true});
      }
      if (button.dataset.action === 'start' && !busy) {
        if (selectedCards().length !== selected.ability_count) return;
        busy = true; renderDetail();
        try { await options.onStart({...selected, ability_ids:selectedCards()}); }
        catch (error) { renderDetail(); details.querySelector('.landing-launch-status').textContent = `Start fehlgeschlagen: ${error.message}. Bitte erneut versuchen.`; }
        finally { busy = false; const start = details.querySelector('[data-action="start"]'); if (start) { start.disabled = false; start.textContent = options.startLabel || (selected.practice ? 'Übungsflug starten →' : 'Spiel starten →'); } }
      }
    });
    renderGrid();
    return {
      show() { root.classList.remove('versteckt'); if (detail) renderDetail(); else renderGrid(); window.scrollTo(0,0); },
      hide() { root.classList.add('versteckt'); },
      selected() { return selected; },
    };
  }

  function updateFlight(z) {
    const s = catalog.scenarios.find(s => s.id === z.szenario_id);
    const summary = document.getElementById('flight-summary');
    if (summary && !document.getElementById('spiel-ui')?.classList.contains('versteckt')) {
      summary.classList.remove('versteckt');
      const full = `${s ? `${s.code} · ${s.name} · ${difficulty(s).label}` : (z.flughafen_name || '')} · ${s?.kind === 'logbook' ? (z.uebung ? 'Übungsflug · Zusatzmodule und Karten inaktiv' : (s.modules.length ? `Originalstrecke · ${s.modules.map(id => catalog.modules[id].name).join(' · ')}` : 'Originalstrecke · Grundspiel')) : 'Eigene Strecke'}`;
      const icons = !z.uebung && s?.modules.map(id => catalog.modules[id].icon).join(' ');
      summary.textContent = s ? `${s.code} · ${s.kind === 'logbook' ? difficulty(s).label : 'Eigene Strecke'}${z.uebung ? ' · Übung' : (icons ? ` · ${icons}` : '')}` : (z.flughafen_name || 'Eigene Strecke');
      summary.title = full;
      summary.setAttribute('aria-label', full);
    }
    if (s && z.status === 'gewonnen') {
      const victories = read('flyteam-landings-v1', {}), key = `${z.mock || z.uebung ? "practice" : "route"}:${s.id}`;
      if (!victories[key]) { victories[key] = new Date().toISOString(); write('flyteam-landings-v1', victories); }
    }
  }
  window.Landings = { mount, updateFlight };
})();
