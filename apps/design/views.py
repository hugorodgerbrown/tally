"""The design page: every token and every component state, drawn by app.css.

It is for the people building the app, so only staff see it; anyone else
gets a 404, as if it weren't there.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

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
    return render(request, "design/index.html", {"families": families})
