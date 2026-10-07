// Tests for static/js/sw_worker.js: re-caching a page never outlives a sign-out.
import { beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/idb.js';
import '../../static/js/outbox_core.js';
import '../../static/js/outbox.js';
import '../../static/js/sw_core.js';

const { AppDB } = self;
const stored = new Map();
let onMessage;

beforeAll(async () => {
  self.SW_CONFIG = {
    prefix: 'app',
    version: 'v1',
    staticUrl: '/static/',
    scope: '/app/',
    workerUrl: '/app/sw.js',
    neverCache: [],
    precache: [],
    offlineUrl: '/app/offline/',
  };
  const add = vi.spyOn(self, 'addEventListener');
  await import('../../static/js/sw_worker.js');
  onMessage = add.mock.calls.find(([type]) => type === 'message')[1];
  add.mockRestore();
});

beforeEach(async () => {
  stored.clear();
  vi.stubGlobal('caches', {
    open: async () => ({
      put: async (url, response) => stored.set(String(url), response),
      delete: async (url) => stored.delete(String(url)),
    }),
  });
  await AppDB.setMeta('principal', '7');
});

/** Post 'cache-page' for /app/ and wait for the worker to finish with it. */
async function cachePage(fetchImpl) {
  vi.stubGlobal('fetch', vi.fn(fetchImpl));
  let work;
  onMessage({ data: { type: 'cache-page', url: '/app/' }, waitUntil: (promise) => (work = promise) });
  await work;
  return [...stored.keys()].some((url) => url.endsWith('/app/'));
}

const page = () => ({ ok: true, redirected: false, type: 'basic', headers: new Headers() });

describe('cache-page', () => {
  it('stores the page for the signed-in user', async () => {
    expect(await cachePage(async () => page())).toBe(true);
  });

  it('takes the copy out again when a sign-out started during the fetch', async () => {
    const cached = await cachePage(async () => {
      await AppDB.setMeta('principal', '');
      return page();
    });
    expect(cached).toBe(false);
  });

  it('takes the copy out when another user signed in during the fetch', async () => {
    const cached = await cachePage(async () => {
      await AppDB.setMeta('principal', '8');
      return page();
    });
    expect(cached).toBe(false);
  });

  it('fetches nothing once signed out', async () => {
    await AppDB.setMeta('principal', '');
    expect(await cachePage(async () => page())).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
  });
});
