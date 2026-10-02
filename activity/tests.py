import json
import uuid

import pytest
from django.urls import reverse

from activity.models import ActivitySession
from library.models import Exercise, ExerciseType, Workout, WorkoutItem


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user("hugo", password="pw")


@pytest.fixture
def client_in(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def workout(db):
    strength = ExerciseType.objects.get(slug="strength")
    squat = Exercise.objects.create(name="Split squat", one_sided=True)
    squat.types.add(strength)
    w = Workout.objects.create(name="Legs")
    WorkoutItem.objects.create(workout=w, exercise=squat, duration_seconds=40)
    return w


def session_payload(workout, **overrides):
    item = workout.items.get()
    data = {
        "uuid": str(uuid.uuid4()),
        "workoutId": workout.pk,
        "workoutName": workout.name,
        "startedAt": "2026-10-02T07:00:00Z",
        "endedAt": "2026-10-02T07:02:00Z",
        "completed": True,
        "rounds": 1,
        "effort": None,
        "entries": [{"exerciseId": item.exercise_id, "name": "Split squat", "seconds": 80}],
    }
    data.update(overrides)
    return data


def post_sessions(client, sessions):
    return client.post(
        reverse("activity:api_sessions"),
        data=json.dumps({"sessions": sessions}),
        content_type="application/json",
    )


def test_exercise_types_seeded(db):
    assert set(ExerciseType.objects.values_list("slug", flat=True)) == {
        "aerobic",
        "anaerobic",
        "strength",
        "flexibility",
        "fitness",
    }


def test_api_requires_login(client, db):
    assert client.get(reverse("activity:api_workouts")).status_code == 401


def test_app_redirects_to_login(client, db):
    response = client.get(reverse("activity:app"))
    assert response.status_code == 302
    assert "/admin/login/" in response["Location"]


def test_workouts_payload(client_in, workout):
    data = client_in.get(reverse("activity:api_workouts")).json()
    (w,) = data["workouts"]
    assert w["name"] == "Legs"
    assert w["rounds"] == 1 and w["roundRest"] == 120 and w["rest"] == 15
    assert w["items"][0] == {
        "exerciseId": workout.items.get().exercise_id,
        "name": "Split squat",
        "dur": 40,
        "sides": True,
        "types": ["strength"],
        "muscles": [],
    }


def test_session_upsert_is_idempotent(client_in, workout, user):
    payload = session_payload(workout)
    assert post_sessions(client_in, [payload]).json()["saved"] == [payload["uuid"]]
    # A retry that adds the effort score updates the same record.
    payload["effort"] = 7
    post_sessions(client_in, [payload])
    session = ActivitySession.objects.get()
    assert session.user == user
    assert session.effort == 7
    assert session.seconds_worked == 80
    assert session.entries.count() == 1


def test_malformed_session_rejected(client_in, workout):
    bad = session_payload(workout, effort=11)
    good = session_payload(workout)
    result = post_sessions(client_in, [bad, good]).json()
    assert result["saved"] == [good["uuid"]]
    assert result["rejected"][0]["uuid"] == bad["uuid"]


def test_session_survives_deleted_workout(client_in, workout):
    payload = session_payload(workout, workoutId=9999)
    payload["entries"][0]["exerciseId"] = 9999
    assert post_sessions(client_in, [payload]).json()["saved"]
    session = ActivitySession.objects.get()
    assert session.workout is None
    assert session.entries.get().exercise is None


def test_cannot_overwrite_another_users_session(client_in, workout, django_user_model):
    other = django_user_model.objects.create_user("other")
    payload = session_payload(workout)
    ActivitySession.objects.create(
        uuid=payload["uuid"],
        user=other,
        workout_name="x",
        started_at="2026-10-01T07:00:00Z",
        ended_at="2026-10-01T07:01:00Z",
        completed=True,
    )
    result = post_sessions(client_in, [payload]).json()
    assert result["rejected"] == [{"uuid": payload["uuid"], "error": "not_owner"}]


def test_service_worker_lists_assets(client, db):
    response = client.get(reverse("activity:service_worker"))
    assert response["Service-Worker-Allowed"] == "/"
    assert b"/static/activity/app.js" in response.content
