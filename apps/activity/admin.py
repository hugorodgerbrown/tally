"""Admin for the activity log."""

from django.contrib import admin

from apps.activity.models import ActivitySession, DiscardedSession, SessionEntry


class SessionEntryInline(admin.TabularInline):
    """A session's entries, read-only: they are the phone's record."""

    model = SessionEntry
    extra = 0
    fields = ("order", "exercise_name", "exercise", "seconds_worked")
    readonly_fields = fields


@admin.register(ActivitySession)
class ActivitySessionAdmin(admin.ModelAdmin):
    """Logged sessions, newest first."""

    list_display = ["workout_name", "owner", "started_at", "seconds_worked", "completed", "effort"]
    list_filter = ["completed"]
    list_select_related = ["owner"]
    search_fields = ["workout_name", "owner__email"]
    date_hierarchy = "started_at"
    raw_id_fields = ["owner", "workout"]
    readonly_fields = ["uuid", "created_at", "updated_at"]
    inlines = [SessionEntryInline]


@admin.register(SessionEntry)
class SessionEntryAdmin(admin.ModelAdmin):
    """Session entries on their own, for finding time logged on an exercise."""

    list_display = ["exercise_name", "session", "seconds_worked"]
    list_select_related = ["session"]
    search_fields = ["exercise_name"]
    raw_id_fields = ["session", "exercise"]


@admin.register(DiscardedSession)
class DiscardedSessionAdmin(admin.ModelAdmin):
    """Sessions thrown away on the finish screen, kept so a late upload is ignored."""

    list_display = ["uuid", "owner", "created_at"]
    list_select_related = ["owner"]
    raw_id_fields = ["owner"]
