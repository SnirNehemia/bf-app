// Service worker: lets the app open with no connection (e.g. at 3am in airplane mode)
// and makes updates arrive on the next open.
//
// RELEASE RULE: bump APP_VERSION here and in index.html together on every release.
// If you add or rename a file the app needs, add it to APP_FILES too.
const APP_VERSION = '4';
const CACHE_NAME = `feeding-app-v${APP_VERSION}`;
const APP_FILES = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable-512.png',
  './fonts/rubik-hebrew.woff2',
  './fonts/rubik-latin.woff2',
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_FILES)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', event => {
  // Remove caches of older versions, then take over open pages.
  event.waitUntil(
    caches.keys()
      .then(cacheNames => Promise.all(cacheNames.filter(name => name !== CACHE_NAME).map(name => caches.delete(name))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET' || new URL(request.url).origin !== self.location.origin) return;

  if (request.mode === 'navigate') {
    // The page itself: ask the server every time (a cheap "has it changed?" check) so a new release
    // shows up on the next open instead of after the host's cache expires; fall back to the saved copy offline.
    event.respondWith(
      fetch(request, { cache: 'no-cache' })
        .then(response => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put('./index.html', copy));
          return response;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }
  // Icons, fonts and manifest: saved copy first.
  event.respondWith(caches.match(request).then(cached => cached || fetch(request)));
});
