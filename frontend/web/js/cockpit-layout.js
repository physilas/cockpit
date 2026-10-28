/* Fit navigation strips into the real viewport; keep dice and fields tappable. */
window.CockpitLayout = (() => {
  let mobileUnit = 36, frame = null, refresh = null, current = null;
  const compact = () => matchMedia('(max-width: 600px)').matches;
  function viewport() {
    document.documentElement.style.setProperty('--cockpit-vh', `${Math.round(window.visualViewport?.height || innerHeight)}px`);
  }
  function fit(state, rerender) {
    current = state; refresh = rerender; viewport();
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const main = document.getElementById('spiel-ui');
      if (!compact() || !main || main.classList.contains('versteckt')) return;
      const strips = document.getElementById('tracks-leiste');
      const columns = [...strips.querySelectorAll('.vtrack-col')];
      const chrome = Math.max(...columns.map(col => col.offsetHeight - col.querySelector('.vtrack').offsetHeight));
      const bottom = Math.max(...[...main.children].map(el => el.getBoundingClientRect().bottom));
      const content = bottom - main.getBoundingClientRect().top + main.scrollTop + parseFloat(getComputedStyle(main).paddingBottom);
      const other = content - strips.offsetHeight;
      const rows = Math.max(1, state.hoehe / 1000 + 1, state.entfernung + 1);
      const next = Math.max(18, Math.min(36, Math.floor((main.clientHeight - other - chrome - 2) / rows)));
      if (next !== mobileUnit) { mobileUnit = next; rerender(); }
    });
  }
  const resize = () => { if (current && refresh) fit(current, refresh); else viewport(); };
  window.addEventListener('resize', resize);
  window.visualViewport?.addEventListener('resize', resize);
  viewport();
  return {
    unit(state) {
      if (compact()) return mobileUnit;
      return state.module.includes('intern') ? Math.max(18, Math.min(36, Math.floor((innerHeight - 590 - (state.zusatzaktion ? 32 : 0)) / Math.max(7, state.entfernung + 1)))) : 36;
    },
    fit,
  };
})();
