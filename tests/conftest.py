"""Fixtures shared by every test."""

from typing import Any

import pytest
from django.test import Client

from tests.factories import UserFactory

IMMEDIATE = {"default": {"BACKEND": "django.tasks.backends.immediate.ImmediateBackend"}}


@pytest.fixture(autouse=True)
def _tasks_run_inline(settings: Any) -> None:
    """Run tasks in the test's own thread, so their email is sent before the response.

    The app runs them on threads (apps.core.task_backends); its own tests
    put that backend back.
    """
    settings.TASKS = IMMEDIATE


@pytest.fixture
def user(db: None) -> Any:
    """A signed-up user."""
    return UserFactory.create()


@pytest.fixture
def signed_in(client: Client, user: Any) -> Client:
    """The test client, signed in as ``user``."""
    client.force_login(user)
    return client
