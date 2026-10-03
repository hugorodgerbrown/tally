import django.utils.timezone
from django.db import migrations, models
from django.db.models import F

SOURCES = [("manage", "Manage"), ("claude", "Claude"), ("seed", "Starter library")]


def created_from_updated(apps, schema_editor):
    """Existing workouts get their last edit as a stand-in creation date."""
    apps.get_model("library", "Workout").objects.update(created_at=F("updated_at"))


class Migration(migrations.Migration):
    dependencies = [
        ("library", "0005_exercise_movement"),
    ]

    # Rows that already exist are added with a blank source ("not recorded"),
    # then the default switches to Manage for everything made from now on.
    operations = [
        migrations.AddField(
            model_name="exercise",
            name="source",
            field=models.CharField(blank=True, choices=SOURCES, default="", max_length=10),
        ),
        migrations.AlterField(
            model_name="exercise",
            name="source",
            field=models.CharField(blank=True, choices=SOURCES, default="manage", max_length=10),
        ),
        migrations.AddField(
            model_name="workout",
            name="source",
            field=models.CharField(blank=True, choices=SOURCES, default="", max_length=10),
        ),
        migrations.AlterField(
            model_name="workout",
            name="source",
            field=models.CharField(blank=True, choices=SOURCES, default="manage", max_length=10),
        ),
        migrations.AddField(
            model_name="workout",
            name="created_at",
            field=models.DateTimeField(default=django.utils.timezone.now, editable=False),
        ),
        migrations.RunPython(created_from_updated, migrations.RunPython.noop),
        migrations.AddField(
            model_name="workout",
            name="one_off",
            field=models.BooleanField(
                default=False,
                help_text="Made for one go. Listed on the phone for 7 days, "
                "then only in Manage until kept.",
            ),
        ),
    ]
