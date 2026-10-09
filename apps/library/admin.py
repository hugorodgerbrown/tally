"""Admin for the exercise library."""

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from apps.library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem


@admin.register(ExerciseType)
class ExerciseTypeAdmin(admin.ModelAdmin):
    """The five shared types; colour and order are editable in the list."""

    list_display = ["name", "slug", "colour", "order"]
    list_editable = ["colour", "order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(MuscleGroup)
class MuscleGroupAdmin(admin.ModelAdmin):
    """Muscle groups: shared ones have no owner."""

    list_display = ["name", "owner"]
    list_filter = [("owner", admin.EmptyFieldListFilter)]
    list_select_related = ["owner"]
    search_fields = ["name"]


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    """Every account's exercises."""

    list_display = [
        "name",
        "owner",
        "equipment",
        "movement",
        "one_sided",
        "default_duration",
        "type_list",
        "source",
    ]
    list_filter = ["types", "equipment", "movement", "one_sided", "source"]
    list_select_related = ["owner"]
    search_fields = ["name", "owner__email"]
    filter_horizontal = ["types", "muscles"]
    raw_id_fields = ["owner"]

    def get_queryset(self, request: HttpRequest) -> QuerySet[Exercise]:
        """Prefetch types for the list column."""
        return super().get_queryset(request).prefetch_related("types")

    @admin.display(description="Types")
    def type_list(self, obj: Exercise) -> str:
        """Return the exercise's types, comma separated."""
        return ", ".join(t.name for t in obj.types.all())


class WorkoutItemInline(admin.TabularInline):
    """A workout's exercises, in order."""

    model = WorkoutItem
    extra = 1
    autocomplete_fields = ["exercise"]
    fields = ["order", "exercise", "duration_seconds"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    """Every account's workouts, with their items inline."""

    list_display = [
        "name",
        "owner",
        "rounds",
        "rest_seconds",
        "is_active",
        "source",
        "created_at",
    ]
    list_filter = ["is_active", "source"]
    list_select_related = ["owner"]
    search_fields = ["name", "owner__email"]
    inlines = [WorkoutItemInline]
    raw_id_fields = ["owner"]
    fields = [
        "owner",
        "name",
        "description",
        "rest_seconds",
        "rounds",
        "round_rest_seconds",
        "is_active",
        "source",
    ]


@admin.register(WorkoutItem)
class WorkoutItemAdmin(admin.ModelAdmin):
    """Workout items on their own, for finding where an exercise is used."""

    list_display = ["workout", "order", "exercise", "duration_seconds"]
    list_select_related = ["workout", "exercise"]
    search_fields = ["workout__name", "exercise__name"]
