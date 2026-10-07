"""Move the library onto BaseModel and give exercises, workouts and muscles an owner.

Three steps, so Postgres never alters a table it has pending updates on:
this one adds the new columns as nullable, 0007 fills them, and 0008
makes them required and swaps the old unique names for per-owner ones.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def _timestamps(model: str, *, created: bool = True, updated: bool = True) -> list:
    ops = []
    if created:
        ops.append(
            migrations.AddField(
                model_name=model,
                name="created_at",
                field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
                preserve_default=False,
            )
        )
    if updated:
        ops.append(
            migrations.AddField(
                model_name=model,
                name="updated_at",
                field=models.DateTimeField(auto_now=True),
            )
        )
    return ops


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0005_exercise_movement"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        *_timestamps("exercisetype"),
        *_timestamps("musclegroup"),
        *_timestamps("exercise"),
        *_timestamps("workout", updated=False),
        *_timestamps("workoutitem"),
        migrations.AddField(
            model_name="exercisetype", name="uuid", field=models.UUIDField(null=True, editable=False)
        ),
        migrations.AddField(
            model_name="musclegroup", name="uuid", field=models.UUIDField(null=True, editable=False)
        ),
        migrations.AddField(
            model_name="workoutitem", name="uuid", field=models.UUIDField(null=True, editable=False)
        ),
        migrations.AddField(
            model_name="musclegroup",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                help_text="Empty for the shared starter set.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="exercise",
            name="owner",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="exercises",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="workout",
            name="owner",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="workouts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
