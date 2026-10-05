import base64
import datetime as dt
import hashlib
import json
import secrets
import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from django.core.cache import cache
from django.utils import timezone
from mcp_auth.testing import MCPAuthContract
from oauth2_provider.models import AccessToken, Application, set_token_value

from activity.models import ActivitySession, SessionEntry
from library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem

CALLBACK = "https://claude.ai/api/mcp/auth_callback"
MCP_URL = "http://testserver/mcp"


@pytest.fixture(autouse=True)
def fast_hashing(settings):
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    # The per-user MCP limit counts in the cache, which outlives each test.
    cache.clear()


@pytest.fixture
def hugo(django_user_model):
    return django_user_model.objects.create_superuser("hugo", password="pw")


@pytest.fixture
def token(hugo):
    app = Application.objects.create(
        name="Claude",
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris=CALLBACK,
    )
    raw = secrets.token_urlsafe(32)
    token = AccessToken(
        user=hugo,
        application=app,
        scope="tally",
        resource=[MCP_URL],
        expires=timezone.now() + dt.timedelta(hours=1),
    )
    set_token_value(token, raw)
    token.save()
    return raw


@pytest.fixture
def library(db):
    strength = ExerciseType.objects.get(slug="strength")
    flex = ExerciseType.objects.get(slug="flexibility")
    glutes = MuscleGroup.objects.create(name="Glutes")
    hips = MuscleGroup.objects.create(name="Hips")
    squat = Exercise.objects.create(name="Split squat", one_sided=True, default_duration=30)
    squat.types.add(strength)
    squat.muscles.add(glutes)
    ninety = Exercise.objects.create(name="90:90", default_duration=45)
    ninety.types.add(flex)
    ninety.muscles.add(hips, glutes)
    legs = Workout.objects.create(name="Legs", rest_seconds=10)
    WorkoutItem.objects.create(workout=legs, exercise=squat, order=0, duration_seconds=40)
    WorkoutItem.objects.create(workout=legs, exercise=ninety, order=1, duration_seconds=60)
    return {"squat": squat, "ninety": ninety, "legs": legs}


def rpc(client, token, method, params=None, msg_id=1):
    body = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        body["params"] = params
    return client.post(
        "/mcp",
        data=json.dumps(body),
        content_type="application/json",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/event-stream",
        },
    )


def call(client, token, name, /, **arguments):
    response = rpc(client, token, "tools/call", {"name": name, "arguments": arguments})
    assert response.status_code == 200, response.content
    return response.json()["result"]


# ---------- OAuth ----------


class TestMCPAuthContract(MCPAuthContract):
    """Claude's connector requirements, from the shared Titan suite."""

    mcp_path = "/mcp"

    def make_allowed_user(self, django_user_model):
        return django_user_model.objects.create_superuser("owner", password="pw")

    def make_refused_user(self, django_user_model):
        return django_user_model.objects.create_user("guest", password="pw")


def register(client, redirect_uris, auth_method="none"):
    return client.post(
        "/oauth/register/",
        data=json.dumps(
            {
                "client_name": "Claude",
                "redirect_uris": redirect_uris,
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": auth_method,
            }
        ),
        content_type="application/json",
    )


def test_full_connect_flow(client, hugo, library):
    """Register, sign in, approve, swap the code for a token, call a tool, refresh."""
    reg = register(client, [CALLBACK], auth_method="client_secret_post")
    assert reg.status_code == 201, reg.content
    client_id, client_secret = reg.json()["client_id"], reg.json()["client_secret"]

    verifier = secrets.token_urlsafe(48)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": CALLBACK,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": "xyz",
        "scope": "tally",
        "resource": MCP_URL,
    }
    # Signed out: off to the login page first.
    assert client.get("/oauth/authorize/", params).status_code == 302

    client.force_login(hugo)
    page = client.get("/oauth/authorize/", params)
    assert page.status_code == 200
    assert b"Connect Claude?" in page.content
    assert "form-action" not in page.get("Content-Security-Policy", "") or (
        "https://claude.ai" in page["Content-Security-Policy"]
    )

    form = page.context["form"].initial
    approved = client.post(
        "/oauth/authorize/", {**{k: v for k, v in form.items() if v}, "allow": "Authorize"}
    )
    assert approved.status_code == 302
    redirect = urlparse(approved["Location"])
    assert f"{redirect.scheme}://{redirect.netloc}{redirect.path}" == CALLBACK
    query = parse_qs(redirect.query)
    assert query["state"] == ["xyz"]
    assert query["iss"] == ["http://testserver"]

    client.logout()
    tokens = client.post(
        "/oauth/token/",
        {
            "grant_type": "authorization_code",
            "code": query["code"][0],
            "redirect_uri": CALLBACK,
            "client_id": client_id,
            "client_secret": client_secret,
            "code_verifier": verifier,
            "resource": MCP_URL,
        },
    )
    assert tokens.status_code == 200, tokens.content
    access = tokens.json()["access_token"]

    result = call(client, access, "list_workouts")
    assert [w["name"] for w in result["structuredContent"]["workouts"]] == ["Legs"]

    refreshed = client.post(
        "/oauth/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": tokens.json()["refresh_token"],
            "client_id": client_id,
            "client_secret": client_secret,
        },
    )
    assert refreshed.status_code == 200, refreshed.content
    assert call(client, refreshed.json()["access_token"], "list_workouts")["structuredContent"]


# ---------- protocol ----------


def test_initialize(client, token):
    response = rpc(client, token, "initialize", {"protocolVersion": "2025-06-18"})
    result = response.json()["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert result["serverInfo"]["name"] == "tally"
    assert "tools" in result["capabilities"]


def test_initialize_offers_latest_for_unknown_version(client, token):
    result = rpc(client, token, "initialize", {"protocolVersion": "1999-01-01"}).json()["result"]
    assert result["protocolVersion"] == "2025-11-25"


def test_notification_is_accepted(client, token):
    response = client.post(
        "/mcp",
        data=json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 202


def test_bad_json_and_unknown_method(client, token):
    bad = client.post(
        "/mcp",
        data="{",
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert bad.json()["error"]["code"] == -32700
    assert rpc(client, token, "nope").json()["error"]["code"] == -32601


def test_tools_list_marks_read_only_tools(client, token):
    tools = {t["name"]: t for t in rpc(client, token, "tools/list").json()["result"]["tools"]}
    assert tools["list_sessions"]["annotations"]["readOnlyHint"] is True
    assert tools["create_workout"]["annotations"]["readOnlyHint"] is False
    assert not any(t["annotations"]["destructiveHint"] for t in tools.values())
    assert not any("delete" in name for name in tools)


def test_unknown_tool(client, token):
    response = rpc(client, token, "tools/call", {"name": "drop_tables", "arguments": {}})
    assert response.json()["error"]["code"] == -32602


# ---------- read tools ----------


def test_list_exercises_filters(client, token, library):
    by_muscle = call(client, token, "list_exercises", muscle="hips")["structuredContent"]
    assert [e["name"] for e in by_muscle["exercises"]] == ["90:90"]
    by_type = call(client, token, "list_exercises", type="strength")["structuredContent"]
    assert [e["name"] for e in by_type["exercises"]] == ["Split squat"]


def test_get_workout_by_name_and_id(client, token, library):
    legs = library["legs"]
    by_name = call(client, token, "get_workout", workout="legs")["structuredContent"]
    by_id = call(client, token, "get_workout", workout=str(legs.uuid))["structuredContent"]
    assert by_name == by_id
    assert [i["exercise"] for i in by_name["items"]] == ["Split squat", "90:90"]
    # 5 ready + 40 + 5 switch + 40 + 10 rest + 60
    assert by_name["total_seconds"] == 160


def test_unknown_workout_is_a_tool_error(client, token, library):
    result = call(client, token, "get_workout", workout="Arms")
    assert result["isError"] is True
    assert "No workout matches" in result["content"][0]["text"]


def log_session(user, workout, day, entries, effort=None, completed=True):
    start = timezone.make_aware(dt.datetime.combine(day, dt.time(7)))
    session = ActivitySession.objects.create(
        user=user,
        workout=workout,
        workout_name=workout.name,
        started_at=start,
        ended_at=start + dt.timedelta(minutes=5),
        completed=completed,
        seconds_worked=sum(s for _, s in entries),
        effort=effort,
    )
    for i, (exercise, seconds) in enumerate(entries):
        SessionEntry.objects.create(
            session=session,
            exercise=exercise,
            exercise_name=exercise.name,
            order=i,
            seconds_worked=seconds,
        )
    return session


def test_sessions_and_summary(client, token, hugo, library):
    squat, ninety, legs = library["squat"], library["ninety"], library["legs"]
    ninety.movement = "static"
    ninety.save()
    log_session(hugo, legs, dt.date(2026, 9, 3), [(squat, 80), (ninety, 60)], effort=6)
    log_session(hugo, legs, dt.date(2026, 9, 30), [(squat, 40)], effort=8, completed=False)
    log_session(hugo, legs, dt.date(2026, 10, 1), [(ninety, 60)])

    september = {"start_date": "2026-09-01", "end_date": "2026-09-30"}
    sessions = call(client, token, "list_sessions", **september)["structuredContent"]
    assert len(sessions["sessions"]) == 2
    assert sessions["sessions"][0]["completed"] is False

    summary = call(client, token, "training_summary", **september)["structuredContent"]
    assert summary["sessions"] == 2
    assert summary["completed_sessions"] == 1
    assert summary["seconds_worked"] == 180
    assert summary["average_effort"] == 7.0
    assert summary["seconds_by_type"] == {"strength": 120, "flexibility": 60}
    assert summary["seconds_by_muscle"] == {"Glutes": 180, "Hips": 60}
    assert summary["seconds_by_movement"] == {"dynamic": 120, "static": 60}
    assert "aerobic" in summary["unused_types"]


def test_summary_rejects_bad_dates(client, token, db):
    result = call(client, token, "training_summary", start_date="Sept", end_date="2026-09-30")
    assert result["isError"] is True


def test_sessions_are_the_users_own(client, token, library, django_user_model):
    other = django_user_model.objects.create_user("other")
    log_session(other, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    assert call(client, token, "list_sessions")["structuredContent"]["sessions"] == []


# ---------- write tools ----------


def test_create_exercise(client, token, library):
    result = call(
        client,
        token,
        "create_exercise",
        name="Cat-cow",
        types=["flexibility"],
        muscles=["spine", "hips"],
        default_duration=45,
    )["structuredContent"]
    assert result["muscles"] == ["Hips", "Spine"]
    exercise = Exercise.objects.get(uuid=uuid.UUID(result["id"]))
    assert exercise.default_duration == 45
    assert MuscleGroup.objects.filter(name="Hips").count() == 1


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"name": "Split squat", "types": ["strength"]}, "already exists"),
        ({"name": "Plank", "types": ["yoga"]}, "Unknown type yoga"),
        ({"name": "Plank", "types": []}, "at least one type"),
        ({"name": "Plank"}, "Missing types"),
        ({"name": "Plank", "types": ["strength"], "default_duration": 2}, "default_duration"),
    ],
)
def test_create_exercise_errors(client, token, library, args, message):
    result = call(client, token, "create_exercise", **args)
    assert result["isError"] is True
    assert message in result["content"][0]["text"]
    assert not Exercise.objects.filter(name="Plank").exists()


def test_update_exercise_changes_only_given_fields(client, token, library):
    result = call(
        client, token, "update_exercise", exercise="split SQUAT", name="Bulgarian split squat"
    )["structuredContent"]
    assert result["name"] == "Bulgarian split squat"
    assert result["types"] == ["strength"]
    assert result["one_sided"] is True


def test_create_workout(client, token, library):
    result = call(
        client,
        token,
        "create_workout",
        name="Mobility",
        rounds=2,
        items=[{"exercise": "90:90"}, {"exercise": "Split squat", "duration_seconds": 20}],
    )["structuredContent"]
    assert [(i["exercise"], i["duration_seconds"]) for i in result["items"]] == [
        ("90:90", 45),
        ("Split squat", 20),
    ]
    assert result["rounds"] == 2
    assert result["is_active"] is True


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"name": "X", "items": []}, "at least one exercise"),
        ({"name": "X", "items": [{"exercise": "Burpee"}]}, "No exercise matches"),
        ({"name": "X", "items": [{"exercise": "90:90", "duration_seconds": 1}]}, "duration"),
        ({"name": "X", "rounds": 0, "items": [{"exercise": "90:90"}]}, "rounds"),
        ({"name": "", "items": [{"exercise": "90:90"}]}, "name"),
    ],
)
def test_create_workout_errors(client, token, library, args, message):
    result = call(client, token, "create_workout", **args)
    assert result["isError"] is True
    assert message in result["content"][0]["text"]
    assert Workout.objects.count() == 1


def test_update_workout_replaces_items_and_can_deactivate(client, token, library):
    result = call(
        client,
        token,
        "update_workout",
        workout="Legs",
        is_active=False,
        items=[{"exercise": "90:90", "duration_seconds": 90}],
    )["structuredContent"]
    assert result["is_active"] is False
    assert [(i["exercise"], i["duration_seconds"]) for i in result["items"]] == [("90:90", 90)]
    assert result["rest_seconds"] == 10
    assert call(client, token, "list_workouts")["structuredContent"]["workouts"] == []


@pytest.mark.parametrize(
    ("body", "headers"),
    [
        ({"jsonrpc": "2.0", "id": 1, "method": "ping"}, {"MCP-Protocol-Version": "2020-01-01"}),
        ([{"jsonrpc": "2.0", "id": 1, "method": "ping"}], {}),
        ({"id": 1, "method": "ping"}, {}),
    ],
)
def test_invalid_requests(client, token, body, headers):
    response = client.post(
        "/mcp",
        data=json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}", **headers},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32600


def test_ping_and_bad_params(client, token):
    assert rpc(client, token, "ping").json()["result"] == {}
    assert rpc(client, token, "tools/list", params=[1]).json()["error"]["code"] == -32602
    bad_args = rpc(client, token, "tools/call", {"name": "get_workout", "arguments": [1]})
    assert bad_args.json()["error"]["code"] == -32602


def test_missing_argument_is_a_tool_error(client, token, db):
    result = call(client, token, "get_workout")
    assert result["isError"] is True
    assert "Missing argument 'workout'" in result["content"][0]["text"]


def test_list_types_and_muscles(client, token, library):
    result = call(client, token, "list_types_and_muscles")["structuredContent"]
    assert "strength" in [t["slug"] for t in result["types"]]
    assert result["muscles"] == ["Glutes", "Hips"]
    assert result["equipment"] == [
        {"slug": "kettlebell", "name": "Kettlebell"},
        {"slug": "dumbbell", "name": "Dumbbell"},
    ]
    assert result["movements"] == [
        {"slug": "dynamic", "name": "Dynamic"},
        {"slug": "static", "name": "Static"},
    ]


def test_tag_and_filter_by_movement(client, token, library):
    assert (
        call(client, token, "get_exercise", exercise="90:90")["structuredContent"]["movement"]
        == "dynamic"
    )
    result = call(client, token, "update_exercise", exercise="90:90", movement="static")
    assert result["structuredContent"]["movement"] == "static"
    found = call(client, token, "list_exercises", movement="static")["structuredContent"]
    assert [e["name"] for e in found["exercises"]] == ["90:90"]
    workout = call(client, token, "get_workout", workout="Legs")["structuredContent"]
    assert {i["exercise"]: i["movement"] for i in workout["items"]}["Split squat"] == "dynamic"


def test_tag_and_filter_by_equipment(client, token, library):
    result = call(client, token, "update_exercise", exercise="Split squat", equipment="dumbbell")[
        "structuredContent"
    ]
    assert result["equipment"] == "dumbbell"
    found = call(client, token, "list_exercises", equipment="dumbbell")["structuredContent"]
    assert [e["name"] for e in found["exercises"]] == ["Split squat"]
    bodyweight = call(client, token, "list_exercises", equipment="")["structuredContent"]
    assert "Split squat" not in [e["name"] for e in bodyweight["exercises"]]
    workout = call(client, token, "get_workout", workout="Legs")["structuredContent"]
    assert {i["exercise"]: i["equipment"] for i in workout["items"]}["Split squat"] == "dumbbell"
    cleared = call(client, token, "update_exercise", exercise="Split squat", equipment="")
    assert cleared["structuredContent"]["equipment"] == ""


def test_list_exercises_by_query(client, token, library):
    result = call(client, token, "list_exercises", query="squat")["structuredContent"]
    assert [e["name"] for e in result["exercises"]] == ["Split squat"]


def test_get_exercise_with_usage(client, token, hugo, library):
    log_session(hugo, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    result = call(client, token, "get_exercise", exercise="Split squat")["structuredContent"]
    assert result["used_in_workouts"] == [{"id": str(library["legs"].uuid), "name": "Legs"}]
    assert result["sessions_logged"] == 1
    assert result["seconds_logged"] == 80


def test_ambiguous_workout_name(client, token, library):
    Workout.objects.create(name="LEGS")
    result = call(client, token, "get_workout", workout="legs")
    assert "More than one workout" in result["content"][0]["text"]


def test_sessions_by_workout_with_limit(client, token, hugo, library):
    other = Workout.objects.create(name="Arms")
    for day in (1, 2, 3):
        log_session(hugo, library["legs"], dt.date(2026, 9, day), [(library["squat"], 40)])
    log_session(hugo, other, dt.date(2026, 9, 4), [(library["squat"], 40)])
    result = call(client, token, "list_sessions", workout="Legs", limit=2)["structuredContent"]
    assert len(result["sessions"]) == 2
    assert result["truncated"] is True
    assert {s["workout"] for s in result["sessions"]} == {"Legs"}


def test_summary_counts_deleted_exercises_as_unknown(client, token, hugo, library):
    session = log_session(hugo, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    session.entries.update(exercise=None)
    summary = call(
        client, token, "training_summary", start_date="2026-09-01", end_date="2026-09-30"
    )["structuredContent"]
    assert summary["seconds_by_type"] == {"unknown": 80}
    assert summary["seconds_by_movement"] == {"unknown": 80}
    assert summary["seconds_by_exercise"] == {"Split squat": 80}


def test_update_exercise_all_fields(client, token, library):
    result = call(
        client,
        token,
        "update_exercise",
        exercise=str(library["ninety"].uuid),
        description="Sit with both knees at 90 degrees.",
        one_sided=True,
        types=["flexibility", "strength"],
        muscles=["Hips", " "],
    )["structuredContent"]
    assert result["one_sided"] is True
    assert result["description"].startswith("Sit")
    assert sorted(result["types"]) == ["flexibility", "strength"]
    assert result["muscles"] == ["Hips"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"name": " "}, "name is empty"),
        ({"muscles": "Hips"}, "muscles must be a list"),
        ({"equipment": "barbell"}, "equipment must be one of kettlebell, dumbbell"),
        ({"movement": "plyometric"}, "movement must be one of dynamic, static"),
    ],
)
def test_update_exercise_errors(client, token, library, args, message):
    result = call(client, token, "update_exercise", exercise="90:90", **args)
    assert message in result["content"][0]["text"]


def test_update_workout_settings(client, token, library):
    result = call(
        client,
        token,
        "update_workout",
        workout="Legs",
        description="Lower body",
        rest_seconds=0,
        round_rest_seconds=60,
    )["structuredContent"]
    assert (result["description"], result["rest_seconds"], result["round_rest_seconds"]) == (
        "Lower body",
        0,
        60,
    )
    bad = call(client, token, "update_workout", workout="Legs", items=[{"duration_seconds": 30}])
    assert "items[0] needs an exercise" in bad["content"][0]["text"]


def test_summary_shares_time_between_types(client, token, hugo, library):
    squat = library["squat"]
    squat.types.add(ExerciseType.objects.get(slug="flexibility"))
    log_session(hugo, library["legs"], dt.date(2026, 9, 3), [(squat, 81)])
    summary = call(
        client, token, "training_summary", start_date="2026-09-01", end_date="2026-09-30"
    )["structuredContent"]
    assert summary["seconds_by_type"] == {"strength": 40, "flexibility": 40}
    assert summary["seconds_by_muscle"] == {"Glutes": 81}


def test_workout_counts_are_the_users_own(client, token, hugo, library, django_user_model):
    other = django_user_model.objects.create_user("other")
    log_session(other, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    legs = call(client, token, "get_workout", workout="Legs")["structuredContent"]
    assert (legs["times_done"], legs["last_done"]) == (0, None)
    log_session(hugo, library["legs"], dt.date(2026, 9, 4), [(library["squat"], 80)])
    listed = call(client, token, "list_workouts")["structuredContent"]["workouts"][0]
    assert listed["times_done"] == 1
