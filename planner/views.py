import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Max, Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from library import timeline
from library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem

from .forms import ExerciseForm, WorkoutForm


def exercise_json(exercise):
    return {
        "id": str(exercise.uuid),
        "name": exercise.name,
        "sides": exercise.one_sided,
        "dur": exercise.default_duration,
        "types": [t.slug for t in exercise.types.all()],
        "muscles": [m.name for m in exercise.muscles.all()],
    }


def _exercises():
    return Exercise.objects.prefetch_related("types", "muscles")


def _wants_json(request):
    return "application/json" in request.headers.get("Accept", "")


# ---------- workouts ----------


@login_required
def workout_list(request):
    workouts = (
        Workout.objects.annotate(
            times_done=Count("sessions"), last_done=Max("sessions__started_at")
        )
        .prefetch_related(
            Prefetch("items", WorkoutItem.objects.select_related("exercise")),
            "items__exercise__types",
        )
        .order_by("-is_active", "name")
    )
    rows = []
    for w in workouts:
        items = list(w.items.all())
        segs = timeline.segments(w, items)
        types = {t for i in items for t in i.exercise.types.all()}
        rows.append(
            {
                "workout": w,
                "items": items,
                "segments": segs,
                "total": sum(s for _, s in segs),
                "types": sorted(types, key=lambda t: t.order),
            }
        )
    return render(request, "planner/workout_list.html", {"rows": rows, "nav": "workouts"})


@login_required
def workout_edit(request, uuid=None):
    workout = get_object_or_404(Workout, uuid=uuid) if uuid else Workout()
    if request.method == "POST":
        form = WorkoutForm(request.POST, instance=workout)
        if form.is_valid():
            with transaction.atomic():
                workout = form.save()
                workout.items.all().delete()
                WorkoutItem.objects.bulk_create(
                    WorkoutItem(workout=workout, exercise=ex, order=i, duration_seconds=dur)
                    for i, (ex, dur) in enumerate(form.cleaned_data["items"])
                )
                workout.save()  # bump updated_at so phones refresh it
            messages.success(request, f"Saved {workout.name}.")
            return redirect("planner:workouts")
        try:
            items = json.loads(request.POST.get("items") or "[]")
        except ValueError:
            items = []
    else:
        form = WorkoutForm(instance=workout)
        items = (
            [
                {"exercise": str(i.exercise.uuid), "dur": i.duration_seconds}
                for i in workout.items.select_related("exercise")
            ]
            if workout.pk
            else []
        )

    context = {
        "form": form,
        "workout": workout,
        "nav": "workouts",
        "builder": {
            "items": items,
            "library": [exercise_json(e) for e in _exercises()],
            "types": [
                {"slug": t.slug, "name": t.name, "colour": t.colour}
                for t in ExerciseType.objects.all()
            ],
            "muscles": list(MuscleGroup.objects.values_list("name", flat=True)),
        },
        "exercise_form": ExerciseForm(auto_id="ex_%s"),
    }
    return render(request, "planner/workout_edit.html", context)


@login_required
@require_POST
def workout_duplicate(request, uuid):
    source = get_object_or_404(Workout, uuid=uuid)
    items = list(source.items.all())
    with transaction.atomic():
        copy = Workout.objects.create(
            name=f"{source.name} (copy)"[:100],
            description=source.description,
            rest_seconds=source.rest_seconds,
            rounds=source.rounds,
            round_rest_seconds=source.round_rest_seconds,
        )
        WorkoutItem.objects.bulk_create(
            WorkoutItem(
                workout=copy,
                exercise_id=i.exercise_id,
                order=i.order,
                duration_seconds=i.duration_seconds,
            )
            for i in items
        )
    return redirect("planner:workout_edit", uuid=copy.uuid)


@login_required
@require_POST
def workout_toggle(request, uuid):
    workout = get_object_or_404(Workout, uuid=uuid)
    workout.is_active = not workout.is_active
    workout.save(update_fields=["is_active", "updated_at"])
    state = "shown on" if workout.is_active else "hidden from"
    messages.success(request, f"{workout.name} is {state} the phone.")
    return redirect("planner:workouts")


@login_required
def workout_delete(request, uuid):
    workout = get_object_or_404(Workout, uuid=uuid)
    if request.method == "POST":
        workout.delete()
        messages.success(request, f"Deleted {workout.name}. Its logged sessions are kept.")
        return redirect("planner:workouts")
    return render(
        request,
        "planner/confirm_delete.html",
        {
            "nav": "workouts",
            "object_name": workout.name,
            "kind": "workout",
            "detail": "Sessions already logged for it stay in your history.",
            "cancel_url": "planner:workouts",
        },
    )


# ---------- exercises ----------


@login_required
def exercise_list(request):
    q = request.GET.get("q", "").strip()
    type_slug = request.GET.get("type", "")
    exercises = (
        _exercises()
        .annotate(used_in=Count("workout_items__workout", distinct=True))
        .order_by("name")
    )
    if q:
        exercises = exercises.filter(
            Q(name__icontains=q) | Q(muscles__name__icontains=q)
        ).distinct()
    if type_slug:
        exercises = exercises.filter(types__slug=type_slug)
    return render(
        request,
        "planner/exercise_list.html",
        {
            "exercises": exercises,
            "types": ExerciseType.objects.all(),
            "q": q,
            "type_slug": type_slug,
            "total": Exercise.objects.count(),
            "nav": "exercises",
        },
    )


@login_required
def exercise_edit(request, uuid=None):
    exercise = get_object_or_404(Exercise, uuid=uuid) if uuid else Exercise()
    form = ExerciseForm(request.POST or None, instance=exercise)
    if request.method == "POST":
        if form.is_valid():
            exercise = form.save()
            if _wants_json(request):
                fresh = _exercises().get(pk=exercise.pk)
                return JsonResponse({"exercise": exercise_json(fresh)}, status=201)
            messages.success(request, f"Saved {exercise.name}.")
            return redirect("planner:exercises")
        if _wants_json(request):
            return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    return render(
        request,
        "planner/exercise_edit.html",
        {"form": form, "exercise": exercise, "nav": "exercises"},
    )


@login_required
def exercise_delete(request, uuid):
    exercise = get_object_or_404(Exercise, uuid=uuid)
    used_in = Workout.objects.filter(items__exercise=exercise).distinct()
    if request.method == "POST" and not used_in:
        exercise.delete()
        messages.success(request, f"Deleted {exercise.name}.")
        return redirect("planner:exercises")
    return render(
        request,
        "planner/confirm_delete.html",
        {
            "nav": "exercises",
            "object_name": exercise.name,
            "kind": "exercise",
            "blocked_by": used_in,
            "detail": "Logged sessions keep its name.",
            "cancel_url": "planner:exercises",
        },
    )
