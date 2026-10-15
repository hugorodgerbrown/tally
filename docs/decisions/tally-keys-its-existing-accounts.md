# Tally keys its existing accounts in place

Status: accepted (2026-10-15)

## Context

The template moved every Titan app to a custom user model that keeps a key
and a masked address instead of the email address
([accounts-keep-a-key-not-an-email-address.md](accounts-keep-a-key-not-an-email-address.md)).
It did so by rewriting `accounts.0001`, on the understanding that no app
had live data and each would reset its database once.

Tally does have live data: accounts, their libraries, their training logs,
passkeys and Claude connections, all on `auth.User`. Resetting would lose
all of it, and Tally's `accounts.0001` has already run, so the template's
rewritten one never would.

## Decision

Swap the user model in place, and key every account in the same deploy.

- **0001 declares the table that is there.** Tally's own `accounts.0001`
  (not the template's) now also creates `accounts.User` exactly as
  `auth.User` stood, on the `auth_user` table. On the live database it has
  already run, so only the migration state changes; a new database creates
  the table here, since `auth` skips a swapped model.
- **0002 makes it the template's model.** A masked address, `BaseModel`'s
  uuid and timestamps (dated from `date_joined`), a big-int key (Postgres
  widens every foreign key to it), and the table renamed to
  `accounts_user` with its two many-to-many tables. Sign-in requests take
  the key and masked address; the pending ones are deleted, as none
  outlives 15 minutes. Reviewer accounts are added.
- **0003 keys the accounts.** Each username becomes `email_key(address)`,
  `masked_email` is set and `email` blanked, so no address is left once the
  deploy has run. `auth.user`'s content type moves to `accounts.user`, so
  the admin's history follows.

Afterwards the state matches the template's model exactly
(`makemigrations --check` finds nothing), so later template updates merge
as for any other app.

## Consequences

- **`ACCOUNTS_EMAIL_KEY` must be set before the deploy**, or the
  `accounts.E001` check stops `migrate` and the deploy with it (nothing
  changes). The Blueprint generates it on the web service and the purge job
  reads it from there; keep a copy outside Render.
- **It can't be undone.** Once 0003 has run the addresses are gone; rolling
  back to the old code would leave people unable to sign in to their
  accounts. Take a database backup before deploying.
- Everyone signs in with the same address as before and lands in the same
  account, with the same library, log, passkeys and Claude connection.
  Tested on Postgres against a copy of the old schema.
- An account whose address is already another account's key is left as it
  is and logged, for staff to merge. Tally has no such pair.
