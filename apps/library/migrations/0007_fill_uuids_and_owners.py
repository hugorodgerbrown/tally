"""Give existing rows a uuid, and give the existing library to its one account.

Before open sign-up Tally had a single account, the superuser, so every
exercise and workout is theirs: the earliest active superuser, or failing
that the earliest account. Muscle groups stay shared (no owner).
"""

import uuid

from django.db import migrations


def fill(apps, schema_editor):
    for name in ("ExerciseType", "MuscleGroup", "WorkoutItem"):
        model = apps.get_model("library", name)
        for row in model.objects.filter(uuid__isnull=True).only("pk"):
            model.objects.filter(pk=row.pk).update(uuid=uuid.uuid4())

    Exercise = apps.get_model("library", "Exercise")
    Workout = apps.get_model("library", "Workout")
    if not (Exercise.objects.exists() or Workout.objects.exists()):
        return
    User = apps.get_model("auth", "User")
    owner = (
        User.objects.filter(is_superuser=True, is_active=True).order_by("pk").first()
        or User.objects.order_by("pk").first()
    )
    if owner is None:
        raise RuntimeError(
            "The library has exercises or workouts but there is no account to own them. "
            "Create one (manage.py createsuperuser) and migrate again."
        )
    Exercise.objects.filter(owner__isnull=True).update(owner=owner)
    Workout.objects.filter(owner__isnull=True).update(owner=owner)


class Migration(migrations.Migration):
    dependencies = [("library", "0006_basemodel_and_owners")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
