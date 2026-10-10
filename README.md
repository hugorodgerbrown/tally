# Tally

Interval workouts built from a library of exercises, run hands-free on a phone.
Build workouts on the desktop at `/app/workouts/`; run them on the phone at
`/app/`, offline if need be; ask Claude about them through `/mcp`. Anyone can
create an account; each account has its own library, workouts and log.

Generated from the Titan [django-titan-template](https://github.com/hugorodgerbrown/django-titan-template).
Pull template improvements in with `copier update --trust`.

## Stack

| Piece | Choice |
| --- | --- |
| Python packaging | uv (`pyproject.toml`, `uv.lock`) |
| Backend | Django 6.1; SQLite locally, Postgres on Render |
| Front end | Django templates + htmx, plain CSS tokens, plain JavaScript; no build step |
| Offline | Service worker (pages and static files) scoped to `/app/`, and an IndexedDB outbox for writes |
| Accounts | Email link or code to sign in and sign up, then passkeys; no passwords |
| Tests | pytest + FactoryBoy, Vitest + fake-indexeddb, Playwright (a few journeys) |
| Checks | ruff (lint, format, bandit, docstrings), mypy + django-stubs, semgrep, pip-audit, npm audit, gitleaks |
| Runner | tox (tox-uv): the same envs locally and in CI |
| MCP | `/mcp`, authenticated by [mcp-auth](https://github.com/hugorodgerbrown/mcp-auth) (OAuth 2.1) |

## Run it

```bash
uv sync
npm install                       # test tooling only
uv run python manage.py migrate
uv run python manage.py createsuperuser --username you@example.com --email you@example.com
uv run python manage.py runserver
```

Open <http://localhost:8000/>. Create an account with any email address: the email,
with its link and code, prints in the `runserver` console. The app itself
is <http://localhost:8000/app/>; the admin is `/admin/` (signed in by email
too, as the superuser above). Service workers run on `localhost` and
HTTPS only; to try offline on a phone, deploy (or tunnel) over HTTPS.

In Claude Code, `.claude/launch.json` starts the dev server on
<http://localhost:8010/> (clear of other projects on 8000) and the
MCP Inspector.

## Checks

```bash
uv run pre-commit install         # once
uv run tox                        # everything CI runs, except e2e and sast
uv run tox -e e2e                 # browser journeys (uv run playwright install chromium first)
```

How to test, and where each test belongs: [docs/testing.md](docs/testing.md).

## Accounts

[docs/accounts.md](docs/accounts.md): sign-in by emailed link or code,
passkeys, rate limits, and the admin.

## How offline works

[docs/pwa.md](docs/pwa.md): the service worker, the outbox, the launch
screen and how to make a new write work offline.
Also: [security](docs/security.md), [performance](docs/performance.md),
[decisions](docs/decisions/).

## Moving the live site onto the template (October 2026)

The first deploy of this version migrates the existing database in place:
the app labels (`library`, `activity`) and tables are unchanged.

- Every existing exercise and workout is given to the earliest active
  superuser (the one account Tally had). Muscle groups stay shared.
- That account signs in by email now, so its `email` must be set. Check in
  a Render shell before deploying:
  `uv run --no-sync python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values_list('username', 'email')))"`
- The phone app moved from `/activity/` to `/app/`. Old addresses redirect
  and the old service workers remove themselves, but an app installed on a
  phone's Home Screen keeps its old start page: delete it and add it again
  from `/app/`. Sessions still waiting to upload on the phone are moved
  into the new outbox the first time `/app/` opens.

## Deploy to Render

`render.yaml` is a Blueprint for the web service and a daily clean-up job.

1. Create a database and role for the project on your Postgres instance.
2. In Render, New → Blueprint, pick this repository, and enter
   `DATABASE_URL` (the instance's internal URL with this project's role and
   database) for both services. `DJANGO_SECRET_KEY` is generated for the
   web service; copy it to the cron job. A service on Render without
   `DATABASE_URL` stops with an error rather than use an empty SQLite file.
3. Set the email relay on the web service: `EMAIL_HOST`, `EMAIL_PORT`,
   `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` and `DEFAULT_FROM_EMAIL`.
   Without them nobody can sign in.
4. On a custom domain, set `SITE_URL` (links in emails, and the passkey
   origin) and add the host to `DJANGO_ALLOWED_HOSTS`.
5. The build runs `collectstatic`; each deploy runs `migrate` first;
   `/livez` is Render's health check (the process is up); `/healthz`
   also reads the database, for an uptime monitor.

## Connect Claude

Add `https://<your host>/mcp` as a custom connector in Claude. Any active
account may connect (`MCP_AUTH["CAN_CONNECT"]` is `mcp_auth.policy.active_user`
in `config/settings.py`), and the tools only ever see that account's data;
the consent page signs people in through the normal email sign-in. For a local token:

```bash
TOKEN=$(uv run python manage.py mint_mcp_token --commit -v 0)
curl -s -X POST http://localhost:8000/mcp -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

To try the whole OAuth sign-in, run the MCP Inspector
(`npx @modelcontextprotocol/inspector`, or its `.claude/launch.json` entry),
add a server with transport `streamable-http` and URL
`http://localhost:8010/mcp`, and connect. It registers itself, sends you to
the sign-in and consent pages, and comes back connected; leave its OAuth
settings empty.
