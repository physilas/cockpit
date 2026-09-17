/*
 * Service Worker für Cockpit PWA
 *
 * Strategie: "Cache first, then network"
 * - Beim ersten Besuch: alle statischen Dateien cachen (inkl. der
 *   Python-Engine-Dateien, die Pyodide später holt).
 * - Bei jedem weiteren Besuch: aus dem Cache laden (funktioniert offline).
 * - Pyodide selbst wird von einem CDN geladen; das CDN hat seinen eigenen
 *   Cache-Header, also kein manuelles Cachen nötig.
 *
 * WICHTIG: CACHE_NAME bei jedem Deploy mit sichtbaren Änderungen erhöhen -
 * sonst bekommen Handys, die die Seite schonmal geöffnet haben, die neuen
 * Dateien nicht zu sehen (der Cache liefert weiter die alte Version aus).
 */

const CACHE_NAME = "cockpit-v10";

const STATIC_ASSETS = [
  "./index.html",
  "./css/style.css",
  "./js/engine-src.js",
  "./js/app.js",
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
