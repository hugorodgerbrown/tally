"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import admin_login
from apps.activity import retired
from apps.core.views import healthz, livez, security_txt
from apps.mcp.views import mcp, openai_apps_challenge
from apps.pwa.conf import APP_NAME

admin.site.site_header = APP_NAME
admin.site.site_title = APP_NAME

urlpatterns = [
    # Public: the homepage, terms, privacy, and signing in and out.
    path("", include("apps.public.urls")),
    path("", include("apps.accounts.urls")),
    # Health checks: /livez for Render (process up), /healthz adds the database.
    path("livez", livez, name="livez"),
    path("healthz", healthz, name="healthz"),
    # RFC 9116: who to tell about a vulnerability.
    path(".well-known/security.txt", security_txt, name="security-txt"),
    # Staff sign in like everyone else; the admin's password form is unused.
    path("admin/login/", admin_login),
    path("admin/", admin.site.urls),
    # The installed app: everything under /app/ (apps/pwa/conf.py: SCOPE).
    # The phone's activity mode is /app/ itself; the planner sits beside it.
    path("app/", include("apps.pwa.urls")),
    path("app/", include("apps.activity.urls")),
    path("app/", include("apps.planner.urls")),
    path("app/", include("apps.design.urls")),
    path("", include("mcp_auth.urls")),
    path("mcp", mcp, name="mcp"),
    # Before the move to /app/: retire the old service workers and send old
    # bookmarks and installed apps to the new addresses.
    path("", include(retired.urlpatterns)),
    # OpenAI's domain check for ChatGPT's app directory.
    path(".well-known/openai-apps-challenge", openai_apps_challenge, name="openai-apps-challenge"),
]

# The error pages (apps/core/errors.py): JSON, plain text for htmx, or HTML.
handler400 = "apps.core.errors.bad_request"
handler403 = "apps.core.errors.permission_denied"
handler404 = "apps.core.errors.page_not_found"
handler500 = "apps.core.errors.server_error"
