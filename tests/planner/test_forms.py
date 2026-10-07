"""Tests for apps.planner.forms: every lookup stays inside the owner's library."""

import json
from typing import Any

import pytest

from apps.library.models import Exercise, MuscleGroup
from apps.planner.forms import ExerciseForm, WorkoutForm
from tests.factories import ExerciseFactory, MuscleGroupFactory, UserFactory

pytestmark = pytest.mark.django_db


def workout_data(items: str) -> dict[str, Any]:
    """Return a valid workout post around the given items JSON."""
    return {
        "name": "Legs",
        "rest_seconds": 15,
        "rounds": 1,
        "round_rest_seconds": 90,
        "items": items,
    }


def test_workout_form_reads_items_in_order(user: Any) -> None:
    """The builder's JSON comes back as (exercise, seconds) pairs in play order."""
    first = ExerciseFactory.create(owner=user)
    second = ExerciseFactory.create(owner=user)
    items = json.dumps(
        [{"exercise": str(second.uuid), "dur": 30}, {"exercise": str(first.uuid), "dur": "45"}]
    )
    form = WorkoutForm(workout_data(items), owner=user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["items"] == [(second, 30), (first, 45)]


def test_workout_form_refuses_another_accounts_exercise(user: Any) -> None:
    """An exercise from someone else's library reads as one that no longer exists."""
    theirs = ExerciseFactory.create()
    items = json.dumps([{"exercise": str(theirs.uuid), "dur": 40}])
    form = WorkoutForm(workout_data(items), owner=user)
    assert not form.is_valid()
    assert form.errors["items"] == ["An exercise in the list no longer exists."]


@pytest.mark.parametrize(
    "items",
    [
        "not json",
        json.dumps([{"dur": 40}]),
        json.dumps([{"exercise": "not-a-uuid", "dur": 40}]),
        json.dumps([{"exercise": "00000000-0000-0000-0000-000000000000", "dur": "long"}]),
        json.dumps([None]),
    ],
)
def test_workout_form_refuses_unreadable_items(user: Any, items: str) -> None:
    """Items that aren't a list of exercise and duration pairs can't be read."""
    form = WorkoutForm(workout_data(items), owner=user)
    assert not form.is_valid()
    assert form.errors["items"] == ["The exercise list could not be read."]


@pytest.mark.parametrize("dur", [4, 3601])
def test_workout_form_refuses_out_of_range_durations(user: Any, dur: int) -> None:
    """Each exercise runs between 5 seconds and an hour."""
    exercise = ExerciseFactory.create(owner=user)
    items = json.dumps([{"exercise": str(exercise.uuid), "dur": dur}])
    form = WorkoutForm(workout_data(items), owner=user)
    assert not form.is_valid()
    assert form.errors["items"] == ["Each exercise needs between 5 and 3600 seconds."]


def test_exercise_form_offers_shared_and_own_muscles_only(user: Any) -> None:
    """The muscle choices are the shared groups plus the owner's, never another account's."""
    shared = MuscleGroupFactory.create(name="Core")
    mine = MuscleGroupFactory.create(owner=user, name="Grip")
    MuscleGroupFactory.create(owner=UserFactory.create(), name="Neck")
    form = ExerciseForm(owner=user)
    choices = form.fields["muscles"].queryset  # type: ignore[attr-defined]
    assert set(choices) == {shared, mine}


def test_exercise_form_refuses_another_accounts_private_muscle(user: Any) -> None:
    """A private muscle group's uuid from another account is not a valid choice."""
    theirs = MuscleGroupFactory.create(owner=UserFactory.create(), name="Neck")
    data = {
        "name": "Shrug",
        "types": ["strength"],
        "muscles": [str(theirs.uuid)],
        "default_duration": 40,
    }
    form = ExerciseForm(data, owner=user)
    assert not form.is_valid()
    assert "muscles" in form.errors


def test_exercise_name_clash_is_per_account(user: Any) -> None:
    """Another account's exercise of the same name is no clash; the owner's own is."""
    ExerciseFactory.create(name="Plank")
    data = {"name": " plank ", "types": ["strength"], "default_duration": 40}
    form = ExerciseForm(data, owner=user)
    assert form.is_valid(), form.errors
    exercise = form.save()
    assert exercise.name == "plank"
    assert exercise.owner == user
    again = ExerciseForm({**data, "name": "PLANK"}, owner=user)
    assert not again.is_valid()
    assert again.errors["name"] == ["An exercise with this name already exists."]


def test_editing_an_exercise_keeps_its_own_name(user: Any) -> None:
    """Saving an exercise under its current name is not a clash with itself."""
    exercise = ExerciseFactory.create(owner=user, name="Plank")
    data = {"name": "Plank", "types": ["strength"], "default_duration": 60}
    form = ExerciseForm(data, instance=exercise, owner=user)
    assert form.is_valid(), form.errors


def test_new_muscles_reuse_shared_groups_and_add_private_ones(user: Any) -> None:
    """A new muscle that matches a shared group uses it; an unknown one is the owner's."""
    core = MuscleGroupFactory.create(name="Core")
    data = {
        "name": "Get-up",
        "types": ["strength"],
        "new_muscles": " core, forearms ,, ",
        "default_duration": 40,
    }
    form = ExerciseForm(data, owner=user)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["new_muscles"] == ["Core", "Forearms"]
    exercise = form.save()
    forearms = MuscleGroup.objects.get(name="Forearms")
    assert forearms.owner == user
    assert set(exercise.muscles.all()) == {core, forearms}


def test_save_without_commit_adds_no_muscles(user: Any) -> None:
    """``commit=False`` leaves the exercise unsaved and adds no muscle groups."""
    data = {"name": "Lunge", "types": ["strength"], "new_muscles": "Glutes", "default_duration": 40}
    form = ExerciseForm(data, owner=user)
    assert form.is_valid(), form.errors
    exercise = form.save(commit=False)
    assert exercise.owner == user
    assert not Exercise.objects.filter(name="Lunge").exists()
    assert not MuscleGroup.objects.filter(name="Glutes").exists()
