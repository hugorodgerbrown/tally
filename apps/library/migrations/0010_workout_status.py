"""Add ``status`` to workouts: pinned, active or archived.

Every workout shown on the phone today becomes pinned, so each account's
home screen looks the same the day this ships; hidden ones become archived.
``is_active`` is dropped in the next migration.
"""

from django.apps.registry import Apps
from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor

STATUSES = [("pinned", "Pinned"), ("active", "Active"), ("archived", "Archived")]


def forwards(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Map shown workouts to pinned and hidden ones to archived."""
    Workout = apps.get_model("library", "Workout")
    Workout.objects.filter(is_active=True).update(status="pinned")
    Workout.objects.filter(is_active=False).update(status="archived")


def backwards(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    """Map pinned and active workouts to shown, archived ones to hidden."""
    Workout = apps.get_model("library", "Workout")
    Workout.objects.filter(status="archived").update(is_active=False)
    Workout.objects.exclude(status="archived").update(is_active=True)


class Migration(migrations.Migration):
    """Give each workout a status, filled from ``is_active``."""

    dependencies = [
        ("library", "0009_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="workout",
            name="status",
            field=models.CharField(
                choices=STATUSES,
                default="active",
                help_text="Pinned shows on the phone's home screen, Active behind "
                '"Show all", Archived not at all.',
                max_length=10,
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
