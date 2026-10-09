# The installed app is scoped to /app/

Status: accepted (from the project template)

## Context

A service worker controls every page under its own path. Registered at
`/sw.js` it controlled the whole site: the homepage, legal pages, sign-in,
the admin and OAuth, each needing an exclusion list so they were never
cached or shown inside the installed app.

## Decision

The app is everything under `/app/`: the manifest's `scope`, `start_url`
and `id`, the worker at `/app/sw.js`, the offline page and every signed-in
page. Public pages (`/`, `/terms/`, `/privacy/`, `/help/`), sign-in
(`/signin/`), `/admin/`, `/oauth/` and `/mcp` sit outside it. The worker bypasses any
same-origin request outside the scope except static files, which it still
caches for the app's pages.

## Consequences

- Public pages are ordinary web pages: no worker, no outbox, no launch
  screen, and they extend `public_base.html` rather than `base.html`.
- Following a link out of scope inside the installed app opens it with the
  browser's own chrome (sign-in, the legal pages), which is the right cue.
- `start_url` (`/app/`) must answer 200 without redirecting, or the app
  can't open offline; Tally's phone app is mounted there.
- Moving the scope later strands installed apps on the old one; choose the
  path once.
