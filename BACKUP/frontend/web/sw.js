/*
 * Service Worker für Cockpit PWA
 *
 * Strategie: "Cache first, then network"
 * - Beim ersten Besuch: alle statischen Dateien cachen (inkl. der
 *   Python-Engine-Dateien, die Pyodide später holt).
 * - Bei jedem weiteren Besuch: aus dem Cache laden (funktioniert offline).
 * - Pyodide selbst wird von einem CDN geladen; das CDN hat seinen eigenen
 *   Cache-Header, also kein manuelles Cachen nötig.
 */

const CACHE_NAME = "cockpit-v2";

// Alle Dateien, die offline verfügbar sein sollen.
// Pyodide-WASM (~10 MB) holen wir NICHT selbst - das macht Pyodide intern.
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

// Installation: alle statischen Assets vorab cachen.
self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
  );
  self.skipWaiting();
});

// Activation: alte Cache-Versionen aufräumen.
self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Fetch: Cache first. Falls nicht im Cache (z.B. Pyodide-CDN-Ressourcen),
// normaler Netzwerkzugriff.
self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request))
  );
});
