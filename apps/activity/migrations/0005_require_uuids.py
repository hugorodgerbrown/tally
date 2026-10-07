"""Make every uuid unique with a default, as BaseModel declares it."""

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("activity", "0004_fill_entry_uuids")]

    operations = [
        *(
            migrations.AlterField(
                model_name=model,
                name="uuid",
                field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
            )
            for model in ("activitysession", "sessionentry", "discardedsession")
        ),
        *(
            migrations.AlterField(
                model_name=model,
                name="id",
                field=models.BigAutoField(primary_key=True, serialize=False),
            )
            for model in ("activitysession", "sessionentry", "discardedsession")
        ),
        migrations.AlterModelOptions(
            name="discardedsession", options={"ordering": ["-created_at"]}
        ),
    ]
