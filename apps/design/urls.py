"""URLs for the design page."""

from django.urls import path

from apps.design import views

app_name = "design"

urlpatterns = [
    path("design/", views.design, name="index"),
    path("design/errors/<str:kind>/", views.error_preview, name="error_preview"),
]
