"""URL routing for tenants and platform gym management."""

from django.urls import path

from apps.tenants.views import (
    ConfirmGymTLSView,
    CreateGymView,
    DemoRequestConvertView,
    DemoRequestDetailView,
    DemoRequestListView,
    DismissFirstRunChecklistView,
    FirstRunChecklistView,
    GymDetailView,
    GymPublicEntryView,
    GymSettingsView,
    PlatformGymConfigView,
    ProposeSubdomainView,
    PublicDemoRequestView,
    ServeMemberPhotoView,
    UploadGymLogoView,
    UploadMemberPhotoView,
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
    # Media & File storage (Sprint 4b)
    path(
        "api/media/member-photos/<uuid:gym_id>/<str:filename>/",
        ServeMemberPhotoView.as_view(),
        name="media-member-photo-serve",
    ),
    path(
        "api/media/member-photos/<uuid:gym_id>/",
        UploadMemberPhotoView.as_view(),
        name="media-member-photo-upload",
    ),
    path(
        "api/media/gym-logo/<uuid:gym_id>/",
        UploadGymLogoView.as_view(),
        name="media-gym-logo-upload",
    ),
    # Gym Settings & Branding (Sprint 4c)
    path(
        "api/gym/settings/",
        GymSettingsView.as_view(),
        name="gym-settings",
    ),
    path(
        "api/platform/gyms/<uuid:gym_id>/config/",
        PlatformGymConfigView.as_view(),
        name="platform-gym-config",
    ),
    # First-run Checklist (Sprint 4c)
    path(
        "api/gym/checklist/",
        FirstRunChecklistView.as_view(),
        name="gym-first-run-checklist",
    ),
    path(
        "api/gym/checklist/dismiss/",
        DismissFirstRunChecklistView.as_view(),
        name="gym-first-run-checklist-dismiss",
    ),
    # Public Entry Page (Sprint 4c)
    path(
        "api/public/gym-entry/",
        GymPublicEntryView.as_view(),
        name="public-gym-entry",
    ),
]
