/*
 * static/js/activity_store.js — the phone app's storage and sync, on the template's outbox.
 *
 *   Store.loadWorkouts()        fetch the workouts, keep a copy on the phone, or use the copy
 *   Store.saveSession(s)        queue a finished session (or a new effort score) for upload
 *   Store.discardSession(uuid)  queue a tombstone, so a synced copy is deleted too
 *   Store.pending()             the sessions still waiting, as [{uuid, discarded, failed}]
 *   Store.get / set / del       small per-user values: the workouts, the running checkpoint
 *   Store.flush()               send what is queued now
 *   Store.status()              "ok" | "offline" | "signed-out", with onStatus(fn)
 *
 * Uploads go through the outbox (static/js/outbox.js), which retries with
 * backoff, sends an Idempotency-Key, and waits on a 401 until the user signs
 * in again. Each upload is one session; the server upserts on its uuid, so
 * a later upload of the same session (an effort score added after it
 * synced) updates it, and a tombstone deletes it.
 *
 * Values are kept in the template's IndexedDB `meta` store under the
 * signed-in user's key, so another account on the phone never sees them.
 *
 * Phones that used Tally before it moved to /app/ may have sessions waiting
 * in the old "workouts" database; they are moved into the outbox once.
 */
(function () {
  'use strict';

  const db = self.AppDB;
  const outbox = self.Outbox;
  const root = document.getElementById('app');
  const urls = {
    workouts: root.dataset.workoutsUrl,
    sessions: root.dataset.sessionsUrl,
  };
  const LEGACY_DB = 'workouts';

  function metaContent(name) {
    const el = document.querySelector('meta[name="' + name + '"]');
    return el ? el.content : '';
  }
  const principal = metaContent('app-principal');
  const key = (name) => 'activity:' + principal + ':' + name;

  const get = (name) => db.getMeta(key(name));
  const set = (name, value) => db.setMeta(key(name), value);
  const del = (name) => db.setMeta(key(name), undefined);
  const csrfToken = () => metaContent('csrf-token');

  /* status: "ok" | "offline" | "signed-out" */
  const listeners = new Set();
  let status = navigator.onLine ? 'ok' : 'offline';
  function setStatus(next) {
    status = next;
    listeners.forEach((fn) => fn(status));
  }

  async function loadWorkouts() {
    try {
      const res = await fetch(urls.workouts, {
        credentials: 'same-origin',
        redirect: 'manual',
        headers: { Accept: 'application/json' },
      });
      if (res.status === 401 || res.type === 'opaqueredirect') {
        setStatus('signed-out');
        return (await get('library')) || null;
      }
      if (!res.ok) throw new Error('http ' + res.status);
      const data = await res.json();
      await set('library', Object.assign({}, data, { fetchedAt: new Date().toISOString() }));
      setStatus('ok');
      return data;
    } catch (e) {
      setStatus('offline');
      return (await get('library')) || null;
    }
  }

  /*
   * The outbox stamps each row with the user pwa.js records at page load,
   * and only sends rows stamped with the current one. Wait for that record
   * before queueing anything at start-up (a checkpoint, the old database).
   */
  async function ready() {
    for (let i = 0; i < 40; i += 1) {
      if ((await db.getMeta('principal')) === principal) return true;
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
    return false;
  }

  function enqueue(item) {
    return outbox.enqueue({
      url: urls.sessions,
      body: JSON.stringify({ sessions: [item] }),
      meta: { kind: 'session', uuid: item.uuid, discarded: !!item.discarded },
    });
  }

  async function saveSession(session) {
    await enqueue(Object.assign({}, session, { updatedAt: Date.now() }));
  }

  async function discardSession(uuid) {
    await enqueue({ uuid: uuid, discarded: true, updatedAt: Date.now() });
  }

  /* One entry per session uuid: the newest queued row says what it is now. */
  async function pending() {
    const { pending: waiting, failed } = await outbox.list();
    const latest = new Map();
    const rows = waiting.map((r) => [r, false]).concat(failed.map((r) => [r, true]));
    rows
      .filter(([row]) => row.meta && row.meta.kind === 'session')
      .sort(([a], [b]) => a.id - b.id)
      .forEach(([row, isFailed]) => {
        latest.set(row.meta.uuid, { uuid: row.meta.uuid, discarded: row.meta.discarded, failed: isFailed });
      });
    return [...latest.values()];
  }

  function flush() {
    return outbox.drain();
  }

  /* Move sessions waiting in the pre-/app/ database into the outbox, then delete it. */
  function openLegacy() {
    return new Promise((resolve) => {
      let existed = true;
      const request = indexedDB.open(LEGACY_DB);
      request.onupgradeneeded = () => {
        // It didn't exist: don't create it.
        existed = false;
        request.transaction.abort();
      };
      request.onsuccess = () => resolve(existed ? request.result : null);
      request.onerror = () => resolve(null);
    });
  }

  function readAll(legacy, storeName, getter) {
    return new Promise((resolve) => {
      if (!legacy.objectStoreNames.contains(storeName)) return resolve(undefined);
      const request = getter(legacy.transaction(storeName).objectStore(storeName));
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => resolve(undefined);
    });
  }

  async function migrateLegacy() {
    if (!principal) return;
    const legacy = await openLegacy();
    if (!legacy) return;
    const queued = (await readAll(legacy, 'outbox', (s) => s.getAll())) || [];
    const current = await readAll(legacy, 'kv', (s) => s.get('current'));
    legacy.close();
    for (const item of queued.sort((a, b) => (a.updatedAt || 0) - (b.updatedAt || 0))) {
      await enqueue(item);
    }
    if (current && !(await get('current'))) await set('current', current);
    indexedDB.deleteDatabase(LEGACY_DB);
  }

  document.addEventListener('outbox:changed', () => listeners.forEach((fn) => fn(status)));
  window.addEventListener('online', () => setStatus('ok'));
  window.addEventListener('offline', () => setStatus('offline'));
  // The network can be up while the server is unreachable; keep trying.
  setInterval(() => flush(), 60 * 1000);

  self.Store = Object.freeze({
    get,
    set,
    del,
    pending,
    loadWorkouts,
    saveSession,
    discardSession,
    flush,
    csrfToken,
    migrateLegacy,
    ready,
    onStatus: (fn) => listeners.add(fn),
    status: () => status,
  });
})();
