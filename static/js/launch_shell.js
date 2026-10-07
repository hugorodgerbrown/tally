/*
 * static/js/launch_shell.js — take the launch screen away.
 *
 * Whether it shows at all is launch_gate.js's decision; this file only
 * removes it, at the first of three signals:
 *
 *   1. `app:ready` on document: a page that has something slow to set up
 *      (a map, a chart) dispatches it when that is drawn.
 *   2. window `load`: every other page.
 *   3. a 5 s timeout, because `load` can wait on one slow request forever.
 *
 * A CSS keyframe hides it at 10 s even if this file never runs.
 */
(function () {
  'use strict';

  const TIMEOUT_MS = 5000;
  const FADE_MS = 400; // covers the 300 ms opacity transition in app.css

  function dismiss() {
    const root = document.documentElement;
    const shell = document.getElementById('launch-shell');
    if (!root.classList.contains('app-launching') || !shell) return;
    shell.classList.add('launch-shell--done');
    setTimeout(function () {
      root.classList.remove('app-launching');
    }, FADE_MS);
  }

  document.addEventListener('app:ready', dismiss, { once: true });
  if (document.readyState === 'complete') dismiss();
  else window.addEventListener('load', dismiss, { once: true });
  setTimeout(dismiss, TIMEOUT_MS);

  self.LaunchShell = Object.freeze({ dismiss: dismiss, TIMEOUT_MS: TIMEOUT_MS });
})();
