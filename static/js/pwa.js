/*
 * static/js/pwa.js — wire each page to the service worker and the outbox.
 *
 * On every page load:
 *   1. Record who is signed in, and the CSRF token, in IndexedDB `meta`
 *      for the outbox and the worker. If the user changed (sign out, or a
 *      different account), drop the cached pages: they show the last
 *      user's data.
 *   2. Register the service worker, and ask it to cache this page so it
 *      opens offline next time (and again after queued writes are sent,
 *      since they change it).
 *   3. Send queued writes now, when the connection comes back, when the
 *      app returns to the foreground, and when the worker says to.
 *   4. Keep the offline banner and the header's outbox count current.
 *   5. Before a sign-out form posts, drop the cached pages and the recorded
 *      user, so the next person on this device can't open them offline.
 */
(function () {
  'use strict';

  const db = self.AppDB;
  const outbox = self.Outbox;

  function metaContent(name) {
    const el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.content : '';
  }

  async function forgetPages() {
    if (!self.caches) return;
    const names = await caches.keys();
    await Promise.all(names.filter((n) => n.includes('-pages-')).map((n) => caches.delete(n)));
  }

  async function recordPrincipal() {
    const principal = metaContent('app-principal');
    const previous = await db.getMeta('principal');
    await db.setMeta('principal', principal);
    await db.setMeta('csrf', metaContent('csrf-token'));
    if (previous !== undefined && previous !== principal) await forgetPages();
  }

  async function registerWorker() {
    if (!('serviceWorker' in navigator)) return;
    const registration = await navigator.serviceWorker.register(metaContent('app-worker'), {
      scope: metaContent('app-scope'),
    });
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'outbox:changed') {
        document.dispatchEvent(new CustomEvent('outbox:changed', { detail: event.data.detail }));
      }
    });
    const worker = registration.active || registration.waiting || registration.installing;
    if (worker) {
      worker.postMessage({ type: 'cache-page', url: location.pathname + location.search });
    }
  }

  function renderOnline() {
    const banner = document.querySelector('[data-offline-banner]');
    if (banner) banner.hidden = navigator.onLine;
  }

  function renderOutbox(detail) {
    const el = document.querySelector('[data-outbox-status]');
    if (!el) return;
    const parts = [];
    if (detail.pending) parts.push(detail.pending + ' waiting to send');
    if (detail.failed) parts.push(detail.failed + ' not sent');
    el.textContent = parts.join(' · ');
  }

  document.addEventListener('outbox:changed', (event) => {
    renderOutbox(event.detail);
    if (event.detail.sent > 0) {
      // htmx listens for this to refresh whatever the sent writes changed.
      document.body.dispatchEvent(new CustomEvent('outbox:sent'));
      // The cached copy of this page predates those writes; refresh it so
      // the page opened offline next shows them.
      const worker = navigator.serviceWorker && navigator.serviceWorker.controller;
      if (worker) worker.postMessage({ type: 'cache-page', url: location.pathname + location.search });
    }
  });

  window.addEventListener('online', () => {
    renderOnline();
    outbox.drain();
  });
  window.addEventListener('offline', renderOnline);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') outbox.drain();
  });

  document.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || !form.hasAttribute('data-sign-out')) return;
    if (form.dataset.cleared) return;
    event.preventDefault();
    const submit = () => {
      form.dataset.cleared = '1';
      form.submit();
    };
    // Sign out even if the cleanup fails: the server clears the HTTP cache too.
    // Forget the principal first: the worker checks it after caching a page
    // (sw_worker.js cachePage), so a copy stored mid-sign-out is removed.
    db.setMeta('principal', '').then(forgetPages).then(submit, submit);
  });

  renderOnline();
  recordPrincipal()
    .then(() => outbox.drain())
    .catch((error) => console.error('outbox: could not start', error));
  registerWorker().catch((error) => console.error('service worker: registration failed', error));
})();
