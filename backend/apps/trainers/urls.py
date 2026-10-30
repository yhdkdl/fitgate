from django.urls import path

from apps.trainers.views import (
    GymTrainerDetailView,
    GymTrainerListView,
    TrainerMeView,
)

urlpatterns = [
    path("api/gym/trainers/", GymTrainerListView.as_view(), name="gym-trainers-list"),
    path(
        "api/gym/trainers/<uuid:pk>/",
        GymTrainerDetailView.as_view(),
        name="gym-trainer-detail",
    ),
    path("api/trainers/me/", TrainerMeView.as_view(), name="trainer-me"),
]
