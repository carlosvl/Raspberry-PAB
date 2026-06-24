const CACHE_NAME = "raspberry-pab-shell-v19";
const APP_SHELL = [
  "/",
  "/admin",
  "/css/kiosk.css",
  "/js/kiosk.js",
  "/js/admin.js",
  "/manifest.webmanifest",
  "/assets/icons/pab-icon-180.png",
  "/assets/icons/pab-icon-192.png",
  "/assets/icons/pab-icon-512.png",
];

const NETWORK_FIRST_PATHS = new Set(["/", "/admin", "/js/kiosk.js", "/js/admin.js"]);

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))),
      ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return;

  if (NETWORK_FIRST_PATHS.has(url.pathname)) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request)),
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request)),
  );
});
