from rest_framework.permissions import BasePermission

from apps.accounts.models import User


class CanManageEquipment(BasePermission):
    """Owner and Manager can manage equipment registry."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
        ]


class CanReportEquipmentIssue(BasePermission):
    """All staff (Owner, Manager, Trainer, Reception) can report equipment issues."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
        ]


class CanViewEquipment(BasePermission):
    """Staff and Members of the gym can view equipment. Super Admin is denied."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
            User.ROLE_MEMBER,
        ]
