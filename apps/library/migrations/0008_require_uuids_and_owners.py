"""Make the new uuids and owners required, and names unique per owner."""

import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


def _uuid(model: str) -> migrations.AlterField:
    return migrations.AlterField(
        model_name=model,
        name="uuid",
        field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
    )


def _id(model: str) -> migrations.AlterField:
    return migrations.AlterField(
        model_name=model,
        name="id",
        field=models.BigAutoField(primary_key=True, serialize=False),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0007_fill_uuids_and_owners"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        _uuid("exercisetype"),
        _uuid("musclegroup"),
        _uuid("workoutitem"),
        *(
            _id(m)
            for m in ("exercisetype", "musclegroup", "exercise", "workout", "workoutitem")
        ),
        migrations.AlterField(
            model_name="exercise",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="exercises",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="workout",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workouts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name="exercise",
            name="name",
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name="musclegroup",
            name="name",
            field=models.CharField(max_length=50),
        ),
        migrations.AddConstraint(
            model_name="exercise",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"), name="library_exercise_owner_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="musclegroup",
            constraint=models.UniqueConstraint(
                condition=models.Q(("owner__isnull", True)),
                fields=("name",),
                name="library_musclegroup_shared_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="musclegroup",
            constraint=models.UniqueConstraint(
                fields=("owner", "name"), name="library_musclegroup_owner_name"
            ),
        ),
    ]
