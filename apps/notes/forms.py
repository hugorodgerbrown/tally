"""Forms for notes; used for both form posts and the outbox's JSON."""

from datetime import timedelta

from django import forms
from django.utils import timezone

from apps.notes.models import Note

# How far in the past a client-supplied written_at may be. An offline week
# is plausible; a year is a broken clock.
MAX_OFFLINE_DAYS = 30


class NoteForm(forms.ModelForm):
    """Validate a new note. ``written_at`` is optional and defaults to now."""

    written_at = forms.DateTimeField(required=False)

    class Meta:
        """Form metadata."""

        model = Note
        fields = ["text", "written_at"]

    def clean_written_at(self) -> object:
        """Default to now; refuse times in the future or implausibly old."""
        now = timezone.now()
        value = self.cleaned_data.get("written_at") or now
        if value > now + timedelta(minutes=5):
            raise forms.ValidationError("That time is in the future.")
        if value < now - timedelta(days=MAX_OFFLINE_DAYS):
            raise forms.ValidationError("That time is too long ago.")
        return value
