"""The public pages of an app that serves /mcp: the address, the steps, the footer link."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from apps.public.pages import page_as_markdown

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("name", ["public:home", "public:help"])
def test_the_pages_show_the_real_address(client: Client, settings: Any, name: str) -> None:
    """The front page and help both give the /mcp address on the site's own URL."""
    settings.SITE_URL = "https://example.test"
    content = client.get(reverse(name)).content.decode()
    assert 'data-copy="https://example.test/mcp"' in content


def test_the_footer_links_to_the_steps(client: Client) -> None:
    """The footer's "Use with Claude" goes to the help page's steps."""
    content = client.get(reverse("public:terms")).content.decode()
    assert f'href="{reverse("public:help")}#use-with-ai">Use with Claude</a>' in content


def test_the_help_tool_gives_the_steps_and_the_address(settings: Any) -> None:
    """An assistant asked how to connect reads the same steps, address included."""
    settings.SITE_URL = "https://example.test"
    markdown = page_as_markdown("help")["markdown"]
    assert "## Use it from Claude or ChatGPT" in markdown
    assert "https://example.test/mcp\n" in markdown
    assert "/mcp Copy" not in markdown
