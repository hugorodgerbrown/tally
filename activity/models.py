import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ActivitySession(models.Model):
    """One run through a workout, recorded by the PWA.

    The PWA creates the session offline and generates its UUID, so a sync
    can be retried safely: the server upserts on ``uuid``.
    Names are copied from the workout and exercises at the time of the
    session so the log stays readable if the library changes later.
    """

    uuid = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
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
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.workout_name} {self.started_at:%Y-%m-%d %H:%M}"


class SessionEntry(models.Model):
    """Time actually worked on one exercise within a session."""

    session = models.ForeignKey(ActivitySession, on_delete=models.CASCADE, related_name="entries")
    exercise = models.ForeignKey(
        "library.Exercise", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    exercise_name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    seconds_worked = models.PositiveIntegerField()

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "session entries"

    def __str__(self):
        return f"{self.exercise_name}: {self.seconds_worked}s"
