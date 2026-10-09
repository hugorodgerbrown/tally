"""Tests for apps.library.starter and the seed_library command."""

from io import StringIO
from typing import Any

import pytest
from django.core.management import CommandError, call_command

from apps.library import starter
from apps.library.models import Exercise, MuscleGroup, Workout
from tests.factories import ExerciseFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_install_is_safe_to_run_twice(user: Any) -> None:
    """The second install adds nothing."""
    first = starter.install(user)
    assert (first.exercises, first.workout) == (21, True)
    workout = Workout.objects.for_user(user).get(name=starter.SAMPLE_WORKOUT)
    assert workout.items.count() == 7
    second = starter.install(user)
    assert (second.exercises, second.workout) == (0, False)
    assert Exercise.objects.for_user(user).count() == 21
    # Recorded as the starter library, and a saved workout rather than a one-off.
    assert set(Exercise.objects.for_user(user).values_list("source", flat=True)) == {"seed"}
    assert (workout.source, workout.one_off) == ("seed", False)


def test_install_tags_kit_and_holds(user: Any) -> None:
    """Kettlebell moves carry the kettlebell; holds are static."""
    starter.install(user)
    mine = Exercise.objects.for_user(user)
    assert mine.get(name="Kettlebell swing").equipment == "kettlebell"
    assert mine.get(name="Plank").equipment == ""
    assert mine.get(name="Plank").movement == "static"
    assert mine.get(name="Burpee").movement == "dynamic"


def test_two_accounts_share_muscle_groups_not_exercises(user: Any) -> None:
    """Each account gets its own exercises; the muscle groups are the shared ones."""
    other = UserFactory.create()
    starter.install(user)
    starter.install(other)
    assert Exercise.objects.count() == 42
    assert not MuscleGroup.objects.filter(owner__isnull=False).exists()


def test_command_is_a_dry_run_by_default(user: Any) -> None:
    """Without --commit it lists the accounts and changes nothing."""
    out = StringIO()
    call_command("seed_library", stdout=out)
    assert user.email in out.getvalue()
    assert "dry run" in out.getvalue()
    assert not Exercise.objects.exists()


def test_command_fills_only_empty_libraries(user: Any) -> None:
    """--commit fills accounts with no exercises and leaves the rest alone."""
    stocked = UserFactory.create()
    ExerciseFactory.create(owner=stocked)
    out = StringIO()
    call_command("seed_library", "--commit", stdout=out)
    assert Exercise.objects.for_user(user).count() == 21
    assert Exercise.objects.for_user(stocked).count() == 1
    call_command("seed_library", stdout=out)
    assert "Every account already has a library" in out.getvalue()


def test_command_email_adds_what_is_missing(user: Any) -> None:
    """--email targets one account even if it has exercises."""
    ExerciseFactory.create(owner=user, name="Plank")
    call_command("seed_library", "--commit", "--email", user.email.upper(), stdout=StringIO())
    assert Exercise.objects.for_user(user).count() == 21


def test_command_email_must_match_an_account(db: None) -> None:
    """An unknown address fails, so cron notices."""
    with pytest.raises(CommandError):
        call_command("seed_library", "--email", "nobody@example.com", stdout=StringIO())
