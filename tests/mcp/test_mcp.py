"""Tests for the MCP endpoint: the shared auth contract, the protocol and the resources."""

import json
import re
from pathlib import Path
from typing import Any

import pytest
from django.test import Client
from mcp_auth.testing import MCPAuthContract

from apps.mcp import resources
from apps.mcp.resources import MIME_TYPE, RESOURCES, UiResource
from apps.mcp.tools import TOOLS, Tool
from tests.factories import UserFactory
from tests.mcp.conftest import Rpc


class TestMCPAuth(MCPAuthContract):
    """Every Titan MCP server passes the same OAuth contract."""

    mcp_path = "/mcp"

    def make_allowed_user(self, django_user_model: Any) -> Any:
        """Any active account may connect (``mcp_auth.policy.active_user``)."""
        return UserFactory.create()

    def make_refused_user(self, django_user_model: Any) -> Any:
        """Under ``active_user`` the only refused account is an inactive one."""
        return UserFactory.create(is_active=False)


def test_initialize_and_list_tools(rpc: Rpc) -> None:
    """Initialize names the server; tools/list lists every tool."""
    assert rpc("initialize")["serverInfo"]["name"] == "tally"
    names = {t["name"] for t in rpc("tools/list")["tools"]}
    assert names == set(TOOLS)


def test_initialize_echoes_a_supported_version(rpc: Rpc) -> None:
    """A supported protocol version is echoed back; an unknown one gets the latest."""
    assert rpc("initialize", {"protocolVersion": "2025-06-18"})["protocolVersion"] == "2025-06-18"
    assert rpc("initialize", {"protocolVersion": "1999-01-01"})["protocolVersion"] == "2025-11-25"


def test_tools_list_marks_read_only_tools(rpc: Rpc) -> None:
    """Read tools say so, write tools don't, and nothing is destructive or deletes."""
    tools = {t["name"]: t for t in rpc("tools/list")["tools"]}
    assert tools["list_sessions"]["annotations"]["readOnlyHint"] is True
    assert tools["create_workout"]["annotations"]["readOnlyHint"] is False
    assert not any(t["annotations"]["destructiveHint"] for t in tools.values())
    assert not any("delete" in name for name in tools)
    assert {"privacy_policy", "terms_of_service", "help"} <= set(tools)


def test_initialize_advertises_resources(rpc: Rpc) -> None:
    """The server says it has resources and MCP Apps, so a client could render a tool's UI."""
    capabilities = rpc("initialize")["capabilities"]
    assert "resources" in capabilities
    assert capabilities["extensions"]["io.modelcontextprotocol/ui"] == {"mimeTypes": [MIME_TYPE]}


def test_there_are_no_views_yet(rpc: Rpc) -> None:
    """Tally answers in text: no ui:// resources, and no tool points at one."""
    assert RESOURCES == {}
    assert rpc("resources/list") == {"resources": []}
    assert rpc("resources/templates/list") == {"resourceTemplates": []}
    assert not any(t.ui for t in TOOLS.values())


def test_tools_without_ui_have_no_meta(rpc: Rpc) -> None:
    """A plain tool describes itself without _meta."""
    described = next(t for t in rpc("tools/list")["tools"] if t["name"] == "list_workouts")
    assert "_meta" not in described


def test_a_tool_with_ui_names_it_in_both_key_forms() -> None:
    """A tool's ui goes in _meta, nested and in the older flat key."""
    tool = Tool("t", "A test tool.", {}, lambda user, args: {}, ui="ui://tally/v")
    meta = tool.describe()["_meta"]
    assert meta == {"ui": {"resourceUri": "ui://tally/v"}, "ui/resourceUri": "ui://tally/v"}


def test_a_view_is_one_self_contained_document(
    rpc: Rpc, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A listed view reads back as HTML that loads nothing: its scripts are inline."""
    (tmp_path / "test_view.html").write_text("<!doctype html><body></body>")
    (tmp_path / resources.BRIDGE).write_text("class McpApp {}")
    monkeypatch.setattr(resources, "UI_DIR", tmp_path)
    uri = "ui://tally/test-view"
    view = UiResource(uri, "test-view", "Test", "A test view.", "test_view.html")
    monkeypatch.setattr(resources, "RESOURCES", {uri: view})
    resources.render.cache_clear()
    try:
        (content,) = rpc("resources/read", {"uri": uri})["contents"]
    finally:
        resources.render.cache_clear()
    assert content["uri"] == uri
    assert content["mimeType"] == MIME_TYPE
    assert "prefersBorder" in content["_meta"]["ui"]
    html = content["text"]
    assert html.startswith("<!doctype html>")
    assert "McpApp" in html
    assert not re.search(r"<(script|img|iframe)[^>]*\ssrc=|<link\b", html)
    assert html.count("</script>") == html.count("<script>")


@pytest.mark.parametrize(
    ("params", "code"),
    [({"uri": "ui://nope"}, -32002), ({}, -32602)],
)
def test_resources_read_errors(rpc: Rpc, params: dict[str, Any], code: int) -> None:
    """An unknown URI is 'resource not found'; a missing one is invalid params."""
    from apps.mcp.views import RpcError

    with pytest.raises(RpcError) as caught:
        rpc("resources/read", params)
    assert caught.value.code == code


def test_inlined_scripts_cannot_close_their_tag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A "</script>" inside a view's JavaScript is escaped, not left to end the tag."""
    (tmp_path / "v.html").write_text("<body></body>")
    (tmp_path / "v.js").write_text("const s = '</script>';")
    monkeypatch.setattr(resources, "UI_DIR", tmp_path)
    html = resources.render.__wrapped__("v.html", ("v.js",))
    assert html == "<body><script>\nconst s = '<\\/script>';</script>\n</body>"


def test_a_view_needs_a_body(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """HTML with nowhere to put the scripts is a mistake, caught at once."""
    (tmp_path / "v.html").write_text("<p>no body</p>")
    monkeypatch.setattr(resources, "UI_DIR", tmp_path)
    with pytest.raises(ValueError, match="no </body>"):
        resources.render.__wrapped__("v.html", ())


@pytest.mark.parametrize(
    ("tool", "heading"),
    [("privacy_policy", "# Privacy notice"), ("terms_of_service", "# Terms"), ("help", "# Help")],
)
def test_public_pages_come_back_as_markdown(rpc: Rpc, tool: str, heading: str) -> None:
    """The text content is the Markdown itself; structuredContent adds title and URL."""
    result = rpc("tools/call", {"name": tool, "arguments": {}})
    text = result["content"][0]["text"]
    assert heading in text
    assert text == result["structuredContent"]["markdown"]
    assert result["structuredContent"]["url"].startswith("http")


def test_tool_errors_are_readable(rpc: Rpc) -> None:
    """A bad argument is an isError result, not a protocol error."""
    result = rpc("tools/call", {"name": "get_workout", "arguments": {"workout": "Arms"}})
    assert result["isError"] is True
    assert "No workout matches" in result["content"][0]["text"]


def test_a_missing_argument_is_a_tool_error(rpc: Rpc) -> None:
    """Leaving out a required argument is an isError result naming it, not a crash."""
    result = rpc("tools/call", {"name": "get_workout", "arguments": {}})
    assert result["isError"] is True
    assert "Missing argument 'workout'" in result["content"][0]["text"]


def call_endpoint(client: Client, body: Any, headers: dict[str, str] | None = None) -> Any:
    """POST ``body`` to /mcp with a valid bearer token for an active user."""
    token = TestMCPAuth().token_for(UserFactory.create())
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
        ([{"jsonrpc": "2.0", "id": 1, "method": "ping"}], 400, -32600),
        ({"id": 1, "method": "ping"}, 400, -32600),
        ({"jsonrpc": "2.0", "id": 1, "method": "nope"}, 200, -32601),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": "x"}, 200, -32602),
        ({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "x"}}, 200, -32602),
        (
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "get_workout", "arguments": "x"},
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


@pytest.mark.django_db
def test_a_tool_call_over_http_runs_as_the_tokens_user(client: Client) -> None:
    """A tools/call through the endpoint answers with structured content."""
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "list_workouts", "arguments": {}},
    }
    result = call_endpoint(client, body).json()["result"]
    assert result["structuredContent"] == {"workouts": []}
    assert json.loads(result["content"][0]["text"]) == {"workouts": []}


def test_staff_only_policy() -> None:
    """The template's stricter rule, kept for projects that want it: only active staff."""
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
