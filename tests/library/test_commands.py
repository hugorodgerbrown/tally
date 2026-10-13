"""Tests for the archive_unused_workouts command."""

from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.library.models import Source, Workout, WorkoutStatus
from tests.factories import ActivitySessionFactory, WorkoutFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def workouts(user: Any) -> dict[str, Workout]:
    """Claude's workouts: one unused for eight days, and the kinds that must be kept."""
    made = {
        "stale": WorkoutFactory.create(owner=user, name="Stale", source=Source.CLAUDE),
        "pinned": WorkoutFactory.create(
            owner=user, name="Pinned", source=Source.CLAUDE, status=WorkoutStatus.PINNED
        ),
        "done": WorkoutFactory.create(owner=user, name="Done", source=Source.CLAUDE),
        "manage": WorkoutFactory.create(owner=user, name="Manage", source=Source.MANAGE),
        "fresh": WorkoutFactory.create(owner=user, name="Fresh", source=Source.CLAUDE),
    }
    ActivitySessionFactory.create(owner=user, workout=made["done"])
    old = timezone.now() - timedelta(days=8)
    Workout.objects.exclude(name="Fresh").update(updated_at=old)
    return made


def statuses() -> dict[str, str]:
    """Return each workout's status by name."""
    return dict(Workout.objects.values_list("name", "status"))


def test_dry_run_lists_and_changes_nothing(workouts: dict[str, Workout]) -> None:
    """Without --commit it lists the one it would archive and leaves it alone."""
    out = StringIO()
    call_command("archive_unused_workouts", stdout=out)
    text = out.getvalue()
    assert "Stale" in text
    assert "Done" not in text
    assert "1 unused workouts to archive (dry run" in text
    assert statuses()["Stale"] == "active"


def test_commit_archives_only_claudes_unused_workouts(workouts: dict[str, Workout]) -> None:
    """Pinned, done, Manage-made and recently changed workouts are kept."""
    out = StringIO()
    call_command("archive_unused_workouts", "--commit", stdout=out)
    assert "Archived 1 unused workouts." in out.getvalue()
    assert statuses() == {
        "Stale": "archived",
        "Pinned": "pinned",
        "Done": "active",
        "Manage": "active",
        "Fresh": "active",
    }


def test_commit_is_quiet_at_verbosity_zero(workouts: dict[str, Workout]) -> None:
    """--verbosity 0 prints nothing but still archives."""
    out = StringIO()
    call_command("archive_unused_workouts", "--commit", verbosity=0, stdout=out)
    assert out.getvalue() == ""
    assert statuses()["Stale"] == "archived"
