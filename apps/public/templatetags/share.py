"""``{% absolute_static %}``: a static file's full address, for the share tags.

Open Graph wants absolute URLs: a chat app fetching the card has no page to
resolve a relative one against (DESIGN.md, "The front page").
"""

from typing import Any

from django import template
from django.http import HttpRequest
from django.templatetags.static import static

register = template.Library()


@register.simple_tag(takes_context=True)
def absolute_static(context: dict[str, Any], path: str) -> str:
    """Return the absolute URL of the static file at ``path``."""
    request: HttpRequest = context["request"]
    return request.build_absolute_uri(static(path))
