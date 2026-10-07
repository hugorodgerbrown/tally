"""URLs for the public pages."""

from django.urls import path

from apps.public import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("terms/", views.terms, name="terms"),
    path("privacy/", views.privacy, name="privacy"),
    path("help/", views.help_page, name="help"),
]
