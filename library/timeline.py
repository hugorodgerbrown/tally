"""The interval sequence a workout plays, mirroring the PWA's engine.js."""

from collections.abc import Sequence

from library.models import Workout, WorkoutItem

READY_SECONDS = 5
SWITCH_SECONDS = 5


def segments(workout: Workout, items: Sequence[WorkoutItem] | None = None) -> list[tuple[str, int]]:
    """Return [(kind, seconds)] for every step: ready, work, switch, rest, round."""
    items = list(workout.items.all()) if items is None else items
    out = [("ready", READY_SECONDS)]
    for r in range(workout.rounds):
        for i, item in enumerate(items):
            out.append(("work", item.duration_seconds))
            if item.exercise.one_sided:
                out += [("switch", SWITCH_SECONDS), ("work", item.duration_seconds)]
            if i < len(items) - 1 and workout.rest_seconds:
                out.append(("rest", workout.rest_seconds))
        if r < workout.rounds - 1 and workout.round_rest_seconds:
            out.append(("round", workout.round_rest_seconds))
    return out


def total_seconds(workout: Workout, items: Sequence[WorkoutItem] | None = None) -> int:
    return sum(s for _, s in segments(workout, items))
