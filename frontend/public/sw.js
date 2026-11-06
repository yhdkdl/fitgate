/**
 * FitGate Service Worker
 *
 * Caching boundaries:
 * - Caches ONLY the app shell (HTML, CSS, JS, static icons/fonts).
 * - NEVER caches API responses (/api/*) or media/photos (/media/*).
 * - Offline navigation requests fall back to cached index.html.
 */

const CACHE_NAME = "fitgate-shell-v1";

const APP_SHELL_URLS = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icon-192.png",
  "/icon-512.png",
  "/icon-maskable-512.png",
  "/icon.svg",
];

// Install: precache static app shell
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) => cache.addAll(APP_SHELL_URLS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean up outdated caches
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames
            .filter((name) => name !== CACHE_NAME)
            .map((name) => caches.delete(name))
        );
      })
      .then(() => self.clients.claim())
  );
});

// Fetch: enforce strict caching boundaries
self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // 1. STRICT BOUNDARY: Never cache API endpoints or uploaded media/photos
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
    // NetworkOnly strategy: bypass Cache API completely
    return;
  }

  // 2. Only cache GET requests
  if (request.method !== "GET") {
    return;
  }

  // 3. Navigation requests: Network-first with offline app shell fallback
  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((networkResponse) => {
          // If successful, update cached index.html
          if (networkResponse && networkResponse.status === 200) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put("/index.html", responseToCache);
            });
          }
          return networkResponse;
        })
        .catch(async () => {
          // Fall back to cached app shell when offline
          const cache = await caches.open(CACHE_NAME);
          const cached =
            (await cache.match("/index.html")) || (await cache.match("/"));
          if (cached) return cached;
          return new Response(
            "<!doctype html><html><body><div id='root'>FitGate App Shell (Offline)</div></body></html>",
            {
              headers: { "Content-Type": "text/html" },
            }
          );
        })
    );
    return;
  }

  // 4. Static assets (JS, CSS, static images, fonts): Stale-While-Revalidate
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      const fetchPromise = fetch(request)
        .then((networkResponse) => {
          if (
            networkResponse &&
            networkResponse.status === 200 &&
            (networkResponse.type === "basic" ||
              networkResponse.type === "cors")
          ) {
            const responseToCache = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, responseToCache);
            });
          }
          return networkResponse;
        })
        .catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});

// Skip waiting on message
self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") {
    self.skipWaiting();
  }
});
