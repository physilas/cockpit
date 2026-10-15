/*
 * Service Worker für Cockpit PWA
 *
 * App-Dateien: Cache zuerst; Navigation: aktuelle HTML-Version bevorzugen.
 * - Beim ersten Besuch: alle statischen Dateien cachen (inkl. der
 *   Python-Engine-Dateien, die Pyodide später holt).
 * - Bei jedem weiteren Besuch: App-Shell aus dem Cache laden.
 * - Pyodide/PeerJS kommen bewusst weiter vom CDN; ohne einen zuvor vom
 *   Browser gecachten CDN-Download ist ein Spielstart daher nicht offline.
 *
 * build.py regeneriert build-info.js bei jeder Änderung. Als importierte
 * Abhängigkeit löst sie auch ein Service-Worker-Update aus.
 */

importScripts("./js/build-info.js");
const CACHE_NAME = `cockpit-${COCKPIT_BUILD_VERSION}`;

const STATIC_ASSETS = [
  "./index.html",
  "./css/style.css",
  "./css/landings.css",
  "./js/landing-catalog.js",
  "./js/landings.js",
  "./js/engine-src.js",
  "./js/game-schema.js",
  "./js/traffic.js",
  "./js/build-info.js",
  "./js/app.js",
  "./multiplayer.html",
  "./bildnachweise.html",
  "./js/multiplayer.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-180.png",
  ...["YUL", "LHR", "HND", "OSL", "ATL", "PRG", "GIG", "TGU", "KEF", "KUL", "PBH", "MUC", "FRA"]
    .map(code => `./assets/landings/${code}-city.webp`),
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(
      STATIC_ASSETS.map(asset => new Request(asset, { cache: "reload" }))
    ))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k.startsWith("cockpit-") && k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  // CDN-Abhängigkeiten gehören nicht zum App-Shell-Cache.
  if (new URL(event.request.url).origin !== self.location.origin) return;
  const cachedResponse = () => caches.open(CACHE_NAME).then(cache =>
    cache.match(event.request, { ignoreSearch: true })
  );
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).then(response => {
        if (!response.ok) throw new Error("Navigation nicht verfügbar");
        return response;
      }).catch(async () => {
        const cached = await cachedResponse();
        if (cached) return cached;
        // Verzeichnis-URL /frontend/web/ entspricht index.html.
        if (new URL(event.request.url).pathname === new URL("./", self.location.href).pathname) {
          const cache = await caches.open(CACHE_NAME);
          return cache.match("./index.html");
        }
        return Response.error();
      })
    );
    return;
  }
  event.respondWith(
    cachedResponse().then(cached => cached || fetch(event.request))
  );
});
