/*
 * static/js/copy.js — a Copy button for a piece of text on the page.
 *
 *   <code id="mcp-url">https://…/mcp</code>
 *   <button data-copy="mcp-url" hidden>…</button>
 *
 * The button ships hidden, so without JavaScript (or without the
 * Clipboard API) the text is simply there to select. With them, the
 * button shows, copies the element's text and says "Copied" for a moment.
 */
(function () {
  'use strict';

  function wire(button) {
    const target = document.getElementById(button.getAttribute('data-copy'));
    if (!target || !navigator.clipboard) return;
    const label = button.getAttribute('aria-label');
    button.hidden = false;
    button.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(target.textContent.trim());
        button.setAttribute('aria-label', 'Copied');
        button.title = 'Copied';
        button.classList.add('is-done');
        setTimeout(() => {
          button.setAttribute('aria-label', label);
          button.title = 'Copy';
          button.classList.remove('is-done');
        }, 2000);
      } catch (error) {
        // Denied or unavailable: the text is still there to select.
      }
    });
  }

  function init() {
    document.querySelectorAll('[data-copy]').forEach(wire);
  }

  self.Copy = Object.freeze({ init });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
