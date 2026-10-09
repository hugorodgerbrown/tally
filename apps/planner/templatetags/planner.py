"""Template filters and tags for the planner: time formats and equipment icons."""

from django import template
from django.utils.safestring import SafeString

from apps.library.equipment import icon_svg

register = template.Library()


@register.filter
def mmss(seconds: float | None) -> str:
    """Format seconds as m:ss, the way the phone shows time."""
    seconds = round(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


@register.filter
def duration(seconds: float | None) -> str:
    """Format a length of time as 45 s, 7 min 50 s or 1 h 5 min (matches engine.js)."""
    s = max(0, round(seconds or 0))
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return f"{s // 60} min" + (f" {s % 60} s" if s % 60 else "")
    m = round((s % 3600) / 60)
    return f"{s // 3600} h" + (f" {m} min" if m else "")


@register.simple_tag
def equipment_icon(slug: str) -> SafeString:
    """The equipment's icon as inline SVG; nothing for bodyweight."""
    return icon_svg(slug)
