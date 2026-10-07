// Unit tests for static/js/outbox_core.js: the outbox's rules, no I/O.
import { describe, expect, it } from 'vitest';

import '../../static/js/outbox_core.js';

const core = self.OutboxCore;
const response = (status, headers = {}, type = 'basic') => ({
  status,
  type,
  headers: { get: (name) => headers[name] ?? null },
});
const row = (overrides = {}) => ({
  ...core.newRow({ url: '/x', body: '{}', principal: '1', key: 'k', now: 0 }),
  id: 1,
  ...overrides,
});

describe('backoffMs', () => {
  it('doubles from 2s and caps at five minutes', () => {
    expect([1, 2, 3, 4].map(core.backoffMs)).toEqual([2000, 4000, 8000, 16000]);
    expect(core.backoffMs(20)).toBe(5 * 60 * 1000);
  });
});

describe('classify', () => {
  it.each([
    [null, 'offline'],
    [response(201), 'done'],
    [response(204), 'done'],
    [response(500), 'retry'],
    [response(503), 'retry'],
    [response(429), 'retry'],
    [response(408), 'retry'],
    [response(409, { 'Retry-After': '1' }), 'retry'],
    [response(409), 'fail'],
    [response(400), 'fail'],
    [response(403), 'fail'],
    [response(404), 'fail'],
    [response(401), 'pause'],
    [response(403, { 'X-CSRF-Failure': '1' }), 'pause'],
    [response(0, {}, 'opaqueredirect'), 'pause'],
  ])('%o is %s', (res, outcome) => {
    expect(core.classify(res)).toBe(outcome);
  });
});

describe('nextRow', () => {
  it('deletes a sent row', () => {
    expect(core.nextRow(row(), 'done', 201, 0).action).toBe('delete');
  });

  it('schedules a retry with backoff and counts the attempt', () => {
    const next = core.nextRow(row(), 'retry', 503, 1000);
    expect(next.action).toBe('put');
    expect(next.row).toMatchObject({ attempts: 1, status: 'waiting', last_status: 503, next_attempt_at: 3000 });
  });

  it('fails a row after MAX_ATTEMPTS retries', () => {
    const next = core.nextRow(row({ attempts: core.MAX_ATTEMPTS - 1 }), 'retry', 500, 0);
    expect(next.row.status).toBe('failed');
  });

  it('fails a rejected write at once', () => {
    expect(core.nextRow(row(), 'fail', 400, 0).row).toMatchObject({ status: 'failed', attempts: 1 });
  });

  it('leaves the row alone when paused or offline', () => {
    expect(core.nextRow(row(), 'pause', 401, 0)).toMatchObject({ action: 'pause', row: row() });
    expect(core.nextRow(row(), 'offline', 0, 0)).toMatchObject({ action: 'stop', row: row() });
  });
});

describe('isEligible', () => {
  it('sends only due, unfailed rows written by this user', () => {
    expect(core.isEligible(row(), 0, '1')).toBe(true);
    expect(core.isEligible(row(), 0, '2')).toBe(false);
    expect(core.isEligible(row({ next_attempt_at: 10 }), 5, '1')).toBe(false);
    expect(core.isEligible(row({ status: 'failed' }), 0, '1')).toBe(false);
  });
});

describe('summarise', () => {
  it('splits this user\'s rows into pending and failed, oldest first', () => {
    const rows = [row({ id: 3 }), row({ id: 1, status: 'failed' }), row({ id: 2 }), row({ id: 4, principal: '9' })];
    const { pending, failed } = core.summarise(rows, '1');
    expect(pending.map((r) => r.id)).toEqual([2, 3]);
    expect(failed.map((r) => r.id)).toEqual([1]);
  });
});
