"""JSON endpoints used by the PWA.

Both endpoints use the Django session cookie. Session uploads are
idempotent: the client sends the same UUID on every retry and the server
replaces the stored record.
"""

import json
import uuid

from django.db import transaction
from django.http import JsonResponse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from library.models import Exercise, ExerciseType, Workout

from .models import ActivitySession, SessionEntry


def _login_required_json(view):
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "not_authenticated"}, status=401)
        return view(request, *args, **kwargs)

    return wrapped


def serialize_workout(workout):
    return {
        "id": str(workout.uuid),
        "name": workout.name,
        "description": workout.description,
        "rest": workout.rest_seconds,
        "rounds": workout.rounds,
        "roundRest": workout.round_rest_seconds,
        "updatedAt": workout.updated_at.isoformat(),
        "items": [
            {
                "exerciseId": str(item.exercise.uuid),
                "name": item.exercise.name,
                "dur": item.duration_seconds,
                "sides": item.exercise.one_sided,
                "types": [t.slug for t in item.exercise.types.all()],
                "muscles": [m.name for m in item.exercise.muscles.all()],
            }
            for item in workout.items.all()
        ],
    }


@require_GET
@_login_required_json
def workouts(request):
    qs = Workout.objects.filter(is_active=True).prefetch_related(
        "items__exercise__types", "items__exercise__muscles"
    )
    return JsonResponse(
        {
            "types": [
                {"slug": t.slug, "name": t.name, "colour": t.colour}
                for t in ExerciseType.objects.all()
            ],
            "workouts": [serialize_workout(w) for w in qs if w.items.all()],
        }
    )


class InvalidSession(ValueError):
    pass


def _uuid_or_none(value):
    return None if value in (None, "") else uuid.UUID(str(value))


def _parse_session(data):
    try:
        session_uuid = uuid.UUID(str(data["uuid"]))
        started_at = parse_datetime(data["startedAt"])
        ended_at = parse_datetime(data["endedAt"])
        entries = [
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
def sessions(request):
    """Upsert a batch of sessions: ``{"sessions": [...]}``.

    Returns the UUIDs saved and those rejected as malformed, so the client
    can clear both from its outbox and only retry on network failure.
    """
    try:
        payload = json.loads(request.body)
        items = payload["sessions"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"error": "bad_request"}, status=400)

    parsed, saved, rejected = [], [], []
    for data in items:
        try:
            parsed.append(_parse_session(data))
        except InvalidSession as exc:
            rejected.append(
                {"uuid": data.get("uuid") if isinstance(data, dict) else None, "error": str(exc)}
            )
            continue

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
                uuid=session_uuid, defaults={**fields, "user": request.user}
            )
            if session.user_id != request.user.pk:
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

    return JsonResponse({"saved": saved, "rejected": rejected})
