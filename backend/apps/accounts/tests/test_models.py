"""Tests for custom User model, constraints, and managers."""

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError

from apps.accounts.models import User
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestUserModelAndConstraints:
    """Tests covering User model schema constraints, managers, and properties."""

    @pytest.fixture
    def sample_gyms(self):
        """Create sample gyms for multi-tenant user testing."""
        gym_1 = GymTenant.objects.create(name="First Gym", subdomain="firstgym")
        gym_2 = GymTenant.objects.create(name="Second Gym", subdomain="secondgym")
        return gym_1, gym_2

    def test_email_normalized_to_lowercase(self, sample_gyms):
        """Creating a user with uppercase/mixed case email normalizes it to lowercase."""
        gym_1, _ = sample_gyms
        user = User.objects.create_user(
            email="TEST.USER@Example.COM",
            password="SecurePassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_1,
        )
        assert user.email == "test.user@example.com"

    def test_email_globally_case_insensitively_unique_across_gyms(self, sample_gyms):
        """
        Database UniqueConstraint on Lower(email) guarantees the same email
        cannot exist twice globally across different gyms, regardless of case.
        """
        gym_1, gym_2 = sample_gyms

        User.objects.create_user(
            email="shared@example.com",
            password="Password123!",
            role=User.ROLE_MEMBER,
            gym=gym_1,
        )

        # Attempt to create duplicate email in different case in second gym
        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="SHARED@EXAMPLE.COM",
                password="OtherPassword123!",
                role=User.ROLE_MEMBER,
                gym=gym_2,
            )

    def test_email_globally_unique_between_gym_user_and_super_admin(self, sample_gyms):
        """The same email cannot exist for both a gym user and a platform Super Admin."""
        gym_1, _ = sample_gyms

        User.objects.create_superuser(
            email="admin@fitgate.org",
            password="SuperPassword123!",
        )

        with pytest.raises(IntegrityError):
            User.objects.create_user(
                email="ADMIN@FITGATE.ORG",
                password="Password123!",
                role=User.ROLE_OWNER,
                gym=gym_1,
            )

    def test_check_constraint_super_admin_must_have_null_gym(self, sample_gyms):
        """Database CheckConstraint prevents a Super Admin from having a gym foreign key."""
        gym_1, _ = sample_gyms

        with pytest.raises(IntegrityError):
            User.all_objects.create(
                email="bad_admin@fitgate.org",
                role=User.ROLE_SUPER_ADMIN,
                gym=gym_1,
            )

    def test_check_constraint_gym_user_must_have_gym(self):
        """Database CheckConstraint prevents a non-super-admin user from having a null gym."""
        with pytest.raises(IntegrityError):
            User.all_objects.create(
                email="bad_owner@example.com",
                role=User.ROLE_OWNER,
                gym=None,
            )

    def test_password_changed_at_set_inside_set_password_with_microsecond_precision(
        self, sample_gyms
    ):
        """
        User.set_password() directly sets password_changed_at with microsecond precision.
        """
        gym_1, _ = sample_gyms
        user = User.objects.create_user(
            email="user@firstgym.com",
            password="InitialPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_1,
        )
        initial_pca = user.password_changed_at
        assert initial_pca is not None
        assert initial_pca.microsecond >= 0

        # Change password via set_password directly
        user.set_password("NewPassword123!")
        user.save()

        user.refresh_from_db()
        assert user.password_changed_at > initial_pca

    def test_is_staff_and_is_superuser_properties(self, sample_gyms):
        """
        is_staff and is_superuser are derived properties (role == super_admin and is_active),
        not database columns. has_perm and has_module_perms only return True for active super admins.
        """
        gym_1, _ = sample_gyms

        super_admin = User.objects.create_superuser(
            email="super@fitgate.org",
            password="SuperPassword123!",
        )
        owner = User.objects.create_user(
            email="owner@firstgym.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_1,
        )

        assert super_admin.is_staff is True
        assert super_admin.is_superuser is True
        assert super_admin.has_perm("any_perm") is True
        assert super_admin.has_module_perms("any_app") is True

        assert owner.is_staff is False
        assert owner.is_superuser is False
        assert owner.has_perm("any_perm") is False
        assert owner.has_module_perms("any_app") is False

        # Deactivated Super Admin loses staff/superuser access
        super_admin.is_active = False
        assert super_admin.is_staff is False
        assert super_admin.is_superuser is False
        assert super_admin.has_perm("any_perm") is False

    def test_createsuperuser_management_command(self):
        """
        Django's createsuperuser creates a valid Super Admin obeying all constraints:
        normalized lowercase email, gym=None, and microsecond password_changed_at.
        """
        call_command(
            "createsuperuser",
            "--noinput",
            email="CLI.SUPERADMIN@FitGate.ORG",
        )

        admin_user = User.all_objects.get(email="cli.superadmin@fitgate.org")
        assert admin_user.role == User.ROLE_SUPER_ADMIN
        assert admin_user.gym is None
        assert admin_user.is_staff is True
        assert admin_user.is_superuser is True
        assert admin_user.password_changed_at is not None

    def test_last_active_super_admin_cannot_be_deactivated_or_deleted(self):
        """
        Enforce in save() and delete() that the last active Super Admin cannot be deactivated or deleted.
        """
        admin = User.objects.create_superuser(
            email="sole.admin@fitgate.org",
            password="AdminPassword123!",
        )

        # Attempt to deactivate via save()
        admin.is_active = False
        with pytest.raises(
            ValidationError,
            match="Cannot deactivate or demote the last active Super Admin",
        ):
            admin.save()

        # Attempt to delete via delete()
        admin.is_active = True
        with pytest.raises(
            ValidationError, match="Cannot delete the last active Super Admin"
        ):
            admin.delete()

        # When a second active Super Admin exists, the first can be deactivated and deleted
        second_admin = User.objects.create_superuser(
            email="second.admin@fitgate.org",
            password="AdminPassword123!",
        )

        admin.is_active = False
        admin.save()  # Now succeeds
        assert admin.is_active is False

        # Can delete the inactive one
        admin.delete()
        assert not User.all_objects.filter(email="sole.admin@fitgate.org").exists()

        # Second admin is now sole active admin, cannot be deleted
        with pytest.raises(
            ValidationError, match="Cannot delete the last active Super Admin"
        ):
            second_admin.delete()

    def test_queryset_update_and_delete_bypass_super_admin_protection(self):
        """
        Document and verify that direct queryset operations like update() and delete()
        bypass model hooks and will bypass the last-admin protection.
        """
        admin = User.objects.create_superuser(
            email="bypass.admin@fitgate.org",
            password="AdminPassword123!",
        )

        # Direct queryset update bypasses model save()
        User.all_objects.filter(pk=admin.pk).update(is_active=False)
        admin.refresh_from_db()
        assert admin.is_active is False

        # Direct queryset delete bypasses model delete()
        User.all_objects.filter(pk=admin.pk).delete()
        assert not User.all_objects.filter(pk=admin.pk).exists()
