/*
 * static/js/outbox.js — queue a write on the device, send it when possible.
 *
 *   Outbox.enqueue({url, body, meta})   store the write, then try to send it
 *   Outbox.drain()                      send every eligible write, oldest first
 *   Outbox.list()                       {pending, failed} for the signed-in user
 *   Outbox.retry(id) / discard(id)      the user's answer to a failed write
 *
 * Runs in pages and in the service worker (Background Sync), so it uses
 * only what both have: IndexedDB (idb.js), fetch, and Web Locks so the two
 * never send the same row at once. The rules live in outbox_core.js.
 *
 * Every send carries the row's Idempotency-Key, so a write that reached
 * the server but whose answer was lost is not applied twice
 * (apps/core/idempotency.py). The CSRF token and user are read at send
 * time from the `meta` store, which every page load refreshes (pwa.js):
 * a row is only ever sent as the user who wrote it.
 *
 * Changes are announced as `outbox:changed` on document (pages) or as a
 * postMessage of the same name to every page (worker), with detail
 * {pending, failed, sent}.
 */
(function () {
  'use strict';

  const core = self.OutboxCore;
  const db = self.AppDB;
  const STORE = 'outbox';
  const inPage = typeof document !== 'undefined';
  let queue = Promise.resolve(); // fallback lock where Web Locks are missing

  async function context() {
    return {
      principal: (await db.getMeta('principal')) ?? '',
      csrf: (await db.getMeta('csrf')) ?? '',
    };
  }

  async function list() {
    const { principal } = await context();
    return core.summarise(await db.getAll(STORE), principal);
  }

  async function announce(sent) {
    const { pending, failed } = await list();
    const detail = { pending: pending.length, failed: failed.length, sent: sent || 0 };
    if (inPage) {
      document.dispatchEvent(new CustomEvent('outbox:changed', { detail }));
    } else if (self.clients) {
      const pages = await self.clients.matchAll({ type: 'window' });
      pages.forEach((page) => page.postMessage({ type: 'outbox:changed', detail }));
    }
    return detail;
  }

  async function registerSync() {
    try {
      const registration = inPage
        ? await navigator.serviceWorker?.getRegistration()
        : self.registration;
      await registration?.sync?.register(core.SYNC_TAG);
    } catch (e) {
      // No Background Sync (Safari, Firefox): pages drain on load and on `online`.
    }
  }

  async function enqueue({ url, body, method, contentType, meta }) {
    const { principal } = await context();
    const row = core.newRow({
      method,
      url,
      body,
      contentType,
      meta,
      principal,
      key: crypto.randomUUID(),
      now: Date.now(),
    });
    row.id = await db.add(STORE, row);
    await announce(0);
    await registerSync();
    drain(); // not awaited: the caller shows the pending write at once
    return row;
  }

  async function send(row, csrf, fetchImpl) {
    try {
      return await fetchImpl(row.url, {
        method: row.method,
        body: row.body,
        credentials: 'same-origin',
        redirect: 'manual',
        headers: {
          'Content-Type': row.content_type,
          'Idempotency-Key': row.idempotency_key,
          'X-CSRFToken': csrf,
        },
      });
    } catch (e) {
      return null;
    }
  }

  async function drainOnce(fetchImpl, now) {
    if (typeof navigator !== 'undefined' && navigator.onLine === false) {
      return announce(0);
    }
    const { principal, csrf } = await context();
    const rows = (await db.getAll(STORE))
      .filter((row) => core.isEligible(row, now(), principal))
      .sort((a, b) => a.id - b.id);
    let sent = 0;
    for (const row of rows) {
      const response = await send(row, csrf, fetchImpl);
      const outcome = core.classify(response);
      const next = core.nextRow(row, outcome, response ? response.status : 0, now());
      if (next.action === 'pause' || next.action === 'stop') break;
      if (next.action === 'delete') {
        await db.delete(STORE, row.id);
        sent += 1;
      } else {
        await db.put(STORE, next.row);
      }
    }
    return announce(sent);
  }

  /**
   * Send what can be sent. Safe to call often: drains run one at a time
   * across this page, other tabs and the worker (a Web Lock), so a row is
   * never sent twice at once, and a drain asked for while another runs
   * still happens, straight after it.
   */
  function drain(options) {
    const fetchImpl = (options && options.fetch) || ((...args) => self.fetch(...args));
    const now = (options && options.now) || Date.now;
    const run = () => drainOnce(fetchImpl, now);
    if (typeof navigator !== 'undefined' && navigator.locks) {
      return navigator.locks.request('outbox-drain', run);
    }
    queue = queue.then(run, run);
    return queue;
  }

  async function retry(id) {
    const row = await db.get(STORE, id);
    if (!row) return;
    await db.put(STORE, Object.assign({}, row, { status: 'queued', attempts: 0, next_attempt_at: Date.now() }));
    await announce(0);
    drain();
  }

  async function discard(id) {
    await db.delete(STORE, id);
    await announce(0);
  }

  self.Outbox = Object.freeze({ enqueue, drain, list, retry, discard });
})();
