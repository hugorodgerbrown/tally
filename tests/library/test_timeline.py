"""Tests for apps.library.timeline, the Python twin of engine.js's buildTimeline."""

from typing import Any

import pytest

from apps.library import timeline
from tests.factories import ExerciseFactory, WorkoutFactory, WorkoutItemFactory

pytestmark = pytest.mark.django_db


def test_timeline_matches_engine_js(user: Any) -> None:
    """Ready, work, a side switch, rests and the round break, as the phone plays them."""
    lunge = ExerciseFactory.create(owner=user, name="Lunge", one_sided=True)
    plank = ExerciseFactory.create(owner=user, name="Plank")
    workout = WorkoutFactory.create(owner=user, rest_seconds=10, rounds=2, round_rest_seconds=60)
    WorkoutItemFactory.create(workout=workout, exercise=lunge, order=0, duration_seconds=20)
    WorkoutItemFactory.create(workout=workout, exercise=plank, order=1, duration_seconds=30)
    one_round = [("work", 20), ("switch", 5), ("work", 20), ("rest", 10), ("work", 30)]
    assert timeline.segments(workout) == [("ready", 5), *one_round, ("round", 60), *one_round]
    assert timeline.total_seconds(workout) == 5 + 2 * 85 + 60
