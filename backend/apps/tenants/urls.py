"""URL routing for tenants and platform gym management."""

from django.urls import path

from apps.tenants.views import (
    ConfirmGymTLSView,
    CreateGymView,
    DemoRequestConvertView,
    DemoRequestDetailView,
    DemoRequestListView,
    GymDetailView,
    ProposeSubdomainView,
    PublicDemoRequestView,
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
    # Demo Requests (Sprint 4a)
    path(
        "api/platform/demo-requests/public/",
        PublicDemoRequestView.as_view(),
        name="platform-demo-requests-public",
    ),
    path(
        "api/platform/demo-requests/",
        DemoRequestListView.as_view(),
        name="platform-demo-requests-list",
    ),
    path(
        "api/platform/demo-requests/<uuid:pk>/",
        DemoRequestDetailView.as_view(),
        name="platform-demo-requests-detail",
    ),
    path(
        "api/platform/demo-requests/<uuid:pk>/convert/",
        DemoRequestConvertView.as_view(),
        name="platform-demo-requests-convert",
    ),
]
