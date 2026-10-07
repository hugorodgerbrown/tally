"""The Note model: a short piece of text a user writes, possibly offline."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser
from django.db import models

from apps.core.models import BaseModel


class NoteQuerySet(models.QuerySet["Note"]):
    """Queries over notes."""

    def for_user(self, user: AbstractBaseUser) -> NoteQuerySet:
        """Return the notes ``user`` owns."""
        return self.filter(owner=user)


class Note(BaseModel):
    """A note a user wrote.

    ``written_at`` is when the user wrote it, which for a note written
    offline can be long before the server saw it (``created_at``).
    """

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(max_length=2000)
    written_at = models.DateTimeField()

    objects = NoteQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        """Model metadata."""

        ordering = ["-written_at", "-id"]

    def to_string(self) -> str:
        """Return the first few words of the note."""
        return self.text[:40]
