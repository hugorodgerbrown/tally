# Writes that must work offline go through the outbox, and the server deduplicates them

Status: accepted (from the project template)

## Context

An installed app is used where the connection drops. A write sent with
`hx-post` or a form while offline is lost; a write retried by hand after a
timeout can be applied twice, because the first attempt may have reached
the server even though its answer didn't come back.

## Decision

Writes that must survive being offline are stored on the device first
(IndexedDB, `static/js/outbox.js`) with an `Idempotency-Key` minted once,
and sent until the server answers. `IdempotencyMiddleware` runs a keyed
request at most once per key for 24 hours and replays the first answer to
any repeat. The key is claimed before the view runs, so concurrent repeats
can't both write.

## Consequences

- Writes appear at once as pending, whether or not there is a connection.
- Endpoints that take outbox writes answer JSON, and 401 rather than
  redirect when signed out.
- `IdempotencyRecord` grows by one row per write; a daily job
  (`purge_idempotency_records --commit`) deletes expired rows.
- Writes that need an immediate server answer (sign-in, payments) stay
  online-only and don't use the outbox.
