"""Tests for the environment checks in config/settings.py."""

import runpy
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

SETTINGS = Path(__file__).resolve().parent.parent / "config" / "settings.py"


def test_render_without_database_url_refuses_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Render, a missing DATABASE_URL is an error, not a fresh SQLite file."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DATABASE_URL", "")
    with pytest.raises(ImproperlyConfigured, match="DATABASE_URL is not set"):
        runpy.run_path(str(SETTINGS))


def test_render_with_database_url_uses_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """On Render, DATABASE_URL is used as given."""
    monkeypatch.setenv("RENDER", "true")
    monkeypatch.setenv("DATABASE_URL", "postgres://tally:secret@db.internal:5432/tally")
    databases = runpy.run_path(str(SETTINGS))["DATABASES"]
    assert databases["default"]["HOST"] == "db.internal"
    assert databases["default"]["NAME"] == "tally"


def test_local_without_database_url_uses_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    """Off Render, no DATABASE_URL still means the local SQLite file."""
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("DATABASE_URL", "")
    databases = runpy.run_path(str(SETTINGS))["DATABASES"]
    assert databases["default"]["ENGINE"] == "django.db.backends.sqlite3"
