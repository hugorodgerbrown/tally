from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Workouts"
admin.site.site_title = "Workouts"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("activity.urls")),
]
