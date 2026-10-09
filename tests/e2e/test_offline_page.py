"""A page never visited shows the offline page, not the browser's error.

Scenario: offline fallback (docs/testing.md, "Journeys").
"""

from typing import Any

from playwright.sync_api import Page, expect


def test_unvisited_page_offline_shows_the_offline_page(
    signed_in_page: Page, live_server: Any
) -> None:
    """The worker answers a navigation it can't serve with the offline page."""
    signed_in_page.context.set_offline(True)
    signed_in_page.goto(f"{live_server.url}/app/?never-visited=1")
    expect(signed_in_page.get_by_role("heading", name="You're offline")).to_be_visible()
