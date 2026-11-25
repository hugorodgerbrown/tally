"""Tally's hook for deleting an account (``ACCOUNTS_DELETE_HOOKS``).

A workout's items protect their exercise (``on_delete=PROTECT``), so the
cascade from the account would stop at the exercises. Deleting the
account's workouts first takes their items with them; the cascade then
removes the exercises, muscle groups and log as usual.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.library.models import Workout

logger = logging.getLogger(__name__)


def delete_workouts(user: Any) -> None:
    """Delete ``user``'s workouts (and so their items) before the account goes."""
    Workout.objects.filter(owner=user).delete()
