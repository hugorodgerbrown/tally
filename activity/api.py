"""JSON endpoints used by the PWA.

Both endpoints use the Django session cookie. Session uploads are
idempotent: the client sends the same UUID on every retry and the server
replaces the stored record.
"""

import json
import uuid
from collections.abc import Callable
from typing import Any, cast

from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from library.equipment import equipment_json
from library.models import ONE_OFF_DAYS, Exercise, ExerciseType, Workout

from .models import ActivitySession, DiscardedSession, SessionEntry

type View = Callable[..., HttpResponse]


def _login_required_json(view: View) -> View:
    def wrapped(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return JsonResponse({"error": "not_authenticated"}, status=401)
        return view(request, *args, **kwargs)

    return wrapped


def serialize_workout(workout: Workout) -> dict[str, Any]:
    return {
        "id": str(workout.uuid),
        "name": workout.name,
        "description": workout.description,
        "rest": workout.rest_seconds,
        "rounds": workout.rounds,
        "roundRest": workout.round_rest_seconds,
        "oneOff": workout.one_off,
        "createdAt": workout.created_at.isoformat(),
        "updatedAt": workout.updated_at.isoformat(),
        "items": [
            {
                "exerciseId": str(item.exercise.uuid),
                "name": item.exercise.name,
                "dur": item.duration_seconds,
                "sides": item.exercise.one_sided,
                "equipment": item.exercise.equipment,
                "movement": item.exercise.movement,
                "types": [t.slug for t in item.exercise.types.all()],
                "muscles": [m.name for m in item.exercise.muscles.all()],
            }
            for item in workout.items.all()
        ],
    }


@require_GET
@_login_required_json
def workouts(request: HttpRequest) -> HttpResponse:
    qs = Workout.objects.on_phone().prefetch_related(
        "items__exercise__types", "items__exercise__muscles"
    )
    return JsonResponse(
        {
            "types": [
                {"slug": t.slug, "name": t.name, "colour": t.colour}
                for t in ExerciseType.objects.all()
            ],
            "equipment": equipment_json(),
            "oneOffDays": ONE_OFF_DAYS,
            "workouts": [serialize_workout(w) for w in qs if w.items.all()],
        }
    )


@require_POST
@_login_required_json
def keep_workout(request: HttpRequest, workout_id: uuid.UUID) -> HttpResponse:
    """Turn a one-off into a saved workout, from the phone's Keep button."""
    workout = Workout.objects.filter(uuid=workout_id).first()
    if workout is None:
        return JsonResponse({"error": "not_found"}, status=404)
    workout.one_off = False
    workout.save(update_fields=["one_off", "updated_at"])
    return JsonResponse({"kept": str(workout_id)})


class InvalidSession(ValueError):
    pass


def _uuid_or_none(value: object) -> uuid.UUID | None:
    return None if value in (None, "") else uuid.UUID(str(value))


type ParsedSession = tuple[uuid.UUID, dict[str, Any], list[dict[str, Any]]]


def _parse_session(data: Any) -> ParsedSession:
    try:
        session_uuid = uuid.UUID(str(data["uuid"]))
        started_at = parse_datetime(data["startedAt"])
        ended_at = parse_datetime(data["endedAt"])
        entries: list[dict[str, Any]] = [
            {
                "exercise_uuid": _uuid_or_none(e.get("exerciseId")),
                "exercise_name": str(e["name"])[:100],
                "seconds_worked": max(0, int(e["seconds"])),
            }
            for e in data.get("entries", [])
        ]
        entries = [e for e in entries if e["seconds_worked"] > 0]
        effort = data.get("effort")
        effort = None if effort in (None, "") else int(effort)
        fields = {
            "workout_uuid": _uuid_or_none(data.get("workoutId")),
            "workout_name": str(data["workoutName"])[:100],
            "started_at": started_at,
            "ended_at": ended_at,
            "completed": bool(data.get("completed")),
            "rounds": max(1, int(data.get("rounds", 1))),
            "effort": effort,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidSession(str(exc)) from exc
    if started_at is None or ended_at is None:
        raise InvalidSession("bad timestamp")
    if effort is not None and not 1 <= effort <= 10:
        raise InvalidSession("effort out of range")
    fields["seconds_worked"] = sum(e["seconds_worked"] for e in entries)
    return session_uuid, fields, entries


@require_POST
@_login_required_json
def sessions(request: HttpRequest) -> HttpResponse:
    """Upsert a batch of sessions: ``{"sessions": [...]}``.

    An item of ``{"uuid": ..., "discarded": true}`` deletes that session
    instead and records the UUID, so a later upload of it is ignored.

    Returns the UUIDs saved, discarded, and rejected as malformed, so the
    client can clear all three from its outbox and only retry on network
    failure.
    """
    try:
        payload = json.loads(request.body)
        items = payload["sessions"]
    except ValueError, KeyError, TypeError:
        return JsonResponse({"error": "bad_request"}, status=400)

    user = cast(User, request.user)  # _login_required_json has checked
    parsed: list[ParsedSession] = []
    saved: list[str] = []
    discarded: list[str] = []
    rejected: list[dict[str, str | None]] = []
    for data in items:
        try:
            if isinstance(data, dict) and data.get("discarded") is True:
                session_uuid = uuid.UUID(str(data["uuid"]))
                with transaction.atomic():
                    ActivitySession.objects.filter(uuid=session_uuid, user=user).delete()
                    DiscardedSession.objects.get_or_create(uuid=session_uuid, user=user)
                discarded.append(str(session_uuid))
                continue
            parsed.append(_parse_session(data))
        except (KeyError, ValueError) as exc:
            rejected.append(
                {"uuid": data.get("uuid") if isinstance(data, dict) else None, "error": str(exc)}
            )
            continue

    # Already discarded: acknowledge so the phone clears it, but don't store.
    gone = set(
        DiscardedSession.objects.filter(user=user, uuid__in=[u for u, _, _ in parsed]).values_list(
            "uuid", flat=True
        )
    )
    saved.extend(str(u) for u, _, _ in parsed if u in gone)
    parsed = [p for p in parsed if p[0] not in gone]

    workout_ids = dict(
        Workout.objects.filter(uuid__in={f["workout_uuid"] for _, f, _ in parsed}).values_list(
            "uuid", "pk"
        )
    )
    exercise_ids = dict(
        Exercise.objects.filter(
            uuid__in={e["exercise_uuid"] for _, _, es in parsed for e in es}
        ).values_list("uuid", "pk")
    )
    for session_uuid, fields, entries in parsed:
        # Resolve the public UUIDs; rows deleted since the phone cached the
        # workout resolve to None and the names keep the log readable.
        fields["workout_id"] = workout_ids.get(fields.pop("workout_uuid"))
        for e in entries:
            e["exercise_id"] = exercise_ids.get(e.pop("exercise_uuid"))

        with transaction.atomic():
            session, created = ActivitySession.objects.get_or_create(
                uuid=session_uuid, defaults={**fields, "user": user}
            )
            if session.user_id != user.pk:
                rejected.append({"uuid": str(session_uuid), "error": "not_owner"})
                continue
            if not created:
                for k, v in fields.items():
                    setattr(session, k, v)
                session.save()
                session.entries.all().delete()
            SessionEntry.objects.bulk_create(
                SessionEntry(session=session, order=i, **e) for i, e in enumerate(entries)
            )
        saved.append(str(session_uuid))

    return JsonResponse({"saved": saved, "discarded": discarded, "rejected": rejected})
