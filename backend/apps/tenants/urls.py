"""URL routing for tenants and platform gym management."""

from django.urls import path

from apps.tenants.views import (
    ConfirmGymTLSView,
    CreateGymView,
    GymDetailView,
    ProposeSubdomainView,
)

urlpatterns = [
    path("api/platform/gyms/", CreateGymView.as_view(), name="platform-gyms"),
    path(
        "api/platform/gyms/propose-subdomain/",
        ProposeSubdomainView.as_view(),
        name="platform-gyms-propose-subdomain",
    ),
    path(
        "api/platform/gyms/<uuid:gym_id>/",
        GymDetailView.as_view(),
        name="platform-gym-detail",
    ),
    path(
        "api/platform/gyms/<uuid:gym_id>/confirm-tls/",
        ConfirmGymTLSView.as_view(),
        name="platform-gym-confirm-tls",
    ),
]
