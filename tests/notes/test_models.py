"""Tests for apps.notes.models."""

import pytest

from apps.notes.models import Note
from tests.factories import NoteFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_for_user_filters_by_owner() -> None:
    """for_user() returns only that user's notes."""
    mine = NoteFactory.create()
    NoteFactory.create()
    assert list(Note.objects.for_user(mine.owner)) == [mine]


def test_to_string_is_the_start_of_the_text() -> None:
    """__str__ is the first 40 characters."""
    note = NoteFactory.create(text="x" * 60, owner=UserFactory.create())
    assert str(note) == "x" * 40
