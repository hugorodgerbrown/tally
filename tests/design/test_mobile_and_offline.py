"""The mobile-first and offline rules in DESIGN.md (sections 10 and 11).

Every page fits a phone's screen, the app's frame says when it's offline,
and every script a page under /app/ loads is there offline.
"""

import re
from pathlib import Path

from django.conf import settings

from apps.design.conf import NEEDS_NETWORK
from apps.pwa import conf as pwa_conf

BASE = Path(settings.BASE_DIR)
TEMPLATES = BASE / "templates"


def test_every_page_fits_the_screen() -> None:
    """Both base templates carry the viewport meta."""
    head = (TEMPLATES / "includes" / "_head.html").read_text()
    assert 'name="viewport" content="width=device-width' in head
    for base in ("base.html", "public_base.html"):
        assert '{% include "includes/_head.html" %}' in (TEMPLATES / base).read_text()


def test_the_app_frame_shows_when_its_offline() -> None:
    """The app's frame has the offline banner."""
    assert "data-offline-banner" in (TEMPLATES / "base.html").read_text()


def find_template(name: str) -> Path | None:
    """A template by the name an include gives it, in templates/ or an app's templates/."""
    for folder in [TEMPLATES, *sorted((BASE / "apps").glob("*/templates"))]:
        if (folder / name).is_file():
            return folder / name
    return None


def app_templates() -> list[Path]:
    """The app's frame, every page that extends it, and every template they include."""
    found = [TEMPLATES / "base.html"]
    found += [
        path
        for path in sorted((BASE / "apps").glob("*/templates/**/*.html"))
        if re.search(r"{%\s*extends\s+[\"']base\.html[\"']", path.read_text())
    ]
    for path in found:  # grows as includes are found, so includes of includes count too
        for name in re.findall(r"{%\s*include\s+[\"']([^\"']+)[\"']", path.read_text()):
            include = find_template(name)
            if include and include not in found:
                found.append(include)
    return found


def loaded_static(path: Path) -> set[str]:
    """The scripts and stylesheets a template loads with {% static %}."""
    return set(re.findall(r"{%\s*static\s+[\"']([^\"']+\.(?:js|css))[\"']", path.read_text()))


def test_the_app_opens_offline() -> None:
    """Every script and stylesheet a page under /app/ loads is precached, or needs the network."""
    missing = sorted(
        f"{path.name}: {name}"
        for path in app_templates()
        for name in loaded_static(path)
        if name not in pwa_conf.PRECACHE_STATIC and name not in NEEDS_NETWORK
    )
    assert not missing, "precache these, or list them in NEEDS_NETWORK: " + "; ".join(missing)


def test_what_needs_the_network_is_still_loaded() -> None:
    """An entry in NEEDS_NETWORK for a file no app page loads is stale."""
    loaded = set().union(*(loaded_static(path) for path in app_templates()))
    stale = sorted(set(NEEDS_NETWORK) - loaded)
    assert not stale, stale
