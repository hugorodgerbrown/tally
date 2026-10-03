import uuid
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

# How long a one-off workout stays on the phone after it is made.
ONE_OFF_DAYS = 7


class ExerciseType(models.Model):
    """A training category: aerobic, anaerobic, strength, flexibility, fitness."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=50)
    colour = models.CharField(
        max_length=7, default="#8FD3B0", help_text="Hex colour used in the app."
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name


class MuscleGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Equipment(models.TextChoices):
    """Kit an exercise needs. Blank means bodyweight. Each choice has an icon
    in library/equipment.py, so adding one means drawing one."""

    KETTLEBELL = "kettlebell", "Kettlebell"
    DUMBBELL = "dumbbell", "Dumbbell"


class Source(models.TextChoices):
    """Where an exercise or workout was made. Blank on ones made before
    this was recorded."""

    MANAGE = "manage", "Manage"
    CLAUDE = "claude", "Claude"
    SEED = "seed", "Starter library"


class Movement(models.TextChoices):
    """Whether the body moves through reps (dynamic) or holds a position
    (static, also called isometric). Plyometric moves are dynamic."""

    DYNAMIC = "dynamic", "Dynamic"
    STATIC = "static", "Static"


class Exercise(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=100, unique=True)
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
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANAGE, blank=True
    )
    movement = models.CharField(
        max_length=10,
        choices=Movement.choices,
        default=Movement.DYNAMIC,
        help_text="Dynamic moves through reps; static holds a position.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class WorkoutQuerySet(models.QuerySet["Workout"]):
    def on_phone(self) -> WorkoutQuerySet:
        """Active workouts the phone lists: every saved one, and one-offs
        made in the last ONE_OFF_DAYS days."""
        cutoff = timezone.now() - timedelta(days=ONE_OFF_DAYS)
        return self.filter(Q(one_off=False) | Q(created_at__gte=cutoff), is_active=True)


class Workout(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
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
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.MANAGE, blank=True
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = WorkoutQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def on_phone(self) -> bool:
        if not self.is_active:
            return False
        return not self.one_off or self.created_at >= timezone.now() - timedelta(days=ONE_OFF_DAYS)


class WorkoutItem(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="workout_items")
    order = models.PositiveSmallIntegerField(default=0)
    duration_seconds = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5)],
        help_text="Seconds (per side for one-sided moves).",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self) -> str:
        return f"{self.exercise} ({self.duration_seconds}s)"
