"""User model for FitGate platform."""

import uuid

from django.contrib.auth.base_user import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.accounts.managers import AllUserManager, UserManager
from apps.tenants.models import GymTenant, PlatformTenantAwareModel


class User(AbstractBaseUser, PlatformTenantAwareModel):
    """
    Custom User model for the FitGate platform.

    - Email is unique case-insensitively and globally across all gyms.
    - gym_id is null if and only if role is super_admin.
    - is_staff and is_superuser are derived properties (super_admin + is_active),
      not stored database columns.
    - password_changed_at has microsecond precision and is updated directly in set_password().

    Note on Super Admin protection:
    The last active Super Admin cannot be deactivated or deleted via model save() or delete().
    Direct queryset operations like User.objects.update() or User.objects.filter().delete()
    bypass model hooks and will not enforce this protection.
    """

    ROLE_SUPER_ADMIN = "super_admin"
    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_TRAINER = "trainer"
    ROLE_RECEPTION = "reception"
    ROLE_MEMBER = "member"

    ROLE_CHOICES = [
        (ROLE_SUPER_ADMIN, "Super Admin"),
        (ROLE_OWNER, "Owner"),
        (ROLE_MANAGER, "Manager"),
        (ROLE_TRAINER, "Trainer"),
        (ROLE_RECEPTION, "Reception"),
        (ROLE_MEMBER, "Member"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(max_length=255, unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    gym = models.ForeignKey(
        GymTenant,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    failed_login_count = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)

    objects = UserManager()
    all_objects = AllUserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_lower_email_unique",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(role="super_admin", gym__isnull=True)
                    | (~models.Q(role="super_admin") & models.Q(gym__isnull=False))
                ),
                name="accounts_user_gym_null_iff_super_admin",
            ),
        ]

    def __str__(self):
        gym_name = self.gym.name if self.gym else "Platform"
        return f"{self.email} ({self.role} @ {gym_name})"

    def clean(self):
        super().clean()
        if self.email:
            self.email = self.email.strip().lower()
        if self.role == self.ROLE_SUPER_ADMIN and self.gym_id is not None:
            raise ValidationError({"gym": "Super Admin must not have a gym assigned."})
        if self.role != self.ROLE_SUPER_ADMIN and not self.gym_id:
            raise ValidationError(
                {"gym": "Non-super-admin users must belong to a gym."}
            )

    def set_password(self, raw_password):
        """Set user password and update password_changed_at with microsecond precision."""
        super().set_password(raw_password)
        self.password_changed_at = timezone.now()

    def save(self, *args, **kwargs):
        """Normalize email, ensure password_changed_at, and protect last active Super Admin."""
        if self.email:
            self.email = self.email.strip().lower()
        if not self.password_changed_at:
            self.password_changed_at = timezone.now()

        # Prevent deactivating or demoting the last active Super Admin
        if self.pk:
            orig = User.all_objects.filter(pk=self.pk).first()
            if orig and orig.role == self.ROLE_SUPER_ADMIN and orig.is_active:
                if self.role != self.ROLE_SUPER_ADMIN or not self.is_active:
                    other_active_superadmins = (
                        User.all_objects.filter(
                            role=self.ROLE_SUPER_ADMIN, is_active=True
                        )
                        .exclude(pk=self.pk)
                        .exists()
                    )
                    if not other_active_superadmins:
                        raise ValidationError(
                            "Cannot deactivate or demote the last active Super Admin."
                        )

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Prevent deleting the last active Super Admin."""
        if self.role == self.ROLE_SUPER_ADMIN and self.is_active:
            other_active_superadmins = (
                User.all_objects.filter(role=self.ROLE_SUPER_ADMIN, is_active=True)
                .exclude(pk=self.pk)
                .exists()
            )
            if not other_active_superadmins:
                raise ValidationError("Cannot delete the last active Super Admin.")
        return super().delete(*args, **kwargs)

    @property
    def is_staff(self) -> bool:
        """Staff access is dynamically derived: Super Admin and active."""
        return self.role == self.ROLE_SUPER_ADMIN and self.is_active

    @property
    def is_superuser(self) -> bool:
        """Superuser access is dynamically derived: Super Admin and active."""
        return self.role == self.ROLE_SUPER_ADMIN and self.is_active

    def has_perm(self, perm, obj=None) -> bool:
        """Only active Super Admins have permissions."""
        return self.is_superuser

    def has_module_perms(self, app_label) -> bool:
        """Only active Super Admins have module permissions."""
        return self.is_superuser
