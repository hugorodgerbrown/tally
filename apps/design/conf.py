"""The exceptions to the rules in DESIGN.md, each with its reason.

tests/test_design.py fails when a component in app.css isn't on the design
page. A component that can't sit on the page (the page's own frame, a
screen that covers everything) is named here with the reason instead. The
same goes for a script under /app/ that isn't precached for offline use.
"""

# Component (block) class -> why it isn't on the design page.
NOT_ON_PAGE: dict[str, str] = {
    "app-header": "the frame of every page, the design page included",
    "app-main": "the frame of every page, the design page included",
    "offline-banner": "the frame of every page; shown while offline",
    "launch-shell": "covers the whole screen while the app launches",
    "app-launching": "the state the launch screen is in, set on <html>",
    "htmx-indicator": "htmx's own request state",
    "htmx-request": "htmx's own request state",
    "outbox-status": "the frame of every page; shown while writes wait to send",
}

# Classes a framework puts on elements (no template here names them), so the
# dead-CSS check counts them as used.
ADDED_BY_FRAMEWORKS: dict[str, str] = {
    "errorlist": "Django renders it round a form's errors",
}

# Scripts and stylesheets a page under /app/ loads that aren't precached,
# because they only work with the network anyway (DESIGN.md, section 11).
NEEDS_NETWORK: dict[str, str] = {
    "js/analytics.js": "analytics only send with the network; pages work without them",
    "js/webauthn_json.js": "passkeys need the server to sign in or register",
    "js/passkeys.js": "passkeys need the server to sign in or register",
    "js/design.js": "the design page is a staff reference, not the app",
    "css/planner.css": "Manage needs a connection; offline, the phone app greys it out",
}
