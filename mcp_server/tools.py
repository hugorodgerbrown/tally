"""The tools the MCP server offers: read the library and the log, and
create or change exercises and workouts. Nothing here deletes.

Each tool is a function taking the signed-in user and its arguments and
returning a JSON-ready dict. ``ToolError`` carries a message meant for the
model to read and act on.
"""

import datetime as dt
import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q, QuerySet
from django.utils import timezone

from activity.models import ActivitySession, SessionEntry
from library import timeline
from library.models import (
    Equipment,
    Exercise,
    ExerciseType,
    Movement,
    MuscleGroup,
    Workout,
    WorkoutItem,
)

MIN_SECONDS = 5
MAX_SECONDS = 3600

Args = dict[str, Any]
Result = dict[str, Any]
ToolFunc = Callable[[AbstractBaseUser, Args], Result]


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class Tool:
    name: str
    title: str
    description: str
    input_schema: dict[str, Any]
    func: ToolFunc
    read_only: bool

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "inputSchema": self.input_schema,
            "annotations": {
                "title": self.title,
                "readOnlyHint": self.read_only,
                "destructiveHint": False,
                "idempotentHint": self.read_only,
                "openWorldHint": False,
            },
        }


TOOLS: dict[str, Tool] = {}


def tool(
    title: str, description: str, properties: dict[str, Any], required: list[str], read_only: bool
) -> Callable[[ToolFunc], ToolFunc]:
    schema = {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }

    def register(func: ToolFunc) -> ToolFunc:
        TOOLS[func.__name__] = Tool(func.__name__, title, description, schema, func, read_only)
        return func

    return register


# ---------- schema fragments ----------

EXERCISE_REF = {
    "type": "string",
    "description": "The exercise's id (a UUID) or its exact name, any case.",
}
WORKOUT_REF = {
    "type": "string",
    "description": "The workout's id (a UUID) or its exact name, any case.",
}
SECONDS = {"type": "integer", "minimum": MIN_SECONDS, "maximum": MAX_SECONDS}
DATE = {"type": "string", "format": "date", "description": "YYYY-MM-DD, UK time."}
TYPE_SLUGS = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Type slugs from list_types_and_muscles, e.g. strength, flexibility.",
}
MUSCLES = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Muscle group names. Existing names match in any case; new names are added.",
}
EXERCISE_FIELDS: dict[str, Any] = {
    "description": {"type": "string", "description": "How to do it; shown in the planner."},
    "types": TYPE_SLUGS,
    "muscles": MUSCLES,
    "equipment": {
        "type": "string",
        "enum": ["", *Equipment.values],
        "description": "Kit the exercise needs; an empty string for bodyweight.",
    },
    "movement": {
        "type": "string",
        "enum": Movement.values,
        "description": "dynamic for moves through reps (plyometric jumps included); "
        "static for holds such as planks and stretches (isometric). Defaults to dynamic.",
    },
    "one_sided": {
        "type": "boolean",
        "description": "True for moves done per side; they run as two intervals, left then right.",
    },
    "default_duration": {
        **SECONDS,
        "description": "Seconds the builder suggests (per side for one-sided moves).",
    },
}
ITEMS = {
    "type": "array",
    "minItems": 1,
    "description": "The exercises in play order.",
    "items": {
        "type": "object",
        "properties": {
            "exercise": EXERCISE_REF,
            "duration_seconds": {
                **SECONDS,
                "description": "Per side for one-sided moves. Defaults to the exercise's own.",
            },
        },
        "required": ["exercise"],
        "additionalProperties": False,
    },
}
WORKOUT_FIELDS: dict[str, Any] = {
    "description": {"type": "string"},
    "rest_seconds": {
        "type": "integer",
        "minimum": 0,
        "maximum": MAX_SECONDS,
        "description": "Rest between exercises; 0 for none.",
    },
    "rounds": {"type": "integer", "minimum": 1, "maximum": 20},
    "round_rest_seconds": {
        "type": "integer",
        "minimum": 0,
        "maximum": MAX_SECONDS,
        "description": "Break between rounds.",
    },
    "is_active": {
        "type": "boolean",
        "description": "Inactive workouts are hidden from the phone app.",
    },
    "items": ITEMS,
}


# ---------- lookups and serialisers ----------


def _exercises() -> QuerySet[Exercise]:
    return Exercise.objects.prefetch_related("types", "muscles")


def _workouts(user: AbstractBaseUser) -> QuerySet[Workout]:
    own = Q(sessions__user_id=user.pk)
    return Workout.objects.annotate(
        times_done=Count("sessions", filter=own),
        last_done=Max("sessions__started_at", filter=own),
    ).prefetch_related(
        Prefetch("items", WorkoutItem.objects.select_related("exercise")),
        "items__exercise__types",
        "items__exercise__muscles",
    )


def _as_uuid(ref: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(ref)
    except ValueError:
        return None


def find_exercise(ref: Any, qs: QuerySet[Exercise] | None = None) -> Exercise:
    qs = _exercises() if qs is None else qs
    ref = str(ref).strip()
    key = _as_uuid(ref)
    match = qs.filter(uuid=key) if key else qs.filter(name__iexact=ref)
    exercise = match.first()
    if exercise is None:
        raise ToolError(f"No exercise matches {ref!r}. Use list_exercises to find it.")
    return exercise


def find_workout(ref: Any, user: AbstractBaseUser) -> Workout:
    ref = str(ref).strip()
    key = _as_uuid(ref)
    qs = _workouts(user)
    matches = list(qs.filter(uuid=key) if key else qs.filter(name__iexact=ref))
    if not matches:
        raise ToolError(f"No workout matches {ref!r}. Use list_workouts to find it.")
    if len(matches) > 1:
        ids = ", ".join(str(w.uuid) for w in matches)
        raise ToolError(f"More than one workout is called {ref!r}; use an id: {ids}.")
    return matches[0]


def exercise_json(exercise: Exercise) -> Result:
    return {
        "id": str(exercise.uuid),
        "name": exercise.name,
        "description": exercise.description,
        "types": [t.slug for t in exercise.types.all()],
        "muscles": [m.name for m in exercise.muscles.all()],
        "equipment": exercise.equipment,
        "movement": exercise.movement,
        "one_sided": exercise.one_sided,
        "default_duration": exercise.default_duration,
    }


def workout_summary(workout: Workout) -> Result:
    items = list(workout.items.all())
    last_done = getattr(workout, "last_done", None)
    return {
        "id": str(workout.uuid),
        "name": workout.name,
        "description": workout.description,
        "is_active": workout.is_active,
        "rounds": workout.rounds,
        "rest_seconds": workout.rest_seconds,
        "round_rest_seconds": workout.round_rest_seconds,
        "exercise_count": len(items),
        "total_seconds": timeline.total_seconds(workout, items),
        "times_done": getattr(workout, "times_done", None),
        "last_done": last_done.isoformat() if last_done else None,
        "updated_at": workout.updated_at.isoformat(),
    }


def workout_json(workout: Workout) -> Result:
    return {
        **workout_summary(workout),
        "items": [
            {
                "exercise_id": str(item.exercise.uuid),
                "exercise": item.exercise.name,
                "duration_seconds": item.duration_seconds,
                "one_sided": item.exercise.one_sided,
                "equipment": item.exercise.equipment,
                "movement": item.exercise.movement,
                "types": [t.slug for t in item.exercise.types.all()],
                "muscles": [m.name for m in item.exercise.muscles.all()],
            }
            for item in workout.items.all()
        ],
    }


def session_json(session: ActivitySession) -> Result:
    return {
        "id": str(session.uuid),
        "workout": session.workout_name,
        "workout_id": str(session.workout.uuid) if session.workout else None,
        "started_at": timezone.localtime(session.started_at).isoformat(),
        "ended_at": timezone.localtime(session.ended_at).isoformat(),
        "completed": session.completed,
        "rounds": session.rounds,
        "seconds_worked": session.seconds_worked,
        "effort": session.effort,
        "entries": [
            {"exercise": e.exercise_name, "seconds_worked": e.seconds_worked}
            for e in session.entries.all()
        ],
    }


def _date_range(args: Args) -> tuple[dt.datetime | None, dt.datetime | None]:
    """Turn inclusive start_date/end_date into aware datetimes [start, end)."""
    bounds: list[dt.datetime | None] = []
    for key, offset in (("start_date", 0), ("end_date", 1)):
        value = args.get(key)
        if not value:
            bounds.append(None)
            continue
        try:
            day = dt.date.fromisoformat(value) + dt.timedelta(days=offset)
        except (TypeError, ValueError) as exc:
            raise ToolError(f"{key} must be a date like 2026-10-01.") from exc
        bounds.append(timezone.make_aware(dt.datetime.combine(day, dt.time())))
    return bounds[0], bounds[1]


def _sessions(user: AbstractBaseUser, args: Args) -> QuerySet[ActivitySession]:
    start, end = _date_range(args)
    qs = ActivitySession.objects.filter(user_id=user.pk)
    if start:
        qs = qs.filter(started_at__gte=start)
    if end:
        qs = qs.filter(started_at__lt=end)
    return qs


# ---------- read tools ----------


@tool(
    "List types and muscle groups",
    "The exercise types (slug and name), every muscle group in the library, and the "
    "equipment and movement choices. Use these values when filtering or tagging exercises.",
    {},
    [],
    read_only=True,
)
def list_types_and_muscles(user: AbstractBaseUser, args: Args) -> Result:
    return {
        "types": [{"slug": t.slug, "name": t.name} for t in ExerciseType.objects.all()],
        "muscles": list(MuscleGroup.objects.values_list("name", flat=True)),
        "equipment": [{"slug": e.value, "name": e.label} for e in Equipment],
        "movements": [{"slug": m.value, "name": m.label} for m in Movement],
    }


@tool(
    "List exercises",
    "Exercises in the library, with their types, muscle groups, equipment, movement "
    "(dynamic or static), whether they run per side, and default duration. Filters combine.",
    {
        "query": {"type": "string", "description": "Part of the name or description."},
        "type": {"type": "string", "description": "A type slug, e.g. flexibility."},
        "muscle": {"type": "string", "description": "A muscle group name, any case."},
        "equipment": {
            "type": "string",
            "description": "An equipment slug, e.g. kettlebell; an empty string for bodyweight.",
        },
        "movement": {"type": "string", "description": "dynamic or static."},
    },
    [],
    read_only=True,
)
def list_exercises(user: AbstractBaseUser, args: Args) -> Result:
    qs = _exercises()
    if query := args.get("query"):
        qs = qs.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if type_slug := args.get("type"):
        qs = qs.filter(types__slug=type_slug)
    if muscle := args.get("muscle"):
        qs = qs.filter(muscles__name__iexact=muscle)
    if "equipment" in args:
        qs = qs.filter(equipment=str(args["equipment"]))
    if movement := args.get("movement"):
        qs = qs.filter(movement=movement)
    return {"exercises": [exercise_json(e) for e in qs.distinct()]}


@tool(
    "Get an exercise",
    "One exercise, the workouts that use it, and how much time has been logged on it.",
    {"exercise": EXERCISE_REF},
    ["exercise"],
    read_only=True,
)
def get_exercise(user: AbstractBaseUser, args: Args) -> Result:
    exercise = find_exercise(args["exercise"])
    workouts = Workout.objects.filter(items__exercise=exercise).distinct()
    entries = SessionEntry.objects.filter(exercise=exercise, session__user_id=user.pk)
    seconds = sum(entries.values_list("seconds_worked", flat=True))
    return {
        **exercise_json(exercise),
        "used_in_workouts": [{"id": str(w.uuid), "name": w.name} for w in workouts],
        "sessions_logged": entries.values("session").distinct().count(),
        "seconds_logged": seconds,
    }


@tool(
    "List workouts",
    "Workouts with their settings, total length in seconds (including get-ready, rests, "
    "side switches and round breaks), how often each was done, and when it was last done.",
    {
        "include_inactive": {
            "type": "boolean",
            "description": "Also list workouts hidden from the phone app. Default false.",
        }
    },
    [],
    read_only=True,
)
def list_workouts(user: AbstractBaseUser, args: Args) -> Result:
    qs = _workouts(user)
    if not args.get("include_inactive"):
        qs = qs.filter(is_active=True)
    return {"workouts": [workout_summary(w) for w in qs]}


@tool(
    "Get a workout",
    "One workout with its exercises in play order.",
    {"workout": WORKOUT_REF},
    ["workout"],
    read_only=True,
)
def get_workout(user: AbstractBaseUser, args: Args) -> Result:
    return workout_json(find_workout(args["workout"], user))


@tool(
    "List sessions",
    "Logged workout sessions, newest first, with time worked per exercise and the effort "
    "rating (1 to 10) when one was given. Sessions ended early have completed=false.",
    {
        "start_date": DATE,
        "end_date": {**DATE, "description": "YYYY-MM-DD, UK time, inclusive."},
        "workout": WORKOUT_REF,
        "limit": {"type": "integer", "minimum": 1, "maximum": 500, "default": 50},
    },
    [],
    read_only=True,
)
def list_sessions(user: AbstractBaseUser, args: Args) -> Result:
    qs = _sessions(user, args).select_related("workout").prefetch_related("entries")
    if args.get("workout"):
        qs = qs.filter(workout=find_workout(args["workout"], user))
    limit = int(args.get("limit") or 50)
    sessions = list(qs[:limit])
    return {"sessions": [session_json(s) for s in sessions], "truncated": qs.count() > limit}


@tool(
    "Training summary",
    "Totals for a period: sessions, time worked, average effort, active days, and time "
    "split by exercise type, by muscle group, by movement (dynamic or static) and by "
    "exercise. As on the phone's finish "
    "screen, an exercise's time is shared evenly between its types, but counts in full for "
    "each muscle it works, so the muscle split overlaps. Use it for monthly reviews and to "
    "see what has been neglected.",
    {
        "start_date": DATE,
        "end_date": {**DATE, "description": "YYYY-MM-DD, UK time, inclusive."},
    },
    ["start_date", "end_date"],
    read_only=True,
)
def training_summary(user: AbstractBaseUser, args: Args) -> Result:
    sessions = list(_sessions(user, args))
    entries = SessionEntry.objects.filter(session__in=sessions).prefetch_related(
        "exercise__types", "exercise__muscles"
    )
    by_type: dict[str, float] = defaultdict(float)
    by_muscle: dict[str, int] = defaultdict(int)
    by_exercise: dict[str, int] = defaultdict(int)
    by_movement: dict[str, int] = defaultdict(int)
    for entry in entries:
        by_exercise[entry.exercise_name] += entry.seconds_worked
        if entry.exercise is None:
            by_type["unknown"] += entry.seconds_worked
            by_movement["unknown"] += entry.seconds_worked
            continue
        by_movement[entry.exercise.movement] += entry.seconds_worked
        types = entry.exercise.types.all()
        for t in types:
            by_type[t.slug] += entry.seconds_worked / len(types)
        for m in entry.exercise.muscles.all():
            by_muscle[m.name] += entry.seconds_worked
    efforts = [s.effort for s in sessions if s.effort is not None]

    def ranked(totals: dict[str, int] | dict[str, float]) -> dict[str, int]:
        return {k: round(v) for k, v in sorted(totals.items(), key=lambda kv: -kv[1])}

    return {
        "start_date": args["start_date"],
        "end_date": args["end_date"],
        "sessions": len(sessions),
        "completed_sessions": sum(s.completed for s in sessions),
        "active_days": len({timezone.localdate(s.started_at) for s in sessions}),
        "seconds_worked": sum(s.seconds_worked for s in sessions),
        "average_effort": round(sum(efforts) / len(efforts), 1) if efforts else None,
        "seconds_by_type": ranked(by_type),
        "seconds_by_muscle": ranked(by_muscle),
        "seconds_by_movement": ranked(by_movement),
        "seconds_by_exercise": ranked(by_exercise),
        "unused_types": sorted(
            set(ExerciseType.objects.values_list("slug", flat=True)) - set(by_type)
        ),
    }


# ---------- write tools ----------


def _types(slugs: Any) -> list[ExerciseType]:
    if not isinstance(slugs, list) or not slugs:
        raise ToolError("types needs at least one type slug.")
    found = {t.slug: t for t in ExerciseType.objects.filter(slug__in=slugs)}
    unknown = [s for s in slugs if s not in found]
    if unknown:
        valid = ", ".join(ExerciseType.objects.values_list("slug", flat=True))
        raise ToolError(f"Unknown type {', '.join(unknown)}. Valid types: {valid}.")
    return list(found.values())


def _muscles(names: Any) -> list[MuscleGroup]:
    if not isinstance(names, list):
        raise ToolError("muscles must be a list of names.")
    out = []
    for raw in names:
        name = str(raw).strip()
        if not name:
            continue
        muscle = MuscleGroup.objects.filter(name__iexact=name).first()
        out.append(muscle or MuscleGroup.objects.create(name=name[:1].upper() + name[1:]))
    return out


def _check_seconds(value: Any, field: str, low: int = MIN_SECONDS) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= MAX_SECONDS:
        raise ToolError(f"{field} must be a whole number from {low} to {MAX_SECONDS}.")
    return value


def _save_exercise(exercise: Exercise, args: Args) -> Result:
    if "name" in args:
        name = str(args["name"]).strip()
        clash = Exercise.objects.filter(name__iexact=name).exclude(pk=exercise.pk)
        if not name:
            raise ToolError("name is empty.")
        if clash.exists():
            raise ToolError(f"An exercise called {name!r} already exists.")
        exercise.name = name
    if "description" in args:
        exercise.description = str(args["description"])
    if "equipment" in args:
        equipment = args["equipment"] or ""
        if equipment and equipment not in Equipment.values:
            choices = ", ".join(Equipment.values)
            raise ToolError(f"equipment must be one of {choices}, or empty for bodyweight.")
        exercise.equipment = equipment
    if "movement" in args:
        if args["movement"] not in Movement.values:
            raise ToolError(f"movement must be one of {', '.join(Movement.values)}.")
        exercise.movement = args["movement"]
    if "one_sided" in args:
        exercise.one_sided = bool(args["one_sided"])
    if "default_duration" in args:
        exercise.default_duration = _check_seconds(args["default_duration"], "default_duration")
    with transaction.atomic():
        types = _types(args["types"]) if "types" in args else None
        muscles = _muscles(args["muscles"]) if "muscles" in args else None
        _full_clean(exercise)
        exercise.save()
        if types is not None:
            exercise.types.set(types)
        if muscles is not None:
            exercise.muscles.set(muscles)
    return exercise_json(find_exercise(exercise.uuid))


def _require(args: Args, *fields: str) -> None:
    missing = [f for f in fields if f not in args]
    if missing:
        raise ToolError(f"Missing {', '.join(missing)}.")


def _full_clean(obj: Exercise | Workout) -> None:
    try:
        obj.full_clean()
    except ValidationError as exc:
        problems = [f"{field}: {' '.join(msgs)}" for field, msgs in exc.message_dict.items()]
        raise ToolError("; ".join(problems)) from exc


@tool(
    "Create an exercise",
    "Add an exercise to the library. It needs a unique name and at least one type.",
    {"name": {"type": "string"}, **EXERCISE_FIELDS},
    ["name", "types"],
    read_only=False,
)
def create_exercise(user: AbstractBaseUser, args: Args) -> Result:
    _require(args, "name", "types")
    return _save_exercise(Exercise(), args)


@tool(
    "Update an exercise",
    "Change an exercise. Only the fields given change; types and muscles, when given, "
    "replace the current lists. Renaming keeps its history and workouts.",
    {"exercise": EXERCISE_REF, "name": {"type": "string"}, **EXERCISE_FIELDS},
    ["exercise"],
    read_only=False,
)
def update_exercise(user: AbstractBaseUser, args: Args) -> Result:
    exercise = find_exercise(args["exercise"], Exercise.objects.all())
    return _save_exercise(exercise, args)


def _items(raw: Any) -> list[tuple[Exercise, int]]:
    if not isinstance(raw, list) or not raw:
        raise ToolError("items needs at least one exercise.")
    out = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict) or "exercise" not in item:
            raise ToolError(f"items[{i}] needs an exercise.")
        exercise = find_exercise(item["exercise"], Exercise.objects.all())
        seconds = item.get("duration_seconds", exercise.default_duration)
        out.append((exercise, _check_seconds(seconds, f"items[{i}].duration_seconds")))
    return out


def _save_workout(workout: Workout, user: AbstractBaseUser, args: Args) -> Result:
    if "name" in args:
        workout.name = str(args["name"]).strip()
    if "description" in args:
        workout.description = str(args["description"])
    for field in ("rest_seconds", "round_rest_seconds"):
        if field in args:
            setattr(workout, field, _check_seconds(args[field], field, low=0))
    if "rounds" in args:
        rounds = args["rounds"]
        if isinstance(rounds, bool) or not isinstance(rounds, int) or not 1 <= rounds <= 20:
            raise ToolError("rounds must be a whole number from 1 to 20.")
        workout.rounds = rounds
    if "is_active" in args:
        workout.is_active = bool(args["is_active"])
    items = _items(args["items"]) if "items" in args else None
    _full_clean(workout)
    with transaction.atomic():
        workout.save()
        if items is not None:
            workout.items.all().delete()
            WorkoutItem.objects.bulk_create(
                WorkoutItem(workout=workout, exercise=ex, order=i, duration_seconds=secs)
                for i, (ex, secs) in enumerate(items)
            )
    return workout_json(find_workout(workout.uuid, user))


@tool(
    "Create a workout",
    "Build a workout from library exercises. Defaults: 15 s rest between exercises, "
    "1 round, 120 s between rounds, active. One-sided exercises run twice, once per side.",
    {"name": {"type": "string"}, **WORKOUT_FIELDS},
    ["name", "items"],
    read_only=False,
)
def create_workout(user: AbstractBaseUser, args: Args) -> Result:
    _require(args, "name", "items")
    return _save_workout(Workout(), user, args)


@tool(
    "Update a workout",
    "Change a workout. Only the fields given change; items, when given, replace the whole "
    "exercise list, so send every exercise in order. Set is_active false to hide it.",
    {"workout": WORKOUT_REF, "name": {"type": "string"}, **WORKOUT_FIELDS},
    ["workout"],
    read_only=False,
)
def update_workout(user: AbstractBaseUser, args: Args) -> Result:
    return _save_workout(find_workout(args["workout"], user), user, args)
