/*
 * static/js/sw_worker.js — the service worker.
 *
 * /app/sw.js (apps/pwa/views.py) sets self.SW_CONFIG and importScripts() this
 * after idb.js, outbox_core.js, outbox.js and sw_core.js.
 *
 *   install   precache the shell: static files and the offline page
 *   activate  delete this app's caches from older versions; take control
 *   fetch     static: cache-first. pages: network-first, falling back to the
 *             cached copy after PAGE_TIMEOUT_MS, then to the offline page
 *   sync      Background Sync: send the outbox with no page open
 *   message   'cache-page' (cache the page that just loaded), 'drain'
 *
 * Updates apply at once (skipWaiting + claim): static files have hashed
 * names, so an old page never asks for a file the new caches lack.
 */
/* global SW_CONFIG, SwCore, Outbox, OutboxCore, AppDB */
'use strict';

const config = self.SW_CONFIG;
const names = SwCore.cacheNames(config);

// A dead connection often hangs rather than failing. After this long a
// cached copy is better than a spinner.
const PAGE_TIMEOUT_MS = 4000;

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(names.static)
      .then((cache) => cache.addAll(config.precache.concat([config.offlineUrl])))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => SwCore.isStaleCache(k, config)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

async function fromStatic(request) {
  const cache = await caches.open(names.static);
  if (!config.debug) {
    const hit = await cache.match(request);
    if (hit) return hit;
  }
  try {
    const response = await fetch(request);
    if (SwCore.isStorable(response)) await cache.put(request, response.clone());
    return response;
  } catch (error) {
    const hit = await cache.match(request);
    if (hit) return hit;
    throw error;
  }
}

async function fromPage(event) {
  const request = event.request;
  const cache = await caches.open(names.pages);
  const network = fetch(request).then((response) => {
    if (SwCore.isStorable(response)) {
      event.waitUntil(cache.put(request, response.clone()));
    }
    return response;
  });
  network.catch(() => undefined); // handled below; silences the unhandled-rejection report

  const timedOut = new Promise((resolve) => setTimeout(() => resolve('timeout'), PAGE_TIMEOUT_MS));
  try {
    const first = await Promise.race([network, timedOut]);
    if (first !== 'timeout') return first;
    // Slow network: a cached copy if there is one, otherwise keep waiting.
    const cached = await cache.match(request, { ignoreVary: true });
    return cached || (await network);
  } catch (error) {
    const cached = await cache.match(request, { ignoreVary: true });
    if (cached) return cached;
    if (request.mode === 'navigate') {
      const offline = await caches.match(config.offlineUrl);
      if (offline) return offline;
    }
    return Response.error();
  }
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const strategy = SwCore.route(event.request, url, self.location.origin, config);
  if (strategy === 'static') event.respondWith(fromStatic(event.request));
  else if (strategy === 'page') event.respondWith(fromPage(event));
});

self.addEventListener('sync', (event) => {
  if (event.tag !== OutboxCore.SYNC_TAG) return;
  // Rejecting asks the browser to try the sync again later.
  event.waitUntil(
    Outbox.drain().then((result) => {
      if (result && result.pending > 0 && result.sent === 0) throw new Error('outbox: still pending');
    })
  );
});

// Fetch a page into the pages cache for whoever is signed in now. A
// sign-out can start while the fetch is in flight: pwa.js clears the
// recorded principal and then the cached pages, so a copy stored after
// that is taken out again rather than left for the next person offline.
async function cachePage(url) {
  const before = await AppDB.getMeta('principal');
  if (before === '') return; // signed out, or signing out
  const response = await fetch(url, { credentials: 'same-origin' });
  if (!SwCore.isStorable(response)) return;
  const cache = await caches.open(names.pages);
  await cache.put(url, response);
  const after = await AppDB.getMeta('principal');
  if (after === '' || (before !== undefined && after !== before)) {
    await (await caches.open(names.pages)).delete(url);
  }
}

self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type === 'cache-page' && typeof data.url === 'string') {
    const url = new URL(data.url, self.location.origin);
    if (SwCore.route({ method: 'GET' }, url, self.location.origin, config) !== 'page') return;
    event.waitUntil(cachePage(url).catch(() => undefined));
  } else if (data.type === 'drain') {
    event.waitUntil(Outbox.drain());
  }
});
