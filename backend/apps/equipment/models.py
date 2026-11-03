import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.validators import (
    validate_equipment_category,
    validate_equipment_min_quantity,
    validate_equipment_name,
    validate_equipment_purchase_date,
    validate_equipment_quantity,
)
from apps.equipment.constants import (
    CONDITION_CHOICES,
    CONDITION_GOOD,
    CONDITION_NEEDS_MAINTENANCE,
    CONDITION_OUT_OF_SERVICE,
    CONDITION_UNDER_MAINTENANCE,
    EQUIPMENT_CATEGORY_CHOICES,
    ISSUE_REASON_CHOICES,
)
from apps.tenants.models import TenantAwareModel


class Equipment(TenantAwareModel):
    CONDITION_GOOD = CONDITION_GOOD
    CONDITION_NEEDS_MAINTENANCE = CONDITION_NEEDS_MAINTENANCE
    CONDITION_UNDER_MAINTENANCE = CONDITION_UNDER_MAINTENANCE
    CONDITION_OUT_OF_SERVICE = CONDITION_OUT_OF_SERVICE

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    branch_id = models.UUIDField(null=True, blank=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=EQUIPMENT_CATEGORY_CHOICES)
    serial_number = models.CharField(max_length=100, blank=True, default="")
    quantity = models.PositiveIntegerField(default=1)
    min_qty_threshold = models.PositiveIntegerField(null=True, blank=True)
    condition = models.CharField(
        max_length=30,
        choices=CONDITION_CHOICES,
        default=CONDITION_GOOD,
    )
    purchase_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["gym", "condition"]),
            models.Index(fields=["gym", "category"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "serial_number"],
                condition=~models.Q(serial_number=""),
                name="unique_equipment_serial_per_gym",
            )
        ]

    def clean(self):
        super().clean()
        self.name = validate_equipment_name(self.name)
        self.category = validate_equipment_category(self.category)
        self.quantity = validate_equipment_quantity(self.quantity)
        self.min_qty_threshold = validate_equipment_min_quantity(self.min_qty_threshold)
        self.purchase_date = validate_equipment_purchase_date(self.purchase_date)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_low_quantity(self) -> bool:
        if self.min_qty_threshold is not None:
            return self.quantity <= self.min_qty_threshold
        return False

    def __str__(self):
        return f"{self.name} ({self.get_condition_display()})"


class MaintenanceLog(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="maintenance_logs",
    )
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_maintenance_logs",
    )
    issue_reason = models.CharField(max_length=50, choices=ISSUE_REASON_CHOICES)
    other_details = models.CharField(max_length=200, blank=True, default="")
    reported_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_maintenance_logs",
    )
    resolution_notes = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reported_at"]

    def __str__(self):
        return (
            f"Log for {self.equipment.name} ({self.issue_reason}) on {self.reported_at}"
        )
