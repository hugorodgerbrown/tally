"""Performance budgets that a unit test can hold: shell size and page weight.

Lighthouse (.github/workflows/lighthouse.yml) measures the rest in a browser.
"""

from django.contrib.staticfiles import finders

from apps.pwa import conf

# What the service worker downloads on install. The first launch offline
# depends on all of it arriving, so it stays small. Tally raised the
# template's 150 KB to 160 KB: its phone app (activity_app.js, engine.js,
# activity.css, about 56 KB) is the offline shell itself, not an extra.
# 165 KB since RAS-45: the template's app.css grew by its shared front-page
# and design-system components, which every Titan app's shell carries.
# 170 KB since RAS-86: the workout screen shows each exercise's notes,
# which took the phone app about 1.6 KB past 165 KB.
PRECACHE_BUDGET_BYTES = 170_000


def test_precached_shell_fits_the_budget() -> None:
    """The precached static files, uncompressed, fit the byte budget."""
    sizes = {}
    for path in conf.PRECACHE_STATIC:
        found = finders.find(path)
        assert found, f"{path} is precached but doesn't exist"
        with open(str(found), "rb") as f:
            sizes[path] = len(f.read())
    total = sum(sizes.values())
    assert total <= PRECACHE_BUDGET_BYTES, f"{total} bytes: {sizes}"


def test_worker_scripts_exist() -> None:
    """Every script /app/sw.js imports is a real static file."""
    for path in conf.WORKER_SCRIPTS:
        assert finders.find(path), path
