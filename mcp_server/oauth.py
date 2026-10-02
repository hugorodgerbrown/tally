"""OAuth pieces around django-oauth-toolkit for the MCP connector.

Claude registers itself as a client (RFC 7591), sends the user to the
consent page, and gets a token for ``/mcp``. Registration is open but only
for the redirect URIs in ``MCP_REDIRECT_URI_PATTERNS``, and only the
superuser can approve a client, so a registration on its own grants nothing.
"""

import json
import re
from typing import Any

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponseBase
from django.urls import path
from django.utils.csp import CSP
from django.utils.decorators import method_decorator
from django.views.decorators.csp import csp_override
from oauth2_provider import views as oauth_views


def redirect_uri_allowed(uri: str) -> bool:
    return any(re.match(p, uri) for p in settings.MCP_REDIRECT_URI_PATTERNS)


class AllowedRedirectDCRPermission:
    """Let anyone register a client whose redirect URIs are all allowlisted."""

    def has_permission(self, request: HttpRequest) -> bool:
        try:
            uris = json.loads(request.body).get("redirect_uris")
        except ValueError, AttributeError:
            return False
        return (
            isinstance(uris, list)
            and bool(uris)
            and all(isinstance(u, str) and redirect_uri_allowed(u) for u in uris)
        )


def _consent_csp() -> dict[str, Any]:
    # Approving redirects the browser to the client's callback, and browsers
    # apply form-action to redirects after a form post, so allow those hosts.
    policy = dict(getattr(settings, "SECURE_CSP", {}))
    policy["form-action"] = [
        CSP.SELF,
        "https://claude.ai",
        "https://claude.com",
        "http://localhost:*",
        "http://127.0.0.1:*",
    ]
    return policy


@method_decorator(csp_override(_consent_csp()), name="dispatch")
class ConsentView(oauth_views.AuthorizationView):
    """The consent page, styled like the planner and limited to the superuser."""

    def dispatch(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        user = request.user
        if user.is_authenticated and not user.is_superuser:
            raise PermissionDenied
        response: HttpResponseBase = super().dispatch(request, *args, **kwargs)
        return response


# Named as django-oauth-toolkit expects, so its metadata views can reverse them.
# The well-known documents sit at the site root; the rest under /oauth/.
app_name = "oauth2_provider"

urlpatterns = [
    path(
        ".well-known/oauth-authorization-server",
        oauth_views.OAuthServerMetadataView.as_view(),
        name="oauth-server-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource",
        oauth_views.OAuthProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata",
    ),
    path(
        ".well-known/oauth-protected-resource/<path:resource_path>",
        oauth_views.OAuthProtectedResourceMetadataView.as_view(),
        name="oauth-resource-metadata-path",
    ),
    path("oauth/authorize/", ConsentView.as_view(), name="authorize"),
    path("oauth/token/", oauth_views.TokenView.as_view(), name="token"),
    path("oauth/revoke/", oauth_views.RevokeTokenView.as_view(), name="revoke-token"),
    path(
        "oauth/register/",
        oauth_views.DynamicClientRegistrationView.as_view(),
        name="dcr-register",
    ),
    path(
        "oauth/register/<str:client_id>/",
        oauth_views.DynamicClientRegistrationManagementView.as_view(),
        name="dcr-register-management",
    ),
]
