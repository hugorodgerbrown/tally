import json
import uuid

import pytest
from django.urls import reverse

from activity.models import ActivitySession, DiscardedSession
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
        "workoutId": str(workout.uuid),
        "workoutName": workout.name,
        "startedAt": "2026-10-02T07:00:00Z",
        "endedAt": "2026-10-02T07:02:00Z",
        "completed": True,
        "rounds": 1,
        "effort": None,
        "entries": [{"exerciseId": str(item.exercise.uuid), "name": "Split squat", "seconds": 80}],
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
    assert response["Location"].startswith(reverse("activity:login"))


def test_activity_login_returns_to_activity(client, user):
    response = client.post(reverse("activity:login"), {"username": user.username, "password": "pw"})
    assert response["Location"] == reverse("activity:app")


def test_workouts_payload(client_in, workout):
    data = client_in.get(reverse("activity:api_workouts")).json()
    (w,) = data["workouts"]
    assert w["id"] == str(workout.uuid)
    assert w["name"] == "Legs"
    assert w["rounds"] == 1
    assert w["roundRest"] == 120
    assert w["rest"] == 15
    assert w["items"][0] == {
        "exerciseId": str(workout.items.get().exercise.uuid),
        "name": "Split squat",
        "dur": 40,
        "sides": True,
        "equipment": "",
        "movement": "dynamic",
        "types": ["strength"],
        "muscles": [],
    }
    # Icons travel with the library, like type colours, so the phone works offline.
    kit = {e["slug"]: e for e in data["equipment"]}
    assert set(kit) == {"kettlebell", "dumbbell"}
    assert kit["kettlebell"]["svg"].startswith('<svg class="eq"')
    assert 'aria-label="Kettlebell"' in kit["kettlebell"]["svg"]


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
    payload = session_payload(workout, workoutId=str(uuid.uuid4()))
    payload["entries"][0]["exerciseId"] = str(uuid.uuid4())
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


def test_discard_deletes_a_synced_session(client_in, workout):
    payload = session_payload(workout)
    post_sessions(client_in, [payload])
    result = post_sessions(client_in, [{"uuid": payload["uuid"], "discarded": True}]).json()
    assert result == {"saved": [], "discarded": [payload["uuid"]], "rejected": []}
    assert not ActivitySession.objects.exists()


def test_discard_of_an_unsynced_session_is_a_no_op(client_in, workout):
    gone = str(uuid.uuid4())
    keep = session_payload(workout)
    result = post_sessions(client_in, [{"uuid": gone, "discarded": True}, keep]).json()
    assert result["discarded"] == [gone]
    assert result["saved"] == [keep["uuid"]]
    assert ActivitySession.objects.count() == 1


def test_upload_after_discard_is_ignored(client_in, workout):
    payload = session_payload(workout)
    post_sessions(client_in, [{"uuid": payload["uuid"], "discarded": True}])
    # A late upload from another tab is acknowledged but not stored.
    assert post_sessions(client_in, [payload]).json()["saved"] == [payload["uuid"]]
    assert not ActivitySession.objects.exists()
    assert DiscardedSession.objects.filter(uuid=payload["uuid"]).exists()


def test_cannot_discard_another_users_session(client_in, workout, django_user_model):
    other = django_user_model.objects.create_user("other")
    theirs = ActivitySession.objects.create(
        user=other,
        workout_name="x",
        started_at="2026-10-01T07:00:00Z",
        ended_at="2026-10-01T07:01:00Z",
        completed=True,
    )
    post_sessions(client_in, [{"uuid": str(theirs.uuid), "discarded": True}])
    assert ActivitySession.objects.filter(pk=theirs.pk).exists()


def test_discard_with_bad_uuid_rejected(client_in, workout):
    result = post_sessions(client_in, [{"uuid": "nope", "discarded": True}]).json()
    assert result["rejected"][0]["uuid"] == "nope"


def test_service_worker_lists_assets(client, db):
    response = client.get(reverse("activity:service_worker"))
    assert reverse("activity:service_worker") == "/activity/sw.js"
    assert b"/static/activity/app.js" in response.content


def test_old_service_worker_retires_itself(client, db):
    response = client.get("/sw.js")
    assert response["Content-Type"] == "text/javascript"
    assert b"registration.unregister()" in response.content


@pytest.mark.parametrize(
    "overrides",
    [
        {"startedAt": "not a date"},
        {"endedAt": None},
        {"uuid": "nope"},
        {"workoutName": None, "entries": [{"seconds": "x"}]},
    ],
)
def test_session_with_bad_fields_rejected(client_in, workout, overrides):
    result = post_sessions(client_in, [session_payload(workout, **overrides)]).json()
    assert result["saved"] == []
    assert len(result["rejected"]) == 1


def test_non_dict_session_rejected(client_in, workout):
    result = post_sessions(client_in, ["junk"]).json()
    assert result["saved"] == []
    assert [r["uuid"] for r in result["rejected"]] == [None]


@pytest.mark.parametrize("body", ["not json", "{}", "[]"])
def test_sessions_bad_request(client_in, body):
    response = client_in.post(
        reverse("activity:api_sessions"), data=body, content_type="application/json"
    )
    assert response.status_code == 400


def test_zero_second_entries_are_dropped(client_in, workout):
    payload = session_payload(workout, effort=7)
    payload["entries"].append({"exerciseId": "", "name": "Skipped", "seconds": 0})
    post_sessions(client_in, [payload])
    session = ActivitySession.objects.get()
    assert session.effort == 7
    assert session.seconds_worked == 80
    assert [e.exercise_name for e in session.entries.all()] == ["Split squat"]
    assert str(session).startswith("Legs 2026-10-02")
    assert str(session.entries.get()) == "Split squat: 80s"


def test_inactive_and_empty_workouts_are_not_sent(client_in, workout):
    Workout.objects.create(name="Empty")
    Workout.objects.create(name="Hidden", is_active=False)
    names = [w["name"] for w in client_in.get(reverse("activity:api_workouts")).json()["workouts"]]
    assert names == ["Legs"]


def test_app_shell_and_manifest(client_in):
    assert client_in.get(reverse("activity:app")).status_code == 200
    response = client_in.get(reverse("activity:manifest"))
    assert response["Content-Type"] == "application/manifest+json"


def test_manifest_scopes_the_app_to_activity(client):
    """Only Activity is the installed app; Manage opens in the browser."""
    data = json.loads(client.get(reverse("activity:manifest")).content)
    assert data["id"] == "/"  # unchanged, so existing installs update in place
    assert reverse("activity:manifest") == "/manifest.webmanifest"
    assert data["start_url"] == "/activity/"
    assert data["scope"] == "/activity/"
    assert data["display"] == "standalone"
    sizes = {i["sizes"] for i in data["icons"] if i["purpose"] == "any"}
    assert {"192x192", "512x512"} <= sizes


def test_assets_version_is_cached_outside_debug(settings):
    from activity import views

    settings.DEBUG = False
    views._cached_hash_assets.cache_clear()
    assert views.assets_version() == views._hash_assets()


def test_missing_asset_is_a_configuration_error(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    from activity import views

    monkeypatch.setattr(views, "APP_ASSETS", ["activity/missing.js"])
    with pytest.raises(ImproperlyConfigured):
        views._hash_assets()


# The API's query counts stay fixed as workouts and sessions grow.
@pytest.mark.parametrize("copies", [1, 10])
def test_workouts_api_query_count(client_in, workout, django_assert_num_queries, copies):
    for n in range(copies):
        w = Workout.objects.create(name=f"Copy {n}")
        WorkoutItem.objects.create(
            workout=w, exercise=workout.items.get().exercise, duration_seconds=30
        )
    with django_assert_num_queries(8):
        client_in.get(reverse("activity:api_workouts"))


@pytest.mark.parametrize("count", [1, 10])
def test_sessions_api_query_count(client_in, workout, django_assert_num_queries, count):
    sessions = [session_payload(workout) for _ in range(count)]
    # 5 per request (session, user, discarded, workouts, exercises), then 7 per
    # session for its transaction, upsert and entries. Batches are small.
    with django_assert_num_queries(5 + 7 * count):
        post_sessions(client_in, sessions)
