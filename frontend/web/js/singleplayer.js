/* Static GitHub Pages: local inference and IndexedDB learning records. */
window.Singleplayer = (() => {
  const catalog = window.COCKPIT_AI_CATALOG;
  const names = {play: "Mit KI spielen", feedback: "KI-ndergartenbetreuung", examples: "KI-no"};
  const roleNames = {pilot: "Pilotin", kopilot: "Co-Pilot"};
  const qualifiedModels = () => catalog.models.filter(m => m.quality?.approved === true);
  const isPreview = model => model?.preview?.enabled === true;
  const selectableModels = () => catalog.models.filter(m => m.quality?.approved === true || isPreview(m));
  const modelLabel = model => `${model.name || model.run}${isPreview(model) ? " · Entwicklung" : ""}`;
  const supports = (model, airport) => Boolean(model && (model.supported_airports || [model.airport]).includes(airport));
  const hasCaseManifest = model => isPreview(model) && Object.prototype.hasOwnProperty.call(model.preview, "supported_cases");
  const caseKey = (airport, cards) => `${airport}|${[...cards].sort().join(",")}`;
  const supportedCases = (model, route) => {
    if (!route || !isPreview(model) || model.schema?.version !== 3 || !supports(model, route.engine_code)
        || !Array.isArray(model.preview.supported_cases)
        || (model.preview.positive_only !== undefined && typeof model.preview.positive_only !== "boolean")) return [];
    const known = new Set(window.LANDING_CATALOG.abilities.map(card => card.id)), seen = new Set();
    return model.preview.supported_cases.filter(row => {
      if (row?.airport !== route.engine_code || !Array.isArray(row.abilities) || row.abilities.length !== route.ability_count
          || new Set(row.abilities).size !== row.abilities.length || !row.abilities.every(card => known.has(card))) return false;
      const key = caseKey(row.airport, row.abilities);
      const result = model.preview.case_results?.[key];
      if (!result || !Number.isInteger(result.games) || result.games < 1
          || !Number.isInteger(result.wins) || result.wins < 0 || result.wins > result.games
          || !Number.isFinite(result.win_rate) || result.win_rate !== result.wins / result.games
          || model.preview.positive_only === true && result.wins === 0) return false;
      if (seen.has(key)) return false;
      seen.add(key); return true;
    }).map(row => ({airport:row.airport,abilities:[...row.abilities].sort()}));
  };
  const supportsRoute = (model, route) => Boolean(route && supports(model, route.engine_code)
    && ((route.ability_count || hasCaseManifest(model)) ? supportedCases(model, route).length : true));
  const supportsCase = (model, route, cards) => Boolean(route && Array.isArray(cards) && supportsRoute(model, route)
    && ((route.ability_count || hasCaseManifest(model)) ? supportedCases(model, route).some(row => caseKey(row.airport,row.abilities) === caseKey(route.engine_code,cards)) : cards.length === 0));
  const supportsFeedback = (model, route, cards = null) => Boolean(route && supportsRoute(model, route)
    && ((route.ability_count || hasCaseManifest(model)) ? model.schema?.version === 3 && (cards === null || supportsCase(model,route,cards))
      : !route.modules.length || (model.schema?.version === 3 && route.modules.length === 1 && ["kerosene", "intern"].includes(route.modules[0]))));
  const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const clone = value => JSON.parse(JSON.stringify(value));
  let api, setup = null, session = null, policy = null, reroll = null;
  let menuStep = "mode";
  let timer = null, generation = 0, paused = "", starting = false, storageError = "";
  let feedbackIndex = null, saveQueue = Promise.resolve(), memory = new Map();
  let feedbackHeaderObserver = null;
  let feedbackInfoOpen = false;
  let feedbackUndoStack = [];
  let cloudTimer = null, cloudBusy = false, retryDelay = 5000;
  const root = () => document.getElementById("singleplayer-menu");
  const active = () => Boolean(session);
  const aiRole = () => setup?.humanRole === "pilot" ? "kopilot" : "pilot";
  const hasAI = () => active() && setup.mode !== "examples";
  const activeSchema = () => setup?.mode === "examples" ? catalog.schema : setup?.model?.schema || catalog.schema;
  const pending = () => session?.events.filter(e => e.feedback && !e.feedback.committed && !e.voided) || [];
  const feedbackEvents = () => {
    const events = pending();
    const reviewedIds = new Set(feedbackUndoStack.map(previous => previous.eventId));
    reviewedIds.add(feedbackIndex);
    for (const event of session?.events || []) {
      if (event.feedback && !event.voided && reviewedIds.has(event.id)
          && !events.some(item => item.id === event.id)) events.push(event);
    }
    return events.sort((left, right) => left.id - right.id);
  };

  const dbPromise = new Promise((resolve, reject) => {
    if (!window.indexedDB) { reject(new Error("Lokaler Speicher nicht verfügbar")); return; }
    const request = indexedDB.open("flyteam-learning-v1", 2);
    request.onupgradeneeded = () => {
      for (const name of ["sessions", "outbox"]) if (!request.result.objectStoreNames.contains(name)) request.result.createObjectStore(name, {keyPath: "id"});
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
  // Attach rejection handling immediately, including in private browsing.
  dbPromise.catch(() => { storageError = "Lokales Speichern nicht möglich. Bitte vor dem Schließen exportieren."; });

  function persist() {
    if (!session) return;
    session.data_revision = (session.data_revision || 0) + 1;
    const data = clone(session);
    memory.set(data.id, data);
    saveQueue = saveQueue.then(async () => {
      const db = await dbPromise;
      await new Promise((resolve, reject) => {
        const transaction = db.transaction(["sessions", "outbox"], "readwrite");
        transaction.objectStore("sessions").put(data);
        if (LearningCloud.enabled() && data.consent && data.events.length && ["feedback", "examples"].includes(data.mode)) {
          transaction.objectStore("outbox").put({id: data.id, revision: data.data_revision, session: data});
        }
        transaction.oncomplete = resolve;
        transaction.onerror = transaction.onabort = () => reject(transaction.error);
      });
      storageError = "";
    }).catch(() => { storageError = "Lokales Speichern fehlgeschlagen. Bitte deine Daten exportieren."; })
      .then(() => { updateStatus(); scheduleCloud(); });
  }

  function scheduleCloud(delay = 2000) {
    if (!LearningCloud.enabled() || cloudTimer || cloudBusy) return;
    cloudTimer = setTimeout(() => { cloudTimer = null; syncCloud(); }, delay);
  }

  async function syncCloud() {
    if (!LearningCloud.enabled() || cloudBusy || navigator.onLine === false) return;
    cloudBusy = true;
    try {
      await saveQueue;
      const db = await dbPromise;
      const rows = await new Promise((resolve, reject) => {
        const request = db.transaction("outbox").objectStore("outbox").getAll();
        request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error);
      });
      for (const row of rows) {
        await LearningCloud.upload({format: "flyteam-learning-session", version: 1,
          schema: row.session.schema || catalog.schema, action_mask_version: catalog.action_mask_version, session: row.session});
        await new Promise((resolve, reject) => {
          const tx = db.transaction("outbox", "readwrite"), store = tx.objectStore("outbox");
          const request = store.get(row.id);
          request.onsuccess = () => { if (request.result?.revision === row.revision) store.delete(row.id); };
          tx.oncomplete = resolve; tx.onerror = tx.onabort = () => reject(tx.error);
        });
      }
      retryDelay = 5000;
      // Pick up edits made while the previous snapshot was in flight.
      const count = await new Promise(resolve => {
        const request = db.transaction("outbox").objectStore("outbox").count();
        request.onsuccess = () => resolve(request.result); request.onerror = () => resolve(0);
      });
      if (count) { cloudBusy = false; scheduleCloud(); }
    } catch {
      cloudBusy = false; scheduleCloud(retryDelay); retryDelay = Math.min(300000, retryDelay * 2);
    } finally { cloudBusy = false; }
  }
  window.addEventListener("online", () => { clearTimeout(cloudTimer); cloudTimer = null; scheduleCloud(0); });
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "hidden") syncCloud(); });
  dbPromise.then(() => scheduleCloud()).catch(() => {});

  async function storedSessions() {
    await saveQueue;
    try {
      const db = await dbPromise;
      const rows = await new Promise((resolve, reject) => {
        const request = db.transaction("sessions").objectStore("sessions").getAll();
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
      });
      return [...new Map([...rows, ...memory.values()].map(row => [row.id, row])).values()];
    } catch { return [...memory.values()]; }
  }

  function commitFeedback(trigger, clearSelection = true) {
    for (const event of pending()) {
      event.feedback.committed = true;
      event.feedback.committed_at = new Date().toISOString();
      event.feedback.trigger = trigger;
    }
    if (clearSelection) feedbackIndex = null;
  }

  function canUndoFeedback() {
    if (!session || setup.mode !== "feedback" || !feedbackUndoStack.length) return false;
    const previous = feedbackUndoStack.at(-1);
    const event = session.events.find(item => item.id === previous.eventId);
    return Boolean(event?.feedback && !event.voided && Number.isInteger(previous.engineRevision)
      && previous.engineRevision === api.state()?.rueckgaengig_version);
  }

  function undoFeedback() {
    if (!canUndoFeedback()) return false;
    const previous = feedbackUndoStack.pop();
    const event = session.events.find(item => item.id === previous.eventId);
    event.feedback = clone(previous.feedback);
    feedbackIndex = event.id;
    persist(); renderFeedback(); api.refresh();
    return true;
  }

  async function exportData() {
    commitFeedback("export", false); persist();
    const sessions = await storedSessions();
    const data = {format: "flyteam-learning-data", version: 1, exported_at: new Date().toISOString(),
                  schema: catalog.schema, action_mask_version: catalog.action_mask_version, sessions};
    const blob = new Blob([JSON.stringify(data, null, 2)], {type: "application/json"});
    const url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = `flyteam-training-${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    renderFeedback();
    const status = document.getElementById("ai-export-status");
    if (status) status.textContent = `${sessions.length} Partien exportiert.`;
  }

  function stop(reason = "menu") {
    generation++; clearTimeout(timer); timer = null;
    if (session) {
      commitFeedback(reason);
      session.status = api.state()?.status === "laeuft" ? "aborted" : (api.state()?.status || "aborted");
      session.finished_at = new Date().toISOString(); persist();
    }
    session = null; policy = null; reroll = null; paused = "";
    feedbackInfoOpen = false;
    feedbackUndoStack = [];
    document.getElementById("ai-feedback").classList.add("versteckt");
    document.getElementById("ai-session-bar").classList.add("versteckt");
  }

  function showMenu() {
    if (!api) return;
    stop(); api.hideGame();
    document.getElementById("start-menu").classList.add("versteckt");
    root().innerHTML = `<div class="solo-shell"><button class="landing-back" id="solo-back">← Menü</button>
      <span class="landing-eyebrow" id="solo-step-count"></span><h1 id="solo-heading" tabindex="-1">Modus auswählen</h1>
      <ol class="solo-progress" aria-label="Einzelspieler-Auswahl"><li data-progress="mode">Modus</li><li data-progress="model">KI</li><li data-progress="route">Landung</li></ol>
      <section class="solo-step" data-step="mode" aria-label="Modus auswählen"><div class="solo-modes" role="group" aria-label="Spielmodus">
        <button data-mode="play" aria-pressed="true"><span>🤖</span><strong>Mit KI spielen</strong><small>Du und ein trainiertes Modell im Cockpit.</small></button>
        <button data-mode="feedback" aria-pressed="false"><span>🧸</span><strong>KI-ndergartenbetreuung</strong><small>Spiele mit der KI und bewerte ihre Entscheidungen.</small></button>
        <button data-mode="examples" aria-pressed="false"><span>🎬</span><strong>KI-no</strong><small>Pass &amp; Play: Eure Partien werden zu Lernbeispielen.</small></button>
      </div></section>
      <section class="solo-step" data-step="model" aria-label="KI auswählen" hidden><div class="solo-settings">
        <label id="solo-model-label">KI<select id="solo-model">${selectableModels().map(model => `<option value="${esc(model.id)}">${esc(modelLabel(model))}</option>`).join("")}</select></label>
        <label id="solo-role-label">Deine Rolle<select id="solo-role"><option value="pilot">Pilotin</option><option value="kopilot">Co-Pilot</option></select></label>
      </div><p id="solo-model-description" class="solo-model-description"></p>
      <button id="solo-next" class="landing-start">Landung auswählen →</button></section>
      <section class="solo-step" data-step="route" aria-label="Landung auswählen" hidden><div class="solo-settings">
        <label id="solo-route-label">Landung<select id="solo-route"></select></label>
        <label id="solo-abilities-label" hidden>Fähigkeitskarten<select id="solo-abilities"></select></label>
      </div><p id="solo-description" class="solo-description"></p>
      <label id="solo-consent-label" class="solo-consent" hidden><input id="solo-consent" type="checkbox"><span>Ich bin einverstanden, dass meine Spielzüge, KI-Bewertungen und das Spielergebnis ohne Namen oder E-Mail-Adresse gespeichert und zur Verbesserung der KI an den Betreiber übermittelt werden.</span></label>
      <p id="solo-learning-note" class="solo-storage-note">Die KI lernt später aus den gesammelten Beispielen und Bewertungen.</p>
      <button id="solo-start" class="landing-start">Mit KI starten →</button><p id="solo-error" role="alert"></p>
      <details class="solo-data"><summary>Eigene Aufzeichnungen</summary><div><button id="solo-export">Aufzeichnungen exportieren</button><span id="ai-export-status" role="status"></span></div>
      <p class="solo-storage-note" id="solo-storage-status"></p></details></section></div>`;
    setup = {mode: "play", humanRole: "pilot", model: null};
    // Start with a qualified crew for the first standard base-game landing.
    const firstRoute = window.LANDING_CATALOG.scenarios.find(s => !s.modules.length && !s.ability_count);
    const preferred = [...qualifiedModels()].filter(m => !isPreview(m) && supportsRoute(m, firstRoute)).sort((a,b) =>
      Number(Boolean(b.recommended)) - Number(Boolean(a.recommended)) ||
      Number(b.checkpoint === "latest") - Number(a.checkpoint === "latest") || b.steps - a.steps)[0];
    if (preferred) document.getElementById("solo-model").value = preferred.id;
    document.getElementById("solo-back").onclick = () => {
      if (starting) return;
      if (menuStep === "route") setMenuStep(setup.mode === "examples" ? "mode" : "model");
      else if (menuStep === "model") setMenuStep("mode");
      else { root().classList.add("versteckt"); api.mainMenu(); }
    };
    root().querySelectorAll("[data-mode]").forEach(button => button.onclick = () => {
      if (starting) return;
      if (setup.mode !== button.dataset.mode) document.getElementById("solo-consent").checked = false;
      setup.mode = button.dataset.mode;
      setMenuStep(setup.mode === "examples" ? "route" : "model");
    });
    document.getElementById("solo-next").onclick = () => { if (!starting && setup.model) setMenuStep("route"); };
    document.getElementById("solo-model").onchange = updateMenu;
    document.getElementById("solo-route").onchange = updateMenu;
    document.getElementById("solo-abilities").onchange = updateMenu;
    document.getElementById("solo-consent").onchange = updateMenu;
    document.getElementById("solo-start").onclick = launch;
    document.getElementById("solo-export").onclick = exportData;
    root().classList.remove("versteckt"); setMenuStep("mode");
    storedSessions().then(rows => {
      const label = document.getElementById("solo-storage-status");
      if (label) label.textContent = storageError || `${rows.length} aufgezeichnete Partien auf diesem Gerät.`;
    });
  }

  function setMenuStep(step) {
    menuStep = step;
    updateMenu();
    document.getElementById("solo-heading").focus({preventScroll:true});
    window.scrollTo(0,0);
  }

  function updateMenu() {
    const examples = setup.mode === "examples";
    const steps = examples ? ["mode", "route"] : ["mode", "model", "route"];
    root().dataset.step = menuStep;
    root().querySelectorAll("[data-step]").forEach(panel => { panel.hidden = panel.dataset.step !== menuStep; });
    root().querySelectorAll("[data-progress]").forEach(item => {
      item.hidden = !steps.includes(item.dataset.progress);
      if (item.dataset.progress === menuStep) item.setAttribute("aria-current", "step");
      else item.removeAttribute("aria-current");
    });
    document.getElementById("solo-step-count").textContent = `SINGLEPLAYER · SCHRITT ${steps.indexOf(menuStep) + 1} VON ${steps.length}`;
    document.getElementById("solo-heading").textContent = {mode:"Modus auswählen",model:"KI auswählen",route:"Landung auswählen"}[menuStep];
    document.getElementById("solo-back").textContent = menuStep === "mode" ? "← Menü" : "← Zurück";
    document.getElementById("solo-back").disabled = starting;
    root().querySelectorAll("[data-mode]").forEach(b => {
      b.setAttribute("aria-pressed", String(b.dataset.mode === setup.mode)); b.disabled = starting;
    });
    for (const id of ["solo-model", "solo-role", "solo-route", "solo-abilities", "solo-consent"]) document.getElementById(id).disabled = starting;
    document.getElementById("solo-consent-label").hidden = setup.mode === "play";
    document.getElementById("solo-learning-note").hidden = setup.mode === "play";
    const selector = document.getElementById("solo-model"), previousModel = selector.value;
    const scenarios = window.LANDING_CATALOG.scenarios;
    const choices = selectableModels().filter(m => scenarios.some(route => supportsRoute(m, route)
      && (setup.mode !== "feedback" || supportsFeedback(m, route))))
      .sort((a,b) => Number(b.quality?.approved === true) - Number(a.quality?.approved === true)
        || Number(Boolean(b.recommended)) - Number(Boolean(a.recommended)));
    selector.innerHTML = choices.map(m => `<option value="${esc(m.id)}">${esc(modelLabel(m))}</option>`).join("");
    if (choices.some(m => m.id === previousModel)) selector.value = previousModel;
    setup.model = examples ? null : choices.find(m => m.id === selector.value) || null;
    const routes = scenarios.filter(route => examples ? !route.modules.length && !route.ability_count
      : supportsRoute(setup.model, route) && (setup.mode !== "feedback" || supportsFeedback(setup.model, route)));
    const routeSelector = document.getElementById("solo-route"), previousRoute = routeSelector.value;
    routeSelector.innerHTML = routes.map(s => `<option value="${esc(s.id)}">${esc(s.code)} · ${esc(s.name)}${s.modules.map(module => ` · ${esc(window.LANDING_CATALOG.modules[module]?.name || module)}`).join("")}${s.ability_count ? ` · ${s.ability_count} ${s.ability_count === 1 ? "Karte" : "Karten"}` : ""}${s.kind === "custom" ? " · Eigene Strecke" : ""}</option>`).join("");
    routeSelector.value = routes.find(s => s.id === previousRoute)?.id || routes[0]?.id || "";
    const selectedRoute = routes.find(s => s.id === routeSelector.value);
    document.getElementById("solo-model-description").textContent = !setup.model ? "Keine KI verfügbar."
      : `${isPreview(setup.model) ? "Testmodell · noch nicht unabhängig qualifiziert. " : ""}${routes.length} ${routes.length === 1 ? "Landung verfügbar" : "Landungen verfügbar"}.`;
    document.getElementById("solo-next").disabled = starting || !setup.model || !routes.length;
    const cardSelector = document.getElementById("solo-abilities"), previousCase = cardSelector.value;
    const cases = setup.model && selectedRoute?.ability_count ? supportedCases(setup.model, selectedRoute) : [];
    cardSelector.innerHTML = cases.map(row => `<option value="${esc(caseKey(row.airport,row.abilities))}">${row.abilities.map(id => esc(window.LANDING_CATALOG.abilities.find(card => card.id === id).name)).join(" + ")}</option>`).join("");
    if (cases.some(row => caseKey(row.airport,row.abilities) === previousCase)) cardSelector.value = previousCase;
    const selectedCase = cases.find(row => caseKey(row.airport,row.abilities) === cardSelector.value);
    setup.abilities = selectedCase ? [...selectedCase.abilities] : [];
    setup.caseKey = selectedRoute ? caseKey(selectedRoute.engine_code,setup.abilities) : "";
    document.getElementById("solo-abilities-label").hidden = examples || !selectedRoute?.ability_count;
    const preview = isPreview(setup.model);
    const successRate = selectedRoute?.ability_count || hasCaseManifest(setup.model) ? setup.model?.preview?.case_results?.[setup.caseKey]?.win_rate
      : (preview ? setup.model.preview.route_results : setup.model?.quality?.route_results)?.[selectedRoute?.engine_code]?.win_rate;
    document.getElementById("solo-description").textContent = examples
      ? "Ihr spielt beide Rollen wie bei Pass & Play. Eure Aktionen und der Spielausgang werden als Beispiele aufgezeichnet."
      : !setup.model ? "Für diese Strecke ist noch keine KI verfügbar."
      : `${selectedRoute?.code || ""} · ${preview ? "Testversion: Entwicklungsstand, noch nicht unabhängig qualifiziert. " : ""}${setup.mode === "feedback" ? "Bewerte KI-Aktionen oben mit 👎 oder 👍. Dein Klick speichert sofort; Rückgängig nimmt die letzte Bewertung zurück. Keine Auswahl ist neutral." : "Die KI übernimmt die zweite Rolle. Ihre freien Würfel bleiben verdeckt."}${Number.isFinite(successRate) ? ` ${preview ? "Entwicklungstest" : "Getestet"} im KI-Selbstspiel: ${(successRate*100).toLocaleString("de-DE", {maximumFractionDigits:1})} % erfolgreiche Landungen.` : ""}`;
    document.getElementById("solo-start").disabled = starting || !selectedRoute || (!examples && !setup.model)
      || (!examples && !supportsCase(setup.model,selectedRoute,setup.abilities))
      || (setup.mode !== "play" && !document.getElementById("solo-consent").checked);
    document.getElementById("solo-start").textContent = starting ? "Wird vorbereitet …" : examples ? "Beispielpartie starten →" : "Mit KI starten →";
  }

  async function launch() {
    if (starting || menuStep !== "route") return;
    if (setup.mode !== "play" && !document.getElementById("solo-consent").checked) return;
    const version = ++generation;
    const config = {...setup, abilities:[...(setup.abilities || [])], humanRole: document.getElementById("solo-role").value};
    const scenario = window.LANDING_CATALOG.scenarios.find(s => s.id === document.getElementById("solo-route").value);
    if (!scenario) { document.getElementById("solo-error").textContent = "Die Strecke dieses Modells ist nicht verfügbar."; return; }
    if (config.mode !== "examples" && (!config.model || !supportsCase(config.model,scenario,config.abilities))) return;
    if (scenario.ability_count && document.getElementById("solo-abilities").value !== caseKey(scenario.engine_code,config.abilities)) return;
    if (config.mode === "feedback" && !supportsFeedback(config.model, scenario, config.abilities)) return;
    starting = true; updateMenu();
    try {
      let loadedPolicy = null;
      if (config.mode !== "examples") {
        const response = await fetch(config.model.url);
        if (!response.ok) throw new Error("Modell konnte nicht geladen werden. Bitte Verbindung prüfen und erneut versuchen.");
        loadedPolicy = CockpitPolicy.create(await response.json(), {schema: config.model.schema || catalog.schema});
      }
      if (version !== generation) return;
      setup = config; policy = loadedPolicy;
      // Recording begins before the first render can schedule the AI.
      session = {id: crypto.randomUUID(), created_at: new Date().toISOString(), mode: config.mode,
                 scenario: {id: scenario.id, engine_code: scenario.engine_code,ability_ids:[...config.abilities],case_key:caseKey(scenario.engine_code,config.abilities)}, human_role: config.mode === "examples" ? null : config.humanRole,
                 model: config.model && config.mode !== "examples" ? clone(config.model) : null,
                 schema_version: activeSchema().version, schema: activeSchema(), action_mask_version: catalog.action_mask_version,
                 consent: config.mode === "play" ? null : {version: "2026-10-18", accepted_at: new Date().toISOString()},
                 status: "active", events: [], engine_stack: []};
      await api.start({...scenario, ability_ids: [...config.abilities]});
      if (version !== generation) return;
      root().classList.add("versteckt"); persist();
      navigator.storage?.persist?.().catch(() => {});
    } catch (error) {
      stop("start_failed"); root().classList.remove("versteckt");
      document.getElementById("solo-error").textContent = error.message;
    } finally { starting = false; if (!root().classList.contains("versteckt")) updateMenu(); }
  }

  function actionId(action) {
    return activeSchema().actions.findIndex(a => {
      if (a.kind !== action.kind) return false;
      if (["place", "bonus_place"].includes(a.kind)) {
        const s = activeSchema().slots[a.slot];
        return (a.kind === "bonus_place" || a.die === action.die) && s.target === action.target
          && (s.owner === null || s.owner === (action.target_owner || action.role))
          && s.index === (action.index ?? null) && (s.target !== "funk" || s.radio_index === (action.radio_index || 0));
      }
      if (a.kind === "coffee") return a.die === action.die && a.delta === action.delta;
      if (a.kind === "bonus_coffee") return a.delta === action.delta;
      if (["adaptation", "anticipation", "swap_choose"].includes(a.kind)) return a.die === action.die;
      if (a.kind === "reroll_select") return a.subset === action.subset;
      return true;
    });
  }

  function decision(role) {
    const steps = session.events.filter(e => !e.voided && e.action_id !== null).length;
    return api.decision(role, reroll ? {initiator: reroll.initiator, selections: reroll.selections} : null,
                        steps, setup.model?.max_steps || 256,
                        hasAI() && role === aiRole() ? setup.model?.assistance_version || 0 : 0, activeSchema().version);
  }

  function beforeAction(action, actor = "human", suppliedDecision = null) {
    if (!active()) return null;
    const id = actionId(action);
    return {action: clone(action), action_id: id < 0 ? null : id, actor,
            decision: id < 0 ? null : suppliedDecision || decision(action.role),
            engine_before: api.state()?.rueckgaengig_version};
  }

  function afterAction(context, answer) {
    if (!context || !session || !answer.ergebnis.erfolg) return;
    feedbackUndoStack = [];
    if (context.actor === "human") commitFeedback("human_action");
    const e = {id: session.events.length, timestamp: new Date().toISOString(),
               ...context, engine_after: answer.zustand.rueckgaengig_version,
               outcome: {status: answer.zustand.status, reason: answer.zustand.verlust_grund || "", round: answer.zustand.runde},
               public_after: api.decision(null, reroll && Object.values(reroll.selections).some(s => s === null)
                 ? {initiator: reroll.initiator, selections: reroll.selections} : null,
                 session.events.length + 1, setup.model?.max_steps || 256, 0, activeSchema().version).public_state,
               training_compatible: context.action_id !== null && Boolean(context.decision?.action_mask[context.action_id]), voided: false};
    if (setup.mode === "feedback" && context.actor === "ai") {
      e.feedback = {value: 0, explicit: false, committed: false}; feedbackIndex = e.id;
    }
    session.events.push(e);
    if (e.engine_after !== e.engine_before) session.engine_stack.push(e.id);
    if (answer.zustand.status !== "laeuft") {
      session.status = answer.zustand.status; session.finished_at = e.timestamp;
    }
    persist(); renderFeedback();
  }

  function label(action) {
    if (action.kind === "place") return `Würfel ${action.die + 1} → ${COCKPIT_SCHEMA.feld_layout.find(f => f.ziel === action.target)?.label || action.target}${action.index != null ? ` ${action.index + 1}` : ""}`;
    if (action.kind === "bonus_place") return `Zusatzwürfel → ${COCKPIT_SCHEMA.feld_layout.find(f => f.ziel === action.target)?.label || action.target}${action.index != null ? ` ${action.index + 1}` : ""}`;
    if (action.kind === "bonus_roll") return "Schwarzen Zusatzwürfel werfen";
    if (action.kind === "bonus_coffee") return `Kaffee: Zusatzwürfel ${action.delta > 0 ? "+" : ""}${action.delta}`;
    if (action.kind === "coffee") return `Kaffee: Würfel ${action.die + 1} ${action.delta > 0 ? "+" : ""}${action.delta}`;
    return action.kind === "reroll_start" ? "Gemeinsamen Neuwurf starten" : "Würfel für den Neuwurf auswählen";
  }

  const ratingText = value => value === 0 ? "Neutral" : `${value > 0 ? "+" : "−"}${Math.abs(value)}`;

  function positionFeedback(panel) {
    // Sticky stays in the board's layout, so it does not cover its first controls.
    // Measure the actual header: its height includes the device's safe-area inset.
    const game = document.getElementById("spiel-ui"), header = document.getElementById("game-header");
    if (game && game.firstElementChild !== panel) game.prepend(panel);
    const updateOffset = () => panel.style.setProperty("--ai-feedback-top", `${header?.getBoundingClientRect().height || 0}px`);
    updateOffset();
    if (!feedbackHeaderObserver && header && window.ResizeObserver) {
      feedbackHeaderObserver = new ResizeObserver(updateOffset);
      feedbackHeaderObserver.observe(header);
    }
  }

  function renderFeedback() {
    const panel = document.getElementById("ai-feedback"), events = feedbackEvents();
    const visible = active() && setup.mode === "feedback";
    panel.classList.toggle("versteckt", !visible);
    if (!visible) {
      feedbackInfoOpen = false;
      panel.classList.remove("ai-feedback-expanded");
      panel.onkeydown = null;
      panel.replaceChildren(); return;
    }
    const focusedId = panel.contains(document.activeElement) ? document.activeElement.id : null;
    positionFeedback(panel);
    const selected = events.find(e => e.id === feedbackIndex) || events.at(-1);
    feedbackIndex = selected?.id ?? null;
    const value = selected?.feedback.value || 0;
    panel.innerHTML = `<output id="ai-rating-value" class="ai-feedback-sr-only" aria-live="polite" aria-atomic="true">${ratingText(value)}</output>
      <div class="ai-feedback-toolbar">
      <div class="ai-feedback-thumbs" role="group" aria-label="${esc(selected ? `KI-Aktion bewerten: ${label(selected.action)}` : "KI-Aktion bewerten")}" aria-describedby="ai-feedback-hint">
        <button id="ai-rating-down" type="button" data-feedback-value="-1" aria-label="Daumen runter" aria-pressed="${value < 0}" ${selected ? "" : "disabled"}><span aria-hidden="true">👎</span></button>
        <button id="ai-rating-up" type="button" data-feedback-value="1" aria-label="Daumen hoch" aria-pressed="${value > 0}" ${selected ? "" : "disabled"}><span aria-hidden="true">👍</span></button>
      </div>
      <button id="ai-feedback-info-toggle" type="button" aria-label="Informationen zur KI-Bewertung" aria-expanded="${feedbackInfoOpen}" aria-controls="ai-feedback-info" title="Informationen zur KI-Bewertung"><span class="ai-feedback-info-mark" aria-hidden="true">i</span></button>
      </div>
      <div id="ai-feedback-info" class="ai-feedback-info" role="region" aria-labelledby="ai-feedback-info-title" ${feedbackInfoOpen ? "" : "hidden"}>
        <div class="ai-feedback-info-heading"><strong id="ai-feedback-info-title">KI-Aktion bewerten</strong><button id="ai-feedback-info-close" type="button">Schließen</button></div>
        <p id="ai-feedback-hint">Mit 👎 oder 👍 bewerten: Dein Klick speichert sofort. Der andere Daumen ändert die Bewertung. Rückgängig nimmt die letzte Bewertung zurück; keine Auswahl ist neutral.</p>
        <div class="ai-feedback-copy"><div class="ai-feedback-heading"><strong>KI-Aktion</strong><span id="ai-feedback-info-rating">${ratingText(value)}</span></div>
        ${events.length > 1 ? `<select id="ai-feedback-action" aria-label="KI-Aktion auswählen">${events.map(e => `<option value="${e.id}" ${e.id === selected.id ? "selected" : ""}>${esc(label(e.action))} · ${ratingText(e.feedback.value)}</option>`).join("")}</select>` : `<p class="ai-feedback-current">${selected ? esc(label(selected.action)) : "Warte auf die nächste KI-Aktion."}</p>`}</div>
      </div>`;
    const infoToggle = document.getElementById("ai-feedback-info-toggle");
    const setInfoOpen = open => {
      feedbackInfoOpen = open;
      panel.classList.toggle("ai-feedback-expanded", open);
      document.getElementById("ai-feedback-info").hidden = !open;
      infoToggle.setAttribute("aria-expanded", String(open));
    };
    const closeInfo = () => { setInfoOpen(false); infoToggle.focus({preventScroll: true}); };
    setInfoOpen(feedbackInfoOpen);
    infoToggle.addEventListener("click", () => {
      const opening = !feedbackInfoOpen;
      setInfoOpen(opening);
      if (opening) document.getElementById("ai-feedback-info-close").focus({preventScroll: true});
    });
    document.getElementById("ai-feedback-info-close").addEventListener("click", closeInfo);
    panel.onkeydown = event => {
      if (event.key === "Escape" && feedbackInfoOpen) {
        event.preventDefault(); event.stopPropagation(); closeInfo();
      }
    };
    document.getElementById("ai-feedback-action")?.addEventListener("change", event => {
      feedbackIndex = Number(event.target.value); renderFeedback();
      document.getElementById("ai-feedback-action")?.focus();
    });
    panel.querySelectorAll("[data-feedback-value]").forEach(button => button.addEventListener("click", () => {
      if (!selected) return;
      const sign = Number(button.dataset.feedbackValue);
      if (selected.feedback.committed && selected.feedback.explicit && Math.sign(selected.feedback.value) === sign) return;
      feedbackUndoStack.push({eventId: selected.id, feedback: clone(selected.feedback),
        engineRevision: api.state()?.rueckgaengig_version});
      selected.feedback = {value: sign, explicit: true, committed: true,
        committed_at: new Date().toISOString(), trigger: "thumb"};
      feedbackIndex = selected.id;
      document.getElementById("ai-rating-value").textContent = ratingText(selected.feedback.value);
      document.getElementById("ai-feedback-info-rating").textContent = ratingText(selected.feedback.value);
      panel.querySelectorAll("[data-feedback-value]").forEach(other => other.setAttribute("aria-pressed", String(Math.sign(selected.feedback.value) === Number(other.dataset.feedbackValue))));
      const option = document.getElementById("ai-feedback-action")?.selectedOptions[0];
      if (option) option.textContent = `${label(selected.action)} · ${ratingText(selected.feedback.value)}`;
      persist(); api.refresh();
    }));
    if (focusedId) {
      const target = document.getElementById(focusedId);
      (target && !target.disabled && !target.closest("[hidden]") ? target : infoToggle).focus({preventScroll: true});
    }
  }

  function updateStatus() {
    const el = document.getElementById("ai-storage-status");
    if (el && session) el.textContent = storageError || `${session.events.filter(e => !e.voided && e.action_id !== null).length} Entscheidungen aufgezeichnet`;
  }

  function afterRender(state) {
    const bar = document.getElementById("ai-session-bar");
    bar.classList.toggle("versteckt", !active());
    if (!active()) return;
    renderFeedback();
    if (state.status !== "laeuft") { clearTimeout(timer); timer = null; }
    bar.innerHTML = `<div><strong>${names[setup.mode]}</strong><span>${hasAI() ? `Du: ${roleNames[setup.humanRole]} · KI: ${esc(setup.model.name || setup.model.run)} / ${setup.model.checkpoint}` : "Beide Rollen werden als Beispiele aufgezeichnet"}</span>${hasAI() && isPreview(setup.model) ? '<small>Testversion · noch nicht unabhängig qualifiziert</small>' : ""}<small id="ai-storage-status" role="status"></small></div>
      ${storageError ? '<button id="ai-game-export">Aufzeichnungen sichern</button>' : ""}${paused ? '<button id="ai-resume">KI fortsetzen</button>' : ""}<p class="ai-paused" role="alert">${esc(paused)}</p>`;
    document.getElementById("ai-game-export")?.addEventListener("click", exportData);
    document.getElementById("ai-resume")?.addEventListener("click", () => { paused = ""; afterRender(api.state()); });
    updateStatus();
    const activeRole = reroll ? nextRerollRole() : state.zusatzaktion?.rolle || state.kooperation?.wartet_auf || state.am_zug;
    const pendingAI = state.zusatzaktion?.rolle === aiRole();
    const ready = hasAI() && !paused && state.status === "laeuft" && state.phase === "platzieren"
        && !api.rerollAnimating() && (!api.roundComplete() || pendingAI)
        && activeRole === aiRole();
    if (!ready && timer) {clearTimeout(timer);timer = null;}
    if (ready && !timer) {
      const version = generation;
      timer = setTimeout(() => {
        timer = null;
        if (version !== generation || !hasAI() || paused || api.state().status !== "laeuft") return;
        const current = api.state();
        const currentRole = reroll ? nextRerollRole() : current.zusatzaktion?.rolle || current.kooperation?.wartet_auf || current.am_zug;
        if (currentRole !== aiRole()) return;
        try { playAI(); } catch (error) { paused = error.message; afterRender(api.state()); }
      }, 650);
    }
  }

  function playAI() {
    if (session.events.filter(e => !e.voided && e.action_id !== null).length >= (setup.model.max_steps || 256)) {
      throw new Error("Das Entscheidungslimit ist erreicht. Du kannst die Partie exportieren oder neu starten.");
    }
    const d = decision(aiRole()), id = policy.select(d), action = activeSchema().actions[id];
    const a = {...action, role: aiRole()};
    if (["swap_choose", "swap_cancel"].includes(action.kind)) a.cooperation_id = api.state().kooperation?.id;
    if (action.kind === "place") {
      const slot = activeSchema().slots[action.slot];
      a.target = slot.target; a.index = slot.index; a.radio_index = slot.radio_index;
    }
    if (action.kind === "bonus_place") {
      const slot = activeSchema().slots[action.slot];
      const target = api.state().zusatzaktion?.ziele.find(t => t.ziel === slot.target && (t.index ?? null) === slot.index
        && t.funk_feld === slot.radio_index && (slot.owner === null || t.ziel_besitzer === slot.owner));
      if (!target) throw new Error("Das Ziel für den KI-Zusatzwürfel ist nicht mehr verfügbar.");
      a.target = target.ziel; a.index = target.index; a.radio_index = target.funk_feld; a.target_owner = target.ziel_besitzer;
    }
    if (action.kind === "reroll_start") { beginReroll(aiRole(), "ai", d); return; }
    if (action.kind === "reroll_select") { confirmReroll(aiRole(), action.subset, "ai", d); return; }
    const answer = api.execute(a, "ai", d);
    api.showAnswer(answer);
    if (!answer.ergebnis.erfolg) throw new Error("Die KI-Aktion konnte nicht ausgeführt werden.");
  }

  function nextRerollRole() {
    return [reroll.initiator, reroll.initiator === "pilot" ? "kopilot" : "pilot"].find(role => reroll.selections[role] === null);
  }

  function beginReroll(role, actor = "human", supplied = null) {
    if (!active()) return false;
    if (reroll) { cancelReroll(); return true; }
    if (hasAI() && actor === "human" && role !== setup.humanRole) return true;
    const context = beforeAction({kind: "reroll_start", role}, actor, supplied);
    context.reroll_group = `reroll:${session.events.length}`;
    reroll = {initiator: role, selections: {pilot: null, kopilot: null}, event_ids: [], group: context.reroll_group};
    afterAction(context, {ergebnis: {erfolg: true}, zustand: api.state()});
    reroll.event_ids.push(session.events.at(-1).id);
    api.openReroll(); api.refresh(); return true;
  }

  function confirmReroll(role, subset, actor = "human", supplied = null) {
    if (!reroll || role !== nextRerollRole() || (hasAI() && actor === "human" && role !== setup.humanRole)) return;
    const d = supplied || decision(role);
    const a = {kind: "reroll_select", role, subset}, id = actionId(a);
    if (!d.action_mask[id]) { api.rerollMessage("Wählt zusammen mindestens einen verfügbaren Würfel aus."); return; }
    const context = beforeAction(a, actor, d);
    context.reroll_group = reroll.group;
    reroll.selections[role] = [0,1,2,3].filter(i => subset & (1 << i));
    if (nextRerollRole()) {
      afterAction(context, {ergebnis: {erfolg: true}, zustand: api.state()});
      reroll.event_ids.push(session.events.at(-1).id);
      api.rerollSelection(role, reroll.selections[role]); api.refresh();
    } else {
      const selections = reroll.selections;
      const answer = api.applyReroll(selections);
      if (!answer.ergebnis.erfolg) throw new Error("Der gemeinsame Neuwurf konnte nicht ausgeführt werden.");
      afterAction(context, answer); reroll = null;
      api.rerollSelection(role, selections[role]); api.rerollResult(answer); api.showAnswer(answer);
    }
  }

  function cancelReroll() {
    if (!reroll) return;
    feedbackUndoStack = [];
    for (const id of reroll.event_ids) session.events[id].voided = true;
    reroll = null;
    if (hasAI() && api.state().am_zug === aiRole()) {
      generation++; clearTimeout(timer); timer = null;
      paused = "Neuwurf abgebrochen. Setze die KI fort, wenn du bereit bist.";
    }
    persist(); renderFeedback(); api.closeReroll(); api.refresh();
  }

  function undo(answer) {
    if (!session || !answer.ergebnis.erfolg) return;
    feedbackUndoStack = [];
    feedbackIndex = null;
    const id = session.engine_stack.pop();
    if (id !== undefined) {
      const event = session.events[id]; event.voided = true;
      if (event.reroll_group) for (const other of session.events) if (other.reroll_group === event.reroll_group) other.voided = true;
    }
    if (hasAI()) {
      generation++; clearTimeout(timer); timer = null;
      paused = "Spielschritt rückgängig. Setze die KI fort, wenn du bereit bist.";
    }
    persist(); renderFeedback();
  }

  return {
    connect(adapter) { api = adapter; }, active, hasAI, aiRole, showMenu, stop, beforeAction, afterAction, afterRender, undo,
    canUndoFeedback, undoFeedback,
    hideMenu() { root().classList.add("versteckt"); },
    canControl(role) { return !hasAI() || role === setup.humanRole; },
    visibleRole() { return hasAI() ? setup.humanRole : null; },
    beginReroll, cancelReroll,
    confirmReroll(role, indices) { if (!active()) return false; confirmReroll(role, indices.reduce((bits,i) => bits | (1 << i), 0)); return true; },
    rerollRole() { return hasAI() ? setup.humanRole : null; },
    rerollPending() { return Boolean(reroll); }, exportData,
  };
})();
