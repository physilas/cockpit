/* Explicit offline preparation, including the complete local Python runtime. */
(() => {
  const button = document.getElementById("offline-download");
  const status = document.getElementById("offline-status");
  const progress = document.getElementById("offline-progress");
  const mb = bytes => (bytes / 1e6).toLocaleString("de-DE", {maximumFractionDigits: 1});
  const crews = COCKPIT_OFFLINE_ASSETS.models.length;
  let busy = false;
  async function worker() {
    if (!navigator.serviceWorker || !window.caches) throw new Error("Offline-Speicher ist in diesem Browser nicht verfügbar.");
    const registration = await Promise.race([navigator.serviceWorker.ready,
      new Promise((_, reject) => setTimeout(() => reject(new Error("Offline-Vorbereitung noch nicht bereit. Bitte online neu laden.")), 20000))]);
    if (!navigator.serviceWorker.controller) await new Promise((resolve, reject) => {
      const changed = () => { clearTimeout(timer); resolve(); };
      const timer = setTimeout(() => { navigator.serviceWorker.removeEventListener("controllerchange", changed); reject(new Error("Bitte die App einmal neu laden.")); }, 10000);
      navigator.serviceWorker.addEventListener("controllerchange", changed, {once: true});
      if (navigator.serviceWorker.controller) { navigator.serviceWorker.removeEventListener("controllerchange", changed); changed(); }
    });
    return navigator.serviceWorker.controller || registration.active;
  }
  async function request(type) {
    const target = await worker();
    return new Promise((resolve, reject) => {
      const channel = new MessageChannel();
      let timer;
      const arm = () => { clearTimeout(timer); timer = setTimeout(() => { channel.port1.close(); reject(new Error("Download unterbrochen. Bitte erneut versuchen und die App geöffnet lassen.")); }, 120000); };
      channel.port1.onmessage = ({data}) => {
        arm();
        if (data.progress !== undefined) {
          progress.hidden = false; progress.max = data.total; progress.value = data.progress;
          status.textContent = `${mb(data.progress)} von ${mb(data.total)} MB gespeichert …`;
          return;
        }
        clearTimeout(timer); channel.port1.close();
        if (data.error) reject(new Error(data.error)); else resolve(data);
      };
      arm(); target.postMessage({type, version: COCKPIT_OFFLINE_ASSETS.version}, [channel.port2]);
    });
  }
  function show(result) {
    progress.hidden = true;
    button.textContent = result.ready ? `✓ Alle ${crews} Crews offline verfügbar` : `Alle ${crews} Crews offline speichern · ${mb(COCKPIT_OFFLINE_ASSETS.bytes)} MB`;
    status.textContent = result.ready
      ? "App, Spielregeln und alle Crews sind auf diesem Gerät gespeichert. Auch neue KI-Partien starten ohne Internet."
      : "Einmal online herunterladen, danach ohne Internet mit der KI spielen.";
    button.disabled = result.ready;
  }
  async function check() {
    if (busy) return;
    try { show(await request("OFFLINE_STATUS")); }
    catch (error) { status.textContent = error.message; button.textContent = "Offline-Paket erneut prüfen"; button.disabled = false; }
  }
  button.addEventListener("click", async () => {
    if (busy) return;
    busy = true; button.disabled = true;
    button.textContent = "Offline-Paket wird gespeichert …";
    try {
      // Best effort; WebKit considers Home Screen installation when granting persistence.
      if (navigator.storage?.persist) await navigator.storage.persist().catch(() => false);
      show(await request("OFFLINE_DOWNLOAD"));
    } catch (error) {
      progress.hidden = true; status.textContent = `Nicht vollständig gespeichert: ${error.message}`;
      button.textContent = "Offline-Download fortsetzen"; button.disabled = false;
    } finally { busy = false; }
  });
  window.addEventListener("online", check);
  window.addEventListener("pageshow", check);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) check(); });
  check();
})();
