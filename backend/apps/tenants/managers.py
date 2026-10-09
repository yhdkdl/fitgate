"""Tenant-scoped QuerySet and Manager for row-level gym_id isolation."""

from django.core.exceptions import ValidationError
from django.db import models

from apps.tenants.context import get_current_tenant


class TenantQuerySet(models.QuerySet):
    """QuerySet that automatically applies tenant filtering and validation."""

    def bulk_create(self, objs, *args, **kwargs):
        """
        Validate tenant context and auto-populate gym foreign key for bulk_create.

        Enforces the same rules as TenantAwareModel.save():
        - If tenant context is active and any instance carries a mismatched gym, raises ValidationError.
        - If tenant context is active and any instance has no gym, auto-assigns current_tenant.
        - If no tenant context is active and any instance has no gym, raises ValidationError.
        """
        objs = list(objs)
        current_tenant = get_current_tenant()
        for obj in objs:
            gym_id = getattr(obj, "gym_id", None)
            if not gym_id and getattr(obj, "gym", None):
                gym_id = obj.gym.id

            if current_tenant is not None:
                if gym_id and str(gym_id) != str(current_tenant.id):
                    raise ValidationError(
                        "Cannot assign or modify record for a different tenant."
                    )
                if not gym_id:
                    obj.gym = current_tenant
            else:
                if not gym_id:
                    raise ValidationError(
                        "Tenant context or explicit gym assignment is required to save a tenant-scoped record."
                    )
        return super().bulk_create(objs, *args, **kwargs)


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Base manager for tenant-scoped models.

    Automatically scopes all queries to the tenant in the current context.
    Fails closed: returns an empty queryset (.none()) if no tenant context is active.
    Unscoped queries must explicitly call .unscoped() or use all_objects.
    """

    def get_queryset(self):
        """Return queryset filtered by current tenant if set, else fail closed (.none())."""
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            return super().get_queryset().filter(gym=current_tenant)
        return super().get_queryset().none()

    def unscoped(self):
        """Return full queryset without applying tenant scoping."""
        return super().get_queryset()
