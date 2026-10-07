// Tests for static/js/notes.js: pending and failed notes, and their Retry and Discard buttons.
import { afterEach, describe, expect, it, vi } from 'vitest';

const PAGE = `
  <form data-note-form action="/app/new/"><textarea name="text"></textarea></form>
  <ul data-pending-notes></ul>
  <template data-pending-note>
    <li class="note note--pending">
      <p class="note__text" data-text></p>
      <p class="note__meta" data-state>Waiting to send</p>
      <div class="note__actions" data-actions hidden>
        <button type="button" data-retry>Retry</button>
        <button type="button" data-discard>Discard</button>
      </div>
    </li>
  </template>`;

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

async function load(pending, failed) {
  document.body.innerHTML = PAGE;
  self.Outbox = {
    list: vi.fn(() => Promise.resolve({ pending, failed })),
    enqueue: vi.fn(() => Promise.resolve()),
    retry: vi.fn(() => Promise.resolve()),
    discard: vi.fn(() => Promise.resolve()),
  };
  vi.resetModules();
  await import('../../static/js/notes.js');
  await flush();
  return document.querySelectorAll('[data-pending-notes] li');
}

afterEach(() => {
  delete self.Outbox;
});

describe('pending notes', () => {
  it('draws a waiting note with no actions', async () => {
    const [item] = await load([{ id: 1, url: '/app/new/', status: 'queued', meta: { text: 'hi' } }], []);
    expect(item.querySelector('[data-text]').textContent).toBe('hi');
    expect(item.querySelector('[data-actions]').hidden).toBe(true);
  });

  it('ignores rows for another form', async () => {
    const items = await load([{ id: 1, url: '/elsewhere/', status: 'queued', meta: { text: 'x' } }], []);
    expect(items).toHaveLength(0);
  });
});

describe('failed notes', () => {
  it('says why, and Retry and Discard act on that row', async () => {
    const [item] = await load([], [{ id: 9, url: '/app/new/', status: 'failed', last_status: 403, meta: { text: 'no' } }]);
    expect(item.classList.contains('note--failed')).toBe(true);
    expect(item.querySelector('[data-state]').textContent).toBe('Not sent (403)');
    expect(item.querySelector('[data-actions]').hidden).toBe(false);

    item.querySelector('[data-retry]').click();
    expect(self.Outbox.retry).toHaveBeenCalledWith(9);
    item.querySelector('[data-discard]').click();
    expect(self.Outbox.discard).toHaveBeenCalledWith(9);
  });
});
