"""Fixtures for the MCP tests: call the endpoint's dispatcher as a user."""

from collections.abc import Callable
from typing import Any

import pytest

Rpc = Callable[..., dict[str, Any]]


@pytest.fixture
def rpc(user: Any) -> Rpc:
    """Call the MCP view as ``user``, bypassing OAuth (the auth contract covers that)."""
    from apps.mcp import views

    def call(method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Dispatch one JSON-RPC method and return its result."""
        result: dict[str, Any] = views._dispatch(user, method, params or {})
        return result

    return call


@pytest.fixture
def call(rpc: Rpc) -> Rpc:
    """Call one tool by name with keyword arguments; return the tools/call result."""

    def run(name: str, /, **arguments: Any) -> dict[str, Any]:
        """Run tool ``name`` with ``arguments``."""
        return rpc("tools/call", {"name": name, "arguments": arguments})

    return run
