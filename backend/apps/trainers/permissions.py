from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class HasTrainerModule(BasePermission):
    """
    Ensures that the gym has the trainer module enabled (GymConfig.has_trainer_module=True).
    Super Admin is denied on gym operational data.
    """

    message = "Trainer module is not enabled for this gym."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        # Tenant scoping: User must belong to the tenant
        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        config = getattr(tenant, "config", None)
        if not config or not config.has_trainer_module:
            from apps.tenants.models import GymConfig

            config = GymConfig.objects.filter(gym_id=tenant.id).first()
            if not config or not config.has_trainer_module:
                raise PermissionDenied("Trainer module is not enabled for this gym.")

        return True


class IsOwnerOrManager(BasePermission):
    """Allows access only to Owner or Manager of the tenant."""

    message = "Only Gym Owner or Manager can perform this action."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        return request.user.role in (User.ROLE_OWNER, User.ROLE_MANAGER)


class IsTrainerRole(BasePermission):
    """Allows access only to Trainer of the tenant."""

    message = "Only Trainers can access this endpoint."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied(
                "Super Admin cannot access gym trainer operational data."
            )

        return request.user.role == User.ROLE_TRAINER
