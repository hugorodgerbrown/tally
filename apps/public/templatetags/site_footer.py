"""``{% site_footer %}`` and ``{% site_links %}``: the site's links (apps/public/conf.py).

The website ends with the footer; the app has none, and shows the same
links on its account page (DESIGN.md).
"""

import logging
from typing import Any

from django import template
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from apps.public import conf

logger = logging.getLogger(__name__)

register = template.Library()


def footer_links() -> list[tuple[str, str]]:
    """Return the footer's links as (label, URL), fragments kept."""
    links = []
    for label, target in conf.LINKS:
        name, _, fragment = target.partition("#")
        links.append((label, reverse(name) + (f"#{fragment}" if fragment else "")))
    return links


def footer_anchors() -> list[SafeString]:
    """Return the footer's links as escaped ``<a>`` elements.

    Built here rather than with a template variable in ``href``, which
    semgrep's var-in-href rule blocks in apps that run ``tox -e sast``.
    """
    return [format_html('<a href="{}">{}</a>', url, label) for label, url in footer_links()]


def _context() -> dict[str, Any]:
    """Return what both the footer and the account page's links draw."""
    return {
        "anchors": footer_anchors(),
        "holder": conf.COPYRIGHT_HOLDER,
        "year": timezone.localdate().year,
    }


@register.inclusion_tag("includes/_footer.html")
def site_footer() -> dict[str, Any]:
    """Draw the website's footer: the links and this year's copyright."""
    return _context()


@register.inclusion_tag("includes/_site_links.html")
def site_links() -> dict[str, Any]:
    """Draw the same links as a list, for the app's account page."""
    return _context()
