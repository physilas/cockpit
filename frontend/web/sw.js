/*
 * Service Worker für Cockpit PWA
 *
 * Strategie: "Cache first, then network"
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
  "./js/engine-src.js",
  "./js/game-schema.js",
  "./js/build-info.js",
  "./js/app.js",
  "./multiplayer.html",
  "./js/multiplayer.js",
  "./manifest.json",
  "./icons/icon-192.png",
  "./icons/icon-512.png",
  "./icons/icon-180.png",
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
