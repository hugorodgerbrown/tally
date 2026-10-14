"""The design page: staff only, and drawn from the stylesheet's own tokens."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from apps.design import stylesheet
from tests.factories import UserFactory

URL = reverse("design:index")


@pytest.fixture
def staff(client: Client, db: None) -> Client:
    """The test client, signed in as staff."""
    client.force_login(UserFactory.create(is_staff=True))
    return client


@pytest.mark.django_db
def test_signed_out_is_sent_to_sign_in(client: Client) -> None:
    """Signed-out visitors go to sign in, like every page under /app/."""
    response = client.get(URL)
    assert response.status_code == 302


def test_people_who_arent_staff_get_a_404(signed_in: Client) -> None:
    """To anyone else the page isn't there."""
    assert signed_in.get(URL).status_code == 404


def test_staff_see_every_token(staff: Client) -> None:
    """Every token but the layout ones has a sample on the page."""
    response = staff.get(URL)
    assert response.status_code == 200
    page = response.content.decode()
    for token in stylesheet.tokens(stylesheet.read()).values():
        assert f'data-token-value="{token.name}"' in page


def test_the_account_page_links_staff_to_it(staff: Client) -> None:
    """Staff find the page from their account page."""
    assert URL in staff.get(reverse("accounts:account")).content.decode()


def test_the_account_page_hides_it_from_everyone_else(signed_in: Client, user: Any) -> None:
    """Nobody else sees the link."""
    assert URL not in signed_in.get(reverse("accounts:account")).content.decode()
