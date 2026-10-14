# Every app keeps its own design system, under shared rules

Status: accepted (2026-10-13)

## Context

Each Titan app looks like itself: Gondola's warm greys and blue days are not
Tally's. But they drifted the same way. An audit of Gondola's stylesheet
found 17 colour tokens and a dozen more colours hard-coded beside them, 16
font sizes with no tokens, 14 different corner radii, two text greys too
close to tell apart, and classes no template used. Nothing said what the
system was, so nothing stopped the drift.

A shared package of components would make the apps look alike and couple
their releases. A written spec on its own would go stale.

## Decision

Each app's design system lives in its own repository: the tokens and
components in `static/css/app.css`, and a staff-only design page at
`/app/design/` that reads the tokens from that file and draws every
component state with it.

The rules they all follow live in one file, `DESIGN.md`, shipped by the
template and changed only there. `tests/test_design.py` enforces what it
can: tokens instead of raw values, limits on how many there are, one
spacing scale, every component on the design page, and no dead CSS or
tokens.

## Consequences

- An app keeps its own look; the template's `copier update` keeps every app
  on the same rules.
- A UI change that adds a raw value, an unshown component or a dead class
  fails the build, so the design page stays true without anyone policing it.
- The limits bind every app. Raising one is a change to `DESIGN.md` and the
  test here, made for all of them.
