"""Tests for the library and activity admins: every list and change page renders."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from tests.factories import (
    ActivitySessionFactory,
    DiscardedSessionFactory,
    MuscleGroupFactory,
    SessionEntryFactory,
    UserFactory,
    WorkoutItemFactory,
    exercise_type,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client_in(client: Client) -> Client:
    """The client, signed in as a superuser."""
    client.force_login(UserFactory.create(is_staff=True, is_superuser=True))
    return client


@pytest.fixture
def rows(db: None) -> dict[str, Any]:
    """One row of each model, keyed by its admin URL name."""
    item = WorkoutItemFactory.create()
    session = ActivitySessionFactory.create(owner=item.workout.owner, workout=item.workout)
    return {
        "library_exercisetype": exercise_type("strength"),
        "library_musclegroup": MuscleGroupFactory.create(),
        "library_exercise": item.exercise,
        "library_workout": item.workout,
        "library_workoutitem": item,
        "activity_activitysession": session,
        "activity_sessionentry": SessionEntryFactory.create(session=session),
        "activity_discardedsession": DiscardedSessionFactory.create(),
    }


@pytest.mark.parametrize(
    "name",
    [
        "library_exercisetype",
        "library_musclegroup",
        "library_exercise",
        "library_workout",
        "library_workoutitem",
        "activity_activitysession",
        "activity_sessionentry",
        "activity_discardedsession",
    ],
)
def test_admin_pages_render(admin_client_in: Client, rows: dict[str, Any], name: str) -> None:
    """The changelist and the change page answer 200."""
    assert admin_client_in.get(reverse(f"admin:{name}_changelist")).status_code == 200
    change = reverse(f"admin:{name}_change", args=[rows[name].pk])
    assert admin_client_in.get(change).status_code == 200
