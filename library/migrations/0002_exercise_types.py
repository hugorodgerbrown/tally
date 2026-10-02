from django.db import migrations

TYPES = [
    ("strength", "Strength", "#F7C948"),
    ("flexibility", "Flexibility", "#8FD3B0"),
    ("aerobic", "Aerobic", "#FF8A65"),
    ("anaerobic", "Anaerobic", "#E57BB0"),
    ("fitness", "Fitness", "#8FA2FF"),
]


def create_types(apps, schema_editor):
    ExerciseType = apps.get_model("library", "ExerciseType")
    for order, (slug, name, colour) in enumerate(TYPES):
        ExerciseType.objects.get_or_create(
            slug=slug, defaults={"name": name, "colour": colour, "order": order}
        )


class Migration(migrations.Migration):
    dependencies = [("library", "0001_initial")]
    operations = [migrations.RunPython(create_types, migrations.RunPython.noop)]
