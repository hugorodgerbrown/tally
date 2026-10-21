"""Tests for apps/core/private_pages.py: signed-in pages are never cached."""

from __future__ import annotations

from typing import Any

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponse
from django.test import RequestFactory

from apps.core.private_pages import PrivatePagesMiddleware
from apps.pwa import conf
from tests.factories import UserFactory


def _respond(user: Any, path: str = "/somewhere/", cache_control: str = "") -> HttpResponse:
    """Run a GET for ``path`` through the middleware as ``user``."""

    def view(request: HttpRequest) -> HttpResponse:
        response = HttpResponse("page")
        if cache_control:
            response["Cache-Control"] = cache_control
        return response

    request = RequestFactory().get(path)
    request.user = user
    return PrivatePagesMiddleware(view)(request)


def test_a_signed_in_page_is_not_stored(db: None) -> None:
    """A signed-in page outside the app (the consent page, say) gets no-store."""
    response = _respond(UserFactory(), "/oauth/authorize/")
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert not response.has_header("Offline-Copy")


def test_the_apps_offline_pages_are_not_stored_but_may_be_kept_offline(db: None) -> None:
    """The browser mustn't store an app page; the service worker may keep its own copy."""
    response = _respond(UserFactory(), f"{conf.SCOPE}account/")
    assert "no-store" in response["Cache-Control"]
    assert response["Offline-Copy"] == "allowed"


def test_a_page_the_worker_never_caches_is_not_stored(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A NEVER_CACHE path inside the app gets no-store like any other signed-in page."""
    monkeypatch.setattr(conf, "NEVER_CACHE", [f"{conf.SCOPE}secret/"])
    response = _respond(UserFactory(), f"{conf.SCOPE}secret/")
    assert "no-store" in response["Cache-Control"]
    assert not response.has_header("Offline-Copy")


def test_a_view_that_chose_its_caching_keeps_it(db: None) -> None:
    """A public page stays public for a signed-in user."""
    response = _respond(UserFactory(), cache_control="public, max-age=300")
    assert response["Cache-Control"] == "public, max-age=300"


def test_a_signed_out_page_is_left_alone() -> None:
    """Visitors' pages keep the browser's default caching."""
    assert not _respond(AnonymousUser()).has_header("Cache-Control")


class _UnreadableUser:
    """A user whose session can't be loaded, as in a database outage."""

    @property
    def is_authenticated(self) -> bool:
        """Fail the way a session lookup does when the database is down."""
        raise AssertionError("request.user was read")


def test_a_response_with_a_cache_policy_never_reads_the_user() -> None:
    """/livez (never_cache) must answer without loading the session."""
    response = _respond(_UnreadableUser(), cache_control="no-cache")
    assert response["Cache-Control"] == "no-cache"
