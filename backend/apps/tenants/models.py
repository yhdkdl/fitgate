"""Data models for FitGate multi-tenancy and configuration."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.tenants.context import get_current_tenant
from apps.tenants.managers import TenantManager


class GymTenant(models.Model):
    """
    Represents a gym tenant on the FitGate platform.

    Each tenant has a dedicated subdomain and subscription tier.
    """

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_SUSPENDED = "suspended"
    STATUS_TERMINATED = "terminated"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_TERMINATED, "Terminated"),
    ]

    TIER_STARTER = "starter"
    TIER_GROWTH = "growth"
    TIER_PRO = "pro"

    TIER_CHOICES = [
        (TIER_STARTER, "Starter"),
        (TIER_GROWTH, "Growth"),
        (TIER_PRO, "Pro"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    subdomain = models.SlugField(max_length=63, unique=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default=TIER_STARTER)
    currency = models.CharField(max_length=3, default="ETB")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Gym Tenant"
        verbose_name_plural = "Gym Tenants"

    def clean(self):
        super().clean()
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()
            if self.subdomain in {"api", "admin", "www", "app", "mail", "localhost"}:
                raise ValidationError({"subdomain": "This subdomain is reserved."})

    def save(self, *args, **kwargs):
        if self.subdomain:
            self.subdomain = self.subdomain.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.subdomain})"


class GymConfig(models.Model):
    """
    Feature-gating configuration and payment keys for a gym tenant.

    1:1 relationship with GymTenant where gym_id is both PK and FK.
    """

    gym = models.OneToOneField(
        GymTenant,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="config",
    )
    has_trainer_module = models.BooleanField(default=False)
    has_ai_plans = models.BooleanField(default=False)
    has_analytics = models.BooleanField(default=False)
    has_group_classes = models.BooleanField(default=False)
    has_multi_branch = models.BooleanField(default=False)
    chapa_merchant_id = models.CharField(max_length=255, null=True, blank=True)
    freeze_days_allowed = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Gym Configuration"
        verbose_name_plural = "Gym Configurations"

    def __str__(self):
        return f"Config for {self.gym.name}"


class TenantAwareModel(models.Model):
    """
    Abstract base class for all row-level tenant-scoped models.

    Carries gym_id foreign key, enforces automatic query filtering via
    TenantManager, and provides all_objects for unscoped system access.
    """

    gym = models.ForeignKey(
        GymTenant,
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Auto-populate gym foreign key from context if not already set."""
        if not getattr(self, "gym_id", None):
            current_tenant = get_current_tenant()
            if current_tenant is not None:
                self.gym = current_tenant
        super().save(*args, **kwargs)
