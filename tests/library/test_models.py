"""Tests for apps.library.models: names, querysets and the per-owner rules."""

from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem
from tests.factories import (
    ExerciseFactory,
    MuscleGroupFactory,
    UserFactory,
    WorkoutFactory,
    WorkoutItemFactory,
    exercise_type,
)

pytestmark = pytest.mark.django_db


def test_the_five_types_are_made_by_migration() -> None:
    """The data migration makes the five types, keyed by slug."""
    assert set(ExerciseType.objects.all().by_slug()) == {
        "aerobic",
        "anaerobic",
        "strength",
        "flexibility",
        "fitness",
    }


def test_model_names(user: Any) -> None:
    """Each model's to_string reads as it is shown."""
    lunge = ExerciseFactory.create(owner=user, name="Lunge")
    item = WorkoutItemFactory.create(workout__owner=user, workout__name="Legs", exercise=lunge)
    assert str(lunge) == "Lunge"
    assert str(item.workout) == "Legs"
    assert str(item) == "Lunge (40s)"
    assert str(exercise_type("strength")) == "Strength"
    assert str(MuscleGroupFactory.create(name="Core")) == "Core"


def test_querysets_are_per_owner(user: Any) -> None:
    """for_user keeps to one account's exercises, workouts and items."""
    mine = WorkoutItemFactory.create(workout__owner=user)
    theirs = WorkoutItemFactory.create()
    assert list(Exercise.objects.for_user(user)) == [mine.exercise]
    assert list(Workout.objects.for_user(user)) == [mine.workout]
    assert list(WorkoutItem.objects.for_user(user)) == [mine]
    assert theirs.exercise.owner != user


def test_active_hides_retired_workouts(user: Any) -> None:
    """Only active workouts go to the phone."""
    shown = WorkoutFactory.create(owner=user)
    WorkoutFactory.create(owner=user, is_active=False)
    assert list(Workout.objects.for_user(user).active()) == [shown]


def test_exercise_names_are_unique_per_owner(user: Any) -> None:
    """Two accounts may both have a Plank; one account can't have two."""
    ExerciseFactory.create(owner=user, name="Plank")
    ExerciseFactory.create(name="Plank")
    with pytest.raises(IntegrityError):
        ExerciseFactory.create(owner=user, name="Plank")


def test_muscle_groups_shared_and_private(user: Any) -> None:
    """A user sees the shared groups and their own, never another account's."""
    shared = MuscleGroupFactory.create(name="Core")
    own = MuscleGroupFactory.create(owner=user, name="Forearms")
    MuscleGroupFactory.create(owner=UserFactory.create(), name="Neck")
    assert set(MuscleGroup.objects.visible_to(user)) == {shared, own}


def test_named_finds_before_it_adds(user: Any) -> None:
    """named() matches any case, prefers the shared group, and adds a private one if new."""
    shared = MuscleGroupFactory.create(name="Core")
    assert MuscleGroup.objects.named(user, " core ") == shared
    added = MuscleGroup.objects.named(user, "grip")
    assert (added.name, added.owner) == ("Grip", user)
    assert MuscleGroup.objects.named(user, "GRIP") == added
    other = UserFactory.create()
    assert MuscleGroup.objects.named(other, "grip").owner == other


def test_shared_muscle_names_are_unique() -> None:
    """Only one shared group per name."""
    MuscleGroupFactory.create(name="Core")
    with pytest.raises(IntegrityError):
        MuscleGroupFactory.create(name="Core")


@pytest.mark.parametrize(
    ("fields", "days_ago", "listed"),
    [
        ({}, 30, True),
        ({"one_off": True}, 0, True),
        ({"one_off": True}, 6, True),
        ({"one_off": True}, 8, False),
        ({"is_active": False}, 0, False),
        ({"one_off": True, "is_active": False}, 0, False),
    ],
)
def test_on_phone(fields: dict[str, Any], days_ago: int, listed: bool) -> None:
    """Saved workouts stay on the phone; one-offs for a week; hidden ones never."""
    workout = WorkoutFactory.create(**fields)
    Workout.objects.filter(pk=workout.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago)
    )
    workout.refresh_from_db()
    assert workout.on_phone is listed
    assert Workout.objects.on_phone().filter(pk=workout.pk).exists() is listed


def test_new_rows_are_made_in_manage() -> None:
    """Exercises and workouts default to Manage as their source, and saved."""
    workout = WorkoutFactory.create()
    assert (workout.source, workout.one_off) == ("manage", False)
    assert ExerciseFactory.create().source == "manage"
