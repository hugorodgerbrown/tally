"""A workout run offline is logged on the phone, and uploaded when back online.

Scenario: offline write (docs/testing.md, "Journeys").
"""

from playwright.sync_api import Page, expect

from apps.activity.models import ActivitySession


def test_session_run_offline_is_saved_when_back_online(signed_in_page: Page) -> None:
    """The whole outbox path: offline app load, a session queued, sent on reconnect."""
    page = signed_in_page
    # The sample workout reaches the phone's copy of the library on first load.
    expect(page.get_by_text("Morning mobility")).to_be_visible()
    page.context.set_offline(True)
    page.reload()
    page.get_by_text("Morning mobility").click()
    page.get_by_role("button", name="Start workout").click()
    # Five seconds of "get ready", then a little work so there is time to log.
    page.wait_for_timeout(7500)
    page.locator(".scr").click()
    page.get_by_role("button", name="End").click()
    expect(page.get_by_role("status")).to_contain_text("Saved to your log")
    page.get_by_role("button", name="Done").click()
    assert not ActivitySession.objects.exists()

    page.context.set_offline(False)
    page.evaluate("() => self.Store.flush()")
    expect(page.get_by_text("Morning mobility")).to_be_visible()
    page.wait_for_timeout(1000)
    session = ActivitySession.objects.get()
    assert session.workout_name == "Morning mobility"
    assert session.seconds_worked > 0
