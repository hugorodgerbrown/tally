"""App config for apps.mcp."""

from django.apps import AppConfig


class McpConfig(AppConfig):
    """The MCP server. Authentication is mcp_auth's; the tools are ours."""

    name = "apps.mcp"
    label = "mcp"

    def ready(self) -> None:
        """Let Claude connect although its client metadata lists the JWT-bearer grant."""
        from apps.mcp.grant_types import ignore_unsupported_grant_types

        ignore_unsupported_grant_types()
