"""App config for apps.activity."""

from django.apps import AppConfig


class ActivityConfig(AppConfig):
    """The phone's activity mode: the timer app and its logged sessions."""

    name = "apps.activity"
    # Predates the move under apps/: it names the tables and migrations.
    label = "activity"
