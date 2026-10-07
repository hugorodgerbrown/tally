"""Fixtures for the Playwright journeys: a live server and a signed-in page."""

import os
import re
from typing import Any
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Use a preinstalled Chromium when PLAYWRIGHT_CHROMIUM_EXECUTABLE names one.

    Cloud sandboxes ship a browser but block Playwright's download; CI
    installs its own and leaves this unset.
    """
    if path := os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE"):
        return {**browser_type_launch_args, "executable_path": path}
    return browser_type_launch_args


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Keep the rows data migrations made (the exercise types) across the live server's flush.

    live_server flushes the database after each test, which would take the
    five exercise types with it, and the starter library needs them.
    pytest-django decides what to serialise at collection, so this is a
    marker rather than a fixture.
    """
    for item in items:
        if "tests/e2e/" in str(item.path):
            item.add_marker(pytest.mark.django_db(transaction=True, serialized_rollback=True))


@pytest.fixture
def signed_in_page(page: Page, live_server: Any, mailoutbox: list[Any], settings: Any) -> Page:
    """A page signed in by emailed link, controlled by the service worker.

    The server runs in this process, so the email lands in ``mailoutbox``.
    Passkeys are checked against the live server's origin.
    """
    settings.WEBAUTHN_ORIGINS = [live_server.url]
    page.goto(f"{live_server.url}/signin/")
    page.get_by_label("Email address").fill("walker@example.com")
    page.get_by_role("button", name="Email me a link").click()
    page.wait_for_url("**/signin/code/")
    link = re.search(r"https?://\S+/signin/link/\S+/", mailoutbox[-1].body)
    assert link, mailoutbox[-1].body
    page.goto(live_server.url + urlsplit(link.group()).path)
    page.get_by_role("button", name="Continue").click()
    page.wait_for_url("**/app/")
    # The first load installs the worker; it takes control without a reload.
    # (evaluate, not wait_for_function: the page's CSP forbids the eval the latter uses.)
    page.evaluate(
        """() => navigator.serviceWorker.controller || new Promise((resolve) =>
            navigator.serviceWorker.addEventListener("controllerchange", resolve))"""
    )
    # Load once more through the worker, so this page is cached for offline.
    page.reload()
    return page
