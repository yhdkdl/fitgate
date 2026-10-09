"""URL routing for accounts and auth endpoints."""

from django.urls import path

from apps.accounts.views import (
    CreateSuperAdminView,
    LoginView,
    LogoutView,
    TokenRefreshView,
)

urlpatterns = [
    path("api/auth/login/", LoginView.as_view(), name="auth-login"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="auth-logout"),
    path(
        "api/platform/super-admins/",
        CreateSuperAdminView.as_view(),
        name="platform-super-admins",
    ),
]
