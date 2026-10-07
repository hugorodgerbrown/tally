# Anyone can sign up, and every exercise, workout and session has an owner

Status: accepted (2026-10-07)

## Context

Tally began as one person's app: a single superuser, one shared library,
and a session log keyed to that user. Moving it onto the Titan template
brought email sign-up for free, and the question of who may use it. Hugo
chose open sign-up.

## Decision

- `Exercise` and `Workout` gain a required `owner`. `ActivitySession` and
  `DiscardedSession` already had one (renamed from `user`). Every query in
  the planner, the phone API and the MCP tools goes through `for_user`.
  Another account's uuid answers 404 (or `not_owner` in the session API).
- `ExerciseType` stays shared reference data: five rows from a data
  migration, which the colours and the summary depend on.
- `MuscleGroup` is shared when `owner` is empty (the starter set) and
  private otherwise. Typing a new muscle adds a private one, so one
  account's additions never show in another's lists.
- Every new account gets the starter library (21 exercises and a sample
  workout, `apps/library/starter.py`), so the phone has something to play
  on the first open.
- The migration gives every existing exercise and workout to the earliest
  active superuser (the one account there was). It refuses to guess when
  rows exist but no account does.
- Any active account may connect Claude (`mcp_auth.policy.active_user`):
  the tools only reach that account's data.

## Consequences

- Names are unique per owner, not globally: two accounts may each have a
  Plank.
- The privacy notice and terms now face strangers, not just their author.
  They were written for this change, but should be reviewed before Tally
  is offered widely.
- Making a shared exercise library (or sharing a workout) later is new
  work: nothing here is visible across accounts.
