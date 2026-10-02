from django import template

register = template.Library()


@register.filter
def mmss(seconds):
    """Format seconds as m:ss, the way the phone shows time."""
    seconds = int(round(seconds or 0))
    return f"{seconds // 60}:{seconds % 60:02d}"
