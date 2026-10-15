"""Make Tally's existing ``auth.User`` table the template's ``accounts.User``.

Tally had live accounts when the template moved to a custom user model, so
it can't start again from the template's 0001. Instead this takes the table
0001 declared (``auth_user``, as ``auth.User`` made it) to the template's
shape: a masked address, ``BaseModel``'s uuid, timestamps and big-int key,
and the table renamed to ``accounts_user`` (with its two many-to-many
tables). Sign-in requests move to a key and masked address; the pending ones
are dropped, as they expire within 15 minutes anyway. Reviewer accounts are
new. 0003 keys the accounts themselves. See
docs/decisions/tally-keys-its-existing-accounts.md.
"""

import uuid

from django.db import migrations, models
from django.utils import timezone

import apps.accounts.models


def fill_users(apps, schema_editor):
    """Give every account a uuid, and date its creation from when it joined."""
    User = apps.get_model("accounts", "User")
    for user in User.objects.only("pk", "date_joined"):
        User.objects.filter(pk=user.pk).update(uuid=uuid.uuid4(), created_at=user.date_joined)


def drop_pending_sign_ins(apps, schema_editor):
    """Delete sign-in requests: they hold the address, and none outlives 15 minutes."""
    apps.get_model("accounts", "SignInRequest").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]

    operations = [
        # The account.
        migrations.AddField(
            model_name="user",
            name="masked_email",
            field=models.CharField(blank=True, max_length=254),
        ),
        migrations.AddField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(editable=False, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, default=timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="user",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.RunPython(fill_users, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="uuid",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AlterField(
            model_name="user",
            name="id",
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
        migrations.AlterModelTable(name="user", table=None),
        migrations.AlterModelOptions(
            name="user",
            options={
                "ordering": ["-date_joined"],
                "verbose_name": "user",
                "verbose_name_plural": "users",
            },
        ),
        migrations.AlterModelManagers(
            name="user",
            managers=[("objects", apps.accounts.models.AccountManager())],
        ),
        # Sign-in requests hold a key and a masked address, not the address.
        migrations.RunPython(drop_pending_sign_ins, migrations.RunPython.noop),
        migrations.AddField(
            model_name="signinrequest",
            name="email_key",
            field=models.CharField(db_index=True, default="", max_length=64),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="signinrequest",
            name="masked_email",
            field=models.CharField(default="", max_length=254),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name="signinrequest",
            name="email",
            field=models.EmailField(blank=True, max_length=254),
        ),
        # Reviewer accounts (docs/decisions/app-reviewers-sign-in-with-a-fixed-code.md).
        migrations.CreateModel(
            name="ReviewerAccount",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("code", models.CharField(editable=False, max_length=6)),
            ],
            options={"ordering": ["email"], "abstract": False},
        ),
    ]
