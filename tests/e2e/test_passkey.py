"""A passkey added on the account page signs its owner back in.

Scenario: passkey (docs/testing.md, "Journeys"). A real WebAuthn ceremony,
against Chromium's virtual authenticator, is something only a browser can do.
"""

from typing import Any

from playwright.sync_api import Page, expect


def test_added_passkey_signs_back_in(signed_in_page: Page, live_server: Any) -> None:
    """Add a passkey, sign out, sign in with it."""
    page = signed_in_page
    cdp = page.context.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    cdp.send(
        "WebAuthn.addVirtualAuthenticator",
        {
            "options": {
                "protocol": "ctap2",
                "transport": "internal",
                "hasResidentKey": True,
                "hasUserVerification": True,
                "isUserVerified": True,
                "automaticPresenceSimulation": True,
            }
        },
    )
    page.goto(f"{live_server.url}/app/account/")
    page.get_by_role("button", name="Add a passkey").click()
    expect(page.get_by_text("Passkey on")).to_be_visible()

    page.get_by_role("button", name="Sign out").click()
    page.wait_for_url(f"{live_server.url}/")
    page.goto(f"{live_server.url}/signin/")
    page.get_by_role("button", name="Sign in with a passkey").click()
    page.wait_for_url("**/app/")
    expect(page.get_by_text("Morning mobility")).to_be_visible()
