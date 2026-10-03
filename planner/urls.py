from django.urls import path

from . import views

app_name = "planner"

urlpatterns = [
    path("workouts/", views.workout_list, name="workouts"),
    path("workouts/new/", views.workout_edit, name="workout_new"),
    path("workouts/<uuid:uuid>/", views.workout_edit, name="workout_edit"),
    path("workouts/<uuid:uuid>/duplicate/", views.workout_duplicate, name="workout_duplicate"),
    path("workouts/<uuid:uuid>/toggle/", views.workout_toggle, name="workout_toggle"),
    path("workouts/<uuid:uuid>/keep/", views.workout_keep, name="workout_keep"),
    path("workouts/<uuid:uuid>/delete/", views.workout_delete, name="workout_delete"),
    path("exercises/", views.exercise_list, name="exercises"),
    path("exercises/new/", views.exercise_edit, name="exercise_new"),
    path("exercises/<uuid:uuid>/", views.exercise_edit, name="exercise_edit"),
    path("exercises/<uuid:uuid>/delete/", views.exercise_delete, name="exercise_delete"),
]
