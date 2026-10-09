"""App config for apps.pwa."""

from django.apps import AppConfig


class PwaConfig(AppConfig):
    """Serves what makes the site installable and usable offline."""

    name = "apps.pwa"
    label = "pwa"
