"""Drop ``Workout.is_active``, replaced by ``status`` in 0010."""

from django.db import migrations


class Migration(migrations.Migration):
    """Remove the old shown/hidden flag."""

    dependencies = [
        ("library", "0010_workout_status"),
    ]

    operations = [
        migrations.RemoveField(model_name="workout", name="is_active"),
    ]
