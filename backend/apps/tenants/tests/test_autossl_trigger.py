"""Tests for AutoSSL trigger, throttling, and check_pending_tls management command."""

import ssl
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import AuditLog, User
from apps.tenants.models import GymTenant
from apps.tenants.services import (
    AUTOSSL_THROTTLE_CACHE_KEY,
    create_gym,
    trigger_autossl_check_throttled,
    verify_subdomain_tls,
)
from apps.tenants.uapi import MockCPanelUAPIClient


@pytest.fixture
def super_admin():
    return User.objects.create_superuser(
        email="superadmin@fitgate.test",
        password="SuperPassword123!",
    )


@pytest.mark.django_db
class TestCertificateCheck:
    """Tests that verify_subdomain_tls strictly verifies chains, expiration, and hostnames."""

    def test_refuses_unverifiable_chain(self):
        """Cert check refuses self-signed or untrusted CA certificate chain."""
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        mock_ctx.wrap_socket.side_effect = ssl.SSLCertVerificationError(
            1,
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: self-signed certificate in certificate chain",
        )

        mock_conn = MagicMock()
        is_valid, reason = verify_subdomain_tls(
            subdomain="untrustedgym",
            ssl_context=mock_ctx,
            connection_factory=lambda *a, **kw: mock_conn,
        )
        assert is_valid is False
        assert "Certificate verification failed" in reason

    def test_refuses_expired_certificate(self):
        """Cert check refuses an expired TLS certificate."""
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        mock_ssock = MagicMock()
        # Certificate expired in 2020
        mock_ssock.getpeercert.return_value = {
            "notBefore": "Oct 11 10:00:00 2019 GMT",
            "notAfter": "Oct 11 10:00:00 2020 GMT",
            "subjectAltName": (("DNS", "expiredgym.fitgate.tebebtech.com"),),
        }
        mock_ctx.wrap_socket.return_value.__enter__.return_value = mock_ssock

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = MagicMock()

        is_valid, reason = verify_subdomain_tls(
            subdomain="expiredgym",
            ssl_context=mock_ctx,
            connection_factory=lambda *a, **kw: mock_conn,
        )
        assert is_valid is False
        assert "expired" in reason.lower()

    def test_refuses_wrong_hostname(self):
        """Cert check refuses certificate whose SAN does not match gym subdomain."""
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        mock_ctx.wrap_socket.side_effect = ssl.CertificateError(
            "hostname 'wronggym.fitgate.tebebtech.com' doesn't match 'othergym.fitgate.tebebtech.com'"
        )

        mock_conn = MagicMock()
        is_valid, reason = verify_subdomain_tls(
            subdomain="wronggym",
            ssl_context=mock_ctx,
            connection_factory=lambda *a, **kw: mock_conn,
        )
        assert is_valid is False
        assert "Hostname mismatch" in reason

    def test_accepts_valid_certificate(self):
        """Cert check accepts valid, unexpired certificate matching exact hostname."""
        mock_ctx = MagicMock(spec=ssl.SSLContext)
        mock_ssock = MagicMock()
        # Valid certificate expiring far in the future
        mock_ssock.getpeercert.return_value = {
            "notBefore": "Oct 11 10:00:00 2024 GMT",
            "notAfter": "Oct 11 10:00:00 2035 GMT",
            "subjectAltName": (("DNS", f"validgym.{settings.DOMAIN}"),),
        }
        mock_ctx.wrap_socket.return_value.__enter__.return_value = mock_ssock

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = MagicMock()

        is_valid, reason = verify_subdomain_tls(
            subdomain="validgym",
            ssl_context=mock_ctx,
            connection_factory=lambda *a, **kw: mock_conn,
        )
        assert is_valid is True
        assert reason == "Valid certificate"


@pytest.mark.django_db
class TestCheckPendingTlsCommand:
    """Tests for management command check_pending_tls."""

    def test_command_confirms_valid_tls_and_records_audit_log(self):
        """Valid gym certificate sets tls_confirmed_at and audit logs 'confirmed by certificate check'."""
        gym = GymTenant.objects.create(
            name="Pending TLS Gym",
            subdomain="pendingtls",
            tier="growth",
            tls_confirmed_at=None,
        )

        with patch(
            "apps.tenants.management.commands.check_pending_tls.verify_subdomain_tls"
        ) as mock_verify:
            mock_verify.return_value = (True, "Valid certificate")
            call_command("check_pending_tls")

        gym.refresh_from_db()
        assert gym.tls_confirmed_at is not None
        assert gym.subscription_expires_at is not None

        # Verify audit log
        entry = AuditLog.all_objects.filter(
            action_type="gym_tls_confirmed",
            affected_record_id=str(gym.id),
        ).latest("timestamp")
        assert entry.metadata.get("reason") == "confirmed by certificate check"

    def test_command_leaves_tls_confirmed_at_null_on_failure(self):
        """Invalid certificate leaves tls_confirmed_at null."""
        gym = GymTenant.objects.create(
            name="Failing TLS Gym",
            subdomain="failingtls",
            tier="growth",
            tls_confirmed_at=None,
        )

        with patch(
            "apps.tenants.management.commands.check_pending_tls.verify_subdomain_tls"
        ) as mock_verify:
            mock_verify.return_value = (False, "Certificate verification failed")
            call_command("check_pending_tls")

        gym.refresh_from_db()
        assert gym.tls_confirmed_at is None


@pytest.mark.django_db
class TestAutoSslTriggerAndThrottle:
    """Tests for AutoSSL triggering, error resilience, and platform throttle."""

    def test_gym_creation_succeeds_if_autossl_trigger_fails(self, super_admin):
        """Gym creation succeeds even if AutoSSL UAPI call fails (best-effort)."""
        mock_uapi = MockCPanelUAPIClient(fail_autossl=True)

        res = create_gym(
            name="Resilient Gym",
            subdomain="resilientgym",
            tier="growth",
            owner_email="owner@resilientgym.test",
            payment_amount=15000,
            payment_reference="DEP-RESILIENT-01",
            acting_super_admin=super_admin,
            uapi_client=mock_uapi,
        )

        gym = GymTenant.objects.get(subdomain="resilientgym")
        assert gym is not None
        assert "resilientgym" in mock_uapi.provisioned_subdomains
        assert res["gym"].subdomain == "resilientgym"

    def test_throttle_is_enforced(self):
        """AutoSSL check triggers at most once every 10 minutes across the platform."""
        cache.delete(AUTOSSL_THROTTLE_CACHE_KEY)
        mock_uapi = MockCPanelUAPIClient()

        # First call triggers
        triggered_1 = trigger_autossl_check_throttled(uapi_client=mock_uapi)
        assert triggered_1 is True
        assert mock_uapi.autossl_checks_count == 1

        # Second call immediately after is throttled
        triggered_2 = trigger_autossl_check_throttled(uapi_client=mock_uapi)
        assert triggered_2 is False
        assert mock_uapi.autossl_checks_count == 1

        # Simulate 11 minutes later: triggers again
        eleven_minutes_ago = (timezone.now() - timedelta(minutes=11)).timestamp()
        cache.set(AUTOSSL_THROTTLE_CACHE_KEY, eleven_minutes_ago, timeout=1200)

        triggered_3 = trigger_autossl_check_throttled(uapi_client=mock_uapi)
        assert triggered_3 is True
        assert mock_uapi.autossl_checks_count == 2
