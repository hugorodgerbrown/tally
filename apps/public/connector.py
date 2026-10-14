"""The MCP connector's address, for the pages that tell people how to add it.

The front page shows it with a copy button and the help page's "Use it from
Claude or ChatGPT" section gives the steps around it (DESIGN.md, "The front
page"). An app generated without MCP has no ``mcp`` URL, so both leave the
section out.
"""

from urllib.parse import urljoin

from django.conf import settings
from django.urls import NoReverseMatch, reverse


def mcp_url() -> str:
    """Return the absolute ``/mcp`` address, or ``""`` when the app serves none.

    Built on ``SITE_URL`` rather than the request's host: the tokens
    mcp-auth issues are bound to the canonical address.
    """
    try:
        return urljoin(settings.SITE_URL, reverse("mcp"))
    except NoReverseMatch:
        return ""
