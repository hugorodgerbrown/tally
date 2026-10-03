from django.contrib.auth import views as auth_views
from django.urls import path

from . import api, views

app_name = "activity"

# Everything the installed app opens lives under /activity/, the manifest's
# scope, so it stays inside the app window. Sign-in and sign-out are here too:
# out-of-scope pages open in a browser sheet, and on iOS that sheet doesn't
# share the app's cookies.
urlpatterns = [
    path("activity/", views.app, name="app"),
    path("activity/sw.js", views.service_worker, name="service_worker"),
    path("activity/manifest.webmanifest", views.manifest, name="manifest"),
    path(
        "activity/login/",
        auth_views.LoginView.as_view(
            template_name="planner/login.html",
            redirect_authenticated_user=True,
            next_page="activity:app",
        ),
        name="login",
    ),
    path("activity/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("sw.js", views.retired_service_worker, name="retired_service_worker"),
    path("api/workouts/", api.workouts, name="api_workouts"),
    path("api/sessions/", api.sessions, name="api_sessions"),
]
