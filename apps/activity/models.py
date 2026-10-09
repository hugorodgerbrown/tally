"""The activity log: workouts run on the phone, and the time worked in each.

The phone creates a session offline and makes its uuid, so an upload can be
retried safely: the server upserts on ``uuid``. Names are copied from the
workout and exercises at the time, so the log stays readable if the
library changes later.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import BaseModel


class ActivitySessionQuerySet(models.QuerySet["ActivitySession"]):
    """Queries over sessions."""

    def for_user(self, user: AbstractBaseUser) -> ActivitySessionQuerySet:
        """Return ``user``'s sessions."""
        return self.filter(owner=user)


class ActivitySession(BaseModel):
    """One run through a workout, recorded by the phone.

    ``updated_at`` is when the phone's latest upload of it arrived.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activity_sessions"
    )
    workout = models.ForeignKey(
        "library.Workout",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sessions",
    )
    workout_name = models.CharField(max_length=100)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField()
    completed = models.BooleanField(help_text="False when ended early.")
    rounds = models.PositiveSmallIntegerField(default=1)
    seconds_worked = models.PositiveIntegerField(default=0)
    effort = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        help_text="Optional 1 to 10 rating from the finish screen.",
    )

    objects = ActivitySessionQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-started_at"]

    def to_string(self) -> str:
        """Return the workout's name and when it started."""
        return f"{self.workout_name} {self.started_at:%Y-%m-%d %H:%M}"


class SessionEntryQuerySet(models.QuerySet["SessionEntry"]):
    """Queries over session entries."""

    def for_user(self, user: AbstractBaseUser) -> SessionEntryQuerySet:
        """Return the entries of ``user``'s sessions."""
        return self.filter(session__owner=user)


class SessionEntry(BaseModel):
    """Time actually worked on one exercise within a session."""

    session = models.ForeignKey(ActivitySession, on_delete=models.CASCADE, related_name="entries")
    exercise = models.ForeignKey(
        "library.Exercise", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    exercise_name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    seconds_worked = models.PositiveIntegerField()

    objects = SessionEntryQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["order"]
        verbose_name_plural = "session entries"

    def to_string(self) -> str:
        """Return the exercise's name and the time worked."""
        return f"{self.exercise_name}: {self.seconds_worked}s"


class DiscardedSessionQuerySet(models.QuerySet["DiscardedSession"]):
    """Queries over discarded sessions."""

    def for_user(self, user: AbstractBaseUser) -> DiscardedSessionQuerySet:
        """Return the sessions ``user`` threw away."""
        return self.filter(owner=user)


class DiscardedSession(BaseModel):
    """A session the user threw away on the finish screen.

    Kept so an upload of the same session that arrives after the discard
    (from another tab, or a retry) is ignored rather than re-creating it.
    ``uuid`` is the discarded session's own; ``created_at`` is when.
    """

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")

    objects = DiscardedSessionQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-created_at"]

    def to_string(self) -> str:
        """Return the discarded session's uuid."""
        return str(self.uuid)
