"""Tests for the phone app's page at /app/ and the retired addresses."""

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_app_needs_sign_in(client: Client) -> None:
    """Signed out, /app/ sends you to sign in and back."""
    response = client.get(reverse("activity:app"))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:sign_in"))


def test_app_shell_carries_its_addresses(signed_in: Client) -> None:
    """The page hands the scripts their URLs, rather than the scripts hard-coding them."""
    content = signed_in.get(reverse("activity:app")).content.decode()
    for name in ("activity:api_workouts", "activity:api_sessions", "planner:workouts"):
        assert reverse(name) in content
    assert "js/activity_store.js" in content
    assert "js/activity_app.js" in content


@pytest.mark.parametrize("path", ["/sw.js", "/activity/sw.js"])
def test_old_service_workers_retire_themselves(client: Client, path: str) -> None:
    """Both old workers update to one that clears the old caches and unregisters."""
    response = client.get(path)
    assert response["Content-Type"] == "text/javascript"
    assert b"registration.unregister()" in response.content
    assert "no-cache" in response["Cache-Control"] or "max-age=0" in response["Cache-Control"]


@pytest.mark.parametrize(
    ("old", "new", "permanent"),
    [
        ("/activity/", "/app/", True),
        ("/activity/login/", "/signin/", False),
        ("/login/", "/signin/", False),
        ("/workouts/", "/app/workouts/", True),
        ("/exercises/new/?x=1", "/app/exercises/new/?x=1", True),
    ],
)
def test_old_addresses_redirect(client: Client, old: str, new: str, permanent: bool) -> None:
    """Bookmarks and the installed app's old start page still land somewhere."""
    response = client.get(old)
    assert response["Location"] == new
    assert response.status_code == (301 if permanent else 302)
