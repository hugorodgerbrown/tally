"""Tests for the migration that keys Tally's accounts made before the key (accounts.0003)."""

import importlib
from typing import Any

import pytest
from django.apps import apps as global_apps
from django.contrib.contenttypes.models import ContentType

from apps.accounts.models import User, email_key
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

migration = importlib.import_module("apps.accounts.migrations.0003_key_existing_accounts")


def _legacy(username: str, email: str) -> Any:
    """Return an account stored the old way: the address as username and email."""
    user = UserFactory.create()
    User.objects.filter(pk=user.pk).update(username=username, email=email, masked_email="")
    return User.objects.get(pk=user.pk)


def test_accounts_are_keyed_and_their_addresses_dropped() -> None:
    """Sign-in's account and a createsuperuser one are both keyed and masked."""
    made_here = _legacy("person@example.com", "person@example.com")
    superuser = _legacy("admin", "Boss@Example.com")
    no_address = _legacy("robot", "")

    migration.key_accounts(global_apps, None)

    made_here.refresh_from_db()
    superuser.refresh_from_db()
    no_address.refresh_from_db()
    assert (made_here.username, made_here.email, made_here.masked_email) == (
        email_key("person@example.com"),
        "",
        "p•••@example.com",
    )
    assert superuser.username == email_key("boss@example.com")
    assert superuser.masked_email == "b•••@example.com"
    assert (no_address.username, no_address.masked_email) == ("robot", "")


def test_a_second_account_for_an_address_is_left_alone() -> None:
    """Two accounts for one address: the older is keyed, the newer left for staff."""
    first = _legacy("person@example.com", "person@example.com")
    second = _legacy("admin", "Person@example.com")

    migration.key_accounts(global_apps, None)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.username == email_key("person@example.com")
    assert (second.username, second.email) == ("admin", "Person@example.com")


def test_nothing_changes_when_addresses_are_kept(settings: Any) -> None:
    """With ACCOUNTS_KEEP_EMAIL on, the addresses stay."""
    settings.ACCOUNTS_KEEP_EMAIL = True
    user = _legacy("person@example.com", "person@example.com")

    migration.key_accounts(global_apps, None)

    user.refresh_from_db()
    assert user.username == "person@example.com"


def test_the_content_type_moves_only_if_there_is_none() -> None:
    """auth.user's content type becomes accounts.user, unless that exists already."""
    ContentType.objects.filter(app_label="accounts", model="user").delete()
    old = ContentType.objects.create(app_label="auth", model="user")

    migration.move_content_type(global_apps, None)
    old.refresh_from_db()
    assert old.app_label == "accounts"

    stale = ContentType.objects.create(app_label="auth", model="user")
    migration.move_content_type(global_apps, None)
    stale.refresh_from_db()
    assert stale.app_label == "auth"
