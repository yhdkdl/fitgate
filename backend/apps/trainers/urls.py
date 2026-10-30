from django.urls import path

from apps.trainers.views import (
    GymAssignmentListView,
    GymReassignTrainerView,
    GymTrainerDetailView,
    GymTrainerListView,
    GymUnassignedMembersView,
    TrainerMeView,
    TrainerMyClientsView,
)

urlpatterns = [
    path("api/gym/trainers/", GymTrainerListView.as_view(), name="gym-trainers-list"),
    path(
        "api/gym/trainers/<uuid:pk>/",
        GymTrainerDetailView.as_view(),
        name="gym-trainer-detail",
    ),
    path("api/trainers/me/", TrainerMeView.as_view(), name="trainer-me"),
    path(
        "api/trainers/me/clients/",
        TrainerMyClientsView.as_view(),
        name="trainer-me-clients",
    ),
    path(
        "api/gym/assignments/",
        GymAssignmentListView.as_view(),
        name="gym-assignments-list",
    ),
    path(
        "api/gym/assignments/reassign/",
        GymReassignTrainerView.as_view(),
        name="gym-assignments-reassign",
    ),
    path(
        "api/gym/unassigned-members/",
        GymUnassignedMembersView.as_view(),
        name="gym-unassigned-members",
    ),
    path(
        "api/trainers/me/clients/",
        TrainerMyClientsView.as_view(),
        name="trainer-me-clients",
    ),
    path(
        "api/gym/assignments/",
        GymAssignmentListView.as_view(),
        name="gym-assignments-list",
    ),
    path(
        "api/gym/assignments/reassign/",
        GymReassignTrainerView.as_view(),
        name="gym-assignments-reassign",
    ),
    path(
        "api/gym/unassigned-members/",
        GymUnassignedMembersView.as_view(),
        name="gym-unassigned-members",
    ),
]
