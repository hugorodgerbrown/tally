"""Tests for the migrations that move the one-account library onto per-account owners.

They run the real migration graph: back to the pre-template schema, write
rows as the old app did, then forward to the latest.
"""

import uuid
from typing import Any

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("library", "0005_exercise_movement"), ("activity", "0002_discardedsession")]


def _migrate(targets: list[tuple[str, str]]) -> Any:
    """Migrate to ``targets``; return the historical apps at that state."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def _latest() -> list[tuple[str, str]]:
    """Return the leaf migration of each app under test."""
    graph = MigrationExecutor(connection).loader.graph
    return [n for n in graph.leaf_nodes() if n[0] in {"library", "activity"}]


@pytest.mark.django_db(transaction=True)
def test_existing_rows_go_to_the_superuser_and_keep_their_history() -> None:
    """Exercises, workouts and sessions all end up owned by the existing account."""
    old = _migrate(BEFORE)
    user_model = old.get_model("auth", "User")
    user_model.objects.create(username="someone", email="someone@example.com")
    hugo = user_model.objects.create(username="hugo", is_superuser=True, is_staff=True)
    exercise = old.get_model("library", "Exercise").objects.create(name="Plank")
    workout = old.get_model("library", "Workout").objects.create(name="Core")
    old.get_model("library", "WorkoutItem").objects.create(
        workout=workout, exercise=exercise, duration_seconds=30
    )
    session = old.get_model("activity", "ActivitySession").objects.create(
        uuid=uuid.uuid4(),
        user=hugo,
        workout=workout,
        workout_name="Core",
        started_at="2026-10-01T07:00:00Z",
        ended_at="2026-10-01T07:05:00Z",
        completed=True,
    )
    old.get_model("activity", "SessionEntry").objects.create(
        session=session, exercise=exercise, exercise_name="Plank", seconds_worked=30
    )

    new = _migrate(_latest())
    exercise = new.get_model("library", "Exercise").objects.get()
    assert exercise.owner_id == hugo.pk
    assert new.get_model("library", "Workout").objects.get().owner_id == hugo.pk
    item = new.get_model("library", "WorkoutItem").objects.get()
    assert item.uuid is not None
    moved = new.get_model("activity", "ActivitySession").objects.get()
    assert (moved.uuid, moved.owner_id) == (session.uuid, hugo.pk)
    assert new.get_model("activity", "SessionEntry").objects.get().uuid is not None


@pytest.mark.django_db(transaction=True)
def test_an_empty_database_needs_no_account() -> None:
    """A fresh install migrates with no users at all."""
    _migrate(BEFORE)
    _migrate(_latest())


@pytest.mark.django_db(transaction=True)
def test_rows_without_an_account_stop_the_migration() -> None:
    """Exercises with no account to own them is an error, not a silent guess."""
    old = _migrate(BEFORE)
    old.get_model("library", "Exercise").objects.create(name="Plank")
    with pytest.raises(RuntimeError, match="no account to own them"):
        _migrate([("library", "0007_fill_uuids_and_owners")])
    old.get_model("library", "Exercise").objects.all().delete()
    _migrate(_latest())
