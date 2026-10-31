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
    photo_url = models.CharField(max_length=255, blank=True, default="")
    specialization = models.CharField(max_length=255, blank=True, null=True)
    max_clients = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
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


class FitnessProfile(TenantAwareModel):
    """
    Fitness profile entered exclusively by assigned trainer on the client's page.
    Owner/Manager can view/edit; Member has read-only visibility.
    SPEC §8:
    - member_id (PK+FK -> memberships.Member, CASCADE)
    - gym_id (FK -> tenants.GymTenant, CASCADE)
    - goal (fat_loss, muscle_gain, strength, endurance, general_fitness)
    - fitness_level (beginner, intermediate, advanced)
    - health_limitations (text, optional)
    - equipment_access (text, optional)
    - training_days_per_week (integer 2 to 6)
    - session_length_minutes (30, 45, 60, or 90)
    - dietary_notes (text, optional, max 1000 characters)
    - created_at, updated_at
    """

    GOAL_FAT_LOSS = "fat_loss"
    GOAL_MUSCLE_GAIN = "muscle_gain"
    GOAL_STRENGTH = "strength"
    GOAL_ENDURANCE = "endurance"
    GOAL_GENERAL_FITNESS = "general_fitness"
    GOAL_CHOICES = [
        (GOAL_FAT_LOSS, "Fat Loss"),
        (GOAL_MUSCLE_GAIN, "Muscle Gain"),
        (GOAL_STRENGTH, "Strength"),
        (GOAL_ENDURANCE, "Endurance"),
        (GOAL_GENERAL_FITNESS, "General Fitness"),
    ]

    LEVEL_BEGINNER = "beginner"
    LEVEL_INTERMEDIATE = "intermediate"
    LEVEL_ADVANCED = "advanced"
    LEVEL_CHOICES = [
        (LEVEL_BEGINNER, "Beginner"),
        (LEVEL_INTERMEDIATE, "Intermediate"),
        (LEVEL_ADVANCED, "Advanced"),
    ]

    SESSION_LENGTH_CHOICES = [
        (30, "30 minutes"),
        (45, "45 minutes"),
        (60, "60 minutes"),
        (90, "90 minutes"),
    ]

    member = models.OneToOneField(
        "memberships.Member",
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="fitness_profile",
    )
    goal = models.CharField(max_length=50, choices=GOAL_CHOICES)
    fitness_level = models.CharField(max_length=50, choices=LEVEL_CHOICES)
    health_limitations = models.JSONField(default=list, blank=True)
    other_limitations = models.CharField(max_length=200, blank=True, default="")
    equipment_access = models.JSONField(default=list, blank=True)
    other_equipment = models.CharField(max_length=200, blank=True, default="")
    training_days_per_week = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(2), MaxValueValidator(6)]
    )
    session_length_minutes = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(30), MaxValueValidator(90)]
    )
    dietary_notes = models.JSONField(default=list, blank=True)
    other_dietary = models.CharField(max_length=200, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def has_medical_caution(self) -> bool:
        from apps.trainers.constants import MEDICAL_CAUTION_CODES

        limits = set(self.health_limitations or [])
        return bool(limits.intersection(MEDICAL_CAUTION_CODES))

    class Meta:
        verbose_name = "Fitness Profile"
        verbose_name_plural = "Fitness Profiles"

    def __str__(self):
        return f"FitnessProfile({self.member.full_name} - {self.goal}, {self.fitness_level})"
