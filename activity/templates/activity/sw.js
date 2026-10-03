/* Service worker. Rendered by Django so asset URLs match the deployed
 * static files; the cache name changes whenever an asset changes. */
const CACHE = "tally-{{ version }}";
const FONTS = "tally-fonts";
const SHELL = "/activity/";
const ASSETS = [{% for a in assets %}"{{ a|escapejs }}"{% if not forloop.last %}, {% endif %}{% endfor %}];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    // The shell needs a signed-in session; cache it only if it loads.
    try {
      const res = await fetch(SHELL, { credentials: "same-origin" });
      if (res.ok && !res.redirected) await cache.put(SHELL, res);
    } catch (e) { /* offline during install: cached on first visit */ }
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key !== CACHE && key !== FONTS) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Fonts: cache first, fill on first use.
  if (url.hostname === "fonts.googleapis.com" || url.hostname === "fonts.gstatic.com") {
    event.respondWith(caches.open(FONTS).then(async (cache) => {
      const hit = await cache.match(req);
      if (hit) return hit;
      const res = await fetch(req);
      if (res.ok || res.type === "opaque") cache.put(req, res.clone());
      return res;
    }));
    return;
  }
  if (url.origin !== location.origin) return;

  // The app shell: network first so a deploy shows up, cached copy offline.
  if (req.mode === "navigate" && url.pathname === SHELL) {
    event.respondWith((async () => {
      const cache = await caches.open(CACHE);
      try {
        const res = await fetch(req);
        if (res.ok && !res.redirected) cache.put(SHELL, res.clone());
        return res;
      } catch (e) {
        return (await cache.match(SHELL)) || Response.error();
      }
    })());
    return;
  }

  // Static assets: cache first.
  if (ASSETS.includes(url.pathname)) {
    event.respondWith(caches.match(req).then((hit) => hit || fetch(req)));
  }
  // Everything else (API, admin) goes to the network as normal.
});
