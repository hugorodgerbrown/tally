"""Tests for .claude/launch.json: Claude Code's dev server and tool launchers."""

import json
from pathlib import Path

LAUNCH = Path(__file__).resolve().parent.parent / ".claude" / "launch.json"


def test_launch_config_is_valid_json() -> None:
    """A trailing comma or a stray template tag would break every launcher."""
    configurations = json.loads(LAUNCH.read_text())["configurations"]
    names = [entry["name"] for entry in configurations]
    assert names == ["Dev server", "MCP Inspector"]


def test_dev_server_links_match_its_port() -> None:
    """Sign-in links and passkeys use SITE_URL, so it names the port the server binds."""
    server = json.loads(LAUNCH.read_text())["configurations"][0]
    command = server["runtimeArgs"][-1]
    assert f"SITE_URL=http://localhost:{server['port']}" in command
    assert f"runserver 127.0.0.1:{server['port']}" in command
