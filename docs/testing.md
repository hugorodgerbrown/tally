# Testing

Every check runs through tox, locally and in CI, one CI job per env:

```bash
uv run tox                 # fmt, lint, types, checks, test, js, audit
uv run tox -e e2e          # browser journeys (needs Chromium: uv run playwright install chromium)
uv run tox -e sast         # semgrep (downloads rule packs)
uv run pytest tests/notes  # a targeted run while iterating
```

## Which layer does a test belong in?

Work top-down and stop at the first layer that can hold the assertion. A
test in the wrong layer is a defect, whatever it asserts.

| Layer | Where | For |
| --- | --- | --- |
| **pytest** | `tests/` | Anything the Django test client can see: status codes, redirects, rendered HTML, htmx fragments, JSON, querysets, commands, headers. **A 401 needs no browser.** |
| **Vitest** | `tests/js/` | Anything a `static/js` file does that jsdom can observe: the outbox rules and its IndexedDB use (fake-indexeddb), the service worker's routing rules, the launch screen's timers. The default home for client-side behaviour. |
| **Playwright** | `tests/e2e/` | Only what needs a real browser running real JavaScript against a live server: the service worker, Cache Storage, going offline, multi-script journeys. |

The browser suite is small on purpose and `tests/test_e2e_budget.py`
enforces it: at most 12 journeys, each under 40 lines, each module naming
its scenario below. Raising the cap is a deliberate change with a reason
in the PR; the usual answer is that the assertion belongs in `tests/js`.

### Journeys

- **offline write**: sign in, go offline, reload, add a note, see it
  pending, come back online, see it saved (`test_offline_write.py`).
- **offline fallback**: a page never visited shows the offline page
  (`test_offline_page.py`).
- **passkey**: add a passkey on the account page, sign out, sign back in
  with it, against Chromium's virtual authenticator (`test_passkey.py`).

Every journey signs in through the real email flow (`tests/e2e/conftest.py`
reads the link from `mailoutbox`).

## Rules

- Tests mirror the source tree: `apps/notes/views.py` is tested in
  `tests/notes/test_views.py`.
- Coverage floor is 90% (`pyproject.toml`); new code comes with tests.
- Factories live in `tests/factories.py`, one per model, always called as
  `Factory.create()` so mypy sees the model type.
- Every datetime has a timezone (ruff's `DTZ` rules enforce it).
- Query counts are asserted on list pages with
  `django_assert_max_num_queries`, so an N+1 fails a test, not production.
- Templates may not contain inline `<script>`, `style=` or `on*=`
  attributes (`tests/test_security.py`); the CSP would block them.
