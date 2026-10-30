import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.tenants.models import TenantAwareModel


class Trainer(TenantAwareModel):
    """
    Trainer profile representing a trainer at a gym tenant.
    Links 1:1 with accounts.User (role=trainer).
    Carries capacity (max_clients) and optional specialization.
    Client count is derived from active assignments (ended_at IS NULL).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trainer_profile",
    )
    specialization = models.CharField(max_length=255, blank=True, null=True)
    max_clients = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(200)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__full_name", "user__email"]
        verbose_name = "Trainer"
        verbose_name_plural = "Trainers"

    def __str__(self):
        return f"{self.user.full_name or self.user.email} ({self.gym.name})"

    @property
    def client_count(self) -> int:
        """Derive current client count from active TrainerAssignment rows."""
        return TrainerAssignment.all_objects.filter(
            trainer_id=self.id,
            gym_id=self.gym_id,
            ended_at__isnull=True,
        ).count()


class TrainerAssignment(TenantAwareModel):
    """
    Assignment linking a gym member to a trainer.
    ended_at is NULL while the assignment is active; populated when closed.
    Enforces at DB level that a member can never have two open assignments simultaneously.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.ForeignKey(
        "memberships.Member",
        on_delete=models.CASCADE,
        related_name="trainer_assignments",
    )
    trainer = models.ForeignKey(
        Trainer,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trainer_assignments_made",
    )

    class Meta:
        ordering = ["-assigned_at"]
        verbose_name = "Trainer Assignment"
        verbose_name_plural = "Trainer Assignments"
        constraints = [
            models.UniqueConstraint(
                fields=["member"],
                condition=models.Q(ended_at__isnull=True),
                name="unique_active_assignment_per_member",
            )
        ]

    def __str__(self):
        return f"{self.member.full_name} -> {self.trainer.user.full_name or self.trainer.user.email}"
