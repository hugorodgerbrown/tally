"""Archive the workouts Claude made that nobody has used.

Claude can make a workout every day, and each lands as Active, under
"Show all" on the phone. One still Active, never done and unchanged for
seven days moves to Archived. Pinned workouts, ones done at least once and
ones made in Manage are never touched; restoring one gives it another seven
days.

Read-only by default: it lists what it would archive, and archives only
with ``--commit``. Scheduled daily (the Render cron job in render.yaml).
"""

import logging
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.utils import timezone

from apps.library.models import Workout, WorkoutStatus

logger = logging.getLogger(__name__)

UNUSED_DAYS = 7


class Command(BaseCommand):
    """Move Claude's unused Active workouts to Archived."""

    help = (
        f"Archive Claude-made workouts that are Active, never done and unchanged for "
        f"{UNUSED_DAYS} days (dry run unless --commit)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        """Add the --commit flag."""
        parser.add_argument("--commit", action="store_true", help="Actually archive them.")

    def handle(self, *args: Any, **options: Any) -> None:
        """List, and with --commit archive, the unused workouts."""
        cutoff = timezone.now() - timedelta(days=UNUSED_DAYS)
        workouts = list(Workout.objects.unused_from_claude(cutoff).order_by("owner_id", "name"))
        # A dry run lists them; a committed run only at -v 2, to keep the cron log short.
        if options["verbosity"] > (1 if options["commit"] else 0):
            for w in workouts:
                self.stdout.write(f"  {w.uuid} {w.name} (changed {w.updated_at:%d %b %Y})")
        if not options["commit"]:
            self.stdout.write(
                f"{len(workouts)} unused workouts to archive (dry run; pass --commit)."
            )
            return
        # update() leaves updated_at alone: archiving isn't an edit to the workout.
        archived = Workout.objects.filter(pk__in=[w.pk for w in workouts]).update(
            status=WorkoutStatus.ARCHIVED
        )
        logger.info("Archived %d unused workouts made by Claude", archived)
        if options["verbosity"] > 0:
            self.stdout.write(f"Archived {archived} unused workouts.")
