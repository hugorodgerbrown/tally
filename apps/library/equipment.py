"""Equipment icons, one per ``Equipment`` choice.

The server is the single source: the phone and the builder get these with the
library, the way they get type colours, and templates render them with the
``equipment_icon`` tag. Drawn on a 24 px grid in ``currentColor``.
"""

from typing import Any

from django.utils.html import format_html
from django.utils.safestring import SafeString, mark_safe

from apps.library.models import Equipment

SHAPES = {
    Equipment.KETTLEBELL: (
        '<path d="M7.3 11.2 6.6 7a3.3 3.3 0 0 1 3.3-3.6h4.2A3.3 3.3 0 0 1 17.4 7l-.7 4.2"'
        ' fill="none" stroke="currentColor" stroke-width="2.2" stroke-linejoin="round"/>'
        '<path d="M12 8.6c4.1 0 7.2 3 7.2 6.8 0 1.9-.7 3.5-1.9 4.9H6.7c-1.2-1.4-1.9-3-1.9-4.9'
        ' 0-3.8 3.1-6.8 7.2-6.8z" fill="currentColor"/>'
    ),
    Equipment.DUMBBELL: (
        '<g fill="currentColor"><rect x="1.5" y="9" width="2.6" height="6" rx="1"/>'
        '<rect x="4.6" y="6" width="3.6" height="12" rx="1.2"/>'
        '<rect x="8" y="10.8" width="8" height="2.4"/>'
        '<rect x="15.8" y="6" width="3.6" height="12" rx="1.2"/>'
        '<rect x="19.9" y="9" width="2.6" height="6" rx="1"/></g>'
    ),
}


def icon_svg(slug: str) -> SafeString:
    """The icon as an inline SVG, labelled with the equipment name; empty for none."""
    if slug not in SHAPES:
        return SafeString("")
    label = Equipment(slug).label
    return format_html(
        '<svg class="eq" viewBox="0 0 24 24" role="img" aria-label="{}"><title>{}</title>{}</svg>',
        label,
        label,
        mark_safe(SHAPES[Equipment(slug)]),  # noqa: S308 - constant markup above
    )


def equipment_json() -> list[dict[str, Any]]:
    """Every choice with its icon, sent alongside the library."""
    return [{"slug": e.value, "name": e.label, "svg": str(icon_svg(e.value))} for e in Equipment]
