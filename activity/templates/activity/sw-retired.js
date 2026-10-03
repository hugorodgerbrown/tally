/* Until October 2026 the service worker lived at /sw.js and controlled the
 * whole site. Activity now has its own at /activity/sw.js. This one takes the
 * old one's place, deletes its caches and unregisters, so the homepage and
 * Manage go straight to the network. */
self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith("workouts-")) await caches.delete(key);
    }
    await self.registration.unregister();
  })());
});
