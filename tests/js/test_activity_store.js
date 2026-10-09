// Tests for static/js/activity_store.js: per-user values, queued sessions, the old database.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/idb.js';
import '../../static/js/outbox_core.js';
import '../../static/js/outbox.js';

const { AppDB, Outbox } = self;

async function load() {
  document.head.innerHTML = '<meta name="app-principal" content="7"><meta name="csrf-token" content="t">';
  document.body.innerHTML = '<div id="app" data-workouts-url="/app/api/workouts/" data-sessions-url="/app/api/sessions/"></div>';
  vi.resetModules();
  await import('../../static/js/activity_store.js');
  return self.Store;
}

beforeEach(async () => {
  await AppDB.setMeta('principal', '7');
  await AppDB.setMeta('csrf', 't');
  vi.stubGlobal('navigator', { onLine: false });
  // Every send fails, as if offline, so queued rows stay put.
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
});

describe('values', () => {
  it('are kept under the signed-in user', async () => {
    const Store = await load();
    await Store.set('current', { step: 3 });
    expect(await Store.get('current')).toEqual({ step: 3 });
    expect(await AppDB.getMeta('activity:7:current')).toEqual({ step: 3 });
    await Store.del('current');
    expect(await Store.get('current')).toBeUndefined();
  });
});

describe('sessions', () => {
  it('queue one upload each, and pending() shows the newest state per session', async () => {
    const Store = await load();
    expect(await Store.ready()).toBe(true);
    await Store.saveSession({ uuid: 'a', workoutName: 'Legs' });
    await Store.saveSession({ uuid: 'a', workoutName: 'Legs', effort: 7 });
    await Store.discardSession('b');
    const { pending } = await Outbox.list();
    expect(pending).toHaveLength(3);
    expect(JSON.parse(pending[0].body).sessions[0].uuid).toBe('a');
    expect(pending[0].url).toBe('/app/api/sessions/');
    expect(await Store.pending()).toEqual([
      { uuid: 'a', discarded: false, failed: false },
      { uuid: 'b', discarded: true, failed: false },
    ]);
  });
});

describe('loadWorkouts', () => {
  it('keeps a copy, and uses it when offline or signed out', async () => {
    const Store = await load();
    fetch.mockResolvedValueOnce({ status: 200, ok: true, type: 'basic', json: () => Promise.resolve({ workouts: [1] }) });
    expect(await Store.loadWorkouts()).toEqual({ workouts: [1] });
    expect(Store.status()).toBe('ok');

    expect((await Store.loadWorkouts()).workouts).toEqual([1]);
    expect(Store.status()).toBe('offline');

    fetch.mockResolvedValueOnce({ status: 401, ok: false, type: 'basic' });
    expect((await Store.loadWorkouts()).workouts).toEqual([1]);
    expect(Store.status()).toBe('signed-out');
  });
});

describe('migrateLegacy', () => {
  it('moves waiting sessions from the old database into the outbox, then deletes it', async () => {
    await new Promise((resolve) => {
      const open = indexedDB.open('workouts', 1);
      open.onupgradeneeded = () => {
        open.result.createObjectStore('outbox', { keyPath: 'uuid' });
        open.result.createObjectStore('kv');
      };
      open.onsuccess = () => {
        const tx = open.result.transaction(['outbox', 'kv'], 'readwrite');
        tx.objectStore('outbox').put({ uuid: 'old', updatedAt: 1 });
        tx.objectStore('kv').put({ step: 2 }, 'current');
        tx.oncomplete = () => { open.result.close(); resolve(); };
      };
    });
    const Store = await load();
    await Store.migrateLegacy();
    expect((await Store.pending()).map((p) => p.uuid)).toEqual(['old']);
    expect(await Store.get('current')).toEqual({ step: 2 });
    const names = (await indexedDB.databases()).map((d) => d.name);
    expect(names).not.toContain('workouts');
  });

  it('does nothing, and creates nothing, when there is no old database', async () => {
    const Store = await load();
    await Store.migrateLegacy();
    expect((await indexedDB.databases()).map((d) => d.name)).not.toContain('workouts');
  });
});
