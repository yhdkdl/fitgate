"""Tenant-scoped QuerySet and Manager for row-level gym_id isolation."""

from django.db import models

from apps.tenants.context import get_current_tenant


class TenantQuerySet(models.QuerySet):
    """QuerySet that automatically applies tenant filtering."""

    def filter_by_current_tenant(self):
        """Filter queryset by the current tenant if one is active in context, else empty."""
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            return self.filter(gym=current_tenant)
        return self.none()

    def unscoped(self):
        """Return the un-filtered queryset bypassing tenant scoping."""
        return self


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
