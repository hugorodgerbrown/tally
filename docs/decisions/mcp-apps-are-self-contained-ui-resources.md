# MCP Apps are self-contained ui:// resources served by the MCP endpoint

Status: accepted (2026-10-07)

## Context

A tool result is text to the model, but some answers read better as a
picture: a list, a calendar, a preview to confirm. MCP Apps (the spec's
2026-01-26 extension) lets a tool name a `ui://` HTML resource that the
client draws in a sandboxed frame beside the result. The site's own CSP
forbids inline script and style, and the frame runs on the client's origin,
not ours, so the view can't load scripts from this site anyway.

## Decision

`/mcp` advertises `resources` and answers `resources/list` and
`resources/read`. A view is one HTML file in `apps/mcp/ui/` plus its
scripts, put together into one document at read time with the scripts
inlined (`apps/mcp/resources.py`); it loads nothing over the network and
declares no CSP domains. `ui/bridge.js` is the view's side of the spec
(handshake, theme, size, tool results, calling a tool through the host),
written by hand because the template has no build step. A tool opts in
with `Tool(ui="ui://…")`, which adds `_meta.ui.resourceUri` (and the older
flat `ui/resourceUri`) to its listing.

## Consequences

- The view files are not Django templates and are never served by the site,
  so the no-inline-script rule (`tests/test_security.py`) doesn't cover
  them; the MCP tests check instead that each view is self-contained.
- Views get their data from the tool result over `postMessage` and must put
  it in as text (`textContent`), never as markup.
- The endpoint is stateless, so it can't skip `_meta` for a client without
  MCP Apps; such a client ignores it and still gets the text content.
- Resources are the same for every user and carry no data; a view that
  needs more calls a tool through the host, as the signed-in user.
