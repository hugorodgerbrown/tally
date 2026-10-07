"""App config for apps.public."""

from django.apps import AppConfig


class PublicConfig(AppConfig):
    """The public pages: home, terms and privacy. Outside the installed app."""

    name = "apps.public"
    label = "public"
