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


class IsGymOwner(BasePermission):
    """
    Grants access only to authenticated Gym Owners belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) != User.ROLE_OWNER:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsGymManager(BasePermission):
    """
    Grants access only to authenticated Gym Managers belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) != User.ROLE_MANAGER:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsOwnerOrManager(BasePermission):
    """
    Grants access to authenticated Gym Owners or Managers belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) not in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
        ]:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsGymStaff(BasePermission):
    """
    Grants access to any staff role (Owner, Manager, Trainer, Reception) of the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        staff_roles = [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ]
        if getattr(request.user, "role", None) not in staff_roles:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsTrainer(BasePermission):
    """
    Grants access to authenticated Trainers belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) != User.ROLE_TRAINER:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsReception(BasePermission):
    """
    Grants access to authenticated Reception staff belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) != User.ROLE_RECEPTION:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsMember(BasePermission):
    """
    Grants access to authenticated Members belonging to the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, "role", None) != User.ROLE_MEMBER:
            return False
        tenant = getattr(request, "tenant", None)
        if tenant and getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return True


class IsOwnerOrSuperAdmin(BasePermission):
    """
    Grants access to Super Admin or the Gym Owner of the active tenant.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        is_super = getattr(
            request.user, "role", None
        ) == User.ROLE_SUPER_ADMIN or getattr(request.user, "is_superuser", False)
        if is_super:
            return True
        if getattr(request.user, "role", None) == User.ROLE_OWNER:
            tenant = getattr(request, "tenant", None)
            if tenant and getattr(request.user, "gym_id", None) != tenant.id:
                return False
            return True
        return False


class CanEditGymEntitlements(BasePermission):
    """
    Entitlements (tier, has_* flags, freeze allowance, grace and reminder days)
    can ONLY be modified by Super Admin.
    """

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and (
                getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
                or getattr(request.user, "is_superuser", False)
            )
        )


class CanEditGymSettings(BasePermission):
    """
    Gym settings (branding, member reminder days, payment credentials) can be edited
    by the Gym Owner or Super Admin. Manager and other roles receive 403 Forbidden.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        is_super = getattr(
            request.user, "role", None
        ) == User.ROLE_SUPER_ADMIN or getattr(request.user, "is_superuser", False)
        if is_super:
            return True
        if getattr(request.user, "role", None) == User.ROLE_OWNER:
            tenant = getattr(request, "tenant", None)
            if tenant and getattr(request.user, "gym_id", None) != tenant.id:
                return False
            return True
        return False
