"""Tests for Report: the period maths, the shared totals and the page at /app/report/."""

import datetime as dt
from collections.abc import Sequence
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.activity import report, views
from apps.activity.models import ActivitySession
from apps.activity.report import Period
from apps.library.models import Exercise, ExerciseType, MuscleGroup
from tests.factories import (
    ActivitySessionFactory,
    ExerciseFactory,
    SessionEntryFactory,
    UserFactory,
)

TODAY = dt.date(2026, 10, 14)  # a Wednesday
D = report.DASH


def log(
    owner: Any,
    when: dt.datetime | dt.date,
    entries: Sequence[tuple[Exercise, int]],
    effort: int | None = None,
    completed: bool = True,
) -> ActivitySession:
    """Log a session at ``when`` (07:00 on a bare date) with ``[(exercise, seconds)]``."""
    if not isinstance(when, dt.datetime):
        when = dt.datetime.combine(when, dt.time(7))
    start = timezone.make_aware(when)
    session: ActivitySession = ActivitySessionFactory.create(
        owner=owner,
        workout=None,
        workout_name="Morning",
        started_at=start,
        ended_at=start + dt.timedelta(minutes=5),
        completed=completed,
        seconds_worked=sum(s for _, s in entries),
        effort=effort,
    )
    for i, (exercise, seconds) in enumerate(entries):
        SessionEntryFactory.create(
            session=session,
            exercise=exercise,
            exercise_name=exercise.name,
            order=i,
            seconds_worked=seconds,
        )
    return session


def make_exercise(owner: Any, name: str, types: list[str], muscles: list[str]) -> Exercise:
    """Return ``owner``'s exercise tagged with these type slugs and shared muscle groups."""
    exercise: Exercise = ExerciseFactory.create(owner=owner, name=name)
    exercise.types.set(ExerciseType.objects.filter(slug__in=types))
    exercise.muscles.set(MuscleGroup.objects.get_or_create(owner=None, name=m)[0] for m in muscles)
    return exercise


@pytest.fixture
def today(monkeypatch: pytest.MonkeyPatch) -> dt.date:
    """Pin the report's idea of today to Wednesday 14 October 2026."""
    monkeypatch.setattr(views, "_today", lambda: TODAY)
    return TODAY


# ---------- periods ----------


@pytest.mark.parametrize(
    ("kind", "day", "start", "end"),
    [
        ("week", TODAY, dt.date(2026, 10, 12), dt.date(2026, 10, 19)),
        ("week", dt.date(2026, 10, 12), dt.date(2026, 10, 12), dt.date(2026, 10, 19)),
        ("week", dt.date(2026, 10, 18), dt.date(2026, 10, 12), dt.date(2026, 10, 19)),
        ("month", TODAY, dt.date(2026, 10, 1), dt.date(2026, 11, 1)),
        ("month", dt.date(2026, 12, 31), dt.date(2026, 12, 1), dt.date(2027, 1, 1)),
    ],
)
def test_period_containing(kind: Any, day: dt.date, start: dt.date, end: dt.date) -> None:
    """Weeks run Monday to Sunday and months are calendar months; ``end`` is exclusive."""
    assert Period.containing(kind, day) == Period(kind, start, end)


def test_period_shifted_across_years() -> None:
    """Stepping back and forward crosses month and year ends."""
    january = Period.containing("month", dt.date(2027, 1, 20))
    assert january.shifted(-1).start == dt.date(2026, 12, 1)
    assert january.shifted(-13).start == dt.date(2025, 12, 1)
    week = Period.containing("week", dt.date(2027, 1, 1))
    assert week.shifted(-1).start == dt.date(2026, 12, 21)
    assert week.shifted(1).start == dt.date(2027, 1, 4)


@pytest.mark.parametrize(
    ("period", "label"),
    [
        (Period.containing("week", TODAY), f"12 {D} 18 Oct 2026"),
        (Period.containing("week", dt.date(2026, 10, 1)), f"28 Sep {D} 4 Oct 2026"),
        (Period.containing("week", dt.date(2027, 1, 1)), f"28 Dec 2026 {D} 3 Jan 2027"),
        (Period.containing("month", TODAY), f"1 {D} 31 Oct 2026"),
    ],
)
def test_range_label(period: Period, label: str) -> None:
    """The dates under the heading name the month and year once where they can."""
    assert report.range_label(period) == label


@pytest.mark.parametrize(
    ("period", "title"),
    [
        (Period.containing("week", TODAY), "This week"),
        (Period.containing("week", dt.date(2026, 10, 5)), "Last week"),
        (Period.containing("week", dt.date(2026, 9, 30)), "Week of 28 Sep 2026"),
        (Period.containing("month", TODAY), "This month"),
        (Period.containing("month", dt.date(2026, 9, 3)), "Last month"),
        (Period.containing("month", dt.date(2026, 8, 3)), "August 2026"),
    ],
)
def test_title(period: Period, title: str) -> None:
    """Recent periods are named relative to today; older ones by their dates."""
    assert report.title(period, TODAY) == title


def test_short_labels() -> None:
    """Trend bars are labelled with the week's Monday, or the month."""
    assert Period.containing("week", TODAY).short_label == "12 Oct"
    assert Period.containing("month", TODAY).short_label == "Oct"


# ---------- totals and trend ----------


@pytest.mark.django_db
def test_period_totals_use_uk_days(user: Any) -> None:
    """A session just after midnight on Monday, UK time, is in the new week."""
    squat = make_exercise(user, "Squat", ["strength"], ["Glutes"])
    log(user, dt.datetime.combine(dt.date(2026, 10, 11), dt.time(23, 30)), [(squat, 40)])
    log(user, dt.datetime.combine(dt.date(2026, 10, 12), dt.time(0, 30)), [(squat, 60)])
    week = report.period_totals(user, Period.containing("week", TODAY))
    assert (week.sessions, week.seconds_worked) == (1, 60)


@pytest.mark.django_db
def test_totals_split_types_and_count_muscles_in_full(user: Any) -> None:
    """Time is shared between types but counts in full per muscle; others' sessions are ignored."""
    deadlift = make_exercise(user, "Single-leg deadlift", ["balance", "strength"], ["Glutes"])
    stand = make_exercise(user, "Single-leg stand", ["balance"], ["Calves", "Core"])
    stand.movement = "static"
    stand.save()
    log(user, TODAY, [(deadlift, 60), (stand, 30)], effort=6)
    log(user, TODAY, [(stand, 30)], effort=8, completed=False)
    log(UserFactory.create(), TODAY, [(deadlift, 600)])
    totals = report.period_totals(user, Period.containing("week", TODAY))
    assert (totals.sessions, totals.completed_sessions, totals.active_days) == (2, 1, 1)
    assert totals.seconds_worked == 120
    assert totals.average_effort == 7.0
    assert totals.seconds_by_type == {"balance": 90, "strength": 30}
    assert totals.seconds_by_muscle == {"Glutes": 60, "Calves": 60, "Core": 60}
    assert totals.seconds_by_movement == {"dynamic": 60, "static": 60}


@pytest.mark.django_db
def test_trend_buckets_by_period(user: Any) -> None:
    """The trend has one bucket per period, oldest first, empty ones included."""
    squat = make_exercise(user, "Squat", ["strength"], ["Glutes"])
    log(user, dt.date(2026, 9, 29), [(squat, 40)])
    log(user, TODAY, [(squat, 30)])
    log(user, dt.date(2026, 10, 13), [(squat, 20)])
    trend = report.trend(user, Period.containing("week", TODAY), 3)
    assert [(p.start.day, s) for p, s in trend] == [(28, 40), (5, 0), (12, 50)]


# ---------- the page ----------


def test_report_needs_sign_in(client: Client, db: None) -> None:
    """Signed out, Report sends you to sign in."""
    response = client.get(reverse("activity:report"))
    assert response.status_code == 302
    assert reverse("accounts:sign_in") in response["Location"]


def test_empty_week(signed_in: Client, today: dt.date) -> None:
    """With nothing logged, the page says so and offers the phone app."""
    html = signed_in.get(reverse("activity:report")).content.decode()
    assert "<h1>This week</h1>" in html
    assert "No sessions yet this week" in html
    assert f'href="{reverse("activity:app")}">Start a workout' in html
    assert 'rel="next"' not in html


def test_week_report(signed_in: Client, user: Any, today: dt.date) -> None:
    """The week shows its totals against the week before, splits, gaps and the trend."""
    deadlift = make_exercise(user, "Single-leg deadlift", ["balance", "strength"], ["Glutes"])
    make_exercise(user, "Pigeon pose", ["flexibility"], ["Hips"])
    log(user, TODAY, [(deadlift, 600)], effort=7)
    log(user, dt.date(2026, 10, 6), [(deadlift, 300)])
    html = signed_in.get(reverse("activity:report")).content.decode()
    assert "10 min" in html
    assert "5 min more than the week before" in html
    assert "Same as the week before" in html  # one session each week
    assert "<span>Balance</span>" in html
    assert "<span>Glutes</span>" in html
    assert "<span>Single-leg deadlift</span>" in html
    gaps = html[html.index('id="r-gaps"') :]
    assert "Flexibility" in gaps
    assert "Hips" in gaps
    assert "Glutes" not in gaps[: gaps.index("</section>")]
    assert html.count('<li class="on">') == 1
    assert html.count("<li><a href=") + 1 == 8


def test_month_and_earlier_periods(signed_in: Client, user: Any, today: dt.date) -> None:
    """?period=month&from= picks a month; earlier ones link forward, the current one doesn't."""
    squat = make_exercise(user, "Squat", ["strength"], ["Glutes"])
    log(user, dt.date(2026, 8, 20), [(squat, 120)])
    url = reverse("activity:report")
    html = signed_in.get(url, {"period": "month", "from": "2026-08-31"}).content.decode()
    assert "<h1>August 2026</h1>" in html
    assert "2 min" in html
    assert f"{url}?period=month&amp;from=2026-09-01" in html  # next month
    assert f"{url}?period=month&amp;from=2026-07-01" in html  # previous month
    assert html.count("<li><a href=") + html.count('<li class="on">') == 6


@pytest.mark.parametrize(
    ("query", "heading"),
    [
        ({"period": "year"}, "This week"),
        ({"from": "not a date"}, "This week"),
        ({"from": "2030-01-01"}, "This week"),
        ({"period": "month", "from": "2030-01-01"}, "This month"),
    ],
)
def test_bad_or_future_periods_fall_back(
    signed_in: Client, today: dt.date, query: dict[str, str], heading: str
) -> None:
    """An unknown period is a week, and a date that isn't one or is in the future is today."""
    html = signed_in.get(reverse("activity:report"), query).content.decode()
    assert f"<h1>{heading}</h1>" in html


def test_deleted_exercises_are_named(signed_in: Client, user: Any, today: dt.date) -> None:
    """Time on a deleted exercise shows as such under type and movement, by name in the top list."""
    squat = make_exercise(user, "Squat", ["strength"], ["Glutes"])
    log(user, TODAY, [(squat, 90)]).entries.update(exercise=None)
    html = signed_in.get(reverse("activity:report")).content.decode()
    assert html.count("<span>Deleted exercises</span>") == 2
    assert "<span>Squat</span>" in html
    assert "No muscle groups on these exercises." in html


def test_another_accounts_sessions_never_show(signed_in: Client, user: Any, today: dt.date) -> None:
    """Report only reads the signed-in user's sessions."""
    other = UserFactory.create()
    log(other, TODAY, [(make_exercise(other, "Secret move", ["strength"], ["Glutes"]), 900)])
    html = signed_in.get(reverse("activity:report")).content.decode()
    assert "Secret move" not in html
    assert "No sessions yet this week" in html


def test_report_is_a_mode(signed_in: Client, today: dt.date) -> None:
    """The header shows Workout, Manage and Report, with Report current; the sub-nav is periods."""
    html = signed_in.get(reverse("activity:report")).content.decode()
    modes = html[html.index('<nav class="modes"') : html.index("</nav>")]
    assert f'<a href="{reverse("activity:app")}">Workout</a>' in modes
    assert f'<a href="{reverse("planner:workouts")}">Manage</a>' in modes
    assert '<span aria-current="page">Report</span>' in modes
    assert 'aria-current="page">Week</a>' in html
