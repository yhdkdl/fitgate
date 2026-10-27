"""Tests for Sprint 9b email safety and delivery protections."""

from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import EmailDeliveryStatus, User
from apps.accounts.notifications import send_fitgate_email
from apps.accounts.serializers import StaffMemberSerializer
from apps.core.validators import validate_email_address
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestEmailSafetyWebhook:
    """Test Brevo webhook secret handling and suppression recording."""

    def setup_method(self):
        self.client = APIClient()
        self.webhook_url = "/api/webhooks/brevo/"

    def test_webhook_secret_wrong_or_missing_returns_same_as_unknown_event(
        self, settings
    ):
        settings.BREVO_WEBHOOK_SECRET = "secret-token-123"

        # 1. Missing secret
        resp_missing = self.client.post(
            self.webhook_url,
            data={"event": "hard_bounce", "email": "test@domain.com"},
            format="json",
        )
        assert resp_missing.status_code == status.HTTP_200_OK
        assert resp_missing.json() == {"status": "ignored"}

        # 2. Wrong secret via header
        resp_wrong = self.client.post(
            self.webhook_url,
            data={"event": "hard_bounce", "email": "test@domain.com"},
            format="json",
            HTTP_X_WEBHOOK_SECRET="wrong-secret",
        )
        assert resp_wrong.status_code == status.HTTP_200_OK
        assert resp_wrong.json() == {"status": "ignored"}

        # 3. Unknown event with valid secret
        resp_unknown = self.client.post(
            self.webhook_url,
            data={"event": "opened", "email": "test@domain.com"},
            format="json",
            HTTP_X_WEBHOOK_SECRET="secret-token-123",
        )
        assert resp_unknown.status_code == status.HTTP_200_OK
        assert resp_unknown.json() == {"status": "ignored"}

        # Confirm nothing was suppressed
        assert not EmailDeliveryStatus.all_objects.filter(
            email="test@domain.com"
        ).exists()

    def test_webhook_valid_secret_suppresses_bounced_address(self, settings):
        settings.BREVO_WEBHOOK_SECRET = "secret-token-123"

        payload = {
            "event": "hardBounce",
            "email": "bounced@realmailbox.com",
            "reason": "Mailbox does not exist",
        }
        resp = self.client.post(
            self.webhook_url,
            data=payload,
            format="json",
            HTTP_X_WEBHOOK_SECRET="secret-token-123",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == {"status": "processed"}

        status_obj = EmailDeliveryStatus.all_objects.get(
            email="bounced@realmailbox.com"
        )
        assert status_obj.status == EmailDeliveryStatus.STATUS_SUPPRESSED
        assert "Mailbox does not exist" in status_obj.reason


@pytest.mark.django_db
class TestEmailSafetyDomainGates:
    """Test reserved test domains in strict mode and disposable domains for registration."""

    def test_reserved_test_domains_refused_in_strict_mode(self, settings):
        settings.EMAIL_STRICT_MODE = True

        for domain in ["example.com", "example.net", "test.invalid", "domain.test"]:
            email = f"user@{domain}"
            with pytest.raises(ValidationError) as exc:
                validate_email_address(email, is_lenient=True)
            assert "Use a real email address" in str(exc.value)

    def test_disposable_email_domains_refused_for_registration(self):
        for domain in [
            "tempmail.com",
            "mailinator.com",
            "guerrillamail.com",
            "10minutemail.com",
        ]:
            email = f"testuser@{domain}"
            with pytest.raises(ValidationError) as exc:
                validate_email_address(email, is_public_registration=True)
            assert "Disposable email" in str(exc.value)


@pytest.mark.django_db
class TestEmailSuppressionBlockingSend:
    """Test that a suppressed email address in EmailDeliveryStatus is never sent."""

    def test_suppressed_address_is_never_emailed(self, settings):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        email = "suppressed_target@example.com"

        EmailDeliveryStatus.all_objects.create(
            email=email,
            status=EmailDeliveryStatus.STATUS_SUPPRESSED,
            reason="hard_bounce",
        )

        with patch("django.core.mail.send_mail") as mock_send_mail:
            sent = send_fitgate_email(
                subject="Test Subject",
                message="Test Message",
                recipient_list=[email],
            )
            assert sent == 0
            mock_send_mail.assert_not_called()


@pytest.mark.django_db
class TestEmailSafetyTenancyVisibility:
    """Test item 12: 'Email not delivered' status is visible only to staff of that same gym."""

    def test_delivery_status_tenancy_isolation(self, db):
        # Create Gym A and Gym B
        gym_a = GymTenant.objects.create(name="Gym Alpha", subdomain="alpha")
        gym_b = GymTenant.objects.create(name="Gym Beta", subdomain="beta")

        # Create staff in Gym A and Gym B
        owner_a = User.objects.create(
            email="owner_a@alpha.fitgate.et",
            role=User.ROLE_OWNER,
            gym=gym_a,
            is_active=True,
        )
        staff_b = User.objects.create(
            email="manager_b@beta.fitgate.et",
            role=User.ROLE_MANAGER,
            gym=gym_b,
            is_active=True,
        )

        # Create invited staff in Gym A with not_delivered status
        invited_staff_a = User.objects.create(
            email="trainer_a@alpha.fitgate.et",
            role=User.ROLE_TRAINER,
            gym=gym_a,
            is_active=True,
        )
        invited_staff_a.set_unusable_password()
        invited_staff_a.save()

        EmailDeliveryStatus.all_objects.create(
            email="trainer_a@alpha.fitgate.et",
            gym=gym_a,
            status=EmailDeliveryStatus.STATUS_NOT_DELIVERED,
            reason="dns_lookup_failed",
        )

        # Context: Request from Gym A owner -> sees "not_delivered" and message
        class MockRequestA:
            user = owner_a
            tenant = gym_a

        serializer_a = StaffMemberSerializer(
            invited_staff_a, context={"request": MockRequestA()}
        )
        assert serializer_a.data["invitation_status"] == "not_delivered"
        assert (
            serializer_a.data["email_delivery_message"] == "Fix the address and resend"
        )

        # Context: Request from Gym B staff -> cannot see Gym A's not_delivered status
        class MockRequestB:
            user = staff_b
            tenant = gym_b

        serializer_b = StaffMemberSerializer(
            invited_staff_a, context={"request": MockRequestB()}
        )
        assert serializer_b.data["invitation_status"] == "sent"
        assert serializer_b.data["email_delivery_message"] is None


@pytest.mark.django_db
class TestDatabaseEmailRateCapsWithoutRedis:
    """
    Test Item 1: Hourly per-gym and per-platform email caps must work from the database
    with no fail-open dependency on Redis, blocking when the limit is exceeded.
    """

    def test_rate_cap_blocks_from_database_when_redis_unavailable(
        self, monkeypatch, settings
    ):
        settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
        settings.EMAIL_HOURLY_CAP_PER_GYM = 2
        settings.EMAIL_HOURLY_CAP_PLATFORM = 5

        # Completely disable/break Redis cache to verify zero dependency
        def broken_cache(*args, **kwargs):
            raise ConnectionError("Redis connection refused")

        monkeypatch.setattr("django.core.cache.cache.get", broken_cache)
        monkeypatch.setattr("django.core.cache.cache.set", broken_cache)

        gym = GymTenant.objects.create(name="Cap Gym", subdomain="capgym")

        # Send 1st email -> succeeds
        sent_1 = send_fitgate_email(
            subject="Test 1",
            message="Message 1",
            recipient_list=["user1@capgym.test"],
            gym=gym,
        )
        assert sent_1 == 1

        # Send 2nd email -> succeeds (count becomes 2 == cap)
        sent_2 = send_fitgate_email(
            subject="Test 2",
            message="Message 2",
            recipient_list=["user2@capgym.test"],
            gym=gym,
        )
        assert sent_2 == 1

        # 3rd email -> exceeds gym cap of 2 -> blocks with ValidationError("email limit reached")
        with pytest.raises(ValidationError) as exc:
            send_fitgate_email(
                subject="Test 3",
                message="Message 3",
                recipient_list=["user3@capgym.test"],
                gym=gym,
            )
        assert "email limit reached" in str(exc.value)
