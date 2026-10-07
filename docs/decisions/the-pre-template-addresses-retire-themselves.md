# The pre-template addresses redirect, and the old service workers retire themselves

Status: accepted (2026-10-07)

## Context

Before the move the phone app lived at `/activity/` with its own service
worker (and before that, a worker at `/sw.js` controlled the whole site).
The planner was at `/workouts/` and `/exercises/`, and sign-in at
`/login/`. Phones have the old app installed, possibly with sessions
waiting to upload in its own IndexedDB database.

## Decision

- The phone app moves into the template's `/app/` scope, with the
  template's worker and outbox. The planner moves under `/app/` too,
  because signed-in pages live there.
- `apps/activity/retired.py` answers both old worker URLs with a worker
  that deletes only the old caches and unregisters, and redirects the old
  pages (`/activity/` and the planner permanently, the sign-in pages
  temporarily).
- The first time `/app/` opens on a phone, `Store.migrateLegacy()` moves
  sessions waiting in the old `workouts` database into the outbox, keeps
  a running workout's checkpoint, and deletes the old database.

## Consequences

- An app installed on a Home Screen keeps its old start page, which now
  redirects into a different scope; it works, but in the browser's own
  chrome. Delete it and add it again from `/app/`.
- `retired.py` can be removed once no phone still has the old worker.
  Its traffic in the access log will say when.
