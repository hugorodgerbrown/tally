from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from config.views import healthz, home
from mcp_server.views import mcp

admin.site.site_header = "Tally"
admin.site.site_title = "Tally"

urlpatterns = [
    path("", home, name="home"),
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("mcp", mcp, name="mcp"),
    path("", include("mcp_auth.urls")),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="planner/login.html", redirect_authenticated_user=True
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("planner.urls")),
    path("", include("activity.urls")),
]
