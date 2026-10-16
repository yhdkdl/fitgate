"""URL patterns for memberships app."""

from django.urls import path

from apps.memberships.views import (
    GymMemberDetailView,
    GymMemberListCreateView,
    GymMemberRecordMetricsView,
    MemberSelfMetricsView,
    MemberSelfProfileView,
    PublicMemberRegistrationView,
    VerifyEmailView,
)

urlpatterns = [
    # Public self-service registration and email verification
    path(
        "api/public/members/register/",
        PublicMemberRegistrationView.as_view(),
        name="public-member-register",
    ),
    path(
        "api/auth/verify-email/",
        VerifyEmailView.as_view(),
        name="verify-email",
    ),
    # Staff-assisted registration and member directory
    path(
        "api/gym/members/",
        GymMemberListCreateView.as_view(),
        name="gym-member-list-create",
    ),
    path(
        "api/gym/members/<uuid:pk>/",
        GymMemberDetailView.as_view(),
        name="gym-member-detail",
    ),
    path(
        "api/gym/members/<uuid:pk>/metrics/",
        GymMemberRecordMetricsView.as_view(),
        name="gym-member-record-metrics",
    ),
    # Member self-service endpoints
    path(
        "api/members/me/",
        MemberSelfProfileView.as_view(),
        name="member-me",
    ),
    path(
        "api/members/me/metrics/",
        MemberSelfMetricsView.as_view(),
        name="member-me-metrics",
    ),
]
