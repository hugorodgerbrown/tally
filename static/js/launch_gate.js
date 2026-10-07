/*
 * static/js/launch_gate.js — decide, before first paint, whether the launch
 * screen shows.
 *
 * Loaded as a blocking script in <head> (the CSP allows no inline script),
 * so it must stay tiny. It shows the launch screen only for a cold start of
 * the installed app: standalone display mode, first page of this session.
 * A browser tab, or a later page in the same session, never sees it.
 */
(function () {
  'use strict';
  try {
    const standalone =
      window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
    if (!standalone || sessionStorage.getItem('app:launched')) return;
    sessionStorage.setItem('app:launched', '1');
    document.documentElement.classList.add('app-launching');
  } catch (e) {
    // Storage blocked: show nothing rather than risk a launch screen on every page.
  }
})();
