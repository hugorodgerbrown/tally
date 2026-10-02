from django.urls import path

from . import api, views

app_name = "activity"

urlpatterns = [
    path("", views.app, name="app"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("api/workouts/", api.workouts, name="api_workouts"),
    path("api/sessions/", api.sessions, name="api_sessions"),
]
