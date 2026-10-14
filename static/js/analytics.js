/*
 * static/js/analytics.js — send fivebar the events the server marked.
 *
 * Loaded with fivebar's tag, only while FIVEBAR_DOMAIN is set
 * (templates/includes/_analytics.html). fivebar counts pages by itself;
 * this file adds events, the things people do that a page view can't show.
 *
 * The server marks one by ending a redirect's address with its fragment,
 * e.g. "#signed-up" after an account's first sign-in (apps/core/analytics.py:
 * EVENTS). The fragment is sent as its event once, then taken out of the
 * address, so a reload, a bookmark or a copied link doesn't count again.
 *
 * fivebar's script is async and may load before or after this one: once it
 * has, `tally` is its function; until then it is a queue it sends on load.
 */
(function () {
  'use strict';

  // Fragment → event name. Keep in step with EVENTS in apps/core/analytics.py.
  const EVENTS = { '#signed-up': 'Sign up' };

  function send(name) {
    if (typeof window.tally === 'function') window.tally(name);
    else (window.tally = window.tally || []).push([name]);
  }

  const name = EVENTS[window.location.hash];
  if (name) {
    window.history.replaceState(null, '', window.location.pathname + window.location.search);
    send(name);
  }

  self.Analytics = Object.freeze({ EVENTS: EVENTS, send: send });
})();
