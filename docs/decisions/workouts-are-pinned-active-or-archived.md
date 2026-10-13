# Workouts are pinned, active or archived, and Claude's unused ones age out

Status: accepted (2026-10-13)

## Context

Building a workout is quick, and Claude can make one a day, so the phone's
flat, alphabetical list of every shown workout would soon be too long to
scan. The only control was `Workout.is_active`, a Hide/Show flag. Linear
RAS-42 has the full spec.

## Decision

- `Workout.status` (`pinned`, `active`, `archived`, default `active`)
  replaces `is_active`. Pinned workouts are on the phone's home screen by
  name; active ones wait behind "Show all workouts", newest first; archived
  ones are not sent to the phone.
- The migration maps shown workouts to pinned and hidden ones to archived,
  so every home screen is unchanged on the day it ships. The starter
  workout is created pinned.
- The phone does the grouping (`Engine.groupWorkouts` in `engine.js`) from
  `status` and `createdAt` in the payload. A payload cached before this
  has no status and shows flat, as it did.
- With nothing pinned, the list opens already revealed. The reveal is
  in-page state, not a route, so Back still returns to the list.
- Status is changed in Manage (Pin, Unpin, Archive, Restore, or the
  builder's select) and through the MCP tools, never from the phone, which
  would need an outbox write.
- `archive_unused_workouts`, run daily by the cron job, archives workouts
  Claude made that are still active, never done and unchanged for seven
  days. Pinned workouts, done ones and ones made in Manage are never
  touched. Restoring bumps `updated_at`, which gives another seven days.

## Consequences

- `is_active` is gone from the model, the API, the admin and the MCP
  schema; MCP clients use `status`, and `list_workouts` takes a `status`
  list instead of `include_inactive`.
- Archiving is reversible and never deletes; logged sessions are untouched.
- Ordering pinned workouts by hand, and pinning from the phone, are not
  built; either is a follow-up.
