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

    @property
    def active_subscription(self) -> Optional["MemberSubscription"]:
        from apps.memberships.models import MemberSubscription

        return (
            MemberSubscription.all_objects.filter(
                gym=self.gym, member=self, status=self.STATUS_ACTIVE
            )
            .order_by("-end_date")
            .first()
        )

    def get_subscription_period(self):
        """
        Return (start_date, end_date) for attendance calendar calculation.
        Uses active subscription if present, otherwise defaults to [joined_at.date(), joined_at.date() + 30 days].
        """

        from apps.memberships.models import MemberSubscription

        sub = (
            self.active_subscription
            or MemberSubscription.all_objects.filter(gym=self.gym, member=self)
            .order_by("-end_date")
            .first()
        )
        if sub:
            return sub.start_date, sub.end_date
        return None, None


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
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_body_metrics",
    )
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


class MemberSubscription(TenantAwareModel):
    """
    Member subscription tracking plan validity, freeze periods, and expiry.

    SPEC §8:
    - id (UUID PK)
    - member (FK -> Member, CASCADE)
    - gym_id (inherited from TenantAwareModel)
    - plan_id (nullable UUID)
    - start_date (DateField)
    - end_date (DateField)
    - status (pending/active/frozen/suspended/expired)
    - freeze_start_date (DateField, nullable)
    - frozen_days_total (PositiveIntegerField, default 0)
    """

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_FROZEN = "frozen"
    STATUS_SUSPENDED = "suspended"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_FROZEN, "Frozen"),
        (STATUS_SUSPENDED, "Suspended"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )
    plan_id = models.UUIDField(null=True, blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    freeze_start_date = models.DateField(null=True, blank=True)
    frozen_days_total = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Member Subscription"
        verbose_name_plural = "Member Subscriptions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Subscription({self.member.full_name}: {self.start_date} to {self.end_date} [{self.status}])"
