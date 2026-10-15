"""Key the accounts made before Tally stopped keeping email addresses.

Each account's username was its address (or, for one ``createsuperuser``
made, its ``email`` held it). This makes the username ``email_key(address)``,
sets ``masked_email`` and blanks ``email``, as sign-in now stores them, so no
address is left in the database once it has run. ``ACCOUNTS_EMAIL_KEY`` must
be set: the ``accounts.E001`` check stops ``migrate`` without it. It can't be
undone, since the addresses are gone; an account whose address can't be
found is left as it is. With ``ACCOUNTS_KEEP_EMAIL`` on it does nothing.

The ``auth.user`` content type becomes ``accounts.user``, so the admin's
history and any permissions follow the model. See
docs/decisions/tally-keys-its-existing-accounts.md.
"""

import logging

from django.conf import settings
from django.db import migrations

from apps.accounts.models import email_key, mask_email, normalise_email

logger = logging.getLogger(__name__)


def _address(user) -> str:
    """Return the address an account signs in with, or "" if it has none."""
    for value in (user.email, user.username):
        if "@" in value:
            return normalise_email(value)
    return ""


def key_accounts(apps, schema_editor):
    """Replace each account's stored address with its key and masked form."""
    if settings.ACCOUNTS_KEEP_EMAIL:
        return
    User = apps.get_model("accounts", "User")
    taken = set(User.objects.values_list("username", flat=True))
    for user in User.objects.order_by("pk"):
        address = _address(user)
        if not address:
            continue
        key = email_key(address)
        if key in taken and user.username != key:
            # An older account already has this address: leave this one for staff.
            logger.warning("accounts.keying_skipped user=%s (address already keyed)", user.pk)
            continue
        taken.discard(user.username)
        taken.add(key)
        User.objects.filter(pk=user.pk).update(
            username=key, masked_email=mask_email(address), email=""
        )


def move_content_type(apps, schema_editor):
    """Point ``auth.user``'s content type at ``accounts.user``."""
    ContentType = apps.get_model("contenttypes", "ContentType")
    if ContentType.objects.filter(app_label="accounts", model="user").exists():
        return
    ContentType.objects.filter(app_label="auth", model="user").update(app_label="accounts")


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_and_keyed_sign_in"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(key_accounts, migrations.RunPython.noop),
        migrations.RunPython(move_content_type, migrations.RunPython.noop),
    ]
