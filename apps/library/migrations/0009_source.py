"""Add ``source`` to workouts and exercises: who made each one.

Rows that already exist get a blank source ("not recorded"); the default
then switches to Manage for everything made from now on.
"""

from django.db import migrations, models

SOURCES = [("manage", "Manage"), ("claude", "Claude"), ("seed", "Starter library")]


class Migration(migrations.Migration):
    """Record who made each workout and exercise."""

    dependencies = [
        ("library", "0008_require_uuids_and_owners"),
    ]

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
    ]
