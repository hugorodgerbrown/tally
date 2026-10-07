# Security

What is on by default, and what checks it.

| Control | Where | Checked by |
| --- | --- | --- |
| HTTPS redirect, HSTS, secure cookies (when `DJANGO_DEBUG=0`) | `config/settings.py` | `tox -e checks` (`check --deploy --fail-level WARNING`) |
| CSP: same-origin only, no inline script or style, no eval | `SECURE_CSP` | `tests/test_security.py` |
| Clickjacking, sniffing, referrer, COOP headers | settings + middleware | `tests/test_security.py` |
| CSRF on every form and outbox write (token read at send time) | Django + `outbox.js` | `tests/core/test_views.py` |
| No passwords: sign-in by single-use emailed link or code, or a passkey | `apps/accounts/` | `tests/accounts/` |
| Sign-in links and codes stored only as hashes; the code works only in the asking browser, five tries | `apps/accounts/sign_in.py` | `tests/accounts/test_sign_in.py` |
| Rate limits on sign-in emails, codes and passkey challenges | `apps/core/ratelimit.py` | `tests/accounts/test_views.py`, `test_passkeys.py` |
| Passkeys require user verification; challenges are single-use | `apps/accounts/passkeys.py` | `tests/accounts/test_passkeys.py`, `tests/e2e/test_passkey.py` |
| Post-sign-in redirects stay on this site | `apps/core/redirects.py` | `tests/core/test_redirects.py` |
| Signing out drops cached pages on the device | `pwa.js` + `Clear-Site-Data` | `tests/accounts/test_views.py` |
| Each keyed write runs at most once, per user, per body | `apps/core/idempotency.py` | `tests/core/test_idempotency.py` |
| Signed-out writes get 401, never a redirect | `login_required_json` | `tests/notes/test_views.py` |
| Fragments refuse non-htmx requests | `require_htmx` | `tests/core/test_decorators.py` |
| Python security lint (bandit rules) | ruff `S` | `tox -e lint` |
| Static analysis: Django, Python, JS, security-audit packs | semgrep | `tox -e sast` (CI and weekly) |
| Known CVEs in runtime Python deps and npm packages | pip-audit, npm audit | `tox -e audit` (CI and weekly) |
| Secrets in commits | gitleaks | pre-commit and CI |
| Dependency updates | Dependabot (uv, npm, actions) | weekly PRs |
| MCP: OAuth 2.1, PKCE, audience-bound tokens, staff-only by default | `mcp-auth` | `tests/mcp/test_mcp.py` (the shared contract) |
| MCP App views: self-contained, no network, data drawn as text only | `apps/mcp/resources.py`, `apps/mcp/ui/` | `tests/mcp/test_mcp.py`, `tests/js/mcp/` |

## Invariants

1. No `mark_safe()` or `|safe` on anything that came from outside the code.
2. No secrets in source: everything through `python-decouple`; `.env` is
   gitignored.
3. No inline script, style or event handler in a template.
4. Every fragment view is `@require_htmx`; every outbox endpoint is
   `@login_required_json`.
5. A sign-in secret (link token, code) is never stored or logged as given.
6. Widening who may connect an MCP client (`apps/mcp/policy.py`) is a
   product decision, made in a PR that says so.
