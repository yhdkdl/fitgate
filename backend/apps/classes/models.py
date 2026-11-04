import uuid
from datetime import timedelta

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.classes.constants import (
    BOOKING_STATUS_BOOKED,
    BOOKING_STATUS_CHOICES,
    CLASS_DURATION_CHOICES,
    CLASS_TITLE_CHOICES,
    CLASS_TITLE_OTHER,
    SESSION_STATUS_CHOICES,
    SESSION_STATUS_SCHEDULED,
)
from apps.memberships.models import Member
from apps.tenants.models import TenantAwareModel
from apps.trainers.models import Trainer


class ClassSession(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=50, choices=CLASS_TITLE_CHOICES)
    other_title = models.CharField(max_length=50, blank=True, default="")
    trainer = models.ForeignKey(
        Trainer,
        on_delete=models.CASCADE,
        related_name="class_sessions",
    )
    start_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(
        choices=CLASS_DURATION_CHOICES,
        default=60,
    )
    end_time = models.DateTimeField()
    capacity = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
    )
    status = models.CharField(
        max_length=20,
        choices=SESSION_STATUS_CHOICES,
        default=SESSION_STATUS_SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["gym", "start_time", "status"]),
            models.Index(fields=["trainer", "start_time", "end_time"]),
        ]

    def __str__(self):
        return f"{self.display_title} ({self.start_time.strftime('%Y-%m-%d %H:%M')})"

    def clean(self):
        super().clean()
        if self.start_time and self.duration_minutes:
            self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)

    def save(self, *args, **kwargs):
        if self.start_time and self.duration_minutes and not self.end_time:
            self.end_time = self.start_time + timedelta(minutes=self.duration_minutes)
        super().save(*args, **kwargs)

    @property
    def display_title(self) -> str:
        if self.title == CLASS_TITLE_OTHER:
            return self.other_title.strip() if self.other_title else "Other"
        return dict(CLASS_TITLE_CHOICES).get(self.title, self.title)

    @property
    def booked_count(self) -> int:
        return ClassBooking.all_objects.filter(
            session=self,
            status=BOOKING_STATUS_BOOKED,
        ).count()

    @property
    def spots_remaining(self) -> int:
        return max(0, self.capacity - self.booked_count)

    @property
    def is_full(self) -> bool:
        return self.spots_remaining <= 0

    @property
    def is_past(self) -> bool:
        return self.start_time <= timezone.now()


class ClassBooking(TenantAwareModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ClassSession,
        on_delete=models.CASCADE,
        related_name="bookings",
    )
    member = models.ForeignKey(
        Member,
        on_delete=models.CASCADE,
        related_name="class_bookings",
    )
    booked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booked_class_members",
    )
    status = models.CharField(
        max_length=20,
        choices=BOOKING_STATUS_CHOICES,
        default=BOOKING_STATUS_BOOKED,
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_class_bookings",
    )
    attended = models.BooleanField(default=False)
    marked_at = models.DateTimeField(null=True, blank=True)
    marked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="marked_class_attendances",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-session__start_time", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["session", "member"],
                condition=models.Q(status=BOOKING_STATUS_BOOKED),
                name="unique_active_class_booking",
            )
        ]
        indexes = [
            models.Index(fields=["gym", "member", "status"]),
            models.Index(fields=["session", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.member.full_name} -> {self.session.display_title} ({self.status})"
        )
