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
                 │  passkey button                    │
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
| `apps/accounts/models.py` | `User`, `SignInRequest`, `Passkey`, `ReviewerAccount`; `email_key()` and `mask_email()` |
| `apps/accounts/checks.py` | Fails the system checks (so `migrate`, so a deploy) without `ACCOUNTS_EMAIL_KEY` |
| `static/js/passkeys.js`, `webauthn_json.js` | The browser side of both ceremonies |
| `static/js/code_input.js` | The code as six digit boxes; a pasted or autofilled code fills them all |
| `apps/core/ratelimit.py` | Cache-backed limits on emails, codes and passkey challenges |

## Signing in by email

- **Sign-up is the same flow.** `/signup/` sends the same link and code
  (with sign-up wording) and sets the next page to `/app/welcome/`. An
  address that already has an account gets the sign-in email instead; the
  page looks the same, so it doesn't reveal who has an account. Both pages
  share the rate limits. The welcome page sends anyone who already has a
  passkey straight on to the app.
- **The account is made on first use.** The first redeemed link or code
  for an address, from either page, creates the account (no usable
  password) with the starter library. Nothing about an address is stored
  before then except the pending request.
- **No address is kept.** The account's `username` is `email_key(address)`,
  an HMAC-SHA256 of the lower-cased address keyed with `ACCOUNTS_EMAIL_KEY`,
  and `email` is blank. `masked_email` (`h•••@example.com`) is what the
  account page, the code and link pages and passkeys show. The request holds
  the same key and masked address; the address itself is only the sign-in
  task's argument, in memory while the email is sent. Set
  `ACCOUNTS_KEEP_EMAIL = True` to keep it as the username and email too, for
  an app that emails people later; the privacy notice follows the setting.
  Why: docs/decisions/accounts-keep-a-key-not-an-email-address.md.
- **Accounts made before the key.** Tally had live accounts when the key
  arrived, so `accounts.0003` keyed them in place: each one's username
  became the key of its address, its masked address was set and the
  address blanked. Why: docs/decisions/tally-keys-its-existing-accounts.md.
- **Never change `ACCOUNTS_EMAIL_KEY`.** It is not `SECRET_KEY`, which can
  be rotated freely. Changing or losing this one cuts every account off from
  its address. Render generates it once; keep a copy.
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
- **Six boxes, one field.** `code_input.js` shows the code as six digit
  boxes: typing moves on, Backspace goes back, and pasting the code (or
  iPhone's one-time-code autofill) into any box fills all six and submits.
  Underneath it is still the one `code` field, which is all a browser
  without JavaScript sees.
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
- Sign-in needs no email: pressing "Sign in with a passkey" makes the
  browser offer every passkey it holds for the site. Nothing asks before
  the button is pressed: no autofill (conditional mediation) request on
  page load, which some browsers and password managers show as a prompt
  nobody asked for.
- A passkey deleted here but still on a device answers 404 with its id;
  the page asks the browser to forget it (`signalUnknownCredential`).
- `WEBAUTHN_RP_ID` is the site's host name and `WEBAUTHN_ORIGINS` its
  origin(s), both from `SITE_URL` by default. A passkey only works on the
  host it was made for: moving to a custom domain means users add new ones.
  If `SITE_URL` is unset in production it is the onrender.com name, and the
  browser refuses passkeys on a custom domain without telling the server.
  So both options endpoints answer 409 `wrong_host`, and log
  `passkeys.wrong_host`, when the request's host isn't the RP ID or a
  subdomain of it.

## Staff and the admin

The admin's password form redirects to `/signin/`. Make the first
superuser with your email, then sign in by email. `createsuperuser` stores
the account as sign-in does (keyed, masked, the address blank unless
addresses are kept), so it works before or after your first sign-in: if
the address already has an account (even one stored in an older form,
which sign-in would adopt), it makes that one staff and superuser rather
than a second. The username it asks for is ignored, so
give it any placeholder: not your address, which Django refuses as taken
once you have signed in with `ACCOUNTS_KEEP_EMAIL` on.

```bash
uv run python manage.py createsuperuser --username admin --email you@example.com
```

The admin lists accounts by masked address. Type a whole address into the
user search to find its account (the search turns it into the username).

## Reviewer accounts

App directories (OpenAI's for ChatGPT, Anthropic's for Claude) review an
app by signing in to a test account, and refuse one that needs an inbox, an
SMS or any other verification step. A reviewer account is an address that
signs in with a fixed code instead:

1. In the admin, add a **Reviewer account** with an address that has no
   mailbox behind it, such as `reviewer@<slug>.ultraniche.ai`. Its six-digit
   code is made when you save it.
2. Give the reviewers the address, the code, and: "Enter the email on the
   sign-in page, then type the code on the next page. No email is sent."
3. After the review, select the account and run **Give the selected
   accounts a new code**, or delete it.

- **Nothing else changes.** The reviewer uses `/signin/` and
  `/signin/code/` like anyone else. `sign_in.issue()` gives that address's
  request the fixed code, and the view sends it no email. The account
  itself is made on first sign-in, as for anyone.
- **Same limits.** Five wrong codes end a request, and an address gets five
  requests an hour, so the code can't be guessed in any useful time.
- **The code is kept as it is,** not hashed like an emailed code, so staff
  can read it in the admin. It is a shared test credential for an account
  with no one's data in it, not a person's secret.

## Email

Sent through `MAILERS["default"]`: the console in development, SMTP in
production (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`). Views only enqueue
`send_sign_in_email`; `TASKS` uses `apps.core.task_backends.ThreadBackend`,
which sends it on a thread of its own, so the page answers while the mail
relay is still talking. A failed send is logged (`django.tasks`, ERROR).
Tests run tasks inline, so mail is in the outbox before the response. Swap in
a queue-backed backend and a worker when volume needs it.

## Signing out

`POST /signout/`. `pwa.js` deletes the service worker's cached pages and
the recorded user before the form posts, so the next person on the device
can't open the last one's pages offline. Every signed-in page is sent
`no-store` (`apps/core/private_pages.py`), so Back can't show it from the
browser's cache; app pages also carry `Offline-Copy: allowed`, which lets the
service worker keep its own copy. Don't send `Clear-Site-Data: "cache"`: Chrome walks its whole
disk cache before following the redirect, which held sign-out for ~25 s. Unsent outbox rows stay on the device and are
sent only if the same user signs back in.
