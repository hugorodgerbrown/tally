"""Tests for the share tags every public page carries (DESIGN.md, "The front page")."""

import re

import pytest
from django.contrib.staticfiles import finders
from django.test import Client, RequestFactory
from django.urls import reverse

from apps.public.templatetags.share import absolute_static

pytestmark = pytest.mark.django_db

PAGES = ["public:home", "public:terms", "public:privacy", "public:help", "accounts:sign_in"]


def meta(content: str, key: str) -> str:
    """The content of the one meta tag named (``property`` or ``name``) ``key``."""
    pattern = rf'<meta (?:property|name)="{re.escape(key)}" content="([^"]*)"'
    found = [match[1] for match in re.finditer(pattern, content)]
    assert len(found) == 1, f"{key}: {found}"
    return found[0]


@pytest.mark.parametrize("name", PAGES)
def test_every_public_page_unfurls(client: Client, name: str) -> None:
    """A title, a description and a large card at an absolute address."""
    content = client.get(reverse(name)).content.decode()
    assert meta(content, "og:title")
    assert meta(content, "og:description")
    image = meta(content, "og:image")
    assert image.startswith("http://testserver/")
    assert image.endswith(".png")
    assert (meta(content, "og:image:width"), meta(content, "og:image:height")) == ("1200", "630")
    assert meta(content, "og:image:alt")
    assert meta(content, "twitter:card") == "summary_large_image"


def test_the_front_page_shares_its_promise(client: Client) -> None:
    """The unfurl reads like the page: the promise and the lede."""
    content = client.get(reverse("public:home")).content.decode()
    h1 = re.search(r"<h1>(.*?)</h1>", content)
    assert h1
    assert meta(content, "og:title") == h1.group(1)


def test_the_share_card_exists() -> None:
    """bin/make-share-card drew it when the app was made."""
    assert finders.find("img/share-card.png")


def test_absolute_static() -> None:
    """A static file's address, with the scheme and host of the request."""
    request = RequestFactory().get("/", secure=True)
    assert absolute_static({"request": request}, "img/share-card.png") == (
        "https://testserver/static/img/share-card.png"
    )


def test_no_tag_repeats_the_address(client: Client) -> None:
    """A sign-in link's address is its token: no share tag may copy it."""
    content = client.get(reverse("accounts:sign_in_link", args=["secret-token"])).content.decode()
    assert 'property="og:url"' not in content
    assert "secret-token" not in content
