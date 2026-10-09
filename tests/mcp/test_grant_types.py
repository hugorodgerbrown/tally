"""Claude connects although its client metadata lists the JWT-bearer grant."""

import json
from typing import Any

import pytest
from django.core.cache import cache
from django.test import Client
from mcp_auth.testing import CALLBACK, pkce_pair
from oauth2_provider import cimd

pytestmark = pytest.mark.django_db

CLAUDE_CLIENT_ID = "https://claude.ai/oauth/mcp-oauth-client-metadata"
# Claude's published client metadata document, as fetched on 9 October 2026.
CLAUDE_METADATA = {
    "client_id": CLAUDE_CLIENT_ID,
    "client_name": "Claude",
    "client_uri": "https://claude.ai",
    "redirect_uris": [CALLBACK],
    "grant_types": [
        "authorization_code",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:jwt-bearer",
    ],
    "response_types": ["code"],
    "token_endpoint_auth_method": "none",
}


@pytest.fixture(autouse=True)
def _no_cimd_backoff() -> None:
    """A failed CIMD fetch is backed off in the cache; start each test with none."""
    cache.clear()


@pytest.fixture
def claude_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve Claude's metadata document without going to the network."""
    monkeypatch.setattr(
        cimd.SafeMetadataFetcher, "fetch", lambda self, client_id: (CLAUDE_METADATA, 3600)
    )


def test_claude_reaches_the_consent_page(signed_in: Client, claude_metadata: None) -> None:
    """The authorise step asks for consent instead of refusing the client_id."""
    _, challenge = pkce_pair()
    response = signed_in.get(
        "/oauth/authorize/",
        {
            "response_type": "code",
            "client_id": CLAUDE_CLIENT_ID,
            "redirect_uri": CALLBACK,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": "xyz",
            "scope": "offline_access tally",
            "resource": "http://testserver/mcp",
        },
    )
    assert response.status_code == 200
    assert b"Invalid client_id" not in response.content


def test_registration_accepts_claudes_grant_types(client: Client) -> None:
    """Dynamic client registration takes the same list and registers the code grant."""
    body: dict[str, Any] = {
        k: v for k, v in CLAUDE_METADATA.items() if k not in {"client_id", "client_uri"}
    }
    response = client.post("/oauth/register/", json.dumps(body), content_type="application/json")
    assert response.status_code == 201
    assert response.json()["grant_types"] == ["authorization_code", "refresh_token"]
