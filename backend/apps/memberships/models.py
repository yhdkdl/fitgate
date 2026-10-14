"""Data models for member profiles, body composition metrics, and waiver tracking."""

import uuid
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.memberships.calculations import calculate_bmi, calculate_us_navy_body_fat
from apps.tenants.models import TenantAwareModel


class Member(TenantAwareModel):
    """
    Member profile representing an enrolled individual at a gym tenant.

    Links 1:1 with accounts.User (role=member).
    Captures contact info, emergency contact, date of birth, gender,
    profile photo key, membership status, and required health waiver timestamp.
    """

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_FROZEN = "frozen"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_FROZEN, "Frozen"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    GENDER_MALE = "male"
    GENDER_FEMALE = "female"
    GENDER_OTHER = "other"
    GENDER_PREFER_NOT_TO_SAY = "prefer_not_to_say"

    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
        (GENDER_OTHER, "Other"),
        (GENDER_PREFER_NOT_TO_SAY, "Prefer not to say"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="member_profile",
    )
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(
        max_length=20, choices=GENDER_CHOICES, blank=True, default=""
    )
    emergency_contact = models.CharField(max_length=255, blank=True, default="")
    referral_source = models.CharField(max_length=100, blank=True, default="")
    photo_url = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    waiver_accepted_at = models.DateTimeField()

    class Meta:
        verbose_name = "Member"
        verbose_name_plural = "Members"
        ordering = ["-joined_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "phone"],
                name="memberships_member_gym_phone_unique",
            )
        ]

    def __str__(self) -> str:
        gym_name = self.gym.name if self.gym_id else "No Gym"
        return f"{self.full_name} ({self.phone}) @ {gym_name}"

    @property
    def latest_metrics(self) -> Optional["BodyMetrics"]:
        return self.body_metrics.order_by("-recorded_at").first()


class BodyMetrics(TenantAwareModel):
    """
    Body composition measurements recorded for a member.

    Tracks weight (kg), height (cm), and flexible circumference measurements
    (e.g. neck_cm, waist_cm, hip_cm) in jsonb.
    BMI and US Navy circumference method body fat percentage are calculated
    dynamically on read as labeled estimates.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="body_metrics",
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    height_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    measurements = models.JSONField(default=dict, blank=True)
    recorded_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Body Metrics"
        verbose_name_plural = "Body Metrics"
        ordering = ["-recorded_at"]

    def __str__(self) -> str:
        return f"Metrics for {self.member.full_name} at {self.recorded_at.isoformat()}"

    @property
    def estimated_bmi(self) -> Optional[float]:
        return calculate_bmi(self.weight_kg, self.height_cm)

    @property
    def estimated_body_fat_percentage(self) -> Optional[float]:
        gender = self.member.gender if self.member_id else None
        return calculate_us_navy_body_fat(gender, self.height_cm, self.measurements)
