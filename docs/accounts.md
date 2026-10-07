# Accounts: email sign-in and passkeys

There are no passwords. Someone signs up at `/signup/` with an email
address; the link or code in the email creates the account and lands on
`/app/welcome/`, which suggests a passkey (Face ID, a fingerprint or a
device PIN). From then on they sign in with the passkey, or by email.

```
   /signup/ ── email ──┐   (same request, worded "Finish creating your account",
                       │    next = /app/welcome/ ─▶ Add a passkey / Not now)
                 ┌─────▼────── /signin/ ─────────────┐
                 │  email ──▶ SignInRequest (hashes)  │──▶ email: link + 6-digit code
                 │  passkey button / autofill         │
                 └──────┬─────────────────────┬──────┘
          link, any browser                code, this browser only
   /signin/link/<token>/ ── Continue (POST)    /signin/code/ ── POST code
                 └──────────────┬──────────────┘
                     used once ─▶ account found or created ─▶ login() ─▶ next (or /app/)

 /app/account/ ── Add a passkey ─▶ options (challenge in session) ─▶ create() ─▶ verify, save Passkey
 /signin/      ── passkey       ─▶ options (challenge in session) ─▶ get()    ─▶ verify, login()
```

## Pieces

| File | Job |
| --- | --- |
| `apps/accounts/sign_in.py` | Issue a request; redeem its link or code once; find or create the account |
| `apps/accounts/passkeys.py` | WebAuthn options and verification (py_webauthn) |
| `apps/accounts/views.py` | The sign-up, sign-in, code, link, welcome, sign-out, account and passkey endpoints |
| `apps/accounts/tasks.py` | `send_sign_in_email`, enqueued by the view (`django.tasks`) |
| `apps/accounts/models.py` | `SignInRequest`, `Passkey` |
| `static/js/passkeys.js`, `webauthn_json.js` | The browser side of both ceremonies |
| `apps/core/ratelimit.py` | Cache-backed limits on emails, codes and passkey challenges |

## Signing in by email

- **Sign-up is the same flow.** `/signup/` sends the same link and code
  (with sign-up wording) and sets the next page to `/app/welcome/`. An
  address that already has an account gets the sign-in email instead; the
  page looks the same, so it doesn't reveal who has an account. Both pages
  share the rate limits. The welcome page sends anyone who already has a
  passkey straight on to the app.
- **The account is made on first use.** The first redeemed link or code
  for an address, from either page, creates the account (`username` and `email` both the lowercased address,
  no usable password). Nothing about an address is stored before then
  except the pending request.
- **Link and code, either once.** Each email carries a link and a six-digit
  code, valid for `SIGN_IN_MAX_AGE_SECONDS` (15 minutes). Asking again ends
  the earlier request, so only the newest email works. Only hashes are
  stored: the link token as SHA-256, the code as an HMAC with the secret key.
- **Why a code too.** An app installed on an iPhone home screen keeps its
  own cookies, separate from Safari. A link opened from Mail signs in
  Safari, not the app; the app's user types the code instead.
- **The code only works where it was asked for.** The session holds the
  request's uuid, so a code is useless in another browser, and five wrong
  codes (`SIGN_IN_MAX_CODE_ATTEMPTS`) end it. That is what makes six digits
  enough.
- **The link page needs a click.** Mail scanners open links to check them;
  a link that signed in on GET would be used up before the person saw it.
- **No enumeration.** The form answers the same whether or not the address
  has an account. A deactivated account is told so only after it proves it
  owns the address.
- **Limits.** 10 sign-in emails per IP per 10 minutes, 5 per address per
  hour, 20 code tries per IP per 10 minutes, 30 passkey challenges per IP
  per 10 minutes. Behind Render the
  client IP is the last `X-Forwarded-For` hop (`RATE_LIMIT_PROXY_COUNT`).
  The counters live in the cache: point `CACHES` at Redis or the database
  when there is more than one process.
- **`next` survives.** It is checked (`apps/core/redirects.safe_next`),
  stored on the request, and used wherever the link is opened, so signing
  in from the MCP consent page or a deep link comes back there.

## Passkeys

- Added from `/app/account/`, removed there too. Each is named after the
  device it was made on ("Passkey on iPhone").
- Discoverable credentials with user verification required: a passkey alone
  signs someone in, so it has to be the person, not just the device.
- Sign-in needs no email: the browser offers every passkey it holds for the
  site, from the button or from the email field's autofill (conditional
  mediation).
- A passkey deleted here but still on a device answers 404 with its id;
  the page asks the browser to forget it (`signalUnknownCredential`).
- `WEBAUTHN_RP_ID` is the site's host name and `WEBAUTHN_ORIGINS` its
  origin(s), both from `SITE_URL` by default. A passkey only works on the
  host it was made for: moving to a custom domain means users add new ones.

## Staff and the admin

The admin's password form redirects to `/signin/`. Make the first
superuser with your email as the username, then sign in by email:

```bash
uv run python manage.py createsuperuser --username you@example.com --email you@example.com
```

## Email

Sent through `MAILERS["default"]`: the console in development, SMTP in
production (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). Views only enqueue
`send_sign_in_email`; `TASKS` uses the immediate backend, which runs it in
the request. Swap in a queue-backed backend and a worker when volume needs it.

## Signing out

`POST /signout/`. `pwa.js` deletes the service worker's cached pages and
the recorded user before the form posts, and the response sends
`Clear-Site-Data: "cache"`, so the next person on the device can't open the
last one's pages offline. Unsent outbox rows stay on the device and are
sent only if the same user signs back in.
