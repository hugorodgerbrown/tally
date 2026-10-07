"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path

from apps.accounts.views import admin_login
from apps.activity import retired
from apps.core.views import healthz, livez
from apps.mcp.views import mcp
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
    # Staff sign in like everyone else; the admin's password form is unused.
    path("admin/login/", admin_login),
    path("admin/", admin.site.urls),
    # The installed app: everything under /app/ (apps/pwa/conf.py: SCOPE).
    # The phone's activity mode is /app/ itself; the planner sits beside it.
    path("app/", include("apps.pwa.urls")),
    path("app/", include("apps.activity.urls")),
    path("app/", include("apps.planner.urls")),
    path("", include("mcp_auth.urls")),
    path("mcp", mcp, name="mcp"),
    # Before the move to /app/: retire the old service workers and send old
    # bookmarks and installed apps to the new addresses.
    path("", include(retired.urlpatterns)),
]
