"""Tests for the site's links (DESIGN.md, §8 and §9)."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.public import conf
from apps.public.templatetags.site_footer import footer_anchors, footer_links

pytestmark = pytest.mark.django_db


def test_public_pages_end_with_the_footer(client: Client) -> None:
    """A public page ends with the footer: its links and the copyright."""
    content = client.get(reverse("public:home")).content.decode()
    assert 'class="site-footer"' in content
    for _label, url in footer_links():
        assert f'href="{url}"' in content
    year = timezone.localdate().year
    assert f"© {year} {escape(conf.COPYRIGHT_HOLDER)}. All rights reserved." in content


def test_app_pages_have_no_footer(signed_in: Client) -> None:
    """The installed app is an app, not a website: no footer."""
    content = signed_in.get(reverse("accounts:account")).content.decode()
    assert 'class="site-footer"' not in content


def test_the_account_page_lists_the_links(signed_in: Client) -> None:
    """The app's links live on its account page instead."""
    content = signed_in.get(reverse("accounts:account")).content.decode()
    assert 'class="site-links"' in content
    for _label, url in footer_links():
        assert f'href="{url}"' in content
    assert f"{escape(conf.COPYRIGHT_HOLDER)}. All rights reserved." in content


def test_the_footer_links_to_help_terms_and_privacy() -> None:
    """Without terms and a privacy notice, a site isn't legit."""
    names = {target.partition("#")[0] for _label, target in conf.LINKS}
    assert {"public:help", "public:terms", "public:privacy"} <= names


def test_a_link_can_name_part_of_a_page(monkeypatch: Any) -> None:
    """A "#fragment" after the URL name is kept on the link."""
    monkeypatch.setattr(conf, "LINKS", [("Use with Claude", "public:home#mcp")])
    assert footer_links() == [("Use with Claude", reverse("public:home") + "#mcp")]


@pytest.mark.parametrize("url_name", ["public:help", "accounts:account"])
def test_the_top_left_mark_goes_home(signed_in: Client, url_name: str) -> None:
    """On public and app pages alike, the header's name links to the front page."""
    content = signed_in.get(reverse(url_name)).content.decode()
    header = content[content.index("<header") : content.index("</header>")]
    assert f'href="{reverse("public:home")}"' in header.split("</a>")[0]


def test_link_labels_are_escaped(monkeypatch: Any) -> None:
    """A label is text, never markup."""
    monkeypatch.setattr(conf, "LINKS", [("<b>Help</b>", "public:help")])
    assert footer_anchors() == [f'<a href="{reverse("public:help")}">&lt;b&gt;Help&lt;/b&gt;</a>']
