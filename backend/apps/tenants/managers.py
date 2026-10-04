"""Tenant-scoped QuerySet and Manager for row-level gym_id isolation."""

from django.db import models

from apps.tenants.context import get_current_tenant


class TenantQuerySet(models.QuerySet):
    """QuerySet that automatically applies tenant filtering."""

    def filter_by_current_tenant(self):
        """Filter queryset by the current tenant if one is active in context."""
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            return self.filter(gym=current_tenant)
        return self

    def unscoped(self):
        """Return the un-filtered queryset bypassing tenant scoping."""
        return self


class TenantManager(models.Manager.from_queryset(TenantQuerySet)):
    """
    Base manager for tenant-scoped models.

    Automatically scopes all queries to the tenant in the current context
    unless explicitly queried through an unscoped manager.
    """

    def get_queryset(self):
        """Return queryset filtered by current tenant if set in context."""
        qs = super().get_queryset()
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            return qs.filter(gym=current_tenant)
        return qs

    def unscoped(self):
        """Return full queryset without applying tenant scoping."""
        return super().get_queryset()
