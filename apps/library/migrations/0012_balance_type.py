"""Add balance, the sixth shared exercise type, and its two starter exercises.

Balance is listed after flexibility. New accounts get the two balance
exercises from ``apps.library.starter``; this gives them to accounts that
already have a library too, skipping any account that has an exercise of
the same name. Nothing else in an existing library is touched.
"""

from django.db import migrations

ORDER_WITH = ["strength", "flexibility", "balance", "aerobic", "anaerobic", "fitness"]
ORDER_WITHOUT = [s for s in ORDER_WITH if s != "balance"]

# A copy of the starter entries, as migrations can't import live code:
# name, types, muscles, one_sided, default seconds, movement.
EXERCISES = [
    ("Single-leg stand", ["balance"], ["Calves", "Core"], True, 30, "static"),
    ("Single-leg deadlift", ["balance", "strength"], ["Hamstrings", "Glutes", "Core"], True, 40, "dynamic"),
]


def _renumber(exercise_type, slugs):
    """Set each type's ``order`` to its place in ``slugs``."""
    for order, slug in enumerate(slugs):
        exercise_type.objects.filter(slug=slug).update(order=order)


def add_balance(apps, schema_editor):
    """Create the balance type, move the types after it down, and top up existing libraries."""
    ExerciseType = apps.get_model("library", "ExerciseType")
    Exercise = apps.get_model("library", "Exercise")
    MuscleGroup = apps.get_model("library", "MuscleGroup")
    ExerciseType.objects.get_or_create(
        slug="balance", defaults={"name": "Balance", "colour": "#3FB8AF"}
    )
    _renumber(ExerciseType, ORDER_WITH)

    types = {t.slug: t for t in ExerciseType.objects.all()}
    owners = Exercise.objects.values_list("owner_id", flat=True).distinct()
    for owner_id in owners:
        have = set(Exercise.objects.filter(owner_id=owner_id).values_list("name", flat=True))
        for name, type_slugs, muscles, one_sided, seconds, movement in EXERCISES:
            if name in have:
                continue
            exercise = Exercise.objects.create(
                owner_id=owner_id,
                name=name,
                one_sided=one_sided,
                default_duration=seconds,
                movement=movement,
                source="seed",
            )
            exercise.types.set([types[s] for s in type_slugs if s in types])
            exercise.muscles.set(
                [MuscleGroup.objects.get_or_create(owner=None, name=m)[0] for m in muscles]
            )


def remove_balance(apps, schema_editor):
    """Delete the balance type and close the gap it left; the exercises stay."""
    ExerciseType = apps.get_model("library", "ExerciseType")
    ExerciseType.objects.filter(slug="balance").delete()
    _renumber(ExerciseType, ORDER_WITHOUT)


class Migration(migrations.Migration):
    """Add the balance type and its starter exercises."""

    dependencies = [("library", "0011_remove_workout_is_active")]
    operations = [migrations.RunPython(add_balance, remove_balance)]
