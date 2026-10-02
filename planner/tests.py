import json
import uuid

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


@pytest.mark.parametrize(
    ("name", "section"), [("planner:workouts", "Workouts"), ("planner:exercises", "Exercises")]
)
def test_header_matches_activity_mode(client_in, name, section):
    """The top row holds the wordmark, the mode switch and Sign out, as on the phone."""
    html = client_in.get(reverse(name)).content.decode()
    top = html[html.index('<div class="hrow">') : html.index('<nav class="nav"')]
    assert '<span aria-current="page">Manage</span>' in top
    assert 'action="/logout/"' in top
    assert f'aria-current="page">{section}</a>' in html


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
    assert copy.rounds == 2
    assert copy.items.count() == 1


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(45, "45 s"), (60, "1 min"), (470, "7 min 50 s"), (3600, "1 h"), (3930, "1 h 6 min")],
)
def test_duration_filter(seconds, text):
    from planner.templatetags.planner import duration

    assert duration(seconds) == text


@pytest.mark.parametrize(
    ("items", "error"),
    [
        ("not json", "could not be read"),
        ("[]", "at least one exercise"),
        (json.dumps([{"exercise": str(uuid.uuid4()), "dur": 40}]), "no longer exists"),
    ],
)
def test_workout_rejects_bad_items(client_in, items, error):
    response = client_in.post(
        reverse("planner:workout_new"),
        {"name": "Legs", "rest_seconds": 15, "rounds": 1, "round_rest_seconds": 90, "items": items},
    )
    assert response.status_code == 200
    assert error in response.content.decode()
    assert not Workout.objects.exists()


def test_workout_rejects_out_of_range_duration(client_in, squat):
    response = client_in.post(
        reverse("planner:workout_new"),
        {
            "name": "Legs",
            "rest_seconds": 15,
            "rounds": 1,
            "round_rest_seconds": 90,
            "items": items_json((squat, 4)),
        },
    )
    assert "between 5 and 3600 seconds" in response.content.decode()


def test_edit_page_loads_existing_items(client_in, squat):
    workout = Workout.objects.create(name="Legs")
    WorkoutItem.objects.create(workout=workout, exercise=squat, order=0, duration_seconds=40)
    response = client_in.get(reverse("planner:workout_edit", args=[workout.uuid]))
    assert response.context["builder"]["items"] == [{"exercise": str(squat.uuid), "dur": 40}]


def test_toggle_hides_and_shows_a_workout(client_in):
    workout = Workout.objects.create(name="Legs")
    url = reverse("planner:workout_toggle", args=[workout.uuid])
    client_in.post(url)
    workout.refresh_from_db()
    assert workout.is_active is False
    client_in.post(url)
    workout.refresh_from_db()
    assert workout.is_active is True


def test_toggle_needs_post(client_in):
    workout = Workout.objects.create(name="Legs")
    response = client_in.get(reverse("planner:workout_toggle", args=[workout.uuid]))
    assert response.status_code == 405


def test_delete_workout_asks_then_deletes(client_in):
    workout = Workout.objects.create(name="Legs")
    url = reverse("planner:workout_delete", args=[workout.uuid])
    assert "Legs" in client_in.get(url).content.decode()
    response = client_in.post(url)
    assert response["Location"] == reverse("planner:workouts")
    assert not Workout.objects.exists()


def test_unused_exercise_can_be_deleted(client_in, squat):
    url = reverse("planner:exercise_delete", args=[squat.uuid])
    assert client_in.get(url).status_code == 200
    client_in.post(url)
    assert not Exercise.objects.filter(pk=squat.pk).exists()


def test_exercise_list_filters(client_in, squat, swing):
    url = reverse("planner:exercises")
    by_type = client_in.get(url, {"type": "aerobic"}).context["exercises"]
    assert list(by_type) == [swing]
    squat.muscles.add(MuscleGroup.objects.create(name="Quads"))
    by_muscle = client_in.get(url, {"q": "quad"}).context["exercises"]
    assert list(by_muscle) == [squat]


def test_edit_exercise_from_the_form(client_in, squat):
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    assert client_in.get(url).status_code == 200
    response = client_in.post(
        url, {"name": "Bulgarian split squat", "types": ["strength"], "default_duration": 50}
    )
    assert response["Location"] == reverse("planner:exercises")
    squat.refresh_from_db()
    assert squat.name == "Bulgarian split squat"
    assert squat.one_sided is False


def test_invalid_exercise_form_shows_errors(client_in):
    response = client_in.post(reverse("planner:exercise_new"), {"name": "Plank"})
    assert response.status_code == 200
    assert "Pick at least one type." in response.content.decode()


@pytest.mark.parametrize(("seconds", "text"), [(None, "0:00"), (5, "0:05"), (125.4, "2:05")])
def test_mmss_filter(seconds, text):
    from planner.templatetags.planner import mmss

    assert mmss(seconds) == text


def _workouts_with_items(count, exercises):
    for n in range(count):
        workout = Workout.objects.create(name=f"Workout {n}")
        for order, ex in enumerate(exercises):
            WorkoutItem.objects.create(
                workout=workout, exercise=ex, order=order, duration_seconds=30
            )


# Query counts are fixed whatever the number of rows: a new N+1 query fails
# these. Each includes the session and user lookups for the signed-in request.
@pytest.mark.parametrize("workouts", [1, 10])
def test_workout_list_query_count(client_in, squat, swing, django_assert_num_queries, workouts):
    _workouts_with_items(workouts, [squat, swing])
    with django_assert_num_queries(5):
        client_in.get(reverse("planner:workouts"))


@pytest.mark.parametrize("workouts", [1, 10])
def test_exercise_list_query_count(client_in, squat, swing, django_assert_num_queries, workouts):
    _workouts_with_items(workouts, [squat, swing])
    with django_assert_num_queries(7):
        client_in.get(reverse("planner:exercises"))


@pytest.mark.parametrize("extra", [0, 10])
def test_builder_query_count(client_in, squat, django_assert_num_queries, extra):
    for n in range(extra):
        Exercise.objects.create(name=f"Move {n}").types.add(ExerciseType.objects.first())
    with django_assert_num_queries(9):
        client_in.get(reverse("planner:workout_new"))
