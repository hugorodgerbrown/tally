from django.contrib import admin

from .models import ActivitySession, SessionEntry


class SessionEntryInline(admin.TabularInline):
    model = SessionEntry
    extra = 0
    fields = ["order", "exercise_name", "exercise", "seconds_worked"]
    readonly_fields = fields


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    list_display = ["workout_name", "started_at", "seconds_worked", "completed", "effort", "user"]
    list_filter = ["completed", "user"]
    date_hierarchy = "started_at"
    readonly_fields = ["uuid", "synced_at"]
    inlines = [SessionEntryInline]
