# Claude may list grants Tally doesn't offer

Claude's OAuth client metadata document lists
`urn:ietf:params:oauth:grant-type:jwt-bearer` as well as
`authorization_code` and `refresh_token`. django-oauth-toolkit 3.4.1 maps a
client to exactly one grant and ignores only `refresh_token`, so it refused
Claude's `client_id` and connecting stopped at "Invalid client_id parameter
value".

RFC 7591 lets a server register less than a client asks for, so
`apps/mcp/grant_types.py` adds the JWT-bearer grant to the toolkit's ignored
set (for CIMD and DCR) when the app loads. Claude is registered for the
authorisation-code grant, which is the only one it uses here.

This belongs in mcp-auth (every Titan project serves Claude) or upstream in
the toolkit; remove the module once either carries it.
