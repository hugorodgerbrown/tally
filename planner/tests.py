import json

import pytest
from django.urls import reverse

from library import timeline
from library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem


@pytest.fixture
def client_in(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("hugo", password="pw"))
    return client


@pytest.fixture
def squat(db):
    ex = Exercise.objects.create(name="Split squat", one_sided=True)
    ex.types.add(ExerciseType.objects.get(slug="strength"))
    return ex


@pytest.fixture
def swing(db):
    ex = Exercise.objects.create(name="Kettlebell swing")
    ex.types.add(
        ExerciseType.objects.get(slug="strength"), ExerciseType.objects.get(slug="aerobic")
    )
    return ex


def items_json(*pairs):
    return json.dumps([{"exercise": str(ex.uuid), "dur": dur} for ex, dur in pairs])


@pytest.mark.parametrize("name", ["planner:workouts", "planner:exercises", "planner:workout_new"])
def test_pages_need_login(client, db, name):
    response = client.get(reverse(name))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("login"))


def test_login_lands_on_workouts(client, django_user_model):
    django_user_model.objects.create_superuser("hugo", password="pw")
    response = client.post(reverse("login"), {"username": "hugo", "password": "pw"})
    assert response["Location"] == reverse("planner:workouts")


def test_create_workout(client_in, squat, swing):
    response = client_in.post(
        reverse("planner:workout_new"),
        {
            "name": "Legs",
            "rest_seconds": 15,
            "rounds": 2,
            "round_rest_seconds": 90,
            "items": items_json((swing, 30), (squat, 40)),
        },
    )
    assert response.status_code == 302
    workout = Workout.objects.get(name="Legs")
    assert [(i.exercise, i.duration_seconds) for i in workout.items.all()] == [
        (swing, 30),
        (squat, 40),
    ]
    # ready 5 + 2 x (30 + 15 rest + 40 + 5 switch + 40) + 90 round break
    assert timeline.total_seconds(workout) == 5 + 2 * 130 + 90


def test_edit_replaces_items_in_order(client_in, squat, swing):
    workout = Workout.objects.create(name="Legs")
    WorkoutItem.objects.create(workout=workout, exercise=squat, order=0, duration_seconds=40)
    client_in.post(
        reverse("planner:workout_edit", args=[workout.uuid]),
        {
            "name": "Legs",
            "rest_seconds": 0,
            "rounds": 1,
            "round_rest_seconds": 120,
            "items": items_json((squat, 20), (swing, 45), (squat, 25)),
        },
    )
    assert [i.duration_seconds for i in workout.items.all()] == [20, 45, 25]


def test_workout_needs_an_exercise(client_in):
    response = client_in.post(
        reverse("planner:workout_new"),
        {
            "name": "Empty",
            "rest_seconds": 15,
            "rounds": 1,
            "round_rest_seconds": 120,
            "items": "[]",
        },
    )
    assert response.status_code == 200
    assert "Add at least one exercise." in response.content.decode()
    assert not Workout.objects.exists()


def test_builder_page_renders(client_in, squat):
    response = client_in.get(reverse("planner:workout_new"))
    assert response.status_code == 200
    assert str(squat.uuid) in response.content.decode()


def test_list_pages_render(client_in, squat):
    workout = Workout.objects.create(name="Legs")
    WorkoutItem.objects.create(workout=workout, exercise=squat, order=0, duration_seconds=40)
    assert "Legs" in client_in.get(reverse("planner:workouts")).content.decode()
    assert "Split squat" in client_in.get(reverse("planner:exercises")).content.decode()


def test_create_exercise_with_new_muscle(client_in):
    MuscleGroup.objects.create(name="Core")
    response = client_in.post(
        reverse("planner:exercise_new"),
        {
            "name": "Turkish get-up",
            "types": ["strength"],
            "muscles": ["Core"],
            "new_muscles": "forearms, core",
            "one_sided": "on",
            "default_duration": 45,
        },
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 201
    data = response.json()["exercise"]
    assert data["sides"] is True
    assert sorted(data["muscles"]) == ["Core", "Forearms"]
    assert MuscleGroup.objects.count() == 2


def test_exercise_name_must_be_unique(client_in, squat):
    response = client_in.post(
        reverse("planner:exercise_new"),
        {"name": "split squat", "types": ["strength"], "default_duration": 40},
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 400
    assert "name" in response.json()["errors"]


def test_used_exercise_cannot_be_deleted(client_in, squat):
    workout = Workout.objects.create(name="Legs")
    WorkoutItem.objects.create(workout=workout, exercise=squat, order=0, duration_seconds=40)
    client_in.post(reverse("planner:exercise_delete", args=[squat.uuid]))
    assert Exercise.objects.filter(pk=squat.pk).exists()


def test_duplicate_workout(client_in, squat):
    workout = Workout.objects.create(name="Legs", rounds=2)
    WorkoutItem.objects.create(workout=workout, exercise=squat, order=0, duration_seconds=40)
    client_in.post(reverse("planner:workout_duplicate", args=[workout.uuid]))
    copy = Workout.objects.get(name="Legs (copy)")
    assert copy.rounds == 2 and copy.items.count() == 1
