"""App config for apps.library."""

from django.apps import AppConfig


class LibraryConfig(AppConfig):
    """Exercise types, muscle groups, exercises and workouts."""

    name = "apps.library"
    # The label predates the move under apps/: it names the tables and the
    # migration history, so it must not change.
    label = "library"
