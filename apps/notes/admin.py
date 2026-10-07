"""Admin for notes."""

from django.contrib import admin

from apps.notes.models import Note


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    """Notes, newest first."""

    list_display = ("to_string", "owner", "written_at", "created_at")
    list_select_related = ("owner",)
    search_fields = ("text",)
