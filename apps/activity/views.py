"""The phone app's page at /app/, and Report at /app/report/.

The phone app is one shell that draws every screen in JavaScript. It is
the manifest's start_url: its scripts, styles and the page itself are
cached by the service worker, and the workouts are kept in IndexedDB, so
it opens and runs a workout with no connection.

Report is an ordinary server-rendered page over the logged sessions; it
needs a connection, like Manage.
"""

import datetime as dt
import logging
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.activity import report as rpt
from apps.core.decorators import signed_in_user
from apps.library.models import Exercise, ExerciseType, Movement, MuscleGroup
from apps.planner.templatetags.planner import duration

logger = logging.getLogger(__name__)

# How many periods the trend shows, ending with the one on screen.
TREND = {"week": 8, "month": 6}
TOP_EXERCISES = 8
UNKNOWN_COLOUR = "var(--muted)"


def _today() -> dt.date:
    """Return today's date, UK time (a seam for tests)."""
    return timezone.localdate()


@require_GET
@login_required
def app(request: HttpRequest) -> HttpResponse:
    """Return the activity-mode shell."""
    return render(request, "activity/app.html")


def _period(request: HttpRequest, today: dt.date) -> rpt.Period:
    """Return the period the query string asks for: ?period=week|month&from=YYYY-MM-DD."""
    kind = request.GET.get("period", "week")
    if kind not in rpt.KINDS:
        kind = "week"
    try:
        day = dt.date.fromisoformat(request.GET.get("from", ""))
    except ValueError:
        day = today
    return rpt.Period.containing(kind, min(day, today))  # type: ignore[arg-type]


def _bars(rows: list[tuple[str, float, str]]) -> list[dict[str, Any]]:
    """Return ``[(label, seconds, colour)]`` as bars sized against the largest, largest first."""
    rows = sorted(rows, key=lambda r: -r[1])
    top = max((s for _, s, _ in rows), default=0) or 1
    return [
        {"label": label, "seconds": round(s), "width": round(100 * s / top, 1), "colour": colour}
        for label, s, colour in rows
    ]


def _change(now: float, before: float, unit: str, noun: str) -> str:
    """Describe ``now`` against ``before``: 12 min more than the week before."""
    diff = now - before
    if not diff:
        return f"Same as the {noun} before"
    if unit == "time":
        return f"{duration(abs(diff))} {'more' if diff > 0 else 'less'} than the {noun} before"
    return f"{abs(diff):g} {'more' if diff > 0 else 'fewer'} than the {noun} before"


@require_GET
@login_required
def report(request: HttpRequest) -> HttpResponse:
    """Show what the user trained in a week or month, split by type, muscle and movement."""
    user = signed_in_user(request)
    today = _today()
    period = _period(request, today)
    previous = period.shifted(-1)
    now = rpt.period_totals(user, period)
    before = rpt.period_totals(user, previous)
    types = ExerciseType.objects.all()

    by_type = [
        (t.name, now.seconds_by_type[t.slug], t.colour)
        for t in types
        if t.slug in now.seconds_by_type
    ]
    if rpt.UNKNOWN in now.seconds_by_type:
        by_type.append(("Deleted exercises", now.seconds_by_type[rpt.UNKNOWN], UNKNOWN_COLOUR))
    movements = dict(Movement.choices) | {rpt.UNKNOWN: "Deleted exercises"}
    library_muscles = MuscleGroup.objects.filter(
        exercises__in=Exercise.objects.for_user(user)
    ).distinct()
    trend = rpt.trend(user, period, TREND[period.kind])
    tallest = max((s for _, s in trend), default=0) or 1
    noun = period.kind
    context = {
        "mode": "report",
        "period": period,
        "title": rpt.title(period, today),
        "range": rpt.range_label(period),
        "previous": previous,
        "next": None if period.contains(today) else period.shifted(1),
        "week": rpt.Period.containing("week", min(period.last_day, today)),
        "month": rpt.Period.containing("month", period.start),
        "totals": now,
        "headline": [
            (
                "Time worked",
                duration(now.seconds_worked),
                _change(now.seconds_worked, before.seconds_worked, "time", noun),
            ),
            ("Sessions", now.sessions, _change(now.sessions, before.sessions, "count", noun)),
            (
                "Active days",
                now.active_days,
                _change(now.active_days, before.active_days, "count", noun),
            ),
            ("Average effort", now.average_effort, None),
        ],
        "by_type": _bars(by_type),
        "by_muscle": _bars([(m, s, "") for m, s in now.seconds_by_muscle.items()]),
        "by_movement": _bars([(movements[k], s, "") for k, s in now.seconds_by_movement.items()]),
        "by_exercise": _bars([(e, s, "") for e, s in now.seconds_by_exercise.items()])[
            :TOP_EXERCISES
        ],
        "untrained_types": [t for t in types if t.slug not in now.seconds_by_type],
        "untrained_muscles": [m for m in library_muscles if m.name not in now.seconds_by_muscle],
        "trend": [
            {
                "label": p.short_label,
                "seconds": s,
                "minutes": round(s / 60),
                "height": round(100 * s / tallest, 1),
                "period": p,
                "current": p == period,
            }
            for p, s in trend
        ],
    }
    return render(request, "activity/report.html", context)
