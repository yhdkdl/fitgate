"""Tests for shared create_notification helper and Notification model."""

import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.notifications import create_notification
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestNotificationHelper:
    """Test suite for shared create_notification helper."""

    @pytest.fixture
    def setup_data(self):
        gym = GymTenant.objects.create(
            name="Apex Fitness", subdomain="apex", tls_confirmed_at=timezone.now()
        )
        user = User.objects.create_user(
            email="member@apex.test",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )
        super_admin = User.objects.create_superuser(
            email="admin@fitgate.test",
            password="SuperPassword123!",
        )
        return {"gym": gym, "user": user, "super_admin": super_admin}

    def test_create_notification_tenant_scoped(self, setup_data):
        user = setup_data["user"]
        gym = setup_data["gym"]

        notif = create_notification(
            recipient=user,
            notification_type="payment_confirmed",
            message="Your payment has been received.",
            gym=gym,
        )
        assert notif.id is not None
        assert notif.recipient == user
        assert notif.gym == gym
        assert notif.type == "payment_confirmed"
        assert notif.message == "Your payment has been received."
        assert notif.is_read is False

    def test_create_notification_infers_gym_from_recipient(self, setup_data):
        user = setup_data["user"]
        gym = setup_data["gym"]

        notif = create_notification(
            recipient=user,
            notification_type="membership_expiring",
            message="Your membership is expiring soon.",
        )
        assert notif.gym == gym

    def test_create_notification_platform_level(self, setup_data):
        admin = setup_data["super_admin"]

        notif = create_notification(
            recipient=admin,
            notification_type="system_alert",
            message="Platform-wide alert.",
            gym=None,
        )
        assert notif.gym is None
        assert notif.recipient == admin
