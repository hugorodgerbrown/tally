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


def test_home_invites_sign_in(client: Client) -> None:
    """Signed out, the homepage's call to action is signing in."""
    content = client.get(reverse("public:home")).content.decode()
    assert reverse("accounts:sign_in") in content


def test_home_opens_the_app_when_signed_in(signed_in: Client) -> None:
    """Signed in, it offers the app instead."""
    content = signed_in.get(reverse("public:home")).content.decode()
    assert reverse("notes:list") in content
    assert "Open the app" in content
