"""The phone app's page: one shell at /app/ that draws every screen in JavaScript.

The manifest's start_url. Its scripts, styles and the page itself are
cached by the service worker, and the workouts are kept in IndexedDB, so
it opens and runs a workout with no connection.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


@require_GET
@login_required
def app(request: HttpRequest) -> HttpResponse:
    """Return the activity-mode shell."""
    return render(request, "activity/app.html")
