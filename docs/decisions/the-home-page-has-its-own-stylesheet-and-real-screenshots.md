# The home page has its own stylesheet and shows real screenshots

Status: accepted (2026-10-14)

## Context

The home page sells the product: a proposition, a picture of the builder
and the phone timer, and what to ask Claude. That needs a hero, a product
shot, tiles, a sample chat and a stats strip, about 6 KB of CSS no other
page uses. `app.css` is in the service worker's precache, which
`tests/test_performance.py` holds to a byte budget, and the public pages
sit outside the installed app.

## Decision

- The home page's styles live in `static/css/home.css`, scoped to
  `.home`, linked from `home.html` alone. It is not precached.
- The product shot is two real screenshots from a demo account (the
  builder at 1280 px, the phone mid-workout at 390 px), saved as WebP in
  `static/img/`, not a drawn mock-up, so the page shows exactly what a new
  account gets.
- The connector address is printed from the request's host, as Account
  does, with a Copy button that `static/js/copy.js` reveals only when the
  Clipboard API is there.

## Consequences

- The installed app's shell is unchanged; the home page weighs about
  200 KB, inside Lighthouse's 250 KB.
- When the builder or the phone timer changes its look, the screenshots
  go stale and should be retaken from a demo account.
