from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from config.views import healthz

admin.site.site_header = "Tally"
admin.site.site_title = "Tally"

urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
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
