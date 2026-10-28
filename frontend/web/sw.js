/* App shell plus an explicit, integrity-checked offline AI pack. */
importScripts("./js/build-info.js", "./js/offline-assets.js");
const PACK = COCKPIT_OFFLINE_ASSETS;
const CACHE_NAME = `cockpit-shell-${COCKPIT_BUILD_VERSION}-${PACK.version}`;
const ASSET_CACHE = PACK.cache;
const absolute = path => new URL(path, self.location.href).href;
const assets = new Map(PACK.assets.map(asset => [absolute(asset.url), asset]));
const shell = [...PACK.shell.map(asset => asset.url), "js/offline-assets.js"];

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);
    await cache.addAll(shell.map(url => new Request(absolute(url), {cache: "reload"})));
    await self.skipWaiting();
  })());
});
self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    // Immutable weights/runtime survive app updates. Keep the current shell only.
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key.startsWith("cockpit-") && key !== CACHE_NAME && key !== ASSET_CACHE).map(key => caches.delete(key)));
    await self.clients.claim();
  })());
});

async function saveAsset(cache, asset) {
  const url = absolute(asset.url);
  const existing = await cache.match(url);
  if (existing) return;
  const response = await fetch(new Request(url, {cache: "reload"}));
  if (!response.ok) throw new Error(`Datei konnte nicht geladen werden (${response.status}).`);
  const bytes = await response.clone().arrayBuffer();
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))].map(v => v.toString(16).padStart(2, "0")).join("");
  if (bytes.byteLength !== asset.bytes || hash !== asset.sha256) throw new Error("Download passt nicht zur App-Version. Bitte online neu laden.");
  await cache.put(url, response);
}
async function packStatus() {
  const [app, data] = await Promise.all([caches.open(CACHE_NAME), caches.open(ASSET_CACHE)]);
  const found = await Promise.all([
    ...shell.map(url => app.match(absolute(url))),
    ...PACK.assets.map(asset => data.match(absolute(asset.url))),
  ]);
  return {ready: found.every(Boolean), version: PACK.version};
}
let downloading = null;
const downloadPorts = new Set();
self.addEventListener("message", event => {
  if (!["OFFLINE_STATUS", "OFFLINE_DOWNLOAD"].includes(event.data?.type)) return;
  const port = event.ports[0];
  if (!port) return;
  event.waitUntil((async () => {
    try {
      if (event.data.version !== PACK.version) throw new Error("Eine neue App-Version ist bereit. Bitte die App neu laden.");
      if (event.data.type === "OFFLINE_DOWNLOAD") {
        downloadPorts.add(port);
        // Serial downloads limit memory use on phones; cached files allow retries.
        if (!downloading) downloading = (async () => {
          const cache = await caches.open(ASSET_CACHE);
          let saved = PACK.shell.reduce((sum, asset) => sum + asset.bytes, 0);
          for (const asset of PACK.assets) {
            await saveAsset(cache, asset);
            saved += asset.bytes;
            for (const subscriber of downloadPorts) subscriber.postMessage({progress: saved, total: PACK.bytes});
          }
        })().finally(() => { downloading = null; });
        await downloading;
      }
      port.postMessage(await packStatus());
    } catch (error) {
      port.postMessage({error: error.name === "QuotaExceededError" ? "Zu wenig freier Speicher auf dem Gerät." : error.message});
    } finally {
      downloadPorts.delete(port);
    }
  })());
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  // Do not cache mutable cloud APIs, feedback or URLs outside this app.
  const asset = assets.get(url.origin + url.pathname);
  if (asset) {
    event.respondWith((async () => {
      const cache = await caches.open(ASSET_CACHE);
      const cached = await cache.match(absolute(asset.url));
      if (cached) return cached;
      // Online play also prepares its selected model/runtime for later offline use.
      try {
        await saveAsset(cache, asset);
        return await cache.match(absolute(asset.url));
      } catch {
        // A full/disabled cache must still allow an ordinary online game.
        return fetch(event.request);
      }
    })());
    return;
  }
  const shellUrl = url.origin + url.pathname;
  const directory = absolute("./");
  const target = shellUrl === directory ? absolute("index.html") : shellUrl;
  if (!shell.some(path => absolute(path) === target)) return;
  // Serve one installed, internally consistent app version, including navigation.
  event.respondWith((async () => {
    const cache = await caches.open(CACHE_NAME);
    return await cache.match(target) || fetch(event.request);
  })());
});
