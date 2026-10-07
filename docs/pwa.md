# The PWA: install, launch screen, offline pages and queued writes

```
 page ──write──▶ Outbox (IndexedDB) ──drain──▶ POST + Idempotency-Key + CSRF ──▶ IdempotencyMiddleware ──▶ view
   │                ▲  online / load / visible / Background Sync                   same key = stored reply
   └──GET──▶ service worker ──▶ Cache Storage (static: cache-first, pages: network-first) ──▶ /app/offline/
```

## Pieces

| File | Job |
| --- | --- |
| `apps/pwa/views.py` | `/app/manifest.webmanifest`, `/app/sw.js` (config + `importScripts`), `/app/offline/` |
| `apps/pwa/conf.py` | Name, colours, `SCOPE`, the precache list, paths never cached |
| `static/js/sw_worker.js` | The worker: install, activate, fetch, sync, message |
| `static/js/sw_core.js` | Its decisions as pure functions (unit-tested) |
| `static/js/idb.js` | The IndexedDB database: `outbox` and `meta` stores |
| `static/js/outbox_core.js` | The outbox rules as pure functions (unit-tested) |
| `static/js/outbox.js` | `Outbox.enqueue / drain / list / retry / discard` |
| `static/js/pwa.js` | Per page: record the user and CSRF token, register the worker, drain on the right events, offline banner |
| `static/js/launch_gate.js`, `launch_shell.js` | The launch screen |
| `apps/core/idempotency.py` | Server half of the outbox |

## Writing data that must survive being offline

1. The endpoint is a POST (or PUT/PATCH/DELETE) that accepts JSON and
   answers JSON, decorated `@login_required_json` (a 401, never a redirect
   to the sign-in page, which fetch would report as success).
2. Validate client-supplied times (`written_at` in `NoteForm`): the write
   may arrive days after the user made it.
3. In the page: `Outbox.enqueue({url, body: JSON.stringify(data), meta})`.
   `meta` is whatever you need to draw the pending item.
4. Draw pending items from `Outbox.list()` on `outbox:changed`; refresh the
   server-rendered part with htmx on `outbox:sent` (see `note_list.html`).
5. Keep a no-JavaScript path: the form posts normally.

You never mint keys or handle retries yourself; the outbox does.

### What happens to a write

| Server answer | Outbox |
| --- | --- |
| 2xx | Deleted; `outbox:sent` fires |
| 5xx, 408, 425, 429, 409 + `Retry-After` | Retried with backoff (2 s doubling to 5 min), up to 10 answers |
| 401, a redirect, a CSRF 403 (`X-CSRF-Failure`) | Kept unchanged; the drain pauses until the next page load |
| Any other 4xx | Failed: shown to the user with Retry and Discard |
| No answer (offline) | Kept unchanged; doesn't count as an attempt |

The server only stores replies the outbox treats as final. A retried or
paused answer (5xx, 408, 425, 429, 401, a CSRF 403) releases the
`Idempotency-Key`, so the next attempt runs the view rather than replaying
"signed out" for 24 hours.

A row is only ever sent as the user who wrote it. Signing in as someone
else leaves the first user's writes on the device, unsent, until they sign
back in.

## Caching

- **Static files**: hashed names in production, so cache-first is safe;
  network-first under `DEBUG`.
- **Pages and htmx fragments**: network-first; after 4 s a cached copy wins
  (a dead connection usually hangs rather than failing). With no cached
  copy, a navigation gets `/app/offline/`.
- **Never cached**: anything outside `SCOPE` (`/app/`) except static
  files, so public pages, sign-in, admin, OAuth and MCP; anything in
  `NEVER_CACHE`; anything non-GET; other origins; `no-store` responses;
  redirects.
- **Versions**: cache names carry a hash of the worker's config (and of the
  files themselves under `DEBUG`). A deploy that changes any precached
  file installs a new worker, which takes over at once and deletes the old
  caches. Pages cached by the old version are dropped too; they are cached
  again as they are visited.
- **Changing user** clears cached pages (`pwa.js`), because they show the
  previous user's data. Signing out clears them before the form posts.

## Scope

The installed app is `/app/` and nothing else: the manifest's `scope`,
`start_url` and `id`, and the worker at `/app/sw.js`, which controls only
paths under its own. Public pages extend `public_base.html` and load no
worker or outbox. Why: [decisions/the-installed-app-is-scoped-to-app.md](decisions/the-installed-app-is-scoped-to-app.md).
A new signed-in page belongs under `/app/` and extends `base.html`; a new
public page sits outside it and extends `public_base.html`.

## Launch screen

Shown only on a cold start of the installed app (standalone display mode,
first page of the session), decided before first paint by the blocking
`launch_gate.js`. It leaves on the first of: `app:ready` on `document`
(dispatch it from a page with slow set-up), window `load`, or 5 s. A CSS
keyframe hides it at 10 s even if no script runs.

## Known limits

- Background Sync exists only in Chromium. Elsewhere the outbox drains on
  page load, on `online` and when the app returns to the foreground.
- iOS shows its own launch image before the page; `apple-touch-startup-image`
  is not generated.
- Pages cached by one deploy are not re-fetched by the next until visited.
