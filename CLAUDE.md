# CLAUDE.md — Tally

Interval workouts built from a library of exercises, run hands-free on a phone. A Django PWA generated from the Titan
[django-titan-template](https://github.com/hugorodgerbrown/django-titan-template); keep
it close to the template so `copier update --trust` stays a clean merge.

## Layout

```
config/          settings (one module, env-driven), urls, wsgi/asgi
apps/core/       BaseModel, IdempotencyMiddleware + IdempotencyRecord,
                 decorators (require_htmx, login_required_json), rate
                 limits, safe_next, livez and healthz
apps/accounts/   sign-in by emailed link or code (SignInRequest), passkeys
                 (Passkey), sign-out, /app/account/ (docs/accounts.md)
apps/public/     the public pages: /, /terms/, /privacy/, /help/ (placeholders);
                 each body is one _<name>_body.html, also served as Markdown
apps/pwa/        /app/manifest.webmanifest, /app/sw.js, /app/offline/;
                 conf.py holds the app's identity, SCOPE and the precache list
apps/notes/      the example offline-capable feature, at /app/; replace it
apps/mcp/        the MCP endpoint (/mcp) and its tools; auth is mcp-auth.
                 privacy_policy, terms_of_service and help return the
                 public pages as Markdown (apps/public/pages.py);
                 resources.py + ui/ hold MCP App views (ui:// HTML a
                 tool names with Tool(ui=...), docs/decisions/)
templates/       base.html (the app, /app/), public_base.html, includes
static/js/       plain JavaScript, classic scripts, no build step
static/css/      app.css: tokens on :root, components below
docs/            accounts, testing, pwa, security, performance, decisions/
```

## Commands

```bash
uv sync && npm install
uv run python manage.py runserver
uv run tox                      # every check CI runs (except e2e, sast)
uv run tox -e e2e               # Playwright journeys
uv run pytest tests/notes       # targeted run while iterating
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
- No inline `<script>`, `style=` or `on*=` in templates: the CSP blocks
  them and `tests/test_security.py` fails the build.
- Style with the tokens in `static/css/app.css`; add a component class
  there rather than one-off values.
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

## Tests

Three layers, top-down, stop at the first that can hold the assertion:
pytest (anything the test client sees), Vitest (anything jsdom sees),
Playwright (only real service-worker and offline journeys, capped).
Coverage floor 90%. Full rules: [docs/testing.md](docs/testing.md).

## Before opening a PR

Run `uv run tox` and fix every failure. Record a non-obvious architectural
choice in `docs/decisions/`.

## Invariants

1. No `mark_safe()` / `|safe` on content from outside the code.
2. No inline script, style or event handler in a template.
3. Every fragment view is `@require_htmx`; every outbox endpoint is
   `@login_required_json`.
4. No secrets in source.
5. Email addresses are lower-cased before storage and lookup.
6. Sign-in secrets (link tokens, codes) are stored only as hashes and
   never logged.
7. Who may connect an MCP client (`apps/mcp/policy.py`) only widens in a PR
   that says so.
