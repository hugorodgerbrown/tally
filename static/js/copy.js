/*
 * static/js/copy.js — a copy button for an address shown on the page.
 *
 * Without this file the address is plain text to select, and the button
 * stays hidden. With it, the button shows, and tapping it puts
 * ``data-copy`` on the clipboard and says "Copied" for two seconds
 * (``data-copied-label``). Where the clipboard is refused, the address is
 * selected so the next tap is the phone's own Copy.
 */
(function () {
  'use strict';

  const SHOWN_MS = 2000;

  function selectText(element) {
    const range = document.createRange();
    range.selectNodeContents(element);
    const selection = window.getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
  }

  async function copy(button) {
    const target = button.dataset.copyTarget && document.getElementById(button.dataset.copyTarget);
    try {
      await navigator.clipboard.writeText(button.dataset.copy);
    } catch (error) {
      if (target) selectText(target);
      return false;
    }
    if (!('label' in button.dataset)) button.dataset.label = button.textContent;
    button.textContent = button.dataset.copiedLabel || 'Copied';
    clearTimeout(button.copyTimer);
    button.copyTimer = setTimeout(function () {
      button.textContent = button.dataset.label;
    }, SHOWN_MS);
    return true;
  }

  function enhance(root) {
    root.querySelectorAll('[data-copy]').forEach(function (button) {
      button.hidden = false;
    });
  }

  document.addEventListener('click', function (event) {
    const button = event.target.closest && event.target.closest('[data-copy]');
    if (button) copy(button);
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      enhance(document);
    });
  } else {
    enhance(document);
  }

  self.CopyButton = { copy: copy, enhance: enhance, SHOWN_MS: SHOWN_MS };
})();
