"""Tests for apps.planner.views: the workout list and builder, and the exercise library."""

import json
from datetime import timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.library import timeline
from apps.library.models import Exercise, MuscleGroup, Source, Workout, WorkoutStatus
from apps.planner.views import round_lines
from tests.factories import (
    ActivitySessionFactory,
    ExerciseFactory,
    MuscleGroupFactory,
    UserFactory,
    WorkoutFactory,
    WorkoutItemFactory,
    exercise_type,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def squat(user: Any) -> Exercise:
    """A one-sided strength exercise in ``user``'s library."""
    exercise: Exercise = ExerciseFactory.create(owner=user, name="Split squat", one_sided=True)
    return exercise


@pytest.fixture
def swing(user: Any) -> Exercise:
    """A strength and aerobic exercise in ``user``'s library."""
    exercise: Exercise = ExerciseFactory.create(
        owner=user,
        name="Kettlebell swing",
        types=[exercise_type("strength"), exercise_type("aerobic")],
    )
    return exercise


@pytest.fixture
def legs(user: Any, squat: Exercise) -> Workout:
    """A one-item workout of ``user``'s, using ``squat``."""
    workout: Workout = WorkoutFactory.create(owner=user, name="Legs")
    WorkoutItemFactory.create(workout=workout, exercise=squat, duration_seconds=40)
    return workout


def items_json(*pairs: tuple[Exercise, int]) -> str:
    """Return the builder's items field for ``(exercise, seconds)`` pairs."""
    return json.dumps([{"exercise": str(ex.uuid), "dur": dur} for ex, dur in pairs])


def workout_post(items: str, **overrides: Any) -> dict[str, Any]:
    """Return a workout form post with the given items."""
    return {
        "name": "Legs",
        "rest_seconds": 15,
        "rounds": 1,
        "round_rest_seconds": 90,
        "items": items,
        **overrides,
    }


def exercise_post(exercise: Exercise, **overrides: Any) -> dict[str, Any]:
    """Return an exercise form post that keeps ``exercise``'s name."""
    return {"name": exercise.name, "types": ["strength"], "default_duration": 40, **overrides}


# ---------- signing in and other accounts ----------


@pytest.mark.parametrize(
    "name", ["planner:workouts", "planner:exercises", "planner:workout_new", "planner:exercise_new"]
)
def test_pages_need_sign_in(client: Client, name: str) -> None:
    """A signed-out visitor is sent to sign in, and brought back afterwards."""
    url = reverse(name)
    response = client.get(url)
    assert response.status_code == 302
    assert response["Location"] == f"{reverse('accounts:sign_in')}?next={url}"


@pytest.mark.parametrize(
    "name",
    [
        "planner:workout_edit",
        "planner:workout_delete",
        "planner:workout_duplicate",
        "planner:workout_status",
    ],
)
def test_workout_pages_need_sign_in(client: Client, name: str) -> None:
    """A signed-out visitor can't reach a workout's own pages either."""
    workout = WorkoutFactory.create()
    response = client.post(reverse(name, args=[workout.uuid]))
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("accounts:sign_in"))
    assert Workout.objects.filter(pk=workout.pk, status=WorkoutStatus.ACTIVE).exists()


@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("planner:workout_edit", "get"),
        ("planner:workout_edit", "post"),
        ("planner:workout_delete", "get"),
        ("planner:workout_delete", "post"),
        ("planner:workout_duplicate", "post"),
        ("planner:workout_status", "post"),
    ],
)
def test_another_accounts_workout_is_not_found(signed_in: Client, name: str, method: str) -> None:
    """Another account's workout uuid is a 404, and nothing about it changes."""
    theirs = WorkoutFactory.create(name="Theirs")
    WorkoutItemFactory.create(workout=theirs)
    url = reverse(name, args=[theirs.uuid])
    response = getattr(signed_in, method)(url)
    assert response.status_code == 404
    theirs.refresh_from_db()
    assert (theirs.name, theirs.status, theirs.items.count()) == ("Theirs", "active", 1)
    assert Workout.objects.count() == 1


@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("planner:exercise_edit", "get"),
        ("planner:exercise_edit", "post"),
        ("planner:exercise_delete", "get"),
        ("planner:exercise_delete", "post"),
    ],
)
def test_another_accounts_exercise_is_not_found(signed_in: Client, name: str, method: str) -> None:
    """Another account's exercise uuid is a 404, and it is neither changed nor deleted."""
    theirs = ExerciseFactory.create(name="Theirs")
    response = getattr(signed_in, method)(
        reverse(name, args=[theirs.uuid]), exercise_post(theirs, name="Mine")
    )
    assert response.status_code == 404
    theirs.refresh_from_db()
    assert theirs.name == "Theirs"


def test_lists_show_only_the_users_own(signed_in: Client, legs: Workout) -> None:
    """The workout and exercise lists leave out another account's library."""
    WorkoutItemFactory.create(
        workout=WorkoutFactory.create(name="Not mine"),
        exercise__name="Someone's press",
    )
    workouts = signed_in.get(reverse("planner:workouts")).content.decode()
    assert "Legs" in workouts
    assert "Not mine" not in workouts
    response = signed_in.get(reverse("planner:exercises"))
    assert [e.name for e in response.context["exercises"]] == ["Split squat"]
    assert response.context["total"] == 1


def test_builder_offers_only_the_users_library(
    signed_in: Client, user: Any, squat: Exercise
) -> None:
    """The builder lists the user's exercises and the muscles they can see, nobody else's."""
    ExerciseFactory.create(name="Someone's press")
    MuscleGroupFactory.create(name="Core")
    MuscleGroupFactory.create(owner=user, name="Grip")
    MuscleGroupFactory.create(owner=UserFactory.create(), name="Neck")
    builder = signed_in.get(reverse("planner:workout_new")).context["builder"]
    assert [e["name"] for e in builder["library"]] == ["Split squat"]
    assert sorted(builder["muscles"]) == ["Core", "Grip"]


# ---------- workouts ----------


def test_create_workout(signed_in: Client, user: Any, squat: Exercise, swing: Exercise) -> None:
    """A new workout is saved as the user's, with its items in the order posted."""
    response = signed_in.post(
        reverse("planner:workout_new"),
        workout_post(items_json((swing, 30), (squat, 40)), rounds=2),
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("planner:workouts")
    workout = Workout.objects.get(name="Legs")
    assert (workout.owner, workout.source) == (user, "manage")
    assert [(i.exercise, i.duration_seconds) for i in workout.items.all()] == [
        (swing, 30),
        (squat, 40),
    ]
    # ready 5 + 2 x (30 + 15 rest + 40 + 5 switch + 40) + 90 round break
    assert timeline.total_seconds(workout) == 5 + 2 * 130 + 90


def test_edit_replaces_items_in_order(
    signed_in: Client, legs: Workout, squat: Exercise, swing: Exercise
) -> None:
    """Saving a workout replaces its items with the posted ones, in order."""
    signed_in.post(
        reverse("planner:workout_edit", args=[legs.uuid]),
        workout_post(items_json((squat, 20), (swing, 45), (squat, 25)), rest_seconds=0),
    )
    assert [i.duration_seconds for i in legs.items.all()] == [20, 45, 25]


def test_workout_cannot_use_another_accounts_exercise(signed_in: Client) -> None:
    """A posted exercise from another account's library is refused."""
    theirs = ExerciseFactory.create()
    response = signed_in.post(
        reverse("planner:workout_new"), workout_post(items_json((theirs, 40)))
    )
    assert response.status_code == 200
    assert "no longer exists" in response.content.decode()
    assert not Workout.objects.exists()


@pytest.mark.parametrize(
    ("items", "error"),
    [
        ("not json", "could not be read"),
        ("[]", "Add at least one exercise."),
        (
            json.dumps([{"exercise": "00000000-0000-4000-8000-000000000000", "dur": 40}]),
            "no longer exists",
        ),
    ],
)
def test_workout_rejects_bad_items(signed_in: Client, items: str, error: str) -> None:
    """Unreadable, empty or unknown items redisplay the builder with the error."""
    response = signed_in.post(reverse("planner:workout_new"), workout_post(items))
    assert response.status_code == 200
    assert error in response.content.decode()
    assert not Workout.objects.exists()


def test_rejected_workout_keeps_the_posted_items(signed_in: Client, squat: Exercise) -> None:
    """A refused post hands the builder back the items it sent."""
    response = signed_in.post(
        reverse("planner:workout_new"), workout_post(items_json((squat, 40)), name="")
    )
    assert response.status_code == 200
    assert response.context["builder"]["items"] == [{"exercise": str(squat.uuid), "dur": 40}]


def test_workout_rejects_out_of_range_duration(signed_in: Client, squat: Exercise) -> None:
    """An exercise shorter than five seconds is refused."""
    response = signed_in.post(reverse("planner:workout_new"), workout_post(items_json((squat, 4))))
    assert "between 5 and 3600 seconds" in response.content.decode()


def test_builder_page_renders(signed_in: Client, squat: Exercise) -> None:
    """The builder carries the user's library."""
    response = signed_in.get(reverse("planner:workout_new"))
    assert response.status_code == 200
    assert str(squat.uuid) in response.content.decode()


def test_edit_page_loads_existing_items(signed_in: Client, legs: Workout, squat: Exercise) -> None:
    """Opening a workout hands the builder its items."""
    response = signed_in.get(reverse("planner:workout_edit", args=[legs.uuid]))
    assert response.context["builder"]["items"] == [{"exercise": str(squat.uuid), "dur": 40}]


def test_list_pages_render(signed_in: Client, legs: Workout) -> None:
    """The workout list names the workout; the exercise list names the exercise."""
    assert "Legs" in signed_in.get(reverse("planner:workouts")).content.decode()
    assert "Split squat" in signed_in.get(reverse("planner:exercises")).content.decode()


def test_exercise_list_edit_is_an_icon(signed_in: Client, squat: Exercise) -> None:
    """Each exercise row edits through a labelled pencil icon, not a named button."""
    html = signed_in.get(reverse("planner:exercises")).content.decode()
    edit = reverse("planner:exercise_edit", args=[squat.uuid])
    assert f'<a class="icon-btn" href="{edit}" aria-label="Edit {squat.name}" title="Edit">' in html
    assert ">Edit</a>" not in html


def test_workout_list_counts_sessions(signed_in: Client, user: Any, legs: Workout) -> None:
    """Each row carries how often the workout was done, and its length."""
    ActivitySessionFactory.create(owner=user, workout=legs)
    ActivitySessionFactory.create(owner=user, workout=legs)
    row = signed_in.get(reverse("planner:workouts")).context["rows"][0]
    assert row["workout"].times_done == 2
    assert row["total"] == timeline.total_seconds(legs)
    assert [t.slug for t in row["types"]] == ["strength"]


@pytest.mark.parametrize(
    ("name", "section"), [("planner:workouts", "Workouts"), ("planner:exercises", "Exercises")]
)
def test_header_matches_activity_mode(signed_in: Client, name: str, section: str) -> None:
    """The top row holds the wordmark, the mode switch and the account link."""
    html = signed_in.get(reverse(name)).content.decode()
    top = html[html.index('<div class="hrow">') : html.index('<nav class="nav"')]
    assert f'<a href="{reverse("activity:app")}">Workout</a>' in top
    assert '<span aria-current="page">Manage</span>' in top
    assert f'<a href="{reverse("activity:report")}">Report</a>' in top
    assert f'href="{reverse("accounts:account")}"' in top
    assert f'aria-current="page">{section}</a>' in html


def test_duplicate_workout(signed_in: Client, user: Any, squat: Exercise) -> None:
    """A copy keeps the settings and items, and opens in the builder."""
    workout = WorkoutFactory.create(owner=user, name="Legs", rounds=2)
    WorkoutItemFactory.create(workout=workout, exercise=squat, duration_seconds=40)
    response = signed_in.post(reverse("planner:workout_duplicate", args=[workout.uuid]))
    copy = Workout.objects.get(name="Legs (copy)")
    assert response["Location"] == reverse("planner:workout_edit", args=[copy.uuid])
    assert copy.owner == user
    assert copy.rounds == 2
    assert [(i.exercise, i.duration_seconds) for i in copy.items.all()] == [(squat, 40)]


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("pinned", "Legs is pinned to the phone."),
        ("archived", "Legs is archived."),
        ("active", "Legs is under Show all on the phone."),
    ],
)
def test_status_pins_archives_and_restores(
    signed_in: Client, user: Any, status: str, message: str
) -> None:
    """Pin, Archive, Unpin and Restore each post a status and say what happened."""
    workout = WorkoutFactory.create(owner=user, name="Legs", status=WorkoutStatus.PINNED)
    if status == "pinned":
        workout.status = WorkoutStatus.ACTIVE
        workout.save()
    url = reverse("planner:workout_status", args=[workout.uuid])
    response = signed_in.post(url, {"status": status}, follow=True)
    workout.refresh_from_db()
    assert workout.status == status
    assert message in response.content.decode()


def test_restore_starts_the_seven_days_again(signed_in: Client, user: Any) -> None:
    """Restoring bumps updated_at, so archive_unused_workouts waits another week."""
    workout = WorkoutFactory.create(owner=user, source=Source.CLAUDE, status=WorkoutStatus.ARCHIVED)
    old = timezone.now() - timedelta(days=30)
    Workout.objects.filter(pk=workout.pk).update(updated_at=old)
    signed_in.post(reverse("planner:workout_status", args=[workout.uuid]), {"status": "active"})
    workout.refresh_from_db()
    assert workout.updated_at > old + timedelta(days=29)


def test_status_rejects_an_unknown_value(signed_in: Client, user: Any) -> None:
    """Only the three statuses are accepted."""
    workout = WorkoutFactory.create(owner=user)
    url = reverse("planner:workout_status", args=[workout.uuid])
    assert signed_in.post(url, {"status": "deleted"}).status_code == 400
    workout.refresh_from_db()
    assert workout.status == WorkoutStatus.ACTIVE


def test_list_groups_pinned_then_newest_then_archived(signed_in: Client, user: Any) -> None:
    """Pinned by name, the rest newest first, archived collapsed with its count."""
    for name, status in [
        ("Zed", WorkoutStatus.PINNED),
        ("Abs", WorkoutStatus.PINNED),
        ("Older", WorkoutStatus.ACTIVE),
        ("Newer", WorkoutStatus.ACTIVE),
        ("Gone", WorkoutStatus.ARCHIVED),
    ]:
        WorkoutItemFactory.create(workout__owner=user, workout__name=name, workout__status=status)
    response = signed_in.get(reverse("planner:workouts"))
    groups = {
        g["status"]: [r["workout"].name for r in g["rows"]] for g in response.context["groups"]
    }
    assert groups == {
        "pinned": ["Abs", "Zed"],
        "active": ["Newer", "Older"],
        "archived": ["Gone"],
    }
    html = response.content.decode()
    assert '<details class="wgroup">' in html
    for action in ("Edit", "Copy", "Unpin", "Pin", "Restore", "Archive"):
        assert f'aria-label="{action} ' in html


def test_the_form_sets_status_and_keeps_it_when_left_out(signed_in: Client, user: Any) -> None:
    """The builder's status select pins a workout; a post without it changes nothing."""
    workout = WorkoutItemFactory.create(workout__owner=user, exercise__owner=user).workout
    url = reverse("planner:workout_edit", args=[workout.uuid])
    item = workout.items.get()
    data = {
        "name": workout.name,
        "description": "",
        "rest_seconds": 15,
        "rounds": 1,
        "round_rest_seconds": 120,
        "items": json.dumps([{"exercise": str(item.exercise.uuid), "dur": 30}]),
    }
    signed_in.post(url, {**data, "status": "pinned"})
    workout.refresh_from_db()
    assert workout.status == WorkoutStatus.PINNED
    signed_in.post(url, data)
    workout.refresh_from_db()
    assert workout.status == WorkoutStatus.PINNED


@pytest.mark.parametrize("name", ["planner:workout_status", "planner:workout_duplicate"])
def test_status_and_duplicate_need_post(signed_in: Client, user: Any, name: str) -> None:
    """A GET can't change or copy a workout."""
    workout = WorkoutFactory.create(owner=user)
    response = signed_in.get(reverse(name, args=[workout.uuid]))
    assert response.status_code == 405


def test_delete_workout_asks_then_deletes(signed_in: Client, user: Any) -> None:
    """A GET asks for confirmation; a POST deletes and goes back to the list."""
    workout = WorkoutFactory.create(owner=user, name="Legs")
    url = reverse("planner:workout_delete", args=[workout.uuid])
    assert "Legs" in signed_in.get(url).content.decode()
    response = signed_in.post(url)
    assert response["Location"] == reverse("planner:workouts")
    assert not Workout.objects.exists()


# ---------- exercises ----------


def test_create_exercise_with_new_muscle(signed_in: Client, user: Any) -> None:
    """The builder's dialog adds an exercise and gets it back as JSON."""
    core = MuscleGroupFactory.create(name="Core")
    response = signed_in.post(
        reverse("planner:exercise_new"),
        {
            "name": "Turkish get-up",
            "types": ["strength"],
            "muscles": [str(core.uuid)],
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
    assert MuscleGroup.objects.get(name="Forearms").owner == user
    assert Exercise.objects.get(name="Turkish get-up").owner == user


def test_exercise_name_must_be_unique(signed_in: Client, squat: Exercise) -> None:
    """A name the library already has, in any case, is refused as JSON for the dialog."""
    response = signed_in.post(
        reverse("planner:exercise_new"),
        {"name": "split squat", "types": ["strength"], "default_duration": 40},
        HTTP_ACCEPT="application/json",
    )
    assert response.status_code == 400
    assert "name" in response.json()["errors"]


def test_exercise_name_may_match_another_accounts(signed_in: Client) -> None:
    """Another account having an exercise of that name is no clash."""
    ExerciseFactory.create(name="Plank")
    response = signed_in.post(
        reverse("planner:exercise_new"),
        {"name": "Plank", "types": ["strength"], "default_duration": 40},
    )
    assert response.status_code == 302
    assert Exercise.objects.filter(name="Plank").count() == 2


def test_used_exercise_cannot_be_deleted(signed_in: Client, legs: Workout, squat: Exercise) -> None:
    """An exercise a workout uses stays, and the page names that workout."""
    url = reverse("planner:exercise_delete", args=[squat.uuid])
    response = signed_in.post(url)
    assert response.status_code == 200
    assert list(response.context["blocked_by"]) == [legs]
    assert Exercise.objects.filter(pk=squat.pk).exists()


def test_unused_exercise_can_be_deleted(signed_in: Client, squat: Exercise) -> None:
    """An exercise no workout uses is deleted after confirmation."""
    url = reverse("planner:exercise_delete", args=[squat.uuid])
    assert signed_in.get(url).status_code == 200
    response = signed_in.post(url)
    assert response["Location"] == reverse("planner:exercises")
    assert not Exercise.objects.filter(pk=squat.pk).exists()


def test_exercise_list_filters(
    signed_in: Client, user: Any, squat: Exercise, swing: Exercise
) -> None:
    """The list filters by type, and searches names and muscles."""
    url = reverse("planner:exercises")
    by_type = signed_in.get(url, {"type": "aerobic"}).context["exercises"]
    assert list(by_type) == [swing]
    squat.muscles.add(MuscleGroupFactory.create(name="Quads"))
    by_muscle = signed_in.get(url, {"q": "quad"}).context["exercises"]
    assert list(by_muscle) == [squat]
    by_name = signed_in.get(url, {"q": " swing "}).context["exercises"]
    assert list(by_name) == [swing]


def test_edit_exercise_from_the_form(signed_in: Client, squat: Exercise) -> None:
    """The edit page saves and goes back to the list; an unticked box clears one_sided."""
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    assert signed_in.get(url).status_code == 200
    response = signed_in.post(
        url, exercise_post(squat, name="Bulgarian split squat", default_duration=50)
    )
    assert response["Location"] == reverse("planner:exercises")
    squat.refresh_from_db()
    assert squat.name == "Bulgarian split squat"
    assert squat.one_sided is False


def test_muscle_choices_post_uuids(signed_in: Client, squat: Exercise) -> None:
    """The muscle checkboxes carry the group's uuid, and posting one ticks it."""
    quads = MuscleGroupFactory.create(name="Quads")
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    assert f'name="muscles" value="{quads.uuid}"' in signed_in.get(url).content.decode()
    signed_in.post(url, exercise_post(squat, muscles=[str(quads.uuid)]))
    assert list(squat.muscles.all()) == [quads]


def test_set_equipment_from_the_form(signed_in: Client, squat: Exercise) -> None:
    """Equipment is a radio choice with icons, and can be set and cleared."""
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    page = signed_in.get(url).content.decode()
    assert '<input type="radio" name="equipment" value="" checked>' in page
    assert 'aria-label="Dumbbell"' in page
    signed_in.post(url, exercise_post(squat, equipment="dumbbell"))
    squat.refresh_from_db()
    assert squat.equipment == "dumbbell"
    signed_in.post(url, exercise_post(squat, equipment=""))
    squat.refresh_from_db()
    assert squat.equipment == ""


def test_set_movement_from_the_form(signed_in: Client, squat: Exercise) -> None:
    """Movement can be set; a post without it (an older page) keeps what was set."""
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    page = signed_in.get(url).content.decode()
    assert '<input type="radio" name="movement" value="dynamic" checked>' in page
    signed_in.post(url, exercise_post(squat, movement="static"))
    squat.refresh_from_db()
    assert squat.movement == "static"
    signed_in.post(url, exercise_post(squat))
    squat.refresh_from_db()
    assert squat.movement == "static"
    signed_in.post(url, exercise_post(squat, movement="dynamic"))
    squat.refresh_from_db()
    assert squat.movement == "dynamic"


def test_new_exercise_without_movement_is_dynamic(signed_in: Client) -> None:
    """A new exercise posted without a movement is dynamic."""
    signed_in.post(
        reverse("planner:exercise_new"),
        {"name": "Lunge", "types": ["strength"], "default_duration": 40},
    )
    assert Exercise.objects.get(name="Lunge").movement == "dynamic"


def test_unknown_movement_is_rejected(signed_in: Client, squat: Exercise) -> None:
    """A movement that isn't a choice redisplays the form with the error."""
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    response = signed_in.post(url, exercise_post(squat, movement="plyometric"))
    assert response.status_code == 200
    assert "plyometric is not one of the available choices" in response.content.decode()


def test_unknown_equipment_is_rejected(signed_in: Client, squat: Exercise) -> None:
    """Equipment that isn't a choice changes nothing."""
    url = reverse("planner:exercise_edit", args=[squat.uuid])
    response = signed_in.post(url, exercise_post(squat, equipment="barbell"))
    assert response.status_code == 200
    squat.refresh_from_db()
    assert squat.equipment == ""


def test_static_tag_on_manage_pages(signed_in: Client, squat: Exercise, swing: Exercise) -> None:
    """A static exercise is tagged in the list, and the builder knows each movement."""
    squat.movement = "static"
    squat.save()
    listing = signed_in.get(reverse("planner:exercises")).content.decode()
    assert listing.count('title="Holds one position">static</span>') == 1
    builder = signed_in.get(reverse("planner:workout_new")).context["builder"]
    by_name = {e["name"]: e["movement"] for e in builder["library"]}
    assert by_name == {"Kettlebell swing": "dynamic", "Split squat": "static"}


def test_equipment_icons_on_manage_pages(
    signed_in: Client, squat: Exercise, swing: Exercise
) -> None:
    """Equipment shows as an icon in the list, and the builder gets every choice."""
    swing.equipment = "kettlebell"
    swing.save()
    listing = signed_in.get(reverse("planner:exercises")).content.decode()
    assert listing.count('<svg class="eq"') == 1
    assert 'aria-label="Kettlebell"' in listing
    builder = signed_in.get(reverse("planner:workout_new")).context["builder"]
    by_name = {e["name"]: e for e in builder["library"]}
    assert by_name["Kettlebell swing"]["equipment"] == "kettlebell"
    assert by_name["Split squat"]["equipment"] == ""
    assert [e["slug"] for e in builder["equipment"]] == ["kettlebell", "dumbbell"]


def test_invalid_exercise_form_shows_errors(signed_in: Client) -> None:
    """An exercise with no type redisplays the form with the error."""
    response = signed_in.post(reverse("planner:exercise_new"), {"name": "Plank"})
    assert response.status_code == 200
    assert "Pick at least one type." in response.content.decode()


# ---------- who made it ----------


def test_claude_tag_on_workout_list(signed_in: Client, user: Any, squat: Exercise) -> None:
    """A workout Claude made carries the Claude tag; one made in Manage doesn't."""
    WorkoutItemFactory.create(workout__owner=user, workout__source="claude", exercise=squat)
    WorkoutItemFactory.create(workout__owner=user, exercise=squat)
    html = signed_in.get(reverse("planner:workouts")).content.decode()
    assert html.count('class="tag-src"') == 1


def test_claude_tag_on_exercise_list(signed_in: Client, user: Any) -> None:
    """An exercise Claude made carries the Claude tag."""
    ExerciseFactory.create(owner=user, name="Cat-cow", source="claude")
    html = signed_in.get(reverse("planner:exercises")).content.decode()
    assert 'class="tag-src"' in html


# ---------- query counts ----------


def _workouts_with_items(owner: Any, count: int, exercises: list[Exercise]) -> None:
    """Make ``count`` workouts for ``owner``, each using every exercise given."""
    for _ in range(count):
        workout = WorkoutFactory.create(owner=owner)
        for order, ex in enumerate(exercises):
            WorkoutItemFactory.create(
                workout=workout, exercise=ex, order=order, duration_seconds=30
            )


# Query counts are fixed whatever the number of rows: a new N+1 query fails
# these. Each includes the session and user lookups for the signed-in request.
@pytest.mark.parametrize("workouts", [1, 10])
def test_workout_list_query_count(
    signed_in: Client,
    user: Any,
    squat: Exercise,
    swing: Exercise,
    django_assert_num_queries: Any,
    workouts: int,
) -> None:
    """The workout list costs the same number of queries for one workout or ten."""
    _workouts_with_items(user, workouts, [squat, swing])
    with django_assert_num_queries(5):
        signed_in.get(reverse("planner:workouts"))


@pytest.mark.parametrize("workouts", [1, 10])
def test_exercise_list_query_count(
    signed_in: Client,
    user: Any,
    squat: Exercise,
    swing: Exercise,
    django_assert_num_queries: Any,
    workouts: int,
) -> None:
    """The exercise list costs the same number of queries however much it is used."""
    _workouts_with_items(user, workouts, [squat, swing])
    with django_assert_num_queries(7):
        signed_in.get(reverse("planner:exercises"))


@pytest.mark.parametrize("extra", [0, 10])
def test_builder_query_count(
    signed_in: Client, user: Any, squat: Exercise, django_assert_num_queries: Any, extra: int
) -> None:
    """The builder costs the same number of queries for a small library or a large one."""
    for _ in range(extra):
        ExerciseFactory.create(owner=user)
    with django_assert_num_queries(9):
        signed_in.get(reverse("planner:workout_new"))


def test_round_lines_puts_each_round_on_its_own_line() -> None:
    """One line per round, without the get-ready or the breaks between rounds."""
    segs = [("ready", 5), ("work", 40), ("rest", 10), ("work", 30), ("round", 55)]
    segs += [("work", 40), ("rest", 10), ("work", 30)]
    assert round_lines(segs) == [
        [("work", 40), ("rest", 10), ("work", 30)],
        [("work", 40), ("rest", 10), ("work", 30)],
    ]
    assert round_lines([("ready", 5), ("work", 40)]) == [[("work", 40)]]


def test_list_draws_a_strip_line_per_round(signed_in: Client, user: Any) -> None:
    """A three-round workout gets three strip lines."""
    WorkoutItemFactory.create(workout__owner=user, workout__rounds=3)
    html = signed_in.get(reverse("planner:workouts")).content.decode()
    assert html.count('class="strip mini"') == 3
    assert "one line per round" in html
