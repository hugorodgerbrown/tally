/*
 * static/js/outbox_core.js — the outbox's rules, as pure functions.
 *
 * No IndexedDB, no fetch, no clock: every input is an argument, so each
 * rule is unit-tested directly (tests/js/test_outbox_core.js). outbox.js
 * does the I/O.
 *
 * A row's life:
 *
 *   queued ──send──▶ 2xx ─────────────▶ deleted (done)
 *     ▲               5xx/408/429/409+Retry-After ─▶ waiting (backoff), then queued again
 *     │               401, redirect, CSRF 403 ─────▶ unchanged; the drain pauses (sign in)
 *     │               any other 4xx ───────────────▶ failed (user retries or discards)
 *     └── network error: unchanged, the drain stops (offline is not a failure)
 *
 * Attempts count only answers from the server, so a week offline never
 * uses up a write's retries.
 */
(function () {
  'use strict';

  const MAX_ATTEMPTS = 10;
  const BASE_DELAY_MS = 2000;
  const MAX_DELAY_MS = 5 * 60 * 1000;
  const SYNC_TAG = 'outbox';

  /** Delay before retry number `attempts` (1-based): 2s, 4s, 8s … capped at 5 min. */
  function backoffMs(attempts) {
    return Math.min(BASE_DELAY_MS * 2 ** Math.max(0, attempts - 1), MAX_DELAY_MS);
  }

  /**
   * What a fetch outcome means for the row.
   * @param {{status: number, type?: string, headers?: {get(name: string): string|null}}|null} response
   *   null when fetch() threw (offline, DNS, CORS).
   * @returns {'done'|'retry'|'pause'|'fail'|'offline'}
   */
  function classify(response) {
    if (response === null) return 'offline';
    const header = (name) => (response.headers ? response.headers.get(name) : null);
    // redirect: 'manual' turns a redirect (to the sign-in page) into this.
    if (response.type === 'opaqueredirect') return 'pause';
    const status = response.status;
    if (status >= 200 && status < 300) return 'done';
    if (status === 401) return 'pause';
    if (status === 403 && header('X-CSRF-Failure')) return 'pause';
    if (status === 409 && header('Retry-After')) return 'retry';
    if (status === 408 || status === 425 || status === 429 || status >= 500) return 'retry';
    return 'fail';
  }

  /**
   * The row as it should be stored after an outcome.
   * @returns {{action: 'delete'|'put'|'pause'|'stop', row: object}}
   */
  function nextRow(row, outcome, status, now) {
    switch (outcome) {
      case 'done':
        return { action: 'delete', row: row };
      case 'pause':
        return { action: 'pause', row: row };
      case 'offline':
        return { action: 'stop', row: row };
      case 'retry': {
        const attempts = row.attempts + 1;
        if (attempts >= MAX_ATTEMPTS) {
          return { action: 'put', row: Object.assign({}, row, { attempts, status: 'failed', last_status: status }) };
        }
        return {
          action: 'put',
          row: Object.assign({}, row, {
            attempts,
            status: 'waiting',
            last_status: status,
            next_attempt_at: now + backoffMs(attempts),
          }),
        };
      }
      default:
        return {
          action: 'put',
          row: Object.assign({}, row, { attempts: row.attempts + 1, status: 'failed', last_status: status }),
        };
    }
  }

  /** True when the row should be sent now, by this user. */
  function isEligible(row, now, principal) {
    return row.status !== 'failed' && row.next_attempt_at <= now && row.principal === principal;
  }

  /** A new row. `key` is the Idempotency-Key, minted once and sent on every attempt. */
  function newRow({ method, url, body, contentType, principal, key, now, meta }) {
    return {
      idempotency_key: key,
      method: method || 'POST',
      url: url,
      body: body,
      content_type: contentType || 'application/json',
      principal: principal,
      created_at: new Date(now).toISOString(),
      attempts: 0,
      status: 'queued',
      last_status: null,
      next_attempt_at: now,
      // Anything the page needs to draw the pending item (e.g. the note text).
      meta: meta || null,
    };
  }

  /** Rows that belong to `principal`, oldest first, split by state. */
  function summarise(rows, principal) {
    const mine = rows.filter((r) => r.principal === principal).sort((a, b) => a.id - b.id);
    return {
      pending: mine.filter((r) => r.status !== 'failed'),
      failed: mine.filter((r) => r.status === 'failed'),
    };
  }

  self.OutboxCore = Object.freeze({
    MAX_ATTEMPTS,
    SYNC_TAG,
    backoffMs,
    classify,
    nextRow,
    isEligible,
    newRow,
    summarise,
  });
})();
