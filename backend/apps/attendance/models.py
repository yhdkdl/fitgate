"""Data models for attendance tracking and QR check-in."""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.memberships.models import Member
from apps.tenants.models import TenantAwareModel


class QRToken(TenantAwareModel):
    """
    Issued asymmetric JWT QR token metadata for offline/online scan verification.

    Tracks single-use consumption and expiration window (90s).
    SPEC §8:
    - id (UUID PK)
    - gym_id (inherited from TenantAwareModel)
    - member_id (FK -> Member, CASCADE)
    - token_hash (CharField 64, SHA-256 of the JWT)
    - issued_at (DateTimeField)
    - expires_at (DateTimeField)
    - is_active (BooleanField, default True)
    - used_at (DateTimeField, nullable)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="qr_tokens",
    )
    token_hash = models.CharField(max_length=64, db_index=True)
    issued_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-issued_at"]
        verbose_name = "QR Token"
        verbose_name_plural = "QR Tokens"

    def __str__(self):
        return f"QRToken({self.member.full_name} - active={self.is_active})"


class Attendance(TenantAwareModel):
    """
    Attendance records for physical member check-ins.

    Written only on actual check-in (absence is derived).
    SPEC §8:
    - id (UUID PK)
    - gym_id (inherited from TenantAwareModel)
    - member_id (FK -> Member, CASCADE)
    - branch_id (UUIDField, nullable)
    - date (DateField, db_index=True)
    - status (CharField 20, default "checked_in")
    - checked_in_at (DateTimeField)
    - is_override (BooleanField, default False)
    - override_reason (TextField, blank=True)
    - recorded_by (FK -> User, nullable, SET_NULL)
    """

    STATUS_CHECKED_IN = "checked_in"

    STATUS_CHOICES = [
        (STATUS_CHECKED_IN, "Checked In"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="attendances",
    )
    branch_id = models.UUIDField(null=True, blank=True)
    date = models.DateField(default=timezone.localdate, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_CHECKED_IN,
    )
    checked_in_at = models.DateTimeField(default=timezone.now)
    is_override = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendances",
    )

    class Meta:
        ordering = ["-checked_in_at"]
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "member", "date"],
                name="attendance_gym_member_date_unique",
            )
        ]

    def __str__(self):
        return f"Attendance({self.member.full_name} on {self.date})"
