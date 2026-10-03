"""Load a starter exercise library and one sample workout.

Safe to run more than once: existing exercises and workouts are left alone.
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from library.models import Exercise, ExerciseType, MuscleGroup, Source, Workout, WorkoutItem

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

MORNING_MOBILITY = [
    ("90/90 hip switch", 45),
    ("Cat-cow", 40),
    ("Thread the needle", 30),
    ("Split squat", 40),
    ("Kettlebell swing", 40),
    ("Curtsey squat", 40),
    ("Child's pose", 60),
]


class Command(BaseCommand):
    help = "Load starter exercises and a sample 'Morning mobility' workout."

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        types = {t.slug: t for t in ExerciseType.objects.all()}
        created = 0
        for name, type_slugs, muscles, one_sided, duration in EXERCISES:
            exercise, is_new = Exercise.objects.get_or_create(
                name=name,
                defaults={
                    "one_sided": one_sided,
                    "default_duration": duration,
                    "equipment": EQUIPMENT.get(name, ""),
                    "source": Source.SEED,
                },
            )
            if not is_new:
                continue
            created += 1
            exercise.types.set([types[s] for s in type_slugs])
            exercise.muscles.set([MuscleGroup.objects.get_or_create(name=m)[0] for m in muscles])
        self.stdout.write(f"{created} exercises created")

        workout, is_new = Workout.objects.get_or_create(
            name="Morning mobility", defaults={"source": Source.SEED}
        )
        if is_new:
            for order, (name, seconds) in enumerate(MORNING_MOBILITY):
                WorkoutItem.objects.create(
                    workout=workout,
                    exercise=Exercise.objects.get(name=name),
                    order=order,
                    duration_seconds=seconds,
                )
            self.stdout.write(f"{workout.pk} {workout.name}: created")
