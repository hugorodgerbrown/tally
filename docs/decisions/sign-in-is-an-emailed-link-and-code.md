# Sign-in is an emailed link and code, then passkeys; there are no passwords

Status: accepted (from the project template)

## Context

Passwords are the largest account-security cost a small product carries:
storage, reset flows, reuse across sites, phishing. A magic link alone
fails in one place that matters for a PWA: an app installed on an iPhone
home screen has its own cookie jar, so a link opened from Mail signs in
Safari and leaves the app signed out.

## Decision

Sign-in and sign-up are one flow: an email carrying a single-use link and a
six-digit code. The link works in any browser; the code only in the session
that asked for it, with five tries. Once signed in, a user can add passkeys
(WebAuthn, user verification required) and sign in with those instead. The
admin uses the same sign-in.

## Consequences

- No password storage, reset or strength rules.
- Sign-in depends on email delivery: an SMTP relay is a production
  requirement, and its failures are sign-in failures.
- Passkeys are tied to the host name; a domain change means users add new
  ones (email sign-in still works).
- `SignInRequest` grows by one row per email; `purge_sign_in_requests
  --commit` runs daily with the idempotency purge.
