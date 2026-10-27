import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import Notification, User
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


@pytest.mark.django_db
class TestNotificationAPI:
    """Test suite for Notification Center API endpoints and access controls."""

    def setup_method(self):
        self.client = APIClient()

    def test_user_sees_only_own_notifications_unread_first(self, db):
        gym = GymTenant.objects.create(
            name="Alpha Gym", subdomain="alpha-notif", tls_confirmed_at=timezone.now()
        )
        user_1 = User.objects.create_user(
            email="u1@alpha.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )
        user_2 = User.objects.create_user(
            email="u2@alpha.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )

        # Create notifications for user 1: 1 read, 1 unread
        create_notification(
            recipient=user_1,
            notification_type="info",
            message="Older Read Message",
            gym=gym,
        )
        n_read = Notification.all_objects.filter(recipient=user_1).first()
        n_read.is_read = True
        n_read.save(update_fields=["is_read"])

        create_notification(
            recipient=user_1,
            notification_type="alert",
            message="Newer Unread Message",
            gym=gym,
        )

        # Create notification for user 2
        create_notification(
            recipient=user_2,
            notification_type="promo",
            message="User 2 Secret Message",
            gym=gym,
        )

        self.client.force_authenticate(user=user_1)
        resp = self.client.get("/api/notifications/", HTTP_HOST="alpha-notif.localhost")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()

        assert data["unread_count"] == 1
        assert len(data["results"]) == 2
        # Unread first!
        assert data["results"][0]["message"] == "Newer Unread Message"
        assert data["results"][0]["is_read"] is False
        assert data["results"][1]["message"] == "Older Read Message"
        assert data["results"][1]["is_read"] is True

        # User 2 message never appears for User 1
        messages = [r["message"] for r in data["results"]]
        assert "User 2 Secret Message" not in messages

    def test_mark_read_affects_only_own_notification(self, db):
        gym = GymTenant.objects.create(
            name="Beta Gym", subdomain="beta-notif", tls_confirmed_at=timezone.now()
        )
        user_1 = User.objects.create_user(
            email="u1@beta.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )
        user_2 = User.objects.create_user(
            email="u2@beta.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )

        n1 = create_notification(
            recipient=user_1,
            notification_type="notice",
            message="Notice for U1",
            gym=gym,
        )
        n2 = create_notification(
            recipient=user_2,
            notification_type="notice",
            message="Notice for U2",
            gym=gym,
        )

        self.client.force_authenticate(user=user_1)

        # 1. Attempt to mark User 2's notification as read -> 404 Not Found
        resp_other = self.client.post(
            f"/api/notifications/{n2.id}/read/",
            HTTP_HOST="beta-notif.localhost",
        )
        assert resp_other.status_code == status.HTTP_404_NOT_FOUND
        n2.refresh_from_db()
        assert n2.is_read is False

        # 2. Mark own notification as read -> 200 OK
        resp_own = self.client.post(
            f"/api/notifications/{n1.id}/read/",
            HTTP_HOST="beta-notif.localhost",
        )
        assert resp_own.status_code == status.HTTP_200_OK
        n1.refresh_from_db()
        assert n1.is_read is True

    def test_mark_all_read_affects_only_current_user(self, db):
        gym = GymTenant.objects.create(
            name="Gamma Gym", subdomain="gamma-notif", tls_confirmed_at=timezone.now()
        )
        user_1 = User.objects.create_user(
            email="u1@gamma.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )
        user_2 = User.objects.create_user(
            email="u2@gamma.fitgate.et",
            password="StrongPassword123!",
            gym=gym,
            role=User.ROLE_MEMBER,
        )

        create_notification(
            recipient=user_1,
            notification_type="notice",
            message="Notice 1 for U1",
            gym=gym,
        )
        create_notification(
            recipient=user_1,
            notification_type="notice",
            message="Notice 2 for U1",
            gym=gym,
        )
        n2 = create_notification(
            recipient=user_2,
            notification_type="notice",
            message="Notice for U2",
            gym=gym,
        )

        self.client.force_authenticate(user=user_1)
        resp = self.client.post(
            "/api/notifications/mark-all-read/",
            HTTP_HOST="gamma-notif.localhost",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["updated_count"] == 2

        # User 1's notifications are all read
        assert (
            Notification.all_objects.filter(recipient=user_1, is_read=False).count()
            == 0
        )

        # User 2's notification is completely untouched
        n2.refresh_from_db()
        assert n2.is_read is False

    def test_tenant_isolation_and_super_admin_platform_alerts(self, db):
        gym_a = GymTenant.objects.create(
            name="Gym Alpha", subdomain="alpha-ten", tls_confirmed_at=timezone.now()
        )
        gym_b = GymTenant.objects.create(
            name="Gym Beta", subdomain="beta-ten", tls_confirmed_at=timezone.now()
        )

        user_a = User.objects.create_user(
            email="owner@alpha.fitgate.et",
            password="StrongPassword123!",
            gym=gym_a,
            role=User.ROLE_OWNER,
        )
        user_b = User.objects.create_user(
            email="owner@beta.fitgate.et",
            password="StrongPassword123!",
            gym=gym_b,
            role=User.ROLE_OWNER,
        )
        super_admin = User.objects.create_superuser(
            email="admin@platform.fitgate.et",
            password="SuperPassword123!",
        )

        create_notification(
            recipient=user_a,
            notification_type="gym_event",
            message="Gym A Secret",
            gym=gym_a,
        )
        create_notification(
            recipient=user_b,
            notification_type="gym_event",
            message="Gym B Secret",
            gym=gym_b,
        )
        create_notification(
            recipient=super_admin,
            notification_type="platform_alert",
            message="Platform Maintenance Alert",
            gym=None,
        )

        # 1. Gym A owner sees only Gym A notifications
        self.client.force_authenticate(user=user_a)
        resp_a = self.client.get("/api/notifications/", HTTP_HOST="alpha-ten.localhost")
        assert resp_a.status_code == status.HTTP_200_OK
        messages_a = [n["message"] for n in resp_a.json()["results"]]
        assert "Gym A Secret" in messages_a
        assert "Gym B Secret" not in messages_a
        assert "Platform Maintenance Alert" not in messages_a

        # 2. Super Admin at apex sees only platform-level notifications
        self.client.force_authenticate(user=super_admin)
        resp_admin = self.client.get("/api/notifications/", HTTP_HOST="localhost")
        assert resp_admin.status_code == status.HTTP_200_OK
        messages_admin = [n["message"] for n in resp_admin.json()["results"]]
        assert "Platform Maintenance Alert" in messages_admin
        assert "Gym A Secret" not in messages_admin
        assert "Gym B Secret" not in messages_admin
