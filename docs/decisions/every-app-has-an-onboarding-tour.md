# Every app has an onboarding tour, run on demo data

Status: accepted (2026-10-12)

## Context

A new Titan app is usually empty for the person who has just signed up:
no data of their own yet, and often nobody else's. An empty screen
explains nothing, so people leave before they see what the app is for.
Gondola worked through this first. A tour that asked people to do real
work on their own empty data broke down: the real date might be in
another month, the real search might find nothing, and being the first
person in a group meant every screen was blank.

## Decision

- Every app ships a first-run tour, offered once after an account's first
  sign-in and available again from the account page.
- The script is written and agreed before it is built, in
  `docs/onboarding-tour.md`: the chapters, every frame's words, and why
  each one is there.
- The tour runs on demo data: a private copy made for the one person
  taking it, dated around today, so every screen is full and every step
  lands on something real. Nobody else ever sees that copy.
- It is look-and-tap. Real controls take real taps, so people learn the
  way through, but anything that would save (a form, a create) moves the
  tour on and writes nothing. The server refuses writes while a tour is
  running, not only the script.
- Every page has the same shape: a whole-page intro that says what the
  page is for, then the spotlight zooms into one part at a time, then a
  real tap leads to the next page.
- A bar on every tour screen says it is a demo and offers End tour.
- The tour ends by deleting the demo copy and handing over to the
  person's real first action: the thing the app is for, on their own data.
- It is measured in fivebar with three events, `Tour started`,
  `Tour ended` (with the chapter) and `Tour finished`, plus the app's own
  first real action, so the tour's effect can be compared with people who
  skipped it.

## Consequences

- Each app needs a demo-data builder and a way to keep demo data out of
  everything real: lists, counts, emails, exports, the MCP tools.
- A demo copy abandoned mid-tour is deleted the next time its owner loads
  a page, or by the daily clean-up job, so no scheduled job is added.
- The tour's words are the app's copy like any other: they go through
  `{% trans %}` and are reviewed in the PR that changes the page.
- The first app to build this was Gondola; its engine is the reference
  until the template carries one of its own.
