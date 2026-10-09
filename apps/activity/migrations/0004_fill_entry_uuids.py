"""Give existing session entries a uuid."""

import uuid

from django.db import migrations


def fill(apps, schema_editor):
    SessionEntry = apps.get_model("activity", "SessionEntry")
    for row in SessionEntry.objects.filter(uuid__isnull=True).only("pk"):
        SessionEntry.objects.filter(pk=row.pk).update(uuid=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [("activity", "0003_basemodel")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
