# A style that comes from data goes in data-css, applied by styles.js

Status: accepted (2026-10-07)

## Context

The template's CSP allows no inline `style` attribute. Tally draws a few
things whose look is data: an exercise type's colour (stored on the
type), a bar's width in a summary, a segment's share of a strip. The
planner templates and the phone app's HTML strings both did this with
`style="..."`.

## Decision

Markup carries `data-css="background:#F7C948;flex:40"` instead.
`static/js/styles.js` sets each declaration with `style.setProperty`
(the CSSOM, which the CSP allows), and watches the page so markup added
later (the builder, every screen of the phone app) is styled as it lands.
Styles that are not data became classes in `planner.css` and
`activity.css`.

## Consequences

- Without JavaScript those few data styles are missing: the colour dots
  and bars are blank, everything else reads. That is acceptable for
  decoration.
- The phone app and planner load `styles.js` first; it is in the precache.
- `data-css` is only ever written by our templates and scripts, from
  stored values; it is not a way to put user input into CSS.
