"""URLs for the phone's activity mode, mounted at /app/ (the installed app's start)."""

from django.urls import path

from apps.activity import api, views

app_name = "activity"

urlpatterns = [
    path("", views.app, name="app"),
    path("api/workouts/", api.workouts, name="api_workouts"),
    path("api/sessions/", api.sessions, name="api_sessions"),
]
