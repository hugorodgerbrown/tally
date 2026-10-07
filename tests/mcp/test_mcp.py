"""Tests for the MCP endpoint: the shared auth contract, then the tools."""

import json
import re
from typing import Any

import pytest
from django.test import Client
from mcp_auth.testing import MCPAuthContract

from apps.mcp.resources import MIME_TYPE, RESOURCES
from apps.mcp.tools import TOOLS, ToolError, add_note, list_notes
from apps.notes.models import Note
from tests.factories import NoteFactory, UserFactory


class TestMCPAuth(MCPAuthContract):
    """Every Titan MCP server passes the same OAuth contract."""

    mcp_path = "/mcp"

    def make_allowed_user(self, django_user_model: Any) -> Any:
        """A user who may connect: staff and superuser satisfy either policy."""
        return UserFactory.create(is_staff=True, is_superuser=True)

    def make_refused_user(self, django_user_model: Any) -> Any:
        """A signed-in user who may not connect."""
        return UserFactory.create()


@pytest.fixture
def rpc(user: Any) -> Any:
    """Call the MCP view as ``user``, bypassing OAuth (the contract covers that)."""
    from apps.mcp import views

    def call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        result: dict[str, Any] = views._dispatch(user, method, params or {})
        return result

    return call


def test_initialize_and_list_tools(rpc: Any) -> None:
    """Initialize names the server; tools/list lists every tool."""
    assert rpc("initialize")["serverInfo"]["name"]
    names = {t["name"] for t in rpc("tools/list")["tools"]}
    assert names == set(TOOLS)


def test_add_then_list_notes(rpc: Any, user: Any) -> None:
    """add_note writes as the user; list_notes reads it back."""
    rpc("tools/call", {"name": "add_note", "arguments": {"text": "from Claude"}})
    result = rpc("tools/call", {"name": "list_notes", "arguments": {}})
    assert result["structuredContent"]["notes"][0]["text"] == "from Claude"
    assert Note.objects.get().owner == user


def test_initialize_advertises_resources(rpc: Any) -> None:
    """The server says it has resources and MCP Apps, so the client renders a tool's UI."""
    capabilities = rpc("initialize")["capabilities"]
    assert "resources" in capabilities
    assert capabilities["extensions"]["io.modelcontextprotocol/ui"] == {"mimeTypes": [MIME_TYPE]}


def test_resources_list_every_view(rpc: Any) -> None:
    """resources/list lists every ui:// view as an MCP App."""
    listed = rpc("resources/list")["resources"]
    assert {r["uri"] for r in listed} == set(RESOURCES)
    assert all(r["uri"].startswith("ui://") and r["mimeType"] == MIME_TYPE for r in listed)
    assert rpc("resources/templates/list") == {"resourceTemplates": []}


@pytest.mark.parametrize("tool", [t for t in TOOLS.values() if t.ui], ids=lambda t: t.name)
def test_a_tool_ui_names_a_listed_resource(rpc: Any, tool: Any) -> None:
    """A tool's _meta points at a resource the server serves, in both key forms."""
    described = next(t for t in rpc("tools/list")["tools"] if t["name"] == tool.name)
    assert described["_meta"]["ui"]["resourceUri"] in RESOURCES
    assert described["_meta"]["ui/resourceUri"] == described["_meta"]["ui"]["resourceUri"]


@pytest.mark.parametrize("uri", list(RESOURCES))
def test_a_view_is_one_self_contained_document(rpc: Any, uri: str) -> None:
    """The HTML loads nothing from anywhere: its scripts and styles are inline."""
    (content,) = rpc("resources/read", {"uri": uri})["contents"]
    assert content["uri"] == uri
    assert content["mimeType"] == MIME_TYPE
    assert "prefersBorder" in content["_meta"]["ui"]
    html = content["text"]
    assert html.startswith("<!doctype html>")
    assert "McpApp" in html
    assert not re.search(r"<(script|img|iframe)[^>]*\ssrc=|<link\b", html)
    assert html.count("</script>") == html.count("<script>")


def test_tools_without_ui_have_no_meta(rpc: Any) -> None:
    """A plain tool describes itself as before."""
    described = next(t for t in rpc("tools/list")["tools"] if t["name"] == "add_note")
    assert "_meta" not in described


@pytest.mark.parametrize(
    ("params", "code"),
    [({"uri": "ui://nope"}, -32002), ({}, -32602)],
)
def test_resources_read_errors(rpc: Any, params: dict[str, Any], code: int) -> None:
    """An unknown URI is 'resource not found'; a missing one is invalid params."""
    from apps.mcp.views import RpcError

    with pytest.raises(RpcError) as caught:
        rpc("resources/read", params)
    assert caught.value.code == code


def test_inlined_scripts_cannot_close_their_tag(tmp_path: Any, monkeypatch: Any) -> None:
    """A "</script>" inside a view's JavaScript is escaped, not left to end the tag."""
    from apps.mcp import resources

    (tmp_path / "v.html").write_text("<body></body>")
    (tmp_path / "v.js").write_text("const s = '</script>';")
    monkeypatch.setattr(resources, "UI_DIR", tmp_path)
    html = resources.render.__wrapped__("v.html", ("v.js",))
    assert html == "<body><script>\nconst s = '<\\/script>';</script>\n</body>"


def test_a_view_needs_a_body(tmp_path: Any, monkeypatch: Any) -> None:
    """HTML with nowhere to put the scripts is a mistake, caught at once."""
    from apps.mcp import resources

    (tmp_path / "v.html").write_text("<p>no body</p>")
    monkeypatch.setattr(resources, "UI_DIR", tmp_path)
    with pytest.raises(ValueError, match="no </body>"):
        resources.render.__wrapped__("v.html", ())


@pytest.mark.parametrize(
    ("tool", "heading"),
    [("privacy_policy", "# Privacy notice"), ("terms_of_service", "# Terms"), ("help", "# Help")],
)
def test_public_pages_come_back_as_markdown(rpc: Any, tool: str, heading: str) -> None:
    """The text content is the Markdown itself; structuredContent adds title and URL."""
    result = rpc("tools/call", {"name": tool, "arguments": {}})
    text = result["content"][0]["text"]
    assert heading in text
    assert text == result["structuredContent"]["markdown"]
    assert result["structuredContent"]["url"].startswith("http")


def test_tool_errors_are_readable(rpc: Any) -> None:
    """A bad argument is an isError result, not a protocol error."""
    result = rpc("tools/call", {"name": "list_notes", "arguments": {"limit": 0}})
    assert result["isError"] is True


@pytest.mark.django_db
def test_list_notes_is_per_user() -> None:
    """A user's tools never see another user's notes."""
    NoteFactory.create(text="private")
    assert list_notes(UserFactory.create(), {}) == {"notes": []}


@pytest.mark.django_db
def test_add_note_validates() -> None:
    """Empty text is refused with a message the model can act on."""
    with pytest.raises(ToolError):
        add_note(UserFactory.create(), {"text": ""})


def call_endpoint(client: Client, body: Any, headers: dict[str, str] | None = None) -> Any:
    """POST ``body`` to /mcp with a valid bearer token for a staff user."""
    token = TestMCPAuth().token_for(UserFactory.create(is_staff=True))
    return client.post(
        "/mcp",
        body if isinstance(body, str) else json.dumps(body),
        content_type="application/json",
        headers={"Authorization": f"Bearer {token}", **(headers or {})},
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ("{nope", 400, -32700),
        ({"jsonrpc": "1.0"}, 400, -32600),
        ({"jsonrpc": "2.0", "id": 1, "method": "nope"}, 200, -32601),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": "x"}, 200, -32602),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "x"}}, 200, -32602),
        (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "list_notes", "arguments": "x"},
            },
            200,
            -32602,
        ),
        (
            {"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": "ui://x"}},
            200,
            -32002,
        ),
    ],
)
def test_protocol_errors(client: Client, body: Any, status: int, code: int) -> None:
    """Malformed JSON-RPC gets the standard error codes."""
    response = call_endpoint(client, body)
    assert response.status_code == status
    assert response.json()["error"]["code"] == code


@pytest.mark.django_db
def test_notifications_get_202_and_old_versions_are_refused(client: Client) -> None:
    """A notification needs no answer; an unknown protocol version is refused."""
    assert call_endpoint(client, {"jsonrpc": "2.0", "method": "initialized"}).status_code == 202
    response = call_endpoint(
        client,
        {"jsonrpc": "2.0", "id": 1, "method": "ping"},
        {"MCP-Protocol-Version": "1999-01-01"},
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_ping_with_a_token(client: Client) -> None:
    """A valid token reaches the tools."""
    response = call_endpoint(client, {"jsonrpc": "2.0", "id": 7, "method": "ping"})
    assert response.json() == {"jsonrpc": "2.0", "id": 7, "result": {}}


def test_staff_only_policy() -> None:
    """Only active staff may connect."""
    from types import SimpleNamespace

    from apps.mcp.policy import staff_only

    assert staff_only(SimpleNamespace(is_active=True, is_staff=True))
    assert not staff_only(SimpleNamespace(is_active=True, is_staff=False))
    assert not staff_only(SimpleNamespace(is_active=False, is_staff=True))


@pytest.mark.django_db
def test_endpoint_refuses_anonymous_calls(client: Client) -> None:
    """No bearer token, no tools: a 401 that starts OAuth discovery."""
    response = client.post(
        "/mcp",
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}),
        content_type="application/json",
    )
    assert response.status_code == 401
    assert "resource_metadata" in response["WWW-Authenticate"]
