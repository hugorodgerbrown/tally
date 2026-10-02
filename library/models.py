from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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

    def __str__(self):
        return self.name


class MuscleGroup(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Exercise(models.Model):
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

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Workout(models.Model):
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
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class WorkoutItem(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="items")
    exercise = models.ForeignKey(Exercise, on_delete=models.PROTECT, related_name="+")
    order = models.PositiveSmallIntegerField(default=0)
    duration_seconds = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(5)],
        help_text="Seconds (per side for one-sided moves).",
    )

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.exercise} ({self.duration_seconds}s)"
