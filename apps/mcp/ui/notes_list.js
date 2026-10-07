/*
 * apps/mcp/ui/notes_list.js — draw list_notes' result as a card.
 *
 * Everything from the result goes in as text, never as markup.
 */
(function () {
  'use strict';

  const status = document.querySelector('[data-status]');
  const list = document.querySelector('[data-notes]');
  const template = document.querySelector('template[data-note]');

  function when(iso) {
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
  }

  self.McpApp.onToolResult((result) => {
    if (result.isError) {
      list.replaceChildren();
      status.textContent = ((result.content || [])[0] || {}).text || 'Something went wrong.';
      status.hidden = false;
      return;
    }
    const notes = (result.structuredContent && result.structuredContent.notes) || [];
    list.replaceChildren(
      ...notes.map((note) => {
        const item = template.content.firstElementChild.cloneNode(true);
        item.querySelector('[data-text]').textContent = note.text;
        const time = item.querySelector('[data-when]');
        time.dateTime = note.written_at;
        time.textContent = when(note.written_at);
        return item;
      })
    );
    status.textContent = notes.length ? '' : 'No notes yet.';
    status.hidden = notes.length > 0;
  });
})();
