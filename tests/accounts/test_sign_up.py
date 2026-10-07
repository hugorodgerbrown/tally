"""Tests for creating an account: /signup/, the sign-up email, and the welcome page."""

import re
from typing import Any
from urllib.parse import urlsplit

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from apps.library.models import Exercise
from tests.factories import PasskeyFactory, UserFactory

pytestmark = pytest.mark.django_db

SIGN_UP = reverse("accounts:sign_up")
CODE = reverse("accounts:sign_in_code")
WELCOME = reverse("accounts:welcome")


@pytest.fixture(autouse=True)
def _fresh_rate_limits() -> None:
    """Rate-limit counters live in the cache; start each test with none."""
    cache.clear()


def emailed() -> tuple[str, str]:
    """Return the path of the last email's link, and its code."""
    body = str(mail.outbox[-1].body)
    link = re.search(r"https?://\S+/signin/link/\S+/", body)
    code = re.search(r"^(\d{6})$", body, re.MULTILINE)
    assert link, body
    assert code, body
    return urlsplit(link.group()).path, code.group(1)


def test_sign_up_page_asks_for_an_email(client: Client) -> None:
    """The page has the email field and links to sign-in for existing accounts."""
    content = client.get(SIGN_UP).content.decode()
    assert "Create an account" in content
    assert 'type="email"' in content
    assert reverse("accounts:sign_in") in content


def test_signed_in_visitors_go_to_the_app(signed_in: Client) -> None:
    """Someone already signed in has an account: straight to the app."""
    assert signed_in.get(SIGN_UP)["Location"] == reverse("activity:app")


def test_sign_up_emails_a_link_and_code_worded_for_a_new_account(client: Client) -> None:
    """A new address gets the sign-up email, and the code page says Create account."""
    response = client.post(SIGN_UP, {"email": " New@Example.com "})
    assert response["Location"] == CODE
    message = mail.outbox[-1]
    assert message.to == ["new@example.com"]
    assert "sign-up code" in message.subject
    assert "Finish creating your" in str(message.body)
    assert "Create account" in client.get(CODE).content.decode()
    assert not get_user_model().objects.filter(username="new@example.com").exists()


def test_the_code_creates_the_account_and_suggests_a_passkey(client: Client) -> None:
    """Redeeming the code makes the account, with its starter library, then the welcome page."""
    client.post(SIGN_UP, {"email": "new@example.com"})
    _, code = emailed()
    response = client.post(CODE, {"code": code})
    assert response["Location"] == WELCOME
    user = get_user_model().objects.get(username="new@example.com")
    assert Exercise.objects.for_user(user).count() == 21
    page = client.get(WELCOME).content.decode()
    assert "Add a passkey" in page
    assert f'data-next="{reverse("activity:app")}"' in page
    assert reverse("accounts:passkey_register_options") in page


def test_the_link_also_lands_on_the_welcome_page(client: Client) -> None:
    """The emailed link, opened anywhere, does the same."""
    client.post(SIGN_UP, {"email": "new@example.com"})
    link, _ = emailed()
    assert Client().post(link)["Location"] == WELCOME


def test_sign_up_for_an_existing_account_sends_the_sign_in_email(client: Client) -> None:
    """The page looks the same, so it reveals nothing; the email just signs them in."""
    UserFactory.create(email="known@example.com")
    response = client.post(SIGN_UP, {"email": "known@example.com"})
    assert response["Location"] == CODE
    assert "sign-in code" in mail.outbox[-1].subject
    assert "Sign in" in client.get(CODE).content.decode()


def test_a_bad_email_is_refused(client: Client) -> None:
    """A malformed address re-shows the form with an error and sends nothing."""
    response = client.post(SIGN_UP, {"email": "not-an-email"})
    assert response.status_code == 400
    assert not mail.outbox


def test_an_address_too_long_for_a_username_is_refused(client: Client) -> None:
    """The address becomes the username (150 characters), so a longer one is refused up front."""
    email = "a" * 140 + "@example.com"
    response = client.post(SIGN_UP, {"email": email})
    assert response.status_code == 400
    assert not mail.outbox


def test_sign_up_shares_the_sign_in_rate_limit(client: Client) -> None:
    """Five emails an hour per address, whichever page asks."""
    for _ in range(5):
        client.post(reverse("accounts:sign_in"), {"email": "walker@example.com"})
    response = client.post(SIGN_UP, {"email": "walker@example.com"})
    assert response.status_code == 429
    assert len(mail.outbox) == 5


def test_welcome_skips_an_account_with_a_passkey(signed_in: Client, user: Any) -> None:
    """The suggestion is only for accounts without one."""
    PasskeyFactory.create(user=user)
    assert signed_in.get(WELCOME)["Location"] == reverse("activity:app")


def test_welcome_needs_sign_in(client: Client) -> None:
    """The welcome page is in the app: signed-out visitors are sent to sign in."""
    assert reverse("accounts:sign_in") in client.get(WELCOME)["Location"]
