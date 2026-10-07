"""URLs for notes."""

from django.urls import path

from apps.notes import views

app_name = "notes"

urlpatterns = [
    path("", views.note_list, name="list"),
    path("new/", views.note_create, name="create"),
    path("partials/items/", views.note_items, name="items"),
]
