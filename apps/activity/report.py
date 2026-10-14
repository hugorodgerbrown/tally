"""What a user has trained over a period: the numbers behind Report and ``training_summary``.

The splitting rules live here so the Report page and Claude never disagree.
An exercise's time is shared evenly between its types, but counts in full
for each muscle it works, so the muscle split overlaps. Time on an exercise
since deleted keeps its name but has no type, muscle or movement.

Periods are calendar weeks (Monday to Sunday) or calendar months, in UK
time like every other date in the app.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal

from django.contrib.auth.base_user import AbstractBaseUser
from django.utils import timezone

from apps.activity.models import ActivitySession, ActivitySessionQuerySet, SessionEntry

logger = logging.getLogger(__name__)

Kind = Literal["week", "month"]
KINDS: tuple[Kind, ...] = ("week", "month")
UNKNOWN = "unknown"
DASH = "\u2013"


def day_start(day: dt.date) -> dt.datetime:
    """Return midnight at the start of ``day``, UK time."""
    return timezone.make_aware(dt.datetime.combine(day, dt.time()))


def _add_months(day: dt.date, months: int) -> dt.date:
    """Return the first of the month ``months`` after ``day``'s month."""
    index = day.year * 12 + day.month - 1 + months
    return dt.date(index // 12, index % 12 + 1, 1)


@dataclass(frozen=True)
class Period:
    """A calendar week or month: ``start`` is its first day, ``end`` the day after its last."""

    kind: Kind
    start: dt.date
    end: dt.date

    @classmethod
    def containing(cls, kind: Kind, day: dt.date) -> Period:
        """Return the week (from Monday) or month that ``day`` falls in."""
        if kind == "week":
            start = day - dt.timedelta(days=day.weekday())
            return cls(kind, start, start + dt.timedelta(days=7))
        start = day.replace(day=1)
        return cls(kind, start, _add_months(start, 1))

    def shifted(self, steps: int) -> Period:
        """Return the period ``steps`` before (negative) or after (positive) this one."""
        if self.kind == "week":
            return Period.containing("week", self.start + dt.timedelta(weeks=steps))
        return Period.containing("month", _add_months(self.start, steps))

    @property
    def last_day(self) -> dt.date:
        """Return the period's last day, inclusive."""
        return self.end - dt.timedelta(days=1)

    def contains(self, day: dt.date) -> bool:
        """Return whether ``day`` falls in this period."""
        return self.start <= day < self.end

    @property
    def short_label(self) -> str:
        """Return a label for a trend bar: 6 Oct, or Oct."""
        if self.kind == "week":
            return f"{self.start.day} {self.start:%b}"
        return f"{self.start:%b}"


@dataclass
class Totals:
    """A user's sessions and time over a span, split by type, muscle, movement and exercise.

    The ``seconds_by_*`` mappings are unrounded; ``ranked`` rounds them for display.
    """

    sessions: int = 0
    completed_sessions: int = 0
    active_days: int = 0
    seconds_worked: int = 0
    average_effort: float | None = None
    seconds_by_type: dict[str, float] = field(default_factory=dict)
    seconds_by_muscle: dict[str, int] = field(default_factory=dict)
    seconds_by_movement: dict[str, int] = field(default_factory=dict)
    seconds_by_exercise: dict[str, int] = field(default_factory=dict)


def ranked(totals: dict[str, int] | dict[str, float]) -> dict[str, int]:
    """Return the totals rounded to whole seconds, largest first."""
    return {k: round(v) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}


def sessions_between(
    user: AbstractBaseUser, start: dt.datetime | None, end: dt.datetime | None
) -> ActivitySessionQuerySet:
    """Return ``user``'s sessions that started in [start, end); either end may be open."""
    qs = ActivitySession.objects.for_user(user)
    if start:
        qs = qs.filter(started_at__gte=start)
    if end:
        qs = qs.filter(started_at__lt=end)
    return qs


def totals(user: AbstractBaseUser, start: dt.datetime | None, end: dt.datetime | None) -> Totals:
    """Return ``user``'s totals for sessions that started in [start, end)."""
    sessions = list(sessions_between(user, start, end))
    entries = SessionEntry.objects.filter(session__in=sessions).prefetch_related(
        "exercise__types", "exercise__muscles"
    )
    by_type: dict[str, float] = defaultdict(float)
    by_muscle: dict[str, int] = defaultdict(int)
    by_exercise: dict[str, int] = defaultdict(int)
    by_movement: dict[str, int] = defaultdict(int)
    for entry in entries:
        by_exercise[entry.exercise_name] += entry.seconds_worked
        if entry.exercise is None:
            by_type[UNKNOWN] += entry.seconds_worked
            by_movement[UNKNOWN] += entry.seconds_worked
            continue
        by_movement[entry.exercise.movement] += entry.seconds_worked
        types = entry.exercise.types.all()
        for t in types:
            by_type[t.slug] += entry.seconds_worked / len(types)
        for m in entry.exercise.muscles.all():
            by_muscle[m.name] += entry.seconds_worked
    efforts = [s.effort for s in sessions if s.effort is not None]
    return Totals(
        sessions=len(sessions),
        completed_sessions=sum(s.completed for s in sessions),
        active_days=len({timezone.localdate(s.started_at) for s in sessions}),
        seconds_worked=sum(s.seconds_worked for s in sessions),
        average_effort=round(sum(efforts) / len(efforts), 1) if efforts else None,
        seconds_by_type=dict(by_type),
        seconds_by_muscle=dict(by_muscle),
        seconds_by_movement=dict(by_movement),
        seconds_by_exercise=dict(by_exercise),
    )


def period_totals(user: AbstractBaseUser, period: Period) -> Totals:
    """Return ``user``'s totals for one week or month."""
    return totals(user, day_start(period.start), day_start(period.end))


def trend(user: AbstractBaseUser, period: Period, count: int) -> list[tuple[Period, int]]:
    """Return the seconds worked in each of the ``count`` periods ending with ``period``."""
    periods = [period.shifted(-i) for i in reversed(range(count))]
    seconds = dict.fromkeys(periods, 0)
    for s in sessions_between(user, day_start(periods[0].start), day_start(period.end)):
        seconds[Period.containing(period.kind, timezone.localdate(s.started_at))] += (
            s.seconds_worked
        )
    return list(seconds.items())


def range_label(period: Period) -> str:
    """Return the period's dates, joined by an en dash: 6-12 Oct 2026, 29 Sep-5 Oct 2026."""
    first, last = period.start, period.last_day
    end = f"{last.day} {last:%b %Y}"
    if first.month == last.month:
        return f"{first.day} {DASH} {end}"
    if first.year == last.year:
        return f"{first.day} {first:%b} {DASH} {end}"
    return f"{first.day} {first:%b %Y} {DASH} {end}"


def title(period: Period, today: dt.date) -> str:
    """Return the period's heading: This week, Last month, Week of 6 Oct, September 2026."""
    current = Period.containing(period.kind, today)
    if period == current:
        return f"This {period.kind}"
    if period == current.shifted(-1):
        return f"Last {period.kind}"
    if period.kind == "week":
        return f"Week of {period.start.day} {period.start:%b %Y}"
    return f"{period.start:%B %Y}"
