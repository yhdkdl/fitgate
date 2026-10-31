"""Custom permissions for accounts and platform access control."""

from django.conf import settings
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated

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


class IsSuperAdmin(IsAuthenticated):
    """
    Grants access only to authenticated Super Admins at the apex platform domain.
    Fails closed: requires request.tenant is None (denies on gym subdomains).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if getattr(request, "tenant", None) is not None:
            return False
        return bool(
            getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
            or getattr(request.user, "is_superuser", False)
        )


class DocsPermission(BasePermission):
    """
    Permission for OpenAPI docs:
    - Public when settings.DOCS_PUBLIC is True (e.g. local development).
    - Super Admin only at apex platform domain when settings.DOCS_PUBLIC is False (production).
    No behavior depends on settings.DEBUG.
    """

    def has_permission(self, request, view):
        if getattr(settings, "DOCS_PUBLIC", False):
            return True
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request, "tenant", None) is not None:
            return False
        return bool(
            getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
            or getattr(request.user, "is_superuser", False)
        )


class IsGymOwner(IsAuthenticated):
    """
    Grants access only to authenticated Gym Owners belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_OWNER


class IsGymManager(IsAuthenticated):
    """
    Grants access only to authenticated Gym Managers belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_MANAGER


class IsOwnerOrManager(IsAuthenticated):
    """
    Grants access to authenticated Gym Owners or Managers belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
        ]


class IsGymStaff(IsAuthenticated):
    """
    Grants access to any staff role (Owner, Manager, Trainer, Reception) of the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        staff_roles = [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ]
        return getattr(request.user, "role", None) in staff_roles


class IsTrainer(IsAuthenticated):
    """
    Grants access to authenticated Trainers belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_TRAINER


class IsReception(IsAuthenticated):
    """
    Grants access to authenticated Reception staff belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_RECEPTION


class IsMember(IsAuthenticated):
    """
    Grants access to authenticated Members belonging to the active tenant.
    Fails closed: requires request.tenant to be set AND user.gym_id == request.tenant.id.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_MEMBER


class IsOwnerOrSuperAdmin(IsAuthenticated):
    """
    Grants access to Super Admin (apex only, tenant is None) or Gym Owner (active tenant only).
    Fails closed: Super Admin denied on gym host; Owner denied on apex or mismatched tenant.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        is_super = getattr(
            request.user, "role", None
        ) == User.ROLE_SUPER_ADMIN or getattr(request.user, "is_superuser", False)
        if is_super:
            return tenant is None

        if getattr(request.user, "role", None) == User.ROLE_OWNER:
            if not tenant:
                return False
            return getattr(request.user, "gym_id", None) == tenant.id

        return False


class CanEditGymEntitlements(IsAuthenticated):
    """
    Entitlements (tier, has_* flags, freeze allowance, grace and reminder days)
    can ONLY be modified by Super Admin at apex (tenant is None).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if getattr(request, "tenant", None) is not None:
            return False
        return bool(
            getattr(request.user, "role", None) == User.ROLE_SUPER_ADMIN
            or getattr(request.user, "is_superuser", False)
        )


class CanEditGymSettings(IsAuthenticated):
    """
    Gym settings (branding, member reminder days, payment credentials) can be edited
    by the Gym Owner on the active tenant. Manager and other roles receive 403 Forbidden.
    Super Admin is denied (SPEC §2 indicates '-' for Super Admin on gym settings).
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) == User.ROLE_OWNER


class CanEndFreezeEarly(IsAuthenticated):
    """
    Grants access to Gym Owner, Manager, or Reception on the active tenant to end freezes early.
    Trainers, Members, Super Admin, and cross-tenant users receive 403 Forbidden.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
        ]


class CanRegisterMember(IsAuthenticated):
    """
    Grants access to Gym Owner, Manager, or Reception on the active tenant.
    Trainers, Members, and Super Admin (at gym host) receive 403 Forbidden.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
        ]


class CanManageAttendance(IsAuthenticated):
    """
    Grants check-in scan and manual override access to Gym Owner, Manager, or Reception
    on the active tenant.
    Trainers, Members, and Super Admin (at gym host) receive 403 Forbidden.
    """

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False
        return getattr(request.user, "role", None) in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
        ]
