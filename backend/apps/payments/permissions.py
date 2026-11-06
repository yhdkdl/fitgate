from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from apps.accounts.models import User
from apps.tenants.models import GymConfig


class HasExpensesEnabled(BasePermission):
    """
    Ensures that the gym has expenses and reports enabled (GymConfig.has_expenses=True).
    Super Admin is denied on gym operational data.
    Cross-tenant access is denied.
    """

    message = "Expenses and reports are not enabled for this gym."

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.role == User.ROLE_SUPER_ADMIN:
            raise PermissionDenied("Super Admin cannot access gym operational data.")

        tenant = getattr(request, "tenant", None)
        if not tenant:
            return False

        if getattr(request.user, "gym_id", None) != tenant.id:
            return False

        config = getattr(tenant, "config", None)
        if not config or not config.has_expenses:
            config = GymConfig.objects.filter(gym_id=tenant.id).first()
            if not config or not config.has_expenses:
                raise PermissionDenied(
                    "Expenses and reports are not enabled for this gym."
                )

        return True
