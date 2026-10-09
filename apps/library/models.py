"""The exercise library: types, muscle groups, exercises and workouts.

Exercise types are shared reference data (five, made by a data migration).
Muscle groups are shared when ``owner`` is empty (the starter set) and
private otherwise, so one account's additions never appear in another's
lists. Exercises and workouts always belong to one account.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.core.models import BaseModel

# How long a one-off workout stays on the phone after it is made.
ONE_OFF_DAYS = 7


class ExerciseTypeQuerySet(models.QuerySet["ExerciseType"]):
    """Queries over exercise types."""

    def by_slug(self) -> dict[str, ExerciseType]:
        """Return every type keyed by its slug."""
        return {t.slug: t for t in self}


class ExerciseType(BaseModel):
    """A training category: aerobic, anaerobic, strength, flexibility, fitness."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=50)
    colour = models.CharField(
        max_length=7, default="#8FD3B0", help_text="Hex colour used in the app."
    )
    order = models.PositiveSmallIntegerField(default=0)

    objects = ExerciseTypeQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["order", "name"]

    def to_string(self) -> str:
        """Return the type's name."""
        return self.name


class MuscleGroupQuerySet(models.QuerySet["MuscleGroup"]):
    """Queries over muscle groups."""

    def visible_to(self, user: AbstractBaseUser) -> MuscleGroupQuerySet:
        """Return the shared groups and the ones ``user`` added."""
        return self.filter(Q(owner__isnull=True) | Q(owner=user))

    def named(self, user: AbstractBaseUser, name: str) -> MuscleGroup:
        """Return the group called ``name`` (any case) that ``user`` sees, adding it if new."""
        name = name.strip()
        found = self.visible_to(user).filter(name__iexact=name).order_by("owner_id").first()
        if found is not None:
            return found
        return self.create(owner=user, name=name[:1].upper() + name[1:])


class MuscleGroup(BaseModel):
    """A muscle group an exercise works: shared when ``owner`` is empty."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="Empty for the shared starter set.",
    )
    name = models.CharField(max_length=50)

    objects = MuscleGroupQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(owner__isnull=True),
                name="library_musclegroup_shared_name",
            ),
            models.UniqueConstraint(
                fields=["owner", "name"], name="library_musclegroup_owner_name"
            ),
        ]

    def to_string(self) -> str:
        """Return the group's name."""
        return self.name


class Equipment(models.TextChoices):
    """Kit an exercise needs. Blank means bodyweight.

    Each choice has an icon in ``apps/library/equipment.py``, so adding one
    means drawing one.
    """

    KETTLEBELL = "kettlebell", "Kettlebell"
    DUMBBELL = "dumbbell", "Dumbbell"


class Source(models.TextChoices):
    """Where an exercise or workout was made. Blank on ones made before this was recorded."""

    MANAGE = "manage", "Manage"
    CLAUDE = "claude", "Claude"
    SEED = "seed", "Starter library"


class Movement(models.TextChoices):
    """Whether the body moves through reps (dynamic) or holds a position (static).

    Static is also called isometric. Plyometric moves are dynamic.
    """

    DYNAMIC = "dynamic", "Dynamic"
    STATIC = "static", "Static"


class ExerciseQuerySet(models.QuerySet["Exercise"]):
    """Queries over exercises."""

    def for_user(self, user: AbstractBaseUser) -> ExerciseQuerySet:
        """Return the exercises in ``user``'s library."""
        return self.filter(owner=user)

    def with_tags(self) -> ExerciseQuerySet:
        """Prefetch types and muscles, which every listing shows."""
        return self.prefetch_related("types", "muscles")


class Exercise(BaseModel):
    """One exercise in an account's library."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="exercises"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    types = models.ManyToManyField(ExerciseType, related_name="exercises")
    muscles = models.ManyToManyField(MuscleGroup, related_name="exercises", blank=True)
    one_sided = models.BooleanField(
        default=False,
        help_text="Runs as two intervals, left then right, with a switch between.",
    )
    default_duration = models.PositiveSmallIntegerField(
        default=40, help_text="Seconds (per side for one-sided moves)."
    )
    equipment = models.CharField(
        max_length=20,
        choices=Equipment.choices,
        blank=True,
        help_text="Leave blank for bodyweight.",
    )
    movement = models.CharField(
        max_length=10,
        choices=Movement.choices,
        default=Movement.DYNAMIC,
        help_text="Dynamic moves through reps; static holds a position.",
    )
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANAGE, blank=True
    )

    objects = ExerciseQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "name"], name="library_exercise_owner_name"),
        ]

    def to_string(self) -> str:
        """Return the exercise's name."""
        return self.name


class WorkoutQuerySet(models.QuerySet["Workout"]):
    """Queries over workouts."""

    def for_user(self, user: AbstractBaseUser) -> WorkoutQuerySet:
        """Return ``user``'s workouts."""
        return self.filter(owner=user)

    def active(self) -> WorkoutQuerySet:
        """Return the workouts shown on the phone."""
        return self.filter(is_active=True)

    def on_phone(self) -> WorkoutQuerySet:
        """Return the active workouts the phone lists.

        That is every saved one, and one-offs made in the last ``ONE_OFF_DAYS`` days.
        """
        cutoff = timezone.now() - timedelta(days=ONE_OFF_DAYS)
        return self.active().filter(Q(one_off=False) | Q(created_at__gte=cutoff))


class Workout(BaseModel):
    """An ordered list of exercises with rests and rounds, played by the phone."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workouts"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    rest_seconds = models.PositiveSmallIntegerField(
        default=15, help_text="Rest between exercises. 0 for none."
    )
    rounds = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    round_rest_seconds = models.PositiveSmallIntegerField(
        default=120, help_text="Break between rounds."
    )
    is_active = models.BooleanField(
        default=True, help_text="Inactive workouts are hidden from the app."
    )
    one_off = models.BooleanField(
        default=False,
        help_text=f"Made for one go. Listed on the phone for {ONE_OFF_DAYS} days, then "
        "only in Manage until kept.",
    )
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANAGE, blank=True
    )

    objects = WorkoutQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["name"]

    def to_string(self) -> str:
        """Return the workout's name."""
        return self.name

    @property
    def on_phone(self) -> bool:
        """Return whether the phone lists this workout (see ``WorkoutQuerySet.on_phone``)."""
        if not self.is_active:
            return False
        return not self.one_off or self.created_at >= timezone.now() - timedelta(days=ONE_OFF_DAYS)


class WorkoutItemQuerySet(models.QuerySet["WorkoutItem"]):
    """Queries over workout items."""

    def for_user(self, user: AbstractBaseUser) -> WorkoutItemQuerySet:
        """Return the items of ``user``'s workouts."""
        return self.filter(workout__owner=user)


class WorkoutItem(BaseModel):
    """One exercise in a workout, with how long it runs."""

    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="workout_items")
    order = models.PositiveSmallIntegerField(default=0)
    duration_seconds = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5)],
        help_text="Seconds (per side for one-sided moves).",
    )

    objects = WorkoutItemQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["order", "id"]

    def to_string(self) -> str:
        """Return the exercise and its length."""
        return f"{self.exercise} ({self.duration_seconds}s)"
