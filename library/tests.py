from importlib import import_module
from io import StringIO

import pytest
from django.apps import apps
from django.contrib.admin.sites import site
from django.core.management import call_command
from django.test import RequestFactory

from library import timeline
from library.admin import ExerciseAdmin
from library.equipment import icon_svg
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


def test_icon_for_bodyweight_is_empty():
    assert icon_svg("") == ""
    assert icon_svg("barbell") == ""


def test_icon_is_labelled():
    svg = icon_svg("kettlebell")
    assert svg.startswith('<svg class="eq" viewBox="0 0 24 24" role="img" aria-label="Kettlebell">')
    assert "<title>Kettlebell</title>" in svg


def test_seed_and_migration_tag_kettlebell_moves(db):
    call_command("seed_library", stdout=StringIO())
    assert Exercise.objects.get(name="Kettlebell swing").equipment == "kettlebell"
    assert Exercise.objects.get(name="Plank").equipment == ""
    Exercise.objects.create(name="Dumbbell row")
    Exercise.objects.filter(name="Goblet squat").update(equipment="")  # seeded before this change
    migration = import_module("library.migrations.0004_exercise_equipment")
    migration.tag_by_name(apps, None)
    assert Exercise.objects.get(name="Dumbbell row").equipment == "dumbbell"
    assert Exercise.objects.get(name="Goblet squat").equipment == "kettlebell"
