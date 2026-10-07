"""Data models for FitGate multi-tenancy and configuration."""

import re
import uuid

from django.core.exceptions import ValidationError
from django.db import models

from apps.tenants.context import get_current_tenant
from apps.tenants.managers import TenantManager

SUBDOMAIN_REGEX = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
RESERVED_SUBDOMAINS = frozenset(
    {
        "api",
        "admin",
        "www",
        "app",
        "mail",
        "localhost",
    }
)


def validate_subdomain(value: str) -> None:
    """
    Enforce valid single DNS label format and reject reserved subdomains.

    Must match ^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$ and not be in RESERVED_SUBDOMAINS.
    """
    if not isinstance(value, str):
        raise ValidationError("Subdomain must be a string.")
    if not SUBDOMAIN_REGEX.match(value):
        raise ValidationError(
            "Subdomain must be a valid DNS label (lowercase alphanumeric and hyphens, 1-63 chars, no leading/trailing hyphens)."
        )
    if value.lower() in RESERVED_SUBDOMAINS:
        raise ValidationError(f"'{value}' is a reserved subdomain.")


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
    name = models.CharField(max_length=150)
    subdomain = models.CharField(
        max_length=63,
        unique=True,
        db_index=True,
        validators=[validate_subdomain],
    )
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

    def clean_fields(self, exclude=None):
        if self.subdomain and isinstance(self.subdomain, str):
            self.subdomain = self.subdomain.strip().lower()
        super().clean_fields(exclude=exclude)

    def clean(self):
        super().clean()
        if self.subdomain and isinstance(self.subdomain, str):
            self.subdomain = self.subdomain.strip().lower()

    def save(self, *args, **kwargs):
        if self.subdomain and isinstance(self.subdomain, str):
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
    chapa_merchant_id = models.CharField(max_length=100, null=True, blank=True)
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
        """
        Validate tenant context and auto-populate gym foreign key.

        Fails closed:
        - If tenant context is active and instance carries a mismatched gym, raises ValidationError.
        - If tenant context is active and instance has no gym, auto-assigns current_tenant.
        - If no tenant context is active and instance has no gym, raises ValidationError.
        """
        current_tenant = get_current_tenant()
        if current_tenant is not None:
            if self.gym_id and str(self.gym_id) != str(current_tenant.id):
                raise ValidationError(
                    "Cannot assign or modify record for a different tenant."
                )
            if not self.gym_id:
                self.gym = current_tenant
        else:
            if not getattr(self, "gym_id", None):
                raise ValidationError(
                    "Tenant context or explicit gym assignment is required to save a tenant-scoped record."
                )
        super().save(*args, **kwargs)
