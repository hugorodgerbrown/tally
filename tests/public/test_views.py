"""Tests for apps.public.views: the homepage, terms, privacy and help."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


PAGES = ["public:home", "public:terms", "public:privacy", "public:help"]


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_need_no_sign_in(client: Client, name: str) -> None:
    """Anyone can read them, and they link to each other."""
    response = client.get(reverse(name))
    assert response.status_code == 200
    content = response.content.decode()
    assert reverse("public:terms") in content
    assert reverse("public:privacy") in content
    assert reverse("public:help") in content


@pytest.mark.parametrize("name", PAGES)
def test_public_pages_are_outside_the_app(client: Client, name: str) -> None:
    """No manifest, worker or outbox: the installed app is /app/ alone."""
    content = client.get(reverse(name)).content.decode()
    assert "manifest" not in content
    assert "pwa.js" not in content


def test_home_invites_sign_up(client: Client) -> None:
    """Signed out, the homepage offers creating an account; Sign in is in the header."""
    content = client.get(reverse("public:home")).content.decode()
    sign_up = f'class="home-button home-button--light" href="{reverse("accounts:sign_up")}"'
    assert content.count(sign_up) == 1
    assert f'href="{reverse("accounts:sign_in")}"' in content
    assert "No password." in content


def test_home_gives_the_mcp_address_and_example_questions(client: Client) -> None:
    """The Claude section names the connector address on this host, with a Copy button."""
    content = client.get(reverse("public:home"), HTTP_HOST="localhost").content.decode()
    assert '<code id="mcp-url">http://localhost/mcp</code>' in content
    assert 'data-copy="mcp-url"' in content
    assert content.count("<li>“") == 4


def test_home_shows_the_product(client: Client) -> None:
    """Both screenshots are on the page, sized, with alt text."""
    content = client.get(reverse("public:home")).content.decode()
    for name in ("home-builder.webp", "home-timer.webp"):
        tag = content[content.index(name) - 60 : content.index(name) + 200]
        assert 'width="' in tag
        assert 'alt="The ' in tag


def test_home_opens_the_app_when_signed_in(signed_in: Client) -> None:
    """Signed in, it offers the app instead."""
    content = signed_in.get(reverse("public:home")).content.decode()
    assert reverse("activity:app") in content
    assert "Start a workout" in content
