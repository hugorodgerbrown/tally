// Tests for static/js/outbox.js against fake-indexeddb: enqueue, drain, retry.
import { beforeEach, describe, expect, it, vi } from 'vitest';

import '../../static/js/idb.js';
import '../../static/js/outbox_core.js';
import '../../static/js/outbox.js';

const { AppDB, Outbox } = self;

const reply = (status, headers = {}) => ({ status, type: 'basic', headers: { get: (n) => headers[n] ?? null } });

beforeEach(async () => {
  await AppDB.setMeta('principal', '7');
  await AppDB.setMeta('csrf', 'token-1');
  vi.stubGlobal('navigator', { onLine: true });
});

async function enqueueOffline(body = '{"text":"hi"}') {
  // Enqueue triggers a drain; make that first one fail as if offline.
  const offline = vi.fn().mockRejectedValue(new TypeError('offline'));
  vi.stubGlobal('fetch', offline);
  const row = await Outbox.enqueue({ url: '/app/new/', body, meta: { text: 'hi' } });
  await Outbox.drain({ fetch: offline });
  return row;
}

describe('enqueue', () => {
  it('stores the write with a key and the current user, and announces it', async () => {
    const changed = vi.fn();
    document.addEventListener('outbox:changed', (e) => changed(e.detail));
    const row = await enqueueOffline();
    expect(row.idempotency_key).toMatch(/^[0-9a-f-]{36}$/);
    expect(row.principal).toBe('7');
    expect((await Outbox.list()).pending).toHaveLength(1);
    expect(changed).toHaveBeenCalledWith(expect.objectContaining({ pending: 1 }));
  });
});

describe('drain', () => {
  it('sends with the key and CSRF token, then deletes the row', async () => {
    const row = await enqueueOffline();
    const send = vi.fn().mockResolvedValue(reply(201));
    const result = await Outbox.drain({ fetch: send });
    const [url, init] = send.mock.calls[0];
    expect(url).toBe('/app/new/');
    expect(init.headers['Idempotency-Key']).toBe(row.idempotency_key);
    expect(init.headers['X-CSRFToken']).toBe('token-1');
    expect(init.redirect).toBe('manual');
    expect(result).toMatchObject({ sent: 1, pending: 0 });
  });

  it('keeps the same key across retries', async () => {
    await enqueueOffline();
    let now = Date.now();
    const send = vi.fn().mockResolvedValueOnce(reply(503)).mockResolvedValueOnce(reply(201));
    await Outbox.drain({ fetch: send, now: () => now });
    now += 60_000;
    await Outbox.drain({ fetch: send, now: () => now });
    const keys = send.mock.calls.map(([, init]) => init.headers['Idempotency-Key']);
    expect(keys[0]).toBe(keys[1]);
    expect((await Outbox.list()).pending).toHaveLength(0);
  });

  it('does not count offline attempts', async () => {
    await enqueueOffline();
    const [pending] = (await Outbox.list()).pending;
    expect(pending.attempts).toBe(0);
  });

  it('waits on 401 without losing the write', async () => {
    await enqueueOffline();
    await Outbox.drain({ fetch: vi.fn().mockResolvedValue(reply(401)) });
    const { pending, failed } = await Outbox.list();
    expect(pending).toHaveLength(1);
    expect(failed).toHaveLength(0);
  });

  it('marks a rejected write failed; retry and discard act on it', async () => {
    await enqueueOffline();
    await Outbox.drain({ fetch: vi.fn().mockResolvedValue(reply(400)) });
    const [failed] = (await Outbox.list()).failed;
    expect(failed.last_status).toBe(400);

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    await Outbox.retry(failed.id);
    expect((await Outbox.list()).pending).toHaveLength(1);
    await Outbox.discard(failed.id);
    expect(await Outbox.list()).toEqual({ pending: [], failed: [] });
  });

  it('never sends another user\'s writes', async () => {
    await enqueueOffline();
    await AppDB.setMeta('principal', '8');
    const send = vi.fn().mockResolvedValue(reply(201));
    await Outbox.drain({ fetch: send });
    expect(send).not.toHaveBeenCalled();
  });

  it('does nothing while the browser says it is offline', async () => {
    await enqueueOffline();
    vi.stubGlobal('navigator', { onLine: false });
    const send = vi.fn();
    await Outbox.drain({ fetch: send });
    expect(send).not.toHaveBeenCalled();
  });
});
