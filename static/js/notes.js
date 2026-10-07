/*
 * static/js/notes.js — send the note form through the outbox.
 *
 * Without this file the form is a normal post. With it, a note is stored on
 * the device first and drawn at once as "Waiting to send", whether or not
 * there is a connection; the outbox sends it when it can, and htmx then
 * refreshes the list (`outbox:sent`, see note_list.html). A note the server
 * refused shows why, with Retry (after fixing whatever refused it, such as a
 * permission) and Discard.
 */
(function () {
  'use strict';

  const form = document.querySelector('[data-note-form]');
  const list = document.querySelector('[data-pending-notes]');
  const template = document.querySelector('template[data-pending-note]');
  if (!form || !list || !template) return;

  async function drawPending() {
    const { pending, failed } = await self.Outbox.list();
    const rows = pending.concat(failed).filter((row) => row.url === form.getAttribute('action'));
    list.replaceChildren(
      ...rows.map((row) => {
        const item = template.content.firstElementChild.cloneNode(true);
        item.querySelector('[data-text]').textContent = (row.meta && row.meta.text) || '';
        if (row.status === 'failed') {
          item.classList.add('note--failed');
          item.querySelector('[data-state]').textContent = 'Not sent (' + row.last_status + ')';
          item.querySelector('[data-actions]').hidden = false;
          item.querySelector('[data-retry]').addEventListener('click', () => self.Outbox.retry(row.id));
          item.querySelector('[data-discard]').addEventListener('click', () => self.Outbox.discard(row.id));
        }
        return item;
      })
    );
  }

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const text = form.elements.text.value.trim();
    if (!text) return;
    await self.Outbox.enqueue({
      url: form.getAttribute('action'),
      body: JSON.stringify({ text: text, written_at: new Date().toISOString() }),
      meta: { text: text },
    });
    form.reset();
  });

  document.addEventListener('outbox:changed', drawPending);
  drawPending();
})();
