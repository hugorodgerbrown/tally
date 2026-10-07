"""Give accounts with an empty library the starter exercises and sample workout.

New accounts get the starter library when they are created; this is for
accounts that predate that, or whose library was emptied. Read-only by
default: it lists the accounts it would fill, and fills them only with
``--commit``. ``--email`` limits it to one account, whether or not its
library is empty (adding only what is missing).
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.library import starter


class Command(BaseCommand):
    """Install the starter library for accounts that have none."""

    help = "Add the starter exercises and sample workout (dry run unless --commit)."

    def add_arguments(self, parser: CommandParser) -> None:
        """Add --email and --commit."""
        parser.add_argument("--email", help="Only this account (adds whatever is missing).")
        parser.add_argument("--commit", action="store_true", help="Actually add the library.")

    def handle(self, *args: Any, **options: Any) -> None:
        """List, and with --commit fill, the accounts."""
        users = get_user_model().objects.filter(is_active=True).order_by("-id")
        if options["email"]:
            users = users.filter(email__iexact=options["email"].strip().lower())
            if not users.exists():
                raise CommandError(f"No active account has the email {options['email']}.")
        else:
            users = users.filter(exercises__isnull=True)

        total = users.count()
        if not total:
            self.stdout.write("Every account already has a library.")
            return
        for n, user in enumerate(users.only("pk", "email").iterator(), start=1):
            label = f"{total - n + 1}: account {user.pk} {user.email}"
            if not options["commit"]:
                self.stdout.write(f"{label} (dry run; pass --commit)")
                continue
            result = starter.install(user)
            if options["verbosity"] > 0:
                workout = ", sample workout" if result.workout else ""
                self.stdout.write(f"{label}: {result.exercises} exercises{workout}")
