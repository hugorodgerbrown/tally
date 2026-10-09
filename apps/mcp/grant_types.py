"""Accept OAuth clients that list grant types Tally doesn't offer.

django-oauth-toolkit turns a client's ``grant_types`` into the single grant
its Application row holds, ignoring only ``refresh_token``. Claude's client
metadata document (``https://claude.ai/oauth/mcp-oauth-client-metadata``)
now also lists ``urn:ietf:params:oauth:grant-type:jwt-bearer``, so the
toolkit refuses it and connecting from Claude stops at "Invalid client_id
parameter value".

A client may list grants the server doesn't support (RFC 7591 section 2:
the server chooses what to register), so these are ignored like
``refresh_token`` and the client is registered for the authorisation-code
grant it also asks for. Remove this once the toolkit or mcp-auth does it.
"""

import logging

from oauth2_provider import cimd
from oauth2_provider.views import dynamic_client_registration

logger = logging.getLogger(__name__)

# Grants a client may list alongside authorization_code that Tally never issues.
UNSUPPORTED_GRANT_TYPES = frozenset({"urn:ietf:params:oauth:grant-type:jwt-bearer"})


def ignore_unsupported_grant_types() -> None:
    """Add the unsupported grants to the toolkit's ignored set, for CIMD and DCR alike."""
    cimd.IGNORED_GRANT_TYPES.update(UNSUPPORTED_GRANT_TYPES)
    dynamic_client_registration.IGNORED_GRANT_TYPES.update(UNSUPPORTED_GRANT_TYPES)
