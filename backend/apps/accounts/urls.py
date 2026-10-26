"""URL routing for accounts and auth endpoints."""

from django.urls import path

from apps.accounts.views import (
    BrevoWebhookView,
    ChangePasswordView,
    CreateSuperAdminView,
    GymAuditLogListView,
    LoginView,
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    PlatformAuditLogListView,
    SetPasswordFromInviteView,
    StaffDeactivateView,
    StaffListCreateView,
    StaffReactivateView,
    StaffResendInviteView,
    TokenRefreshView,
    UserProfileView,
)

urlpatterns = [
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path("api/auth/me/", UserProfileView.as_view(), name="user-profile"),
    path(
        "api/auth/change-password/",
        ChangePasswordView.as_view(),
        name="change-password",
    ),
    path(
        "api/auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "api/auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "api/auth/set-password/",
        SetPasswordFromInviteView.as_view(),
        name="auth-set-password",
    ),
    path(
        "api/platform/super-admins/",
        CreateSuperAdminView.as_view(),
        name="platform-super-admins",
    ),
    path(
        "api/gym/staff/",
        StaffListCreateView.as_view(),
        name="gym-staff-list-create",
    ),
    path(
        "api/gym/staff/<uuid:user_id>/deactivate/",
        StaffDeactivateView.as_view(),
        name="gym-staff-deactivate",
    ),
    path(
        "api/gym/staff/<uuid:user_id>/reactivate/",
        StaffReactivateView.as_view(),
        name="gym-staff-reactivate",
    ),
    path(
        "api/gym/staff/<uuid:user_id>/resend-invite/",
        StaffResendInviteView.as_view(),
        name="gym-staff-resend-invite",
    ),
    # Brevo Webhook (Sprint 9b)
    path(
        "api/webhooks/brevo/",
        BrevoWebhookView.as_view(),
        name="brevo-webhook",
    ),
    # Audit Log Viewer (Sprint 9a)
    path(
        "api/gym/audit-logs/",
        GymAuditLogListView.as_view(),
        name="gym-audit-logs",
    ),
    path(
        "api/platform/audit-logs/",
        PlatformAuditLogListView.as_view(),
        name="platform-audit-logs",
    ),
]
