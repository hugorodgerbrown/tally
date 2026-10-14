"""Tests for apps.library.models: names, querysets and the per-owner rules."""

from datetime import timedelta
from typing import Any

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.library.models import (
    Exercise,
    ExerciseType,
    MuscleGroup,
    Source,
    Workout,
    WorkoutItem,
    WorkoutStatus,
)
from tests.factories import (
    ActivitySessionFactory,
    ExerciseFactory,
    MuscleGroupFactory,
    UserFactory,
    WorkoutFactory,
    WorkoutItemFactory,
    exercise_type,
)

pytestmark = pytest.mark.django_db


def test_the_six_types_are_made_by_migration() -> None:
    """The data migrations make the six types, balance after flexibility."""
    assert list(ExerciseType.objects.values_list("slug", flat=True)) == [
        "strength",
        "flexibility",
        "balance",
        "aerobic",
        "anaerobic",
        "fitness",
    ]


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


def test_workout_status_querysets(user: Any) -> None:
    """Pinned and active go to the phone; archived ones don't."""
    pinned = WorkoutFactory.create(owner=user, name="A", status=WorkoutStatus.PINNED)
    active = WorkoutFactory.create(owner=user, name="B")
    archived = WorkoutFactory.create(owner=user, name="C", status=WorkoutStatus.ARCHIVED)
    mine = Workout.objects.for_user(user)
    assert active.status == WorkoutStatus.ACTIVE
    assert list(mine.on_phone()) == [pinned, active]
    assert list(mine.pinned()) == [pinned]
    assert list(mine.archived()) == [archived]


def test_unused_from_claude_picks_only_stale_never_done_active_claude_workouts(
    user: Any,
) -> None:
    """Pinned, done, recent and Manage-made workouts are never picked."""
    old = timezone.now() - timedelta(days=8)
    stale = WorkoutFactory.create(owner=user, name="Stale", source=Source.CLAUDE)
    pinned = WorkoutFactory.create(
        owner=user, name="Pinned", source=Source.CLAUDE, status=WorkoutStatus.PINNED
    )
    done = WorkoutFactory.create(owner=user, name="Done", source=Source.CLAUDE)
    ActivitySessionFactory.create(owner=user, workout=done)
    manage = WorkoutFactory.create(owner=user, name="Manage", source=Source.MANAGE)
    WorkoutFactory.create(owner=user, name="Fresh", source=Source.CLAUDE)
    Workout.objects.filter(pk__in=[stale.pk, pinned.pk, done.pk, manage.pk]).update(updated_at=old)
    cutoff = timezone.now() - timedelta(days=7)
    assert list(Workout.objects.unused_from_claude(cutoff)) == [stale]


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


def test_new_rows_are_made_in_manage() -> None:
    """Exercises and workouts default to Manage as their source."""
    assert WorkoutFactory.create().source == "manage"
    assert ExerciseFactory.create().source == "manage"
