"""URL patterns for memberships app."""

from django.urls import path

from apps.memberships.views import (
    GymFreezeApproveView,
    GymFreezeListView,
    GymFreezeRejectView,
    GymMemberDetailView,
    GymMemberListCreateView,
    GymMemberRecordMetricsView,
    MemberFreezeAllowanceView,
    MemberFreezeRequestView,
    MemberMyFreezesView,
    MemberReactivateView,
    MemberSelfMetricsView,
    MemberSelfProfileView,
    MembershipPlanDetailView,
    MembershipPlanListCreateView,
    MemberSuspendView,
    PublicMemberRegistrationView,
    PublicPlanListView,
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
    # Public plans
    path(
        "api/public/plans/",
        PublicPlanListView.as_view(),
        name="public-plans",
    ),
    # Membership Plans management
    path(
        "api/gym/plans/",
        MembershipPlanListCreateView.as_view(),
        name="gym-plans-list-create",
    ),
    path(
        "api/gym/plans/<uuid:pk>/",
        MembershipPlanDetailView.as_view(),
        name="gym-plan-detail",
    ),
    path(
        "api/gym/membership-plans/",
        MembershipPlanListCreateView.as_view(),
        name="gym-membership-plans-list-create",
    ),
    path(
        "api/gym/membership-plans/<uuid:pk>/",
        MembershipPlanDetailView.as_view(),
        name="gym-membership-plan-detail",
    ),
    path(
        "api/gym/membership-plans/public/",
        PublicPlanListView.as_view(),
        name="gym-membership-plans-public",
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
    path(
        "api/gym/members/<uuid:pk>/suspend/",
        MemberSuspendView.as_view(),
        name="gym-member-suspend",
    ),
    path(
        "api/gym/members/<uuid:pk>/reactivate/",
        MemberReactivateView.as_view(),
        name="gym-member-reactivate",
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
    # Member freeze self-service
    path(
        "api/memberships/freezes/",
        MemberFreezeRequestView.as_view(),
        name="member-freeze-request",
    ),
    path(
        "api/memberships/freezes/mine/",
        MemberMyFreezesView.as_view(),
        name="member-my-freezes",
    ),
    path(
        "api/memberships/freezes/allowance/",
        MemberFreezeAllowanceView.as_view(),
        name="member-freeze-allowance",
    ),
    # Staff freeze review endpoints
    path(
        "api/gym/freezes/",
        GymFreezeListView.as_view(),
        name="gym-freeze-list",
    ),
    path(
        "api/gym/freezes/<uuid:freeze_id>/approve/",
        GymFreezeApproveView.as_view(),
        name="gym-freeze-approve",
    ),
    path(
        "api/gym/freezes/<uuid:freeze_id>/reject/",
        GymFreezeRejectView.as_view(),
        name="gym-freeze-reject",
    ),
]
