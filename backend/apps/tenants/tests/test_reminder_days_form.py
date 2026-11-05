"""Tests for reminder days two-number form validation and role enforcement."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def gym():
    tenant = GymTenant.objects.create(
        name="Reminder Test Gym",
        subdomain="remindertest",
        tier="growth",
        tls_confirmed_at=timezone.now(),
    )
    if not hasattr(tenant, "config"):
        GymConfig.objects.create(gym=tenant)
    return tenant


@pytest.fixture
def other_gym():
    tenant = GymTenant.objects.create(
        name="Other Reminder Gym",
        subdomain="otherremindertest",
        tier="growth",
        tls_confirmed_at=timezone.now(),
    )
    if not hasattr(tenant, "config"):
        GymConfig.objects.create(gym=tenant)
    return tenant


@pytest.fixture
def owner_user(gym):
    return User.objects.create_user(
        email="owner@remindertest.com",
        password="Password123!",
        role=User.ROLE_OWNER,
        gym=gym,
    )


@pytest.fixture
def other_owner_user(other_gym):
    return User.objects.create_user(
        email="owner@otherremindertest.com",
        password="Password123!",
        role=User.ROLE_OWNER,
        gym=other_gym,
    )


@pytest.fixture
def manager_user(gym):
    return User.objects.create_user(
        email="manager@remindertest.com",
        password="Password123!",
        role=User.ROLE_MANAGER,
        gym=gym,
    )


@pytest.fixture
def super_admin_user():
    return User.objects.create_superuser(
        email="admin@fitgate.org",
        password="Password123!",
    )


def auth_client(user, host="remindertest.localhost"):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
class TestReminderDaysServerValidation:
    """Server-side validation for member and subscription reminder days."""

    def test_owner_member_reminder_days_valid_two_numbers(self, owner_user, gym):
        client = auth_client(owner_user)
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [7, 2]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 200
        gym.config.refresh_from_db()
        assert gym.config.member_reminder_days == [7, 2]

    def test_owner_member_reminder_days_valid_single_number(self, owner_user, gym):
        client = auth_client(owner_user)
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [14]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 200
        gym.config.refresh_from_db()
        assert gym.config.member_reminder_days == [14]

    def test_owner_first_reminder_out_of_range(self, owner_user, gym):
        client = auth_client(owner_user)
        # 0 is below allowed 1 to 90
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [0, 2]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "First reminder must be a whole number from 1 to 90." in str(resp.data)

        # 91 is above allowed 1 to 90
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [91, 2]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "First reminder must be a whole number from 1 to 90." in str(resp.data)

    def test_owner_second_reminder_not_smaller_than_first(self, owner_user, gym):
        client = auth_client(owner_user)
        # Equal
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [7, 7]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "Second reminder must be smaller than the first reminder." in str(
            resp.data
        )

        # Larger
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [5, 10]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "Second reminder must be smaller than the first reminder." in str(
            resp.data
        )

    def test_owner_empty_or_more_than_two_reminders(self, owner_user, gym):
        client = auth_client(owner_user)
        # Empty
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": []},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "First reminder must be a whole number from 1 to 90." in str(resp.data)

        # 3 numbers
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [14, 7, 2]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 400
        assert "At most two reminders are allowed." in str(resp.data)


@pytest.mark.django_db
class TestReminderDaysRoleRefusals:
    """Role-based access refusals for reminder days editing."""

    def test_owner_refused_to_edit_subscription_reminder_days(self, owner_user, gym):
        """Owner attempting to edit subscription reminder days is refused 403."""
        client = auth_client(owner_user)
        resp = client.patch(
            "/api/gym/settings/",
            {"subscription_reminder_days": [14, 7]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 403
        assert "Only Super Admin can modify gym entitlements" in str(resp.data)

    def test_manager_refused_to_edit_gym_settings(self, manager_user, gym):
        """Manager attempting to edit gym settings is refused 403."""
        client = auth_client(manager_user)
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [7, 2]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_owner_cannot_edit_other_gym_settings(self, other_owner_user, gym):
        """Owner of other gym attempting to edit this gym is refused 403."""
        client = auth_client(other_owner_user, host=f"{gym.subdomain}.localhost")
        resp = client.patch(
            "/api/gym/settings/",
            {"member_reminder_days": [10, 3]},
            format="json",
            HTTP_HOST=f"{gym.subdomain}.localhost",
        )
        assert resp.status_code in (403, 401)

    def test_super_admin_can_edit_subscription_reminder_days(
        self, super_admin_user, gym
    ):
        """Super Admin can edit subscription reminder days via platform config endpoint."""
        client = auth_client(super_admin_user, host="localhost")
        resp = client.patch(
            f"/api/platform/gyms/{gym.id}/config/",
            {"subscription_reminder_days": [21, 10]},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        gym.config.refresh_from_db()
        assert gym.config.subscription_reminder_days == [21, 10]

    def test_super_admin_validation_rules_enforced(self, super_admin_user, gym):
        """Super Admin must also obey the two-number rules for subscription reminder days."""
        client = auth_client(super_admin_user, host="localhost")
        # Second >= first
        resp = client.patch(
            f"/api/platform/gyms/{gym.id}/config/",
            {"subscription_reminder_days": [10, 10]},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 400
        assert "Second reminder must be smaller than the first reminder." in str(
            resp.data
        )

        # First out of range
        resp = client.patch(
            f"/api/platform/gyms/{gym.id}/config/",
            {"subscription_reminder_days": [100, 5]},
            format="json",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 400
        assert "First reminder must be a whole number from 1 to 90." in str(resp.data)
