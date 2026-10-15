"""The public pages: the front page, terms, privacy and help.

They sit outside the installed app's /app/ scope, so the service worker
never caches them and they never show inside the installed app.
"""

from collections import defaultdict
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.library import starter
from apps.library.models import ExerciseType
from apps.public.connector import mcp_url

# The workout behind the front page's report: the phone's own finish screen
# (DESIGN.md, "The front page": the product, live, with demo data). Its
# exercises come from the starter library, so the types and muscles are the
# ones every new account gets. Nothing is saved. (exercise, one-sided, seconds)
DEMO_NAME = "Kettlebell 20"
DEMO_ITEMS = [
    ("Kettlebell swing", False, 40),
    ("Goblet squat", False, 40),
    ("Split squat", True, 40),
    ("Push-up", False, 30),
    ("Plank", False, 45),
]
DEMO_ROUNDS = 2
DEMO_EFFORT = 7
DEMO_MUSCLES = 6


def demo_report() -> dict[str, Any]:
    """Return the report the phone shows after the demo workout (mirrors engine.js breakdown).

    Time worked goes to each exercise's types, split evenly, and in full to
    each of its muscles. A one-sided exercise is worked once per side.
    """
    library = {name: (types, muscles) for name, types, muscles, *_rest in starter.EXERCISES}
    by_type: dict[str, float] = defaultdict(float)
    by_muscle: dict[str, int] = defaultdict(int)
    worked = 0
    for name, one_sided, seconds in DEMO_ITEMS:
        types, muscles = library[name]
        seconds *= DEMO_ROUNDS * (2 if one_sided else 1)
        worked += seconds
        for slug in types:
            by_type[slug] += seconds / len(types)
        for muscle in muscles:
            by_muscle[muscle] += seconds
    known = ExerciseType.objects.filter(slug__in=by_type).by_slug()
    type_rows = [
        {"name": known[slug].name, "colour": known[slug].colour, "seconds": round(seconds)}
        for slug, seconds in sorted(by_type.items(), key=lambda kv: -kv[1])
        if slug in known
    ]
    top_muscles = sorted(by_muscle.items(), key=lambda kv: -kv[1])[:DEMO_MUSCLES]
    most = top_muscles[0][1]
    return {
        "name": DEMO_NAME,
        "worked": worked,
        "exercises": len(DEMO_ITEMS),
        "rounds": DEMO_ROUNDS,
        "types": type_rows,
        "muscles": [
            {"name": muscle, "seconds": seconds, "percent": round(seconds * 100 / most)}
            for muscle, seconds in top_muscles
        ],
        "effort": range(1, 11),
        "rated": DEMO_EFFORT,
    }


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """The front page: the promise, the product, the connector and the way in."""
    return render(request, "public/home.html", {"report": demo_report(), "mcp_url": mcp_url()})


@require_GET
def terms(request: HttpRequest) -> HttpResponse:
    """The terms of service (placeholder)."""
    return render(request, "public/terms.html")


@require_GET
def privacy(request: HttpRequest) -> HttpResponse:
    """The privacy notice (placeholder, but true of the template as shipped)."""
    return render(request, "public/privacy.html", {"keeps_email": settings.ACCOUNTS_KEEP_EMAIL})


@require_GET
def help_page(request: HttpRequest) -> HttpResponse:
    """Help: signing in, passkeys, installing the app, offline (placeholder)."""
    return render(request, "public/help.html", {"mcp_url": mcp_url()})
