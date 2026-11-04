from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission, IsAuthenticated

from apps.accounts.models import User
from apps.tenants.models import GymConfig


class HasGroupClassesEnabled(IsAuthenticated):
    """
    Ensures that the gym has group classes enabled (GymConfig.has_group_classes=True).
    Super Admin is denied on gym operational data.
    Cross-tenant access is denied.
    """

    message = "Group classes are not enabled for this gym."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym class operational data."
            )

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        # Tenant scoping: User must belong to the tenant
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        config = getattr(tenant, "config", None)
        if not config or not config.has_group_classes:
            config = GymConfig.objects.filter(gym_id=tenant.id).first()
            if not config or not config.has_group_classes:
                raise PermissionDenied("Group classes are not enabled for this gym.")

        return True


class IsClassManager(BasePermission):
    """Allows Owner and Manager to create, edit, cancel sessions."""

    message = "Only Gym Owner or Manager can manage class sessions."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [User.ROLE_OWNER, User.ROLE_MANAGER]


class CanMarkClassAttendance(BasePermission):
    """Allows Trainer, Owner, or Manager to mark class attendance."""

    message = "Only Trainer, Owner, or Manager can mark class attendance."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
        ]
