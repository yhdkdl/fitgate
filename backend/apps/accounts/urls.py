"""URL routing for accounts and auth endpoints."""

from django.urls import path

from apps.accounts.views import (
    ChangePasswordView,
    CreateSuperAdminView,
    LoginView,
    LogoutView,
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
        "api/platform/super-admins/",
        CreateSuperAdminView.as_view(),
        name="platform-super-admins",
    ),
]
