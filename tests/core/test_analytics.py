"""Tests for apps.core.analytics: fivebar's tag, its CSP sources and counted paths."""

from typing import Any

import pytest
from django.test import Client, RequestFactory
from django.urls import resolve, reverse

from apps.core.analytics import (
    ORIGIN,
    SCRIPT,
    SIGNED_UP,
    analytics,
    counted_path,
    csp_sources,
    mark,
)
from apps.public.pages import page_as_markdown

DOMAIN = "example.ultraniche.ai"


def test_csp_sources_are_empty_while_off() -> None:
    """No FIVEBAR_DOMAIN, no extra origin in the policy."""
    assert csp_sources("") == []
    assert csp_sources(DOMAIN) == [ORIGIN]


def test_the_default_policy_leaves_fivebar_out(client: Client, db: None) -> None:
    """The shipped settings (FIVEBAR_DOMAIN unset) allow no other origin."""
    csp = client.get(reverse("public:home"))["Content-Security-Policy"]
    assert ORIGIN not in csp


@pytest.mark.django_db
def test_no_tag_while_off(client: Client) -> None:
    """Pages carry no fivebar tag until FIVEBAR_DOMAIN is set."""
    html = client.get(reverse("public:home")).content.decode()
    assert SCRIPT not in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name", ["public:home", "public:privacy", "activity:app", "planner:workouts"]
)
def test_every_page_has_the_tag_once(signed_in: Client, settings: Any, url_name: str) -> None:
    """Public and app pages alike: one async tag, with the site's domain."""
    settings.FIVEBAR_DOMAIN = DOMAIN
    html = signed_in.get(reverse(url_name)).content.decode()
    tag = f'<script async data-domain="{DOMAIN}" src="{SCRIPT}"></script>'
    assert html.count(SCRIPT) == 1
    assert tag in html
    assert "js/analytics.js" in html


@pytest.mark.django_db
def test_a_sign_in_link_is_counted_without_its_token(client: Client, settings: Any) -> None:
    """The token in an emailed link never reaches fivebar."""
    settings.FIVEBAR_DOMAIN = DOMAIN
    html = client.get(reverse("accounts:sign_in_link", args=["secret-token"])).content.decode()
    assert 'data-path="/signin/link/:token/"' in html
    assert "secret-token" not in html


def test_counted_path() -> None:
    """A route's values are named; a route without values needs no data-path."""
    factory = RequestFactory()
    request = factory.get("/signin/link/abc/")
    request.resolver_match = resolve("/signin/link/abc/")
    assert counted_path(request) == "/signin/link/:token/"
    request = factory.get("/signin/")
    request.resolver_match = resolve("/signin/")
    assert counted_path(request) == ""
    assert counted_path(factory.get("/nowhere/")) == ""


def test_context_has_no_path_while_off(settings: Any) -> None:
    """Off, the context names nothing, so the tag isn't drawn."""
    settings.FIVEBAR_DOMAIN = ""
    request = RequestFactory().get("/signin/link/abc/")
    request.resolver_match = resolve("/signin/link/abc/")
    assert analytics(request)["analytics"] == {"domain": "", "script": SCRIPT, "path": ""}


def test_privacy_notice_names_fivebar_only_while_on(settings: Any) -> None:
    """The notice (and its Markdown for the MCP tools) says what is counted, once it is."""
    settings.FIVEBAR_DOMAIN = ""
    assert "fivebar" not in page_as_markdown("privacy")["markdown"]
    settings.FIVEBAR_DOMAIN = DOMAIN
    markdown = page_as_markdown("privacy")["markdown"]
    assert "## Visitor counts" in markdown
    assert "fivebar" in markdown


def test_mark(settings: Any) -> None:
    """An event's fragment is added only while on, and never over another fragment."""
    settings.FIVEBAR_DOMAIN = ""
    assert mark("/app/", SIGNED_UP) == "/app/"
    settings.FIVEBAR_DOMAIN = DOMAIN
    assert mark("/app/", SIGNED_UP) == "/app/#signed-up"
    assert mark("/app/#top", SIGNED_UP) == "/app/#top"
