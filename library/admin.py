from django.contrib import admin

from .models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem


@admin.register(ExerciseType)
class ExerciseTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "colour", "order"]
    list_editable = ["colour", "order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(MuscleGroup)
class MuscleGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["name", "one_sided", "default_duration", "type_list"]
    list_filter = ["types", "one_sided", "muscles"]
    search_fields = ["name"]
    filter_horizontal = ["types", "muscles"]

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("types")

    @admin.display(description="Types")
    def type_list(self, obj):
        return ", ".join(t.name for t in obj.types.all())


class WorkoutItemInline(admin.TabularInline):
    model = WorkoutItem
    extra = 1
    autocomplete_fields = ["exercise"]
    fields = ["order", "exercise", "duration_seconds"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ["name", "rounds", "rest_seconds", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    inlines = [WorkoutItemInline]
    fields = ["name", "description", "rest_seconds", "rounds", "round_rest_seconds", "is_active"]
