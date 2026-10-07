"""URLs for the PWA shell, mounted at /app/ so the worker's scope is the app alone."""

from django.urls import path

from apps.pwa import views

app_name = "pwa"

urlpatterns = [
    path("manifest.webmanifest", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("offline/", views.offline, name="offline"),
]
