"""The public pages: the front page, terms, privacy and help.

They sit outside the installed app's /app/ scope, so the service worker
never caches them and they never show inside the installed app.
"""

from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.library import timeline
from apps.library.models import Exercise, Workout, WorkoutItem
from apps.public.connector import mcp_url

# The workout the front page draws with the builder's own make-up panel
# (DESIGN.md, "The front page": the product, live, with demo data). Nothing
# is saved: the objects exist only to go through timeline.segments, the
# same sequence the phone plays. (exercise, one-sided, seconds)
DEMO_NAME = "Kettlebell 20"
DEMO_ITEMS = [
    ("Kettlebell swing", False, 40),
    ("Goblet squat", False, 40),
    ("Split squat", True, 40),
    ("Push-up", False, 30),
    ("Plank", False, 45),
]
DEMO_ROUNDS = 2
DEMO_REST = 20


def demo_workout() -> dict[str, Any]:
    """Return the front page's demo workout: its name, numbers and interval sequence."""
    workout = Workout(name=DEMO_NAME, rounds=DEMO_ROUNDS, rest_seconds=DEMO_REST)
    items = [
        WorkoutItem(exercise=Exercise(name=name, one_sided=one_sided), duration_seconds=seconds)
        for name, one_sided, seconds in DEMO_ITEMS
    ]
    segments = timeline.segments(workout, items)
    total = sum(seconds for _kind, seconds in segments)
    return {
        "name": workout.name,
        "exercises": len(items),
        "rounds": workout.rounds,
        "segments": segments,
        "total": total,
        "minutes": total // 60,
        "seconds": total % 60,
        "working": sum(seconds for kind, seconds in segments if kind == "work"),
    }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """The front page: the promise, the product, the connector and the way in."""
    return render(request, "public/home.html", {"demo": demo_workout(), "mcp_url": mcp_url()})


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    """The terms of service (placeholder)."""
    return render(request, "public/terms.html")


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    """The privacy notice (placeholder, but true of the template as shipped)."""
    return render(request, "public/privacy.html")


@require_GET
def help_page(request: HttpRequest) -> HttpResponse:
    """Help: signing in, passkeys, installing the app, offline (placeholder)."""
    return render(request, "public/help.html", {"mcp_url": mcp_url()})
