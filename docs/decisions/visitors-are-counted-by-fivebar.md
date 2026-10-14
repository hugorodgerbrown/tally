# Visitors are counted by fivebar, and only once the app is live

Status: accepted (2026-10-12)

## Context

Every Titan app needs to know how many people use it and which pages they
open, without a cookie banner and without weakening a CSP that allows
nothing but this origin. fivebar (https://fiveb.ar) counts visits with one
async script tag and no cookies; Traintrackr already uses it. It has no
package and no server code; its API can add a site.

## Decision

- The tag goes in `templates/includes/_head.html`, so every page, public or
  in the app, carries it once. It loads from fiveb.ar as written, never
  bundled or precached: the script sends its counts to the host it came
  from.
- It is off unless `FIVEBAR_DOMAIN` is set. Locally, in CI and in tests
  nothing is drawn and the CSP gains nothing. titan sets it at go-live to
  the app's domain, next to `SITE_URL`, and adds the site to fivebar
  through its API (by hand at https://fiveb.ar/sites when titan has no
  `FIVEBAR_API_KEY`).
- While it is on, `https://fiveb.ar` is added to `script-src` and
  `connect-src` only.
- A page whose route takes values (an emailed sign-in link's token, a
  note's uuid) is counted under its route, `data-path="/signin/link/:token/"`,
  worked out from the URL resolver, so no secret or id reaches fivebar and
  a new route needs nothing added.
- An event is marked by the server with a fragment on a redirect, read by
  a static script, never by an inline script (the CSP forbids them) or a
  flag in the session (a page cached by the service worker would replay it).
- The privacy notice names fivebar, and what it receives, only while it is
  on.

## Consequences

- An app counts nothing until `titan golive`, and nothing before the site
  is added in fivebar.
- Offline, the script and its counts fail quietly; the service worker
  leaves other origins to the browser.
- One event ships: "Sign up", an account's first sign-in, so a new app can
  check it is counting. The sign-in redirect ends in `#signed-up`, which
  `static/js/analytics.js` sends and takes out of the address, so a reload
  or a copied link doesn't count again. More events are each app's to add:
  a fragment in `EVENTS` (both `apps/core/analytics.py` and the script), or
  `data-tally` on anything clicked; see https://fiveb.ar/docs/events.
- Error responses are counted as ordinary pages; Safari needs
  `data-status` on the tag to tell them apart, which the template doesn't
  set.
