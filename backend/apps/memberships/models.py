"""Data models for member profiles, body composition metrics, and waiver tracking."""

import uuid
from typing import Optional

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.memberships.calculations import (
    calculate_bmi,
    calculate_lean_body_mass,
    calculate_us_navy_body_fat,
    calculate_waist_to_hip_ratio,
)
from apps.tenants.managers import TenantManager, TenantQuerySet
from apps.tenants.models import TenantAwareModel


class MemberQuerySet(TenantQuerySet):
    """Tenant-scoped queryset for Member that blocks direct status modifications."""

    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValueError(
                "Direct modification of Member.status via update() is prohibited. "
                "Member.status is derived from MemberSubscription and must only be updated via update_member_status()."
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        if "status" in fields:
            raise ValueError(
                "Direct modification of Member.status via bulk_update() is prohibited. "
                "Member.status is derived from MemberSubscription and must only be updated via update_member_status()."
            )
        return super().bulk_update(objs, fields, *args, **kwargs)


class MemberManager(TenantManager.from_queryset(MemberQuerySet)):
    pass


class MemberAllObjectsQuerySet(models.QuerySet):
    """Unscoped queryset for Member that blocks direct status modifications."""

    def update(self, **kwargs):
        if "status" in kwargs:
            raise ValueError(
                "Direct modification of Member.status via update() is prohibited. "
                "Member.status is derived from MemberSubscription and must only be updated via update_member_status()."
            )
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, *args, **kwargs):
        if "status" in fields:
            raise ValueError(
                "Direct modification of Member.status via bulk_update() is prohibited. "
                "Member.status is derived from MemberSubscription and must only be updated via update_member_status()."
            )
        return super().bulk_update(objs, fields, *args, **kwargs)


class MemberAllObjectsManager(models.Manager.from_queryset(MemberAllObjectsQuerySet)):
    pass


class Member(TenantAwareModel):
    """
    Member profile representing an enrolled individual at a gym tenant.

    Links 1:1 with accounts.User (role=member).
    Captures contact info, emergency contact, date of birth, gender,
    profile photo key, membership status, and required health waiver timestamp.
    """

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_FROZEN = "frozen"
    STATUS_SUSPENDED = "suspended"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_EXPIRED, "Expired"),
        (STATUS_FROZEN, "Frozen"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    GENDER_MALE = "male"
    GENDER_FEMALE = "female"

    GENDER_CHOICES = [
        (GENDER_MALE, "Male"),
        (GENDER_FEMALE, "Female"),
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
        default=STATUS_PENDING,
        db_index=True,
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    waiver_accepted_at = models.DateTimeField()

    objects = MemberManager()
    all_objects = MemberAllObjectsManager()

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

    def save(self, *args, **kwargs):
        if self.pk:
            orig = Member.all_objects.filter(pk=self.pk).values("status").first()
            if orig and orig["status"] != self.status:
                if not getattr(self, "_status_update_allowed", False):
                    raise ValueError(
                        f"Direct modification of Member.status from '{orig['status']}' to '{self.status}' is prohibited. "
                        "Member.status is derived from MemberSubscription and must only be updated via update_member_status()."
                    )
        super().save(*args, **kwargs)

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


class MembershipPlan(TenantAwareModel):
    """
    Membership plan configured by gym Owner/Manager.

    SPEC §8 / Sprint 10:
    - id (UUID PK)
    - gym_id (inherited from TenantAwareModel)
    - name (CharField 100)
    - description (TextField blank)
    - duration_value (PositiveIntegerField)
    - duration_unit (days/months)
    - price_etb (DecimalField)
    - trainer_inclusive (BooleanField, default False)
    - is_active (BooleanField, default True)
    """

    DURATION_DAYS = "days"
    DURATION_MONTHS = "months"
    DURATION_UNIT_CHOICES = [
        (DURATION_DAYS, "Days"),
        (DURATION_MONTHS, "Months"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    duration_value = models.PositiveIntegerField()
    duration_unit = models.CharField(
        max_length=10,
        choices=DURATION_UNIT_CHOICES,
        default=DURATION_MONTHS,
    )
    price_etb = models.DecimalField(max_digits=10, decimal_places=2)
    trainer_inclusive = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membership Plan"
        verbose_name_plural = "Membership Plans"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["gym", "name"],
                name="membershipplan_gym_name_unique",
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.duration_value} {self.duration_unit} - {self.price_etb} ETB)"


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

    @property
    def waist_to_hip_ratio(self) -> Optional[float]:
        return calculate_waist_to_hip_ratio(self.measurements)

    @property
    def lean_body_mass(self) -> Optional[float]:
        bf = None
        if self.measurements and isinstance(self.measurements, dict):
            bf = self.measurements.get("body_fat_percentage")
        if bf is None:
            bf = self.estimated_body_fat_percentage
        return calculate_lean_body_mass(self.weight_kg, bf)

    @property
    def lean_body_mass_label(self) -> str:
        if (
            self.measurements
            and isinstance(self.measurements, dict)
            and self.measurements.get("body_fat_percentage") is not None
        ):
            return "measured"
        if self.estimated_body_fat_percentage is not None:
            return "estimate"
        return "—"


class MemberSubscription(TenantAwareModel):
    """
    Member subscription tracking plan validity, freeze periods, and expiry.

    SPEC §8:
    - id (UUID PK)
    - member (FK -> Member, CASCADE)
    - gym_id (inherited from TenantAwareModel)
    - plan (FK -> MembershipPlan, PROTECT, nullable)
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
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subscriptions",
        db_column="plan_id",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    freeze_start_date = models.DateField(null=True, blank=True)
    frozen_days_total = models.PositiveIntegerField(default=0)
    reminder_sent_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Member Subscription"
        verbose_name_plural = "Member Subscriptions"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Subscription({self.member.full_name}: {self.start_date} to {self.end_date} [{self.status}])"


class MemberFreeze(TenantAwareModel):
    """
    Member membership freeze request and approval workflow record.
    Tracks freeze request date range, reason, review decision, and whether extension has been applied.
    """

    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_COMPLETED = "completed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_COMPLETED, "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="freeze_requests",
    )
    subscription = models.ForeignKey(
        MemberSubscription,
        on_delete=models.CASCADE,
        related_name="freeze_requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    days = models.PositiveIntegerField()
    reason = models.CharField(max_length=500)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_freezes",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=500, blank=True, default="")
    extension_applied = models.BooleanField(default=False)
    unfrozen_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Member Freeze"
        verbose_name_plural = "Member Freezes"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Freeze({self.member.full_name}: {self.days} days [{self.status}])"
