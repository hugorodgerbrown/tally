"""The design page: every token and every component state, drawn by app.css.

It is for the people building the app, so only staff see it; anyone else
gets a 404, as if it weren't there. The same goes for its previews of the
error pages (apps/core/errors.py).
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from apps.core import errors
from apps.core.shortcuts import render
from apps.design import stylesheet

logger = logging.getLogger(__name__)

FAMILY_ORDER = ("colour", "type", "space", "radius", "shadow", "other")


@require_GET
@login_required
def design(request: HttpRequest) -> HttpResponse:
    """The design system, read from the stylesheet so it can't drift from it."""
    if not request.user.is_staff:
        raise Http404
    found = stylesheet.tokens(stylesheet.read())
    families = {
        family: [t for t in found.values() if t.family == family] for family in FAMILY_ORDER
    }
    context = {"families": families, "error_pages": errors.ERROR_PAGES}
    return render(request, "design/index.html", context)


@require_GET
@login_required
def error_preview(request: HttpRequest, kind: str) -> HttpResponse:
    """One error page exactly as it is sent, with its real status.

    With ``DEBUG`` on Django shows its technical pages instead of these, so
    this is how to see them. It goes through the same negotiation:
    ``Accept: application/json`` or ``HX-Request: true`` preview those shapes.
    """
    if not request.user.is_staff or kind not in errors.ERROR_PAGES:
        raise Http404
    return errors.error_response(request, kind)
