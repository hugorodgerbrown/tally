/* Offline storage (IndexedDB) and sync with the server.
 *
 *   kv      workouts payload from the server, the in-progress checkpoint
 *   outbox  finished sessions waiting to upload, keyed by uuid
 *
 * Sessions stay in the outbox until the server confirms them. Uploads are
 * idempotent (the server upserts on uuid), so a retry after a dropped
 * response is harmless, and re-queueing a session to add an effort score
 * updates the stored copy.
 */
(function () {
  "use strict";

  let dbp = null;
  function db() {
    dbp = dbp || new Promise((resolve, reject) => {
      const req = indexedDB.open("workouts", 1);
      req.onupgradeneeded = () => {
        req.result.createObjectStore("kv");
        req.result.createObjectStore("outbox", { keyPath: "uuid" });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    return dbp;
  }

  async function tx(store, mode, fn) {
    const d = await db();
    return new Promise((resolve, reject) => {
      const t = d.transaction(store, mode);
      const result = fn(t.objectStore(store));
      t.oncomplete = () => resolve(result && "result" in result ? result.result : undefined);
      t.onerror = () => reject(t.error);
      t.onabort = () => reject(t.error);
    });
  }

  const get = (key) => tx("kv", "readonly", (s) => s.get(key));
  const set = (key, value) => tx("kv", "readwrite", (s) => s.put(value, key));
  const del = (key) => tx("kv", "readwrite", (s) => s.delete(key));
  const queue = (session) => tx("outbox", "readwrite", (s) => s.put(session));
  const pending = () => tx("outbox", "readonly", (s) => s.getAll());
  const unqueue = (uuids) => tx("outbox", "readwrite", (s) => uuids.forEach((u) => s.delete(u)));

  function csrfToken() {
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  /* status: "ok" | "offline" | "signed-out" */
  const listeners = new Set();
  let status = navigator.onLine ? "ok" : "offline";
  function setStatus(s) {
    status = s;
    listeners.forEach((fn) => fn(s));
  }

  async function api(path, options = {}) {
    const res = await fetch(path, { credentials: "same-origin", ...options });
    if (res.status === 401 || res.status === 403 || res.redirected) {
      setStatus("signed-out");
      throw new Error("signed-out");
    }
    if (!res.ok) throw new Error("http " + res.status);
    setStatus("ok");
    return res.json();
  }

  /* Fetch the latest workouts, falling back to the stored copy. */
  async function loadWorkouts() {
    try {
      const data = await api("/api/workouts/");
      await set("library", { ...data, fetchedAt: new Date().toISOString() });
      return data;
    } catch (e) {
      if (e.message !== "signed-out") setStatus("offline");
      return (await get("library")) || null;
    }
  }

  let flushing = null;
  function flush() {
    flushing = flushing || (async () => {
      try {
        const items = await pending();
        if (!items.length) return;
        const res = await api("/api/sessions/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
          body: JSON.stringify({ sessions: items }),
        });
        const done = [...res.saved, ...res.rejected.map((r) => r.uuid).filter(Boolean)];
        // Only clear the versions we sent; a newer edit made meanwhile stays queued.
        const sent = new Map(items.map((i) => [i.uuid, i.updatedAt]));
        const now = new Map((await pending()).map((i) => [i.uuid, i.updatedAt]));
        await unqueue(done.filter((u) => now.get(u) === sent.get(u)));
      } catch (e) {
        if (e.message !== "signed-out") setStatus("offline");
      } finally {
        flushing = null;
        listeners.forEach((fn) => fn(status));
      }
    })();
    return flushing;
  }

  async function saveSession(session) {
    await queue({ ...session, updatedAt: Date.now() });
    flush();
  }

  window.addEventListener("online", () => flush());
  // The network can be up while the server is unreachable; keep retrying.
  setInterval(() => flush(), 60 * 1000);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") flush();
  });

  window.Store = {
    get, set, del, pending, loadWorkouts, saveSession, flush, csrfToken,
    onStatus: (fn) => listeners.add(fn),
    status: () => status,
  };
})();
