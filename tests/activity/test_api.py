"""Tests for the phone app's JSON endpoints: the workouts feed and session uploads."""

import json
import uuid
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.activity.models import ActivitySession, DiscardedSession
from apps.library.models import Workout
from tests.factories import (
    ActivitySessionFactory,
    ExerciseFactory,
    UserFactory,
    WorkoutFactory,
    WorkoutItemFactory,
)

pytestmark = pytest.mark.django_db

WORKOUTS = reverse("activity:api_workouts")
SESSIONS = reverse("activity:api_sessions")


@pytest.fixture
def workout(user: Any) -> Workout:
    """The user's one-item workout, Legs: a one-sided split squat for 40 seconds."""
    squat = ExerciseFactory.create(owner=user, name="Split squat", one_sided=True)
    item = WorkoutItemFactory.create(workout__owner=user, workout__name="Legs", exercise=squat)
    workout: Workout = item.workout
    return workout


def session_payload(workout: Workout, **overrides: Any) -> dict[str, Any]:
    """Return a session as the phone uploads it, with ``overrides`` applied."""
    item = workout.items.get()
    data: dict[str, Any] = {
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


def post_sessions(client: Client, sessions: list[Any]) -> Any:
    """Upload ``sessions`` in one batch."""
    return client.post(
        SESSIONS, data=json.dumps({"sessions": sessions}), content_type="application/json"
    )


def test_api_needs_sign_in(client: Client, db: None) -> None:
    """Signed out, both endpoints answer 401 so the outbox waits."""
    assert client.get(WORKOUTS).status_code == 401
    assert post_sessions(client, []).status_code == 401


def test_workouts_payload(signed_in: Client, workout: Workout) -> None:
    """The feed has everything the engine plays, plus the icons, for offline use."""
    data = signed_in.get(WORKOUTS).json()
    (w,) = data["workouts"]
    assert (w["id"], w["name"], w["rounds"], w["roundRest"], w["rest"]) == (
        str(workout.uuid),
        "Legs",
        1,
        120,
        15,
    )
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
    kit = {e["slug"]: e for e in data["equipment"]}
    assert set(kit) == {"kettlebell", "dumbbell"}
    assert {t["slug"] for t in data["types"]} >= {"strength", "aerobic"}


def test_only_my_active_workouts_with_items_are_sent(
    signed_in: Client, user: Any, workout: Workout
) -> None:
    """Empty, retired and other accounts' workouts stay off the phone."""
    WorkoutFactory.create(owner=user, name="Empty")
    WorkoutItemFactory.create(workout__owner=user, workout__name="Hidden", workout__is_active=False)
    WorkoutItemFactory.create(workout__name="Someone else's")
    names = [w["name"] for w in signed_in.get(WORKOUTS).json()["workouts"]]
    assert names == ["Legs"]


def test_session_upsert_is_idempotent(signed_in: Client, user: Any, workout: Workout) -> None:
    """A retry that adds the effort score updates the same record."""
    payload = session_payload(workout)
    assert post_sessions(signed_in, [payload]).json()["saved"] == [payload["uuid"]]
    payload["effort"] = 7
    post_sessions(signed_in, [payload])
    session = ActivitySession.objects.get()
    assert (session.owner, session.effort, session.seconds_worked) == (user, 7, 80)
    assert session.workout == workout
    assert session.entries.count() == 1


def test_malformed_session_rejected(signed_in: Client, workout: Workout) -> None:
    """One bad session in a batch doesn't stop the good ones."""
    bad = session_payload(workout, effort=11)
    good = session_payload(workout)
    result = post_sessions(signed_in, [bad, good]).json()
    assert result["saved"] == [good["uuid"]]
    assert result["rejected"][0]["uuid"] == bad["uuid"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"startedAt": "not a date"},
        {"endedAt": None},
        {"uuid": "nope"},
        {"workoutName": None, "entries": [{"seconds": "x"}]},
    ],
)
def test_session_with_bad_fields_rejected(
    signed_in: Client, workout: Workout, overrides: dict[str, Any]
) -> None:
    """Each malformed field rejects its session."""
    result = post_sessions(signed_in, [session_payload(workout, **overrides)]).json()
    assert result["saved"] == []
    assert len(result["rejected"]) == 1


def test_non_dict_session_rejected(signed_in: Client, workout: Workout) -> None:
    """Junk in the list is rejected without a uuid."""
    result = post_sessions(signed_in, ["junk"]).json()
    assert [r["uuid"] for r in result["rejected"]] == [None]


@pytest.mark.parametrize("body", ["not json", "{}", "[]"])
def test_sessions_bad_request(signed_in: Client, body: str) -> None:
    """A body that isn't a batch is a 400."""
    response = signed_in.post(SESSIONS, data=body, content_type="application/json")
    assert response.status_code == 400


def test_session_survives_deleted_workout(signed_in: Client, workout: Workout) -> None:
    """Unknown workout and exercise ids are stored as names only."""
    payload = session_payload(workout, workoutId=str(uuid.uuid4()))
    payload["entries"][0]["exerciseId"] = str(uuid.uuid4())
    assert post_sessions(signed_in, [payload]).json()["saved"]
    session = ActivitySession.objects.get()
    assert session.workout is None
    assert session.entries.get().exercise is None


def test_another_accounts_workout_is_not_linked(signed_in: Client, workout: Workout) -> None:
    """A session can't attach itself to someone else's workout or exercise."""
    theirs = WorkoutItemFactory.create()
    payload = session_payload(workout, workoutId=str(theirs.workout.uuid))
    payload["entries"][0]["exerciseId"] = str(theirs.exercise.uuid)
    post_sessions(signed_in, [payload])
    session = ActivitySession.objects.get()
    assert session.workout is None
    assert session.entries.get().exercise is None


def test_zero_second_entries_are_dropped(signed_in: Client, workout: Workout) -> None:
    """Skipped exercises aren't logged."""
    payload = session_payload(workout, effort=7)
    payload["entries"].append({"exerciseId": "", "name": "Skipped", "seconds": 0})
    post_sessions(signed_in, [payload])
    session = ActivitySession.objects.get()
    assert session.seconds_worked == 80
    assert [e.exercise_name for e in session.entries.all()] == ["Split squat"]
    assert str(session).startswith("Legs 2026-10-02")
    assert str(session.entries.get()) == "Split squat: 80s"


def test_cannot_overwrite_another_accounts_session(signed_in: Client, workout: Workout) -> None:
    """An upload with someone else's uuid is refused."""
    theirs = ActivitySessionFactory.create()
    payload = session_payload(workout, uuid=str(theirs.uuid))
    result = post_sessions(signed_in, [payload]).json()
    assert result["rejected"] == [{"uuid": str(theirs.uuid), "error": "not_owner"}]


def test_discard_deletes_a_synced_session(signed_in: Client, workout: Workout) -> None:
    """A tombstone deletes the stored session."""
    payload = session_payload(workout)
    post_sessions(signed_in, [payload])
    result = post_sessions(signed_in, [{"uuid": payload["uuid"], "discarded": True}]).json()
    assert result == {"saved": [], "discarded": [payload["uuid"]], "rejected": []}
    assert not ActivitySession.objects.exists()


def test_discard_of_an_unsynced_session_is_a_no_op(signed_in: Client, workout: Workout) -> None:
    """A tombstone for a session never uploaded is acknowledged."""
    gone = str(uuid.uuid4())
    keep = session_payload(workout)
    result = post_sessions(signed_in, [{"uuid": gone, "discarded": True}, keep]).json()
    assert result["discarded"] == [gone]
    assert result["saved"] == [keep["uuid"]]


def test_upload_after_discard_is_ignored(signed_in: Client, workout: Workout) -> None:
    """A late upload from another tab is acknowledged but not stored."""
    payload = session_payload(workout)
    post_sessions(signed_in, [{"uuid": payload["uuid"], "discarded": True}])
    assert post_sessions(signed_in, [payload]).json()["saved"] == [payload["uuid"]]
    assert not ActivitySession.objects.exists()
    assert DiscardedSession.objects.filter(uuid=payload["uuid"]).exists()


def test_cannot_discard_another_accounts_session(signed_in: Client) -> None:
    """Their session stays, and no tombstone is left that would block them later."""
    theirs = ActivitySessionFactory.create()
    result = post_sessions(signed_in, [{"uuid": str(theirs.uuid), "discarded": True}]).json()
    assert result["rejected"][0]["error"] == "not_owner"
    assert ActivitySession.objects.filter(pk=theirs.pk).exists()
    assert not DiscardedSession.objects.exists()


def test_cannot_reuse_another_accounts_tombstone(signed_in: Client) -> None:
    """A uuid someone else discarded is theirs."""
    other = UserFactory.create()
    gone = DiscardedSession.objects.create(owner=other)
    result = post_sessions(signed_in, [{"uuid": str(gone.uuid), "discarded": True}]).json()
    assert result["rejected"][0]["error"] == "not_owner"


def test_discard_with_bad_uuid_rejected(signed_in: Client) -> None:
    """A tombstone needs a real uuid."""
    result = post_sessions(signed_in, [{"uuid": "nope", "discarded": True}]).json()
    assert result["rejected"][0]["uuid"] == "nope"


@pytest.mark.parametrize("copies", [1, 10])
def test_workouts_query_count_is_flat(
    signed_in: Client,
    user: Any,
    workout: Workout,
    django_assert_max_num_queries: Any,
    copies: int,
) -> None:
    """The feed's queries don't grow with the number of workouts."""
    for _ in range(copies):
        WorkoutItemFactory.create(workout__owner=user, exercise=workout.items.get().exercise)
    with django_assert_max_num_queries(10):
        signed_in.get(WORKOUTS)


def _made(workout: Workout, days_ago: int) -> None:
    """Backdate ``workout``'s creation by ``days_ago`` days."""
    Workout.objects.filter(pk=workout.pk).update(
        created_at=timezone.now() - timedelta(days=days_ago)
    )


def test_one_offs_drop_off_the_phone_after_a_week(
    signed_in: Client, user: Any, workout: Workout
) -> None:
    """Saved workouts stay; one-offs are sent for seven days after they're made."""
    exercise = workout.items.get().exercise
    for name, days in [("Today", 0), ("Six days", 6), ("Eight days", 8)]:
        item = WorkoutItemFactory.create(
            workout__owner=user, workout__name=name, workout__one_off=True, exercise=exercise
        )
        _made(item.workout, days)
    _made(workout, 30)
    data = signed_in.get(WORKOUTS).json()
    assert data["oneOffDays"] == 7
    assert [(w["name"], w["oneOff"]) for w in data["workouts"]] == [
        ("Legs", False),
        ("Six days", True),
        ("Today", True),
    ]


def test_keep_turns_a_one_off_into_a_saved_workout(signed_in: Client, workout: Workout) -> None:
    """Keep makes an old one-off a saved workout, back on the phone."""
    Workout.objects.filter(pk=workout.pk).update(one_off=True)
    _made(workout, 30)
    assert signed_in.get(WORKOUTS).json()["workouts"] == []
    url = reverse("activity:api_keep_workout", args=[workout.uuid])
    assert signed_in.post(url).json() == {"kept": str(workout.uuid)}
    workout.refresh_from_db()
    assert workout.one_off is False
    (sent,) = signed_in.get(WORKOUTS).json()["workouts"]
    assert sent["oneOff"] is False


def test_keep_unknown_or_another_accounts_workout(signed_in: Client) -> None:
    """An unknown uuid, or another account's workout, is a 404 and changes nothing."""
    theirs = WorkoutFactory.create(one_off=True)
    for workout_id in (uuid.uuid4(), theirs.uuid):
        url = reverse("activity:api_keep_workout", args=[workout_id])
        assert signed_in.post(url).status_code == 404
    theirs.refresh_from_db()
    assert theirs.one_off is True


def test_keep_needs_sign_in_and_post(client: Client, signed_in: Client, workout: Workout) -> None:
    """Keep is POST only, and a signed-out request gets a 401."""
    url = reverse("activity:api_keep_workout", args=[workout.uuid])
    assert signed_in.get(url).status_code == 405
    signed_in.logout()
    assert client.post(url).status_code == 401
