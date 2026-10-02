from io import StringIO

import pytest
from django.contrib.admin.sites import site
from django.core.management import call_command
from django.test import RequestFactory

from library import timeline
from library.admin import ExerciseAdmin
from library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem


def test_seed_library_is_safe_to_run_twice(db):
    out = StringIO()
    call_command("seed_library", stdout=out)
    assert "21 exercises created" in out.getvalue()
    workout = Workout.objects.get(name="Morning mobility")
    assert workout.items.count() == 7

    out = StringIO()
    call_command("seed_library", stdout=out)
    assert "0 exercises created" in out.getvalue()
    assert Exercise.objects.count() == 21
    assert Workout.objects.count() == 1


@pytest.fixture
def lunge(db):
    ex = Exercise.objects.create(name="Lunge", one_sided=True)
    ex.types.add(ExerciseType.objects.get(slug="strength"))
    return ex


def test_timeline_matches_engine_js(lunge):
    # Same shape as engine.js's buildTimeline; tests/js covers the JS side.
    plank = Exercise.objects.create(name="Plank")
    workout = Workout.objects.create(name="Mix", rest_seconds=10, rounds=2, round_rest_seconds=60)
    WorkoutItem.objects.create(workout=workout, exercise=lunge, order=0, duration_seconds=20)
    WorkoutItem.objects.create(workout=workout, exercise=plank, order=1, duration_seconds=30)
    one_round = [("work", 20), ("switch", 5), ("work", 20), ("rest", 10), ("work", 30)]
    assert timeline.segments(workout) == [
        ("ready", 5),
        *one_round,
        ("round", 60),
        *one_round,
    ]
    assert timeline.total_seconds(workout) == 5 + 2 * 85 + 60


def test_model_names(lunge):
    workout = Workout.objects.create(name="Legs")
    item = WorkoutItem.objects.create(workout=workout, exercise=lunge, duration_seconds=40)
    assert str(lunge) == "Lunge"
    assert str(workout) == "Legs"
    assert str(item) == "Lunge (40s)"
    assert str(ExerciseType.objects.get(slug="strength")) == "Strength"
    assert str(MuscleGroup.objects.create(name="Core")) == "Core"


def test_exercise_admin_lists_types(lunge, admin_user):
    admin = ExerciseAdmin(Exercise, site)
    request = RequestFactory().get("/")
    request.user = admin_user
    row = admin.get_queryset(request).get(pk=lunge.pk)
    assert admin.type_list(row) == "Strength"
