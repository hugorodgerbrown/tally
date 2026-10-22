# CLAUDE.md — Tally

Interval workouts built from a library of exercises, run hands-free on a phone.
Anyone can sign up; every exercise, workout and session belongs to one
account. A Django PWA generated from the Titan
[django-titan-template](https://github.com/hugorodgerbrown/django-titan-template); keep
it close to the template so `copier update --trust` stays a clean merge.

## Layout

```
config/          settings (one module, env-driven), urls, wsgi/asgi
apps/core/       BaseModel, IdempotencyMiddleware + IdempotencyRecord,
                 PrivatePagesMiddleware (signed-in pages never cached),
                 decorators (require_htmx, login_required_json), rate
                 limits, safe_next, livez and healthz; errors.py is the
                 error pages (400/403/404/500, CSRF), as JSON, text or
                 HTML (DESIGN.md, "Error pages"); analytics.py puts
                 fivebar's tag on every page while FIVEBAR_DOMAIN is set,
                 and marks events (a sign-up) for static/js/analytics.js
apps/accounts/   sign-up (/signup/) and sign-in by emailed link or code
                 (SignInRequest), passkeys (Passkey), the passkey nudge at
                 /app/welcome/, sign-out, /app/account/ (docs/accounts.md)
apps/public/     the public pages: /, /terms/, /privacy/, /help/;
                 each body is one _<name>_body.html, also served as Markdown
apps/pwa/        /app/manifest.webmanifest, /app/sw.js, /app/offline/;
                 conf.py holds the app's identity, SCOPE and the precache list
apps/library/    ExerciseType (shared, six), MuscleGroup (shared, or private to
                 an owner), Exercise, Workout, WorkoutItem (owned);
                 starter.py installs the 23-exercise starter library on
                 every new account; timeline.py mirrors engine.js
apps/activity/   the phone app at /app/ (Workout mode: one page,
                 static/js/activity_*.js + engine.js), its JSON API under
                 /app/api/, Report at /app/report/ (report.py: the
                 week/month totals training_summary also uses), and the
                 logged ActivitySession / SessionEntry / DiscardedSession;
                 retired.py keeps the pre-template addresses working
apps/planner/    build workouts and exercises: /app/workouts/, /app/exercises/
apps/design/     the design page (/app/design/, staff only): every token
                 and every component state (DESIGN.md)
apps/mcp/        the MCP endpoint (/mcp) and its tools; auth is mcp-auth.
                 privacy_policy, terms_of_service and help return the
                 public pages as Markdown (apps/public/pages.py);
                 resources.py + ui/ hold MCP App views (ui:// HTML a
                 tool names with Tool(ui=...), docs/decisions/);
                 events.py counts each tool call in fivebar as a server
                 event while FIVEBAR_DOMAIN and FIVEBAR_TOKEN are set
templates/       base.html (the app, /app/), public_base.html, includes,
                 errors/ (the error card, its site and standalone pages)
static/js/       plain JavaScript, classic scripts, no build step
static/css/      tokens.css (Tally's tokens and fonts), app.css (template
                 components, the design system's tokens mapped to Tally's;
                 DESIGN.md), planner.css (scoped .planner), activity.css
                 (scoped #app)
docs/            accounts, testing, onboarding-tour, pwa, security,
                 performance, decisions/
.claude/skills/  writing the Titan docs kept in Linear (research, user
                 testing script, blog post), each with a length setting
```

## Commands

```bash
uv sync && npm install
uv run python manage.py runserver
uv run tox                      # every check CI runs (except e2e, sast)
uv run tox -e e2e               # Playwright journeys
uv run pytest tests/library     # targeted run while iterating
```

Never run a bare `pytest`; use `uv run`. Dependencies: `uv add` /
`uv add --group <test|lint|types|e2e> …`, then commit `uv.lock`.

## Code conventions

- A module docstring on every module and a docstring on every class and
  function (ruff `D`, Google style); every argument typed.
- British English in prose and identifiers (colour, behaviour), except
  third-party names.
- Simple over clever; no abstraction until two callers need it.
  Composition over inheritance.
- `logging.getLogger(__name__)` in every module; no `print`.
- No Django signals for side effects: call them from the service function.
- Secrets only through `python-decouple`; never in source.

### Models

Every concrete model ships the full kit: inherits `BaseModel`; has an
admin class, a `to_string()`, an explicit `Meta.ordering`, a custom
queryset, a factory in `tests/factories.py`, and tests. Use `uuid`, never
`id`, in URLs and anything a client sees.

### Views and templates

- Full pages return whole documents; fragments live under `partials/` and
  are `@require_htmx`.
- Render pages with `apps.core.shortcuts.render`, not Django's: it puts the
  response's status in the context as `http_status`, which fivebar's tag
  sends as `data-status` so Safari's 4xx and 5xx pages count as errors.
- No inline `<script>`, `style=` or `on*=` in templates: the CSP blocks
  them and `tests/test_security.py` fails the build. A style that comes
  from data (a type's colour, a bar's width) goes in `data-css="..."`,
  which `static/js/styles.js` applies through the CSSOM.
- Every query for exercises, workouts or sessions is scoped to the signed-in
  user (`for_user`, `signed_in_user`); another account's uuid is a 404.
- Follow [DESIGN.md](DESIGN.md) on every UI change: check the design
  page (`/app/design/`) first, use tokens and never raw values, show every
  new component and state on the page, and delete dead CSS.
  `tests/test_design.py` enforces it (on app.css).
- A page should work without JavaScript; JavaScript makes it better.
- Signed-in pages live under `/app/` (the installed app's scope) and
  extend `base.html`; public pages sit outside it and extend
  `public_base.html`. Read [docs/pwa.md](docs/pwa.md#scope).

### Writes that must work offline

Go through the outbox: `Outbox.enqueue(...)` in the page, an endpoint that
takes JSON and is `@login_required_json`. Read [docs/pwa.md](docs/pwa.md)
first. Add any new static file the shell needs offline to
`apps/pwa/conf.py: PRECACHE_STATIC` (it has a byte budget).

### Management commands

Run with no arguments to do the common thing, read-only unless `--commit`,
respect `--verbosity`, exit non-zero on failure.

### Accounts

No passwords: email link or code, then passkeys. Read
[docs/accounts.md](docs/accounts.md) before touching sign-in. Views never
send mail; they enqueue a task (`apps/accounts/tasks.py`).

## Onboarding tour

Every app ships a first-run tour, offered after an account's first sign-in
and again from the account page. Write the script in
`docs/onboarding-tour.md` and agree it before building. The tour runs on a
private demo copy made for the one person taking it, never on their real
data; real taps move it on, and nothing in it saves. Each page gets an
intro, then zoom-ins on its parts, then a real tap to the next page; it
ends on the person's first real action. Measure it in fivebar with
`Tour started`, `Tour ended`, `Tour finished` and that first action. Why:
[docs/decisions/every-app-has-an-onboarding-tour.md](docs/decisions/every-app-has-an-onboarding-tour.md).

## Linear

Every Titan app has a Linear project, Tally, in the Titan
team (issue keys `RAS-`), and every change maps to an issue there: one
issue per PR, one PR per issue. Why:
[docs/decisions/every-change-starts-as-a-linear-issue.md](docs/decisions/every-change-starts-as-a-linear-issue.md).

- If the project doesn't exist yet (a new app), create it in the Titan
  team first, named after the app, then file the first issue in it.
- The issue is the sign-off. Before writing code, Claude creates it in
  the app's project with the scope: what changes, what doesn't, how
  we'll know it's done, and the decision behind it. Work starts once the
  person agrees the scope, not before.
- If the scope changes during the work, say so on the issue before the
  PR goes up, so the issue records what was built and why.
- The PR title is `RAS-42: what it does` and its body starts
  `Closes RAS-42`, so Linear links the two and closes the issue on merge.
- Reversing an earlier decision is a new issue that links the old one
  and says why it changed. Never rewrite the old issue: the history is
  the point.
- Dependabot's PRs are the one exception: they need no issue.
- Without the Linear MCP server, say so and give the issue as Markdown
  for the person to file; don't start unticketed work.

## Branches

Every new branch starts by pulling in the template, so the app never
drifts far from it and the template's changes are reviewed apart from the
branch's own work.

- Before any other change, on a clean tree, run `copier update --trust`.
- Resolve any conflicts it leaves, keeping the app's deliberate
  differences (their reasons are in `docs/decisions/`), then run
  `uv run tox`.
- Commit the result on its own as the branch's first commit, for example
  `RAS-42: Update from the Titan template`, before starting the issue's
  work.
- If the update changes nothing, there is nothing to commit: skip it,
  never make an empty commit.

## Tests

Three layers, top-down, stop at the first that can hold the assertion:
pytest (anything the test client sees), Vitest (anything jsdom sees),
Playwright (only real service-worker and offline journeys, capped).
Coverage floor 90%. Full rules: [docs/testing.md](docs/testing.md).

## Before opening a PR

Run `uv run tox` and fix every failure. Check the PR names its Linear
issue and its first commit is the template update, if there was one
(above). Record a non-obvious architectural choice in
`docs/decisions/`.

## Invariants

1. No `mark_safe()` / `|safe` on content from outside the code.
2. No inline script, style or event handler in a template.
3. Every fragment view is `@require_htmx`; every outbox endpoint is
   `@login_required_json`.
4. No secrets in source.
5. Email addresses are lower-cased before they are keyed, stored or looked
   up, and stored only where `ACCOUNTS_KEEP_EMAIL` is on: otherwise an
   account holds `email_key(address)` and `masked_email`
   (docs/decisions/accounts-keep-a-key-not-an-email-address.md).
6. Sign-in secrets (link tokens, codes) are stored only as hashes and
   never logged. The one exception is a reviewer account's fixed code,
   which staff read in the admin (docs/accounts.md).
7. Who may connect an MCP client (`MCP_AUTH["CAN_CONNECT"]` in
   `config/settings.py`, now any active account) only changes in a PR that
   says so.
