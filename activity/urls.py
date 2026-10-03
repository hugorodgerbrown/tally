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
    # The manifest keeps its original URL and id ("/") so phones that installed
    # Tally before the move update in place: Chrome matches an installed app by
    # id and picks up the new start_url and scope.
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.retired_service_worker, name="retired_service_worker"),
    path("api/workouts/", api.workouts, name="api_workouts"),
    path("api/workouts/<uuid:workout_id>/keep/", api.keep_workout, name="api_keep_workout"),
    path("api/sessions/", api.sessions, name="api_sessions"),
]
