"""Tests for the MCP tools: reading and changing a user's library and log, and nobody else's."""

import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Any

import pytest
from django.utils import timezone

from apps.activity.models import ActivitySession
from apps.library.models import Exercise, MuscleGroup, Workout
from apps.mcp.tools import (
    ToolError,
    find_exercise,
    find_workout,
    get_exercise,
    get_workout,
    list_exercises,
    list_sessions,
    list_types_and_muscles,
    list_workouts,
    update_exercise,
    update_workout,
    workout_summary,
)
from tests.factories import (
    ActivitySessionFactory,
    ExerciseFactory,
    MuscleGroupFactory,
    SessionEntryFactory,
    UserFactory,
    WorkoutFactory,
    WorkoutItemFactory,
    exercise_type,
)
from tests.mcp.conftest import Rpc

SEPTEMBER = {"start_date": "2026-09-01", "end_date": "2026-09-30"}


@pytest.fixture
def library(user: Any) -> dict[str, Any]:
    """The user's library: two exercises on shared muscles, in one workout called Legs."""
    glutes = MuscleGroupFactory.create(name="Glutes")
    hips = MuscleGroupFactory.create(name="Hips")
    squat = ExerciseFactory.create(
        owner=user,
        name="Split squat",
        one_sided=True,
        default_duration=30,
        types=[exercise_type("strength")],
        muscles=[glutes],
    )
    ninety = ExerciseFactory.create(
        owner=user,
        name="90:90",
        default_duration=45,
        types=[exercise_type("flexibility")],
        muscles=[hips, glutes],
    )
    legs = WorkoutFactory.create(owner=user, name="Legs", rest_seconds=10)
    WorkoutItemFactory.create(workout=legs, exercise=squat, order=0, duration_seconds=40)
    WorkoutItemFactory.create(workout=legs, exercise=ninety, order=1, duration_seconds=60)
    return {"squat": squat, "ninety": ninety, "legs": legs, "glutes": glutes, "hips": hips}


@pytest.fixture
def other(db: None) -> Any:
    """Another account, with a library of its own."""
    return UserFactory.create()


def log_session(
    owner: Any,
    workout: Workout | None,
    day: dt.date,
    entries: Sequence[tuple[Exercise, int]],
    effort: int | None = None,
    completed: bool = True,
) -> ActivitySession:
    """Log a session of ``workout`` at 07:00 on ``day`` with ``[(exercise, seconds)]``."""
    start = timezone.make_aware(dt.datetime.combine(day, dt.time(7)))
    session: ActivitySession = ActivitySessionFactory.create(
        owner=owner,
        workout=workout,
        workout_name=workout.name if workout else "Gone",
        started_at=start,
        ended_at=start + dt.timedelta(minutes=5),
        completed=completed,
        seconds_worked=sum(s for _, s in entries),
        effort=effort,
    )
    for i, (exercise, seconds) in enumerate(entries):
        SessionEntryFactory.create(
            session=session,
            exercise=exercise,
            exercise_name=exercise.name,
            order=i,
            seconds_worked=seconds,
        )
    return session


def names(items: list[dict[str, Any]]) -> list[str]:
    """Return the ``name`` of each listed thing."""
    return [i["name"] for i in items]


# ---------- read tools ----------


def test_list_types_and_muscles(call: Rpc, library: dict[str, Any]) -> None:
    """Types, the muscles the user sees, and the equipment and movement choices."""
    result = call("list_types_and_muscles")["structuredContent"]
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


def test_list_exercises_filters(call: Rpc, library: dict[str, Any]) -> None:
    """Exercises filter by muscle (any case), type and query."""
    by_muscle = call("list_exercises", muscle="hips")["structuredContent"]
    assert names(by_muscle["exercises"]) == ["90:90"]
    by_type = call("list_exercises", type="strength")["structuredContent"]
    assert names(by_type["exercises"]) == ["Split squat"]
    by_query = call("list_exercises", query="squat")["structuredContent"]
    assert names(by_query["exercises"]) == ["Split squat"]


def test_get_workout_by_name_and_id(call: Rpc, library: dict[str, Any]) -> None:
    """A workout is found by name in any case or by id, with its items and length."""
    by_name = call("get_workout", workout="legs")["structuredContent"]
    by_id = call("get_workout", workout=str(library["legs"].uuid))["structuredContent"]
    assert by_name == by_id
    assert [i["exercise"] for i in by_name["items"]] == ["Split squat", "90:90"]
    # 5 ready + 40 + 5 switch + 40 + 10 rest + 60
    assert by_name["total_seconds"] == 160


def test_unknown_workout_is_a_tool_error(call: Rpc, library: dict[str, Any]) -> None:
    """An unknown workout is an error the model can read."""
    result = call("get_workout", workout="Arms")
    assert result["isError"] is True
    assert "No workout matches" in result["content"][0]["text"]


def test_ambiguous_workout_name(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """Two workouts with one name (any case) ask for an id."""
    WorkoutFactory.create(owner=user, name="LEGS")
    result = call("get_workout", workout="legs")
    assert "More than one workout" in result["content"][0]["text"]


def test_get_exercise_with_usage(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """An exercise comes with the workouts that use it and the time logged on it."""
    log_session(user, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    result = call("get_exercise", exercise="Split squat")["structuredContent"]
    assert result["used_in_workouts"] == [{"id": str(library["legs"].uuid), "name": "Legs"}]
    assert result["sessions_logged"] == 1
    assert result["seconds_logged"] == 80


def test_sessions_and_summary(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """Sessions list newest first; the summary splits time by type, muscle and movement."""
    squat, ninety, legs = library["squat"], library["ninety"], library["legs"]
    ninety.movement = "static"
    ninety.save()
    log_session(user, legs, dt.date(2026, 9, 3), [(squat, 80), (ninety, 60)], effort=6)
    log_session(user, legs, dt.date(2026, 9, 30), [(squat, 40)], effort=8, completed=False)
    log_session(user, legs, dt.date(2026, 10, 1), [(ninety, 60)])

    sessions = call("list_sessions", **SEPTEMBER)["structuredContent"]
    assert len(sessions["sessions"]) == 2
    assert sessions["sessions"][0]["completed"] is False
    assert sessions["sessions"][1]["entries"] == [
        {"exercise": "Split squat", "seconds_worked": 80},
        {"exercise": "90:90", "seconds_worked": 60},
    ]

    summary = call("training_summary", **SEPTEMBER)["structuredContent"]
    assert summary["sessions"] == 2
    assert summary["completed_sessions"] == 1
    assert summary["active_days"] == 2
    assert summary["seconds_worked"] == 180
    assert summary["average_effort"] == 7.0
    assert summary["seconds_by_type"] == {"strength": 120, "flexibility": 60}
    assert summary["seconds_by_muscle"] == {"Glutes": 180, "Hips": 60}
    assert summary["seconds_by_movement"] == {"dynamic": 120, "static": 60}
    assert "aerobic" in summary["unused_types"]


def test_summary_rejects_bad_dates(call: Rpc) -> None:
    """A date that isn't YYYY-MM-DD is an error the model can read."""
    result = call("training_summary", start_date="Sept", end_date="2026-09-30")
    assert result["isError"] is True
    assert "start_date" in result["content"][0]["text"]


def test_summary_needs_both_dates(call: Rpc) -> None:
    """The period's ends are required, and a missing one is a readable error."""
    result = call("training_summary", start_date="2026-09-01")
    assert result["isError"] is True
    assert "end_date" in result["content"][0]["text"]


def test_summary_with_no_sessions(call: Rpc) -> None:
    """An empty period has no average effort and every type unused."""
    summary = call("training_summary", **SEPTEMBER)["structuredContent"]
    assert (summary["sessions"], summary["average_effort"]) == (0, None)
    assert "strength" in summary["unused_types"]


def test_summary_counts_deleted_exercises_as_unknown(
    call: Rpc, user: Any, library: dict[str, Any]
) -> None:
    """Time on an exercise since deleted keeps its name but has no type or movement."""
    session = log_session(user, library["legs"], dt.date(2026, 9, 3), [(library["squat"], 80)])
    session.entries.update(exercise=None)
    summary = call("training_summary", **SEPTEMBER)["structuredContent"]
    assert summary["seconds_by_type"] == {"unknown": 80}
    assert summary["seconds_by_movement"] == {"unknown": 80}
    assert summary["seconds_by_exercise"] == {"Split squat": 80}


def test_summary_shares_time_between_types(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """An exercise's time is split between its types but counts in full per muscle."""
    squat = library["squat"]
    squat.types.add(exercise_type("flexibility"))
    log_session(user, library["legs"], dt.date(2026, 9, 3), [(squat, 81)])
    summary = call("training_summary", **SEPTEMBER)["structuredContent"]
    assert summary["seconds_by_type"] == {"strength": 40, "flexibility": 40}
    assert summary["seconds_by_muscle"] == {"Glutes": 81}


def test_sessions_by_workout_with_limit(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """Sessions filter by workout, and a limit says when it cut the list short."""
    arms = WorkoutFactory.create(owner=user, name="Arms")
    for day in (1, 2, 3):
        log_session(user, library["legs"], dt.date(2026, 9, day), [(library["squat"], 40)])
    log_session(user, arms, dt.date(2026, 9, 4), [(library["squat"], 40)])
    result = call("list_sessions", workout="Legs", limit=2)["structuredContent"]
    assert len(result["sessions"]) == 2
    assert result["truncated"] is True
    assert {s["workout"] for s in result["sessions"]} == {"Legs"}
    assert {s["workout_id"] for s in result["sessions"]} == {str(library["legs"].uuid)}


def test_workout_counts_its_sessions(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """A workout reports how often and when it was last done."""
    legs = call("get_workout", workout="Legs")["structuredContent"]
    assert (legs["times_done"], legs["last_done"]) == (0, None)
    log_session(user, library["legs"], dt.date(2026, 9, 4), [(library["squat"], 80)])
    listed = call("list_workouts")["structuredContent"]["workouts"][0]
    assert listed["times_done"] == 1
    assert listed["last_done"].startswith("2026-09-04")


# ---------- write tools ----------


def test_create_exercise(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """A new exercise reuses a muscle the user sees and adds a new one as theirs."""
    result = call(
        "create_exercise",
        name="Cat-cow",
        types=["flexibility"],
        muscles=["spine", "hips"],
        default_duration=45,
    )["structuredContent"]
    assert result["muscles"] == ["Hips", "Spine"]
    exercise = Exercise.objects.get(uuid=uuid.UUID(result["id"]))
    assert (exercise.owner, exercise.default_duration) == (user, 45)
    assert MuscleGroup.objects.filter(name="Hips").count() == 1
    assert MuscleGroup.objects.get(name="Spine").owner == user
    assert (exercise.source, result["made_by"]) == ("claude", "claude")


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"name": "Split squat", "types": ["strength"]}, "already exists"),
        ({"name": "Plank", "types": ["yoga"]}, "Unknown type yoga"),
        ({"name": "Plank", "types": []}, "at least one type"),
        ({"name": "Plank"}, "Missing argument 'types'"),
        ({"name": "Plank", "types": ["strength"], "default_duration": 2}, "default_duration"),
    ],
)
def test_create_exercise_errors(
    call: Rpc, library: dict[str, Any], args: dict[str, Any], message: str
) -> None:
    """A bad exercise is refused with a readable reason, and nothing is saved."""
    result = call("create_exercise", **args)
    assert result["isError"] is True
    assert message in result["content"][0]["text"]
    assert not Exercise.objects.filter(name="Plank").exists()


def test_create_exercise_needs_types_when_called_directly(user: Any) -> None:
    """The tool function itself refuses a call without types."""
    from apps.mcp.tools import create_exercise

    with pytest.raises(ToolError, match="Missing types"):
        create_exercise(user, {"name": "Plank"})


def test_update_exercise_changes_only_given_fields(call: Rpc, library: dict[str, Any]) -> None:
    """A rename (found by name in any case) leaves the other fields alone."""
    result = call("update_exercise", exercise="split SQUAT", name="Bulgarian split squat")[
        "structuredContent"
    ]
    assert result["name"] == "Bulgarian split squat"
    assert result["types"] == ["strength"]
    assert result["one_sided"] is True


def test_update_exercise_all_fields(call: Rpc, library: dict[str, Any]) -> None:
    """Types and muscles replace the current lists; blank muscle names are ignored."""
    result = call(
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
def test_update_exercise_errors(
    call: Rpc, library: dict[str, Any], args: dict[str, Any], message: str
) -> None:
    """A bad change is refused with a readable reason."""
    result = call("update_exercise", exercise="90:90", **args)
    assert result["isError"] is True
    assert message in result["content"][0]["text"]


def test_tag_and_filter_by_movement(call: Rpc, library: dict[str, Any]) -> None:
    """Movement defaults to dynamic, can be changed, filtered on and shown in workouts."""
    assert call("get_exercise", exercise="90:90")["structuredContent"]["movement"] == "dynamic"
    result = call("update_exercise", exercise="90:90", movement="static")
    assert result["structuredContent"]["movement"] == "static"
    found = call("list_exercises", movement="static")["structuredContent"]
    assert names(found["exercises"]) == ["90:90"]
    workout = call("get_workout", workout="Legs")["structuredContent"]
    assert {i["exercise"]: i["movement"] for i in workout["items"]}["Split squat"] == "dynamic"


def test_tag_and_filter_by_equipment(call: Rpc, library: dict[str, Any]) -> None:
    """Equipment can be set, filtered on (empty for bodyweight), shown and cleared."""
    result = call("update_exercise", exercise="Split squat", equipment="dumbbell")
    assert result["structuredContent"]["equipment"] == "dumbbell"
    found = call("list_exercises", equipment="dumbbell")["structuredContent"]
    assert names(found["exercises"]) == ["Split squat"]
    bodyweight = call("list_exercises", equipment="")["structuredContent"]
    assert "Split squat" not in names(bodyweight["exercises"])
    workout = call("get_workout", workout="Legs")["structuredContent"]
    assert {i["exercise"]: i["equipment"] for i in workout["items"]}["Split squat"] == "dumbbell"
    cleared = call("update_exercise", exercise="Split squat", equipment="")
    assert cleared["structuredContent"]["equipment"] == ""


def test_create_workout(call: Rpc, user: Any, library: dict[str, Any]) -> None:
    """A workout is built from library exercises, defaulting to each one's duration."""
    result = call(
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
    assert Workout.objects.get(uuid=uuid.UUID(result["id"])).owner == user
    # Made by Claude, and a one-off unless asked to save it.
    assert (result["made_by"], result["one_off"], result["on_phone"]) == ("claude", True, True)


def test_create_saved_workout(call: Rpc, library: dict[str, Any]) -> None:
    """one_off false makes a saved workout."""
    result = call("create_workout", name="Regular", one_off=False, items=[{"exercise": "90:90"}])[
        "structuredContent"
    ]
    assert result["one_off"] is False


def test_old_one_offs_leave_the_list_until_kept(call: Rpc, library: dict[str, Any]) -> None:
    """A one-off over a week old is listed only with include_inactive, until kept."""
    Workout.objects.filter(name="Legs").update(
        one_off=True, created_at=timezone.now() - dt.timedelta(days=8)
    )
    assert call("list_workouts")["structuredContent"]["workouts"] == []
    (old,) = call("list_workouts", include_inactive=True)["structuredContent"]["workouts"]
    assert (old["one_off"], old["on_phone"]) == (True, False)
    kept = call("update_workout", workout="Legs", one_off=False)["structuredContent"]
    assert kept["on_phone"] is True
    assert names(call("list_workouts")["structuredContent"]["workouts"]) == ["Legs"]


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ({"name": "X", "items": []}, "at least one exercise"),
        ({"name": "X", "items": [{"exercise": "Burpee"}]}, "No exercise matches"),
        ({"name": "X", "items": [{"exercise": "90:90", "duration_seconds": 1}]}, "duration"),
        ({"name": "X", "rounds": 0, "items": [{"exercise": "90:90"}]}, "rounds"),
        ({"name": "X", "rounds": True, "items": [{"exercise": "90:90"}]}, "rounds"),
        ({"name": "X", "rest_seconds": -1, "items": [{"exercise": "90:90"}]}, "rest_seconds"),
        ({"name": "", "items": [{"exercise": "90:90"}]}, "name"),
        ({"name": "X"}, "Missing argument 'items'"),
    ],
)
def test_create_workout_errors(
    call: Rpc, library: dict[str, Any], args: dict[str, Any], message: str
) -> None:
    """A bad workout is refused with a readable reason, and nothing is saved."""
    result = call("create_workout", **args)
    assert result["isError"] is True
    assert message in result["content"][0]["text"]
    assert Workout.objects.count() == 1


def test_update_workout_replaces_items_and_can_deactivate(
    call: Rpc, library: dict[str, Any]
) -> None:
    """Items replace the whole list; an inactive workout drops out of the default list."""
    result = call(
        "update_workout",
        workout="Legs",
        is_active=False,
        items=[{"exercise": "90:90", "duration_seconds": 90}],
    )["structuredContent"]
    assert result["is_active"] is False
    assert [(i["exercise"], i["duration_seconds"]) for i in result["items"]] == [("90:90", 90)]
    assert result["rest_seconds"] == 10
    assert call("list_workouts")["structuredContent"]["workouts"] == []
    listed = call("list_workouts", include_inactive=True)["structuredContent"]["workouts"]
    assert names(listed) == ["Legs"]


def test_update_workout_settings(call: Rpc, library: dict[str, Any]) -> None:
    """Settings change one by one; an item without an exercise is refused."""
    result = call(
        "update_workout",
        workout="Legs",
        name="Lower body",
        description="Hips and legs",
        rest_seconds=0,
        round_rest_seconds=60,
    )["structuredContent"]
    assert (result["name"], result["description"]) == ("Lower body", "Hips and legs")
    assert (result["rest_seconds"], result["round_rest_seconds"]) == (0, 60)
    bad = call("update_workout", workout="Lower body", items=[{"duration_seconds": 30}])
    assert "items[0] needs an exercise" in bad["content"][0]["text"]


# ---------- one account never sees another's ----------


@pytest.fixture
def theirs(other: Any) -> dict[str, Any]:
    """Another account's exercise, workout and session, named like the user's own."""
    squat = ExerciseFactory.create(owner=other, name="Split squat")
    legs = WorkoutFactory.create(owner=other, name="Legs")
    WorkoutItemFactory.create(workout=legs, exercise=squat)
    session = log_session(other, legs, dt.date(2026, 9, 3), [(squat, 80)], effort=9)
    return {"squat": squat, "legs": legs, "session": session}


def test_another_accounts_library_is_invisible(user: Any, theirs: dict[str, Any]) -> None:
    """Lists come back empty and lookups by name or id find nothing."""
    assert list_exercises(user, {}) == {"exercises": []}
    assert list_workouts(user, {"include_inactive": True}) == {"workouts": []}
    assert list_sessions(user, {}) == {"sessions": [], "truncated": False}
    for ref in ("Split squat", str(theirs["squat"].uuid)):
        with pytest.raises(ToolError, match="No exercise matches"):
            get_exercise(user, {"exercise": ref})
    for ref in ("Legs", str(theirs["legs"].uuid)):
        with pytest.raises(ToolError, match="No workout matches"):
            get_workout(user, {"workout": ref})
    with pytest.raises(ToolError, match="No workout matches"):
        list_sessions(user, {"workout": "Legs"})


def test_another_accounts_sessions_are_not_in_the_summary(
    call: Rpc, theirs: dict[str, Any]
) -> None:
    """The summary counts only the caller's own sessions."""
    summary = call("training_summary", **SEPTEMBER)["structuredContent"]
    assert (summary["sessions"], summary["seconds_worked"], summary["average_effort"]) == (
        0,
        0,
        None,
    )


def test_another_accounts_library_cannot_be_changed(user: Any, theirs: dict[str, Any]) -> None:
    """Updates to someone else's exercise or workout are refused and change nothing."""
    with pytest.raises(ToolError, match="No exercise matches"):
        update_exercise(user, {"exercise": str(theirs["squat"].uuid), "name": "Mine now"})
    with pytest.raises(ToolError, match="No workout matches"):
        update_workout(user, {"workout": str(theirs["legs"].uuid), "is_active": False})
    theirs["squat"].refresh_from_db()
    theirs["legs"].refresh_from_db()
    assert theirs["squat"].name == "Split squat"
    assert theirs["legs"].is_active is True


def test_a_workout_cannot_use_another_accounts_exercise(
    call: Rpc, user: Any, theirs: dict[str, Any]
) -> None:
    """A workout's items come only from the caller's own library."""
    result = call("create_workout", name="Borrowed", items=[{"exercise": "Split squat"}])
    assert result["isError"] is True
    assert "No exercise matches" in result["content"][0]["text"]
    assert not Workout.objects.filter(owner=user).exists()


def test_names_only_clash_within_one_account(user: Any, theirs: dict[str, Any]) -> None:
    """The user may name an exercise as another account already has."""
    from apps.mcp.tools import create_exercise

    created = create_exercise(user, {"name": "Split squat", "types": ["strength"]})
    assert find_exercise(created["id"], user).owner == user
    assert find_exercise("Split squat", theirs["squat"].owner) == theirs["squat"]


def test_a_workouts_counts_are_the_users_own(
    user: Any, other: Any, library: dict[str, Any], theirs: dict[str, Any]
) -> None:
    """Another account's sessions never add to the user's workout counts."""
    summary = workout_summary(find_workout("Legs", user))
    assert (summary["times_done"], summary["last_done"]) == (0, None)


def test_a_private_muscle_group_is_only_its_owners(user: Any, other: Any) -> None:
    """Shared groups are listed for everyone; a private one only for its owner."""
    MuscleGroupFactory.create(name="Glutes")
    MuscleGroupFactory.create(owner=other, name="Forearms")
    assert list_types_and_muscles(user, {})["muscles"] == ["Glutes"]
    assert list_types_and_muscles(other, {})["muscles"] == ["Forearms", "Glutes"]


def test_a_new_muscle_name_is_added_privately(call: Rpc, user: Any, other: Any) -> None:
    """Naming a muscle another account added makes the caller their own copy."""
    MuscleGroupFactory.create(owner=other, name="Forearms")
    result = call("create_exercise", name="Wrist curl", types=["strength"], muscles=["forearms"])
    assert result["structuredContent"]["muscles"] == ["Forearms"]
    owners = set(MuscleGroup.objects.filter(name="Forearms").values_list("owner", flat=True))
    assert owners == {user.pk, other.pk}
