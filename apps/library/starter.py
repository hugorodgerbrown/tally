"""The starter library every new account gets: 21 exercises and one workout.

Called from sign-up (``apps.accounts.sign_in.user_for``) when an account is
created, and from ``manage.py seed_library`` for accounts that predate it.
Safe to run twice: exercises the account already has are left alone, and
the sample workout is only added when it is missing.
"""

import logging
from dataclasses import dataclass

from django.contrib.auth.base_user import AbstractBaseUser
from django.db import transaction

from apps.library.models import (
    Exercise,
    ExerciseType,
    MuscleGroup,
    Source,
    Workout,
    WorkoutItem,
)

logger = logging.getLogger(__name__)

# name, types, muscles, one_sided, default seconds
EXERCISES = [
    ("90/90 hip switch", ["flexibility"], ["Hips", "Glutes"], False, 45),
    ("Cat-cow", ["flexibility"], ["Spine", "Core"], False, 40),
    ("Thread the needle", ["flexibility"], ["Upper back", "Shoulders"], True, 30),
    ("Child's pose", ["flexibility"], ["Lower back", "Hips"], False, 60),
    ("World's greatest stretch", ["flexibility"], ["Hips", "Hamstrings", "Upper back"], True, 30),
    ("Downward dog", ["flexibility"], ["Hamstrings", "Calves", "Shoulders"], False, 40),
    ("Pigeon pose", ["flexibility"], ["Hips", "Glutes"], True, 45),
    ("Split squat", ["strength"], ["Quads", "Glutes", "Hamstrings"], True, 40),
    ("Curtsey squat", ["strength"], ["Glutes", "Quads", "Adductors"], False, 40),
    ("Bodyweight squat", ["strength"], ["Quads", "Glutes"], False, 40),
    ("Glute bridge", ["strength"], ["Glutes", "Hamstrings"], False, 40),
    ("Push-up", ["strength"], ["Chest", "Triceps", "Shoulders"], False, 30),
    ("Plank", ["strength", "fitness"], ["Core", "Shoulders"], False, 45),
    ("Side plank", ["strength"], ["Core", "Obliques"], True, 30),
    ("Dead bug", ["strength"], ["Core"], False, 40),
    ("Kettlebell swing", ["strength", "aerobic"], ["Glutes", "Hamstrings", "Core"], False, 40),
    ("Goblet squat", ["strength"], ["Quads", "Glutes", "Core"], False, 40),
    ("Burpee", ["anaerobic", "fitness"], ["Quads", "Chest", "Core"], False, 30),
    ("Mountain climbers", ["aerobic", "fitness"], ["Core", "Shoulders", "Hip flexors"], False, 30),
    ("Jumping jacks", ["aerobic"], ["Calves", "Shoulders"], False, 45),
    ("High knees", ["aerobic", "anaerobic"], ["Hip flexors", "Quads", "Calves"], False, 30),
]

EQUIPMENT = {"Kettlebell swing": "kettlebell", "Goblet squat": "kettlebell"}

STATIC = {"Child's pose", "Downward dog", "Pigeon pose", "Plank", "Side plank"}

MORNING_MOBILITY = [
    ("90/90 hip switch", 45),
    ("Cat-cow", 40),
    ("Thread the needle", 30),
    ("Split squat", 40),
    ("Kettlebell swing", 40),
    ("Curtsey squat", 40),
    ("Child's pose", 60),
]

SAMPLE_WORKOUT = "Morning mobility"


@dataclass(frozen=True)
class StarterResult:
    """What ``install`` added."""

    exercises: int
    workout: bool


@transaction.atomic
def install(user: AbstractBaseUser) -> StarterResult:
    """Add the starter exercises and the sample workout to ``user``'s library."""
    types = ExerciseType.objects.all().by_slug()
    have = set(Exercise.objects.for_user(user).values_list("name", flat=True))
    created = 0
    for name, type_slugs, muscles, one_sided, duration in EXERCISES:
        if name in have:
            continue
        exercise = Exercise.objects.create(
            owner_id=user.pk,
            name=name,
            one_sided=one_sided,
            default_duration=duration,
            equipment=EQUIPMENT.get(name, ""),
            movement="static" if name in STATIC else "dynamic",
            source=Source.SEED,
        )
        exercise.types.set([types[s] for s in type_slugs])
        exercise.muscles.set(
            [MuscleGroup.objects.get_or_create(owner=None, name=m)[0] for m in muscles]
        )
        created += 1

    added_workout = False
    if not Workout.objects.for_user(user).filter(name=SAMPLE_WORKOUT).exists():
        workout = Workout.objects.create(owner_id=user.pk, name=SAMPLE_WORKOUT, source=Source.SEED)
        # Names are unique per owner, not globally, so in_bulk(field_name=...) won't do.
        names = [n for n, _ in MORNING_MOBILITY]
        by_name = {e.name: e for e in Exercise.objects.for_user(user).filter(name__in=names)}
        WorkoutItem.objects.bulk_create(
            WorkoutItem(workout=workout, exercise=by_name[name], order=i, duration_seconds=secs)
            for i, (name, secs) in enumerate(MORNING_MOBILITY)
            if name in by_name
        )
        added_workout = True
    logger.info("library.starter user=%s exercises=%d workout=%s", user.pk, created, added_workout)
    return StarterResult(exercises=created, workout=added_workout)
