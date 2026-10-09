"""Custom managers for User model."""

from django.contrib.auth.base_user import BaseUserManager
from django.db import models
from django.utils import timezone

from apps.tenants.context import get_current_tenant
from apps.tenants.managers import PlatformTenantQuerySet


class UserManager(BaseUserManager.from_queryset(PlatformTenantQuerySet)):
    """
    Tenant-aware and host-scoped User manager.

    - Inside a gym tenant: returns only that gym's users.
    - At the apex domain: returns only platform users (Super Admins, gym is null).
    - Unscoped queries explicit via .unscoped() or User.all_objects.
    """

    def get_queryset(self):
        """Return queryset scoped to current tenant context or apex platform users."""
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            return super().get_queryset().filter(gym=current_tenant)
        return super().get_queryset().filter(gym__isnull=True)

    def unscoped(self):
        """Return full queryset without host/tenant scoping."""
        return super().get_queryset()

    def create_user(self, email, password=None, **extra_fields):
        """
        Create and save a User with normalized lowercase email.

        Enforces lowercase email, microsecond password_changed_at, and standard defaults.
        """
        if not email:
            raise ValueError("The Email field must be set.")
        email = self.normalize_email(email).lower()
        extra_fields.setdefault("is_active", True)
        user = self.model(email=email, **extra_fields)

        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
            user.password_changed_at = timezone.now()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Create and save a Super Admin user at the platform level.

        Enforces role=super_admin, gym=None.
        """
        extra_fields["role"] = self.model.ROLE_SUPER_ADMIN
        extra_fields["gym"] = None
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("must_change_password", False)

        return self.create_user(email, password=password, **extra_fields)


class AllUserManager(BaseUserManager.from_queryset(models.QuerySet)):
    """
    Unscoped User manager providing direct access across all tenants and the platform.

    Used by admin, system maintenance commands, and token validation lookups.
    """

    def get_queryset(self):
        """Return all users unconditionally."""
        return super().get_queryset()
