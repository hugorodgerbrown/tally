"""Move the activity log onto BaseModel; ``user`` becomes ``owner``.

Renames keep the data: ``synced_at`` was already an auto_now timestamp
(now ``updated_at``) and ``discarded_at`` an auto_now_add one (now
``created_at``). Session entries get a uuid here, filled in 0004 and made
unique in 0005.
"""

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("activity", "0002_discardedsession")]

    operations = [
        migrations.RenameField("activitysession", "user", "owner"),
        migrations.RenameField("activitysession", "synced_at", "updated_at"),
        migrations.AddField(
            model_name="activitysession",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.RenameField("discardedsession", "user", "owner"),
        migrations.RenameField("discardedsession", "discarded_at", "created_at"),
        migrations.AddField(
            model_name="discardedsession",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="sessionentry",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="sessionentry",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="sessionentry",
            name="uuid",
            field=models.UUIDField(null=True, editable=False),
        ),
    ]
