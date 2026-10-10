"""Custom permissions for accounts and platform access control."""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class RequirePasswordChanged(BasePermission):
    """
    Blocks every authenticated endpoint except auth endpoints with 403
    'password_change_required' while must_change_password is True.
    """

    message = "password_change_required"

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return True

        # Exempt auth endpoints
        if getattr(view, "is_auth_endpoint", False) or getattr(
            request, "_is_auth_endpoint", False
        ):
            return True

        if getattr(request.user, "must_change_password", False):
            raise PermissionDenied(detail="password_change_required")

        return True


class IsSuperAdmin(BasePermission):
    """Grants access only to authenticated Super Admins."""

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
        )


class DocsPermission(BasePermission):
    """
    Permission for OpenAPI docs:
    - Public when settings.DEBUG is True.
    - Super Admin only when settings.DEBUG is False.
    """

    def has_permission(self, request, view):
        if getattr(settings, "DEBUG", False):
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
        )
