# Performance

Budgets, and what holds each one.

| Budget | Value | Held by |
| --- | --- | --- |
| Precached shell (what the worker downloads on install) | 150 KB uncompressed | `tests/test_performance.py` |
| Page weight | 250 KB | Lighthouse `total-byte-weight` |
| Lighthouse performance (desktop) | ≥ 0.9 | `.github/workflows/lighthouse.yml` |
| Lighthouse accessibility, best practices | ≥ 0.95 | same |
| Queries per list page | flat in the number of rows | `django_assert_max_num_queries` in view tests |

## Defaults that keep it fast

- No build step and no framework: htmx (about 16 KB gzipped) plus a few small
  files, all `defer`, except the tiny blocking launch gate.
- WhiteNoise serves hashed, Brotli/gzip-compressed static files with
  far-future cache headers; the service worker then serves them from
  Cache Storage without touching the network.
- Pages are network-first with a 4 s cut-over to the cached copy.
- `conn_max_age=600` with health checks on Postgres.

Lighthouse runs against gunicorn with `DJANGO_DEBUG=0`, the sign-in and
offline pages. Add a page to `lighthouserc.json` when it is public.
