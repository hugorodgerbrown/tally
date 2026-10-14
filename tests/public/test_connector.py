"""Tests for apps.public.connector: the MCP address the public pages show."""

from typing import Any

from django.urls import NoReverseMatch

from apps.public import connector


def test_the_address_is_absolute_on_the_site_url(settings: Any, monkeypatch: Any) -> None:
    """Built on SITE_URL, which mcp-auth binds the tokens to, not the request's host."""
    settings.SITE_URL = "https://example.test"
    monkeypatch.setattr(connector, "reverse", lambda name: "/mcp")
    assert connector.mcp_url() == "https://example.test/mcp"


def test_no_address_without_mcp(monkeypatch: Any) -> None:
    """An app made without MCP has no mcp URL, so the pages leave the section out."""

    def missing(name: str) -> str:
        raise NoReverseMatch(name)

    monkeypatch.setattr(connector, "reverse", missing)
    assert connector.mcp_url() == ""
