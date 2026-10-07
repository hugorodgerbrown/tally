"""MCP Apps: ui:// resources a client renders alongside a tool's result.

Each view is one HTML file in ``apps/mcp/ui/`` plus its scripts, put
together into a single self-contained document when read. The client
(Claude) draws it in a sandboxed iframe on its own origin and hands it the
tool result over ``postMessage`` (``ui/bridge.js``), so it never loads
anything from this site and the site's CSP doesn't apply to it.

Add a view by writing its HTML and script, listing it in RESOURCES, and
pointing a Tool's ``ui`` at its URI.
"""

from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

UI_DIR = Path(__file__).resolve().parent / "ui"
MIME_TYPE = "text/html;profile=mcp-app"
# The bridge every view needs; its own scripts follow it.
BRIDGE = "bridge.js"


class ResourceNotFound(Exception):
    """No resource has the requested URI."""


@dataclass(frozen=True)
class UiResource:
    """One MCP App view: a ui:// URI, its HTML and the scripts it runs."""

    uri: str
    name: str
    title: str
    description: str
    html: str
    scripts: tuple[str, ...] = ()
    prefers_border: bool = True
    # Origins the view may reach; empty means none, the safe default. See
    # the spec's _meta.ui.csp (connectDomains, resourceDomains).
    csp: dict[str, list[str]] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        """Return the resource as resources/list lists it."""
        return {
            "uri": self.uri,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "mimeType": MIME_TYPE,
        }

    def read(self) -> dict[str, Any]:
        """Return the resource as resources/read returns it."""
        ui: dict[str, Any] = {"prefersBorder": self.prefers_border}
        if self.csp:
            ui["csp"] = self.csp
        return {
            "uri": self.uri,
            "mimeType": MIME_TYPE,
            "text": render(self.html, (BRIDGE, *self.scripts)),
            "_meta": {"ui": ui},
        }


@cache
def render(html: str, scripts: tuple[str, ...]) -> str:
    """Inline ``scripts`` before the closing body tag of ``html``."""
    page = (UI_DIR / html).read_text()
    # "</" inside a script would end it early; "<\/" means the same in JavaScript.
    inline = "".join(
        f"<script>\n{(UI_DIR / name).read_text().replace('</', '<\\/')}</script>\n"
        for name in scripts
    )
    head, sep, tail = page.rpartition("</body>")
    if not sep:
        raise ValueError(f"{html} has no </body>")
    return head + inline + sep + tail


RESOURCES: dict[str, UiResource] = {
    r.uri: r
    for r in [
        UiResource(
            uri="ui://notes/list",
            name="notes_list",
            title="Notes",
            description="The user's latest notes as a card.",
            html="notes_list.html",
            scripts=("notes_list.js",),
        ),
    ]
}


def read_resource(uri: str) -> dict[str, Any]:
    """Return resources/read's result for ``uri``."""
    resource = RESOURCES.get(uri)
    if resource is None:
        raise ResourceNotFound(uri)
    return {"contents": [resource.read()]}
