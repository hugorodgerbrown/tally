"""Add balance, the sixth shared exercise type, listed after flexibility."""

from django.db import migrations

ORDER_WITH = ["strength", "flexibility", "balance", "aerobic", "anaerobic", "fitness"]
ORDER_WITHOUT = [s for s in ORDER_WITH if s != "balance"]


def _renumber(exercise_type, slugs):
    """Set each type's ``order`` to its place in ``slugs``."""
    for order, slug in enumerate(slugs):
        exercise_type.objects.filter(slug=slug).update(order=order)


def add_balance(apps, schema_editor):
    """Create the balance type and move the types after it down one place."""
    ExerciseType = apps.get_model("library", "ExerciseType")
    ExerciseType.objects.get_or_create(
        slug="balance", defaults={"name": "Balance", "colour": "#3FB8AF"}
    )
    _renumber(ExerciseType, ORDER_WITH)


def remove_balance(apps, schema_editor):
    """Delete the balance type and close the gap it left."""
    ExerciseType = apps.get_model("library", "ExerciseType")
    ExerciseType.objects.filter(slug="balance").delete()
    _renumber(ExerciseType, ORDER_WITHOUT)


class Migration(migrations.Migration):
    """Add the balance type."""

    dependencies = [("library", "0011_remove_workout_is_active")]
    operations = [migrations.RunPython(add_balance, remove_balance)]
