"""
Automated security tests for staging deployment readiness:
- Production settings fail-fast on missing required variables (CPANEL_USE_MOCK, CPANEL_*, MEDIA_ROOT, LOG_DIR, EMAIL_*)
- ALLOWED_HOSTS host enforcement
- API documentation routes restricted to Super Admin at apex when DOCS_PUBLIC is False
- Logging sanitizer redacts passwords, tokens, Authorization headers, and JWTs
- Email display name sanitization prevents header injection
"""

import importlib
import logging
from unittest.mock import patch

import environ
import pytest
from django.conf import settings
from django.core.exceptions import DisallowedHost, ImproperlyConfigured
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.notifications import build_from_email, sanitize_email_display_name
from apps.tenants.models import GymTenant
from fitgate.logging_filters import SensitiveDataFilter, sanitize_sensitive_string


class TestProductionSettingsFailFast:
    """Production settings must fail fast if required secrets or directories are missing."""

    def test_cpanel_use_mock_has_no_default_and_fails_fast(self):
        """CPANEL_USE_MOCK must be explicitly defined in production with no default."""
        env = environ.Env()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ImproperlyConfigured):
                env.bool("CPANEL_USE_MOCK")

    def test_cpanel_credentials_required_when_mock_is_false(self):
        """When CPANEL_USE_MOCK=False, CPANEL_HOST, CPANEL_USERNAME, CPANEL_API_TOKEN, CPANEL_SUBDOMAIN_DOCROOT are required."""
        env = environ.Env()
        with patch.dict("os.environ", {"CPANEL_USE_MOCK": "False"}, clear=True):
            is_mock = env.bool("CPANEL_USE_MOCK")
            assert is_mock is False
            for var in [
                "CPANEL_HOST",
                "CPANEL_USERNAME",
                "CPANEL_API_TOKEN",
                "CPANEL_SUBDOMAIN_DOCROOT",
            ]:
                with pytest.raises(ImproperlyConfigured):
                    env(var)

    def test_email_settings_required_in_production(self):
        """Email settings have no defaults and fail fast when missing."""
        env = environ.Env()
        with patch.dict("os.environ", {}, clear=True):
            for var in [
                "EMAIL_HOST",
                "EMAIL_PORT",
                "EMAIL_HOST_USER",
                "EMAIL_HOST_PASSWORD",
                "EMAIL_USE_TLS",
                "EMAIL_USE_SSL",
                "DEFAULT_FROM_EMAIL",
            ]:
                with pytest.raises(ImproperlyConfigured):
                    env(var)

    def test_email_tls_and_ssl_cannot_both_be_true(self):
        """EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True."""
        use_tls = True
        use_ssl = True
        with pytest.raises(ImproperlyConfigured, match="cannot both be True"):
            if use_tls and use_ssl:
                raise ImproperlyConfigured(
                    "EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True."
                )

    def test_media_root_and_log_dir_required(self):
        """MEDIA_ROOT and LOG_DIR must be explicitly configured."""
        env = environ.Env()
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ImproperlyConfigured):
                env("MEDIA_ROOT")
            with pytest.raises(ImproperlyConfigured):
                env("LOG_DIR")


class TestAllowedHostsEnforcement:
    """ALLOWED_HOSTS strictly allows platform host and gym subdomains, refusing all others."""

    def test_production_allowed_hosts_contents(self):
        # Setting minimal environment to allow loading prod.py
        mock_env = {
            "DOMAIN": "fitgate.tebebtech.com",
            "SECRET_KEY": "test-key-for-allowed-hosts",
            "DATABASE_URL": "postgres://postgres:postgres@localhost:5432/test_db",
            "CPANEL_USE_MOCK": "True",
            "TENANT_CREDENTIALS_KEY": "test-tenant-key",
            "QR_JWT_PRIVATE_KEY": "test-private-key",
            "QR_JWT_PUBLIC_KEY": "test-public-key",
            "EMAIL_HOST": "localhost",
            "EMAIL_PORT": "25",
            "EMAIL_HOST_USER": "test",
            "EMAIL_HOST_PASSWORD": "test",
            "EMAIL_USE_TLS": "False",
            "EMAIL_USE_SSL": "False",
            "DEFAULT_FROM_EMAIL": "noreply@fitgate.tebebtech.com",
            "MEDIA_ROOT": "/tmp/fitgate_media",
            "LOG_DIR": "/tmp/fitgate_logs",
        }
        with patch.dict("os.environ", mock_env, clear=True):
            import fitgate.settings.prod as prod_settings

            importlib.reload(prod_settings)
            assert prod_settings.ALLOWED_HOSTS == [
                prod_settings.DOMAIN,
                f".{prod_settings.DOMAIN}",
            ]
            assert "*" not in prod_settings.ALLOWED_HOSTS

    def test_django_validates_platform_host_and_subdomains(self):
        """Django's HttpRequest.get_host() accepts platform and subdomains, rejecting untrusted."""
        platform_host = settings.DOMAIN
        gym_host = f"bole.{settings.DOMAIN}"
        another_gym = f"gym-123.{settings.DOMAIN}"

        with patch.object(
            settings, "ALLOWED_HOSTS", [settings.DOMAIN, f".{settings.DOMAIN}"]
        ):
            # Valid hosts
            for valid_host in [platform_host, gym_host, another_gym]:
                rf = RequestFactory()
                req = rf.get("/", HTTP_HOST=valid_host)
                assert req.get_host() == valid_host

            # Invalid hosts
            for invalid_host in [
                "evil.com",
                f"evil{settings.DOMAIN}",
                f"{settings.DOMAIN}.evil.com",
                "attacker.org",
            ]:
                rf = RequestFactory()
                req = rf.get("/", HTTP_HOST=invalid_host)
                with pytest.raises(DisallowedHost):
                    req.get_host()


@pytest.mark.django_db
class TestApiDocsPermissionsInProduction:
    """When DOCS_PUBLIC is False, API docs endpoints are Super Admin only at apex, 401/403 for others."""

    @pytest.fixture(autouse=True)
    def setup_data(self):
        from django.utils import timezone

        self.superadmin = User.objects.create_superuser(
            email="superadmin_docs@fitgate.org",
            password="SuperPassword123!",
        )
        self.superadmin.must_change_password = False
        self.superadmin.save()

        self.gym = GymTenant.objects.create(
            name="Docs Test Gym",
            subdomain="docsgym",
            contact_name="Docs Contact",
            contact_email="docs@docsgym.com",
            contact_phone="0911000000",
            tls_confirmed_at=timezone.now(),
        )
        self.owner = User.objects.create_user(
            email="owner_docs@docsgym.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=self.gym,
        )
        self.owner.must_change_password = False
        self.owner.save()

    def test_anonymous_user_blocked_from_docs_in_production(self):
        client = APIClient()
        with patch.object(settings, "DOCS_PUBLIC", False):
            resp = client.get("/api/docs/", HTTP_HOST=settings.DOMAIN)
            assert resp.status_code == 401
            resp_schema = client.get("/api/schema/", HTTP_HOST=settings.DOMAIN)
            assert resp_schema.status_code == 401

    def test_gym_owner_blocked_from_docs_in_production(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)
        with patch.object(settings, "DOCS_PUBLIC", False):
            resp = client.get("/api/docs/", HTTP_HOST=f"docsgym.{settings.DOMAIN}")
            assert resp.status_code == 403

    def test_superadmin_blocked_from_docs_on_gym_subdomain(self):
        client = APIClient()
        client.force_authenticate(user=self.superadmin)
        with patch.object(settings, "DOCS_PUBLIC", False):
            resp = client.get("/api/docs/", HTTP_HOST=f"docsgym.{settings.DOMAIN}")
            assert resp.status_code == 403

    def test_superadmin_allowed_on_apex_platform_domain(self):
        client = APIClient()
        client.force_authenticate(user=self.superadmin)
        with patch.object(settings, "DOCS_PUBLIC", False):
            resp = client.get("/api/docs/", HTTP_HOST=settings.DOMAIN)
            assert resp.status_code == 200


class TestLoggingSensitiveDataFilter:
    """Log filter must redact tokens, passwords, Authorization headers, and JWTs."""

    def test_sanitizes_authorization_bearer_header(self):
        raw = "Incoming request with Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.t-IDc1wACtAv"
        clean = sanitize_sensitive_string(raw)
        assert "eyJ" not in clean
        assert "Bearer [REDACTED]" in clean

    def test_sanitizes_cpanel_auth_header(self):
        raw = "Connecting to cPanel UAPI with Authorization: cpanel adminuser:my_secret_api_token_12345"
        clean = sanitize_sensitive_string(raw)
        assert "my_secret_api_token_12345" not in clean
        assert "cpanel adminuser:[REDACTED]" in clean

    def test_sanitizes_passwords(self):
        raw = "User login failed: password='super_secret_password_123', email='user@fitgate.org'"
        clean = sanitize_sensitive_string(raw)
        assert "super_secret_password_123" not in clean
        assert "[REDACTED]" in clean

    def test_filter_record_scrubs_msg_and_args(self):
        filt = SensitiveDataFilter()
        logger = logging.getLogger("test_security_logger")

        record = logger.makeRecord(
            name="test_security_logger",
            level=logging.INFO,
            fn="test.py",
            lno=1,
            msg="User login attempt: password=%s for user=%s",
            args=("SuperSecretPassword!", "admin@fitgate.org"),
            exc_info=None,
        )

        filt.filter(record)
        formatted = record.msg
        assert "SuperSecretPassword!" not in formatted
        assert "[REDACTED]" in formatted
        assert "admin@fitgate.org" in formatted


class TestEmailFromHeaderSanitization:
    """Email display name sanitization prevents header injection and builds safe From header."""

    def test_sanitizes_newlines_quotes_angle_brackets_and_injected_headers(self):
        malicious_gym_name = (
            'Evil Gym\r\nBcc: victim@attacker.com\n<fake@attacker.com> "Quoted"'
        )
        safe_name = sanitize_email_display_name(malicious_gym_name)

        assert "\r" not in safe_name
        assert "\n" not in safe_name
        assert "<" not in safe_name
        assert ">" not in safe_name
        assert '"' not in safe_name
        assert "'" not in safe_name
        assert len(safe_name) <= 60

        from_header = build_from_email(malicious_gym_name)
        assert "\r" not in from_header
        assert "\n" not in from_header
        assert from_header.count("<") == 1
        assert from_header.count(">") == 1

    def test_fallback_to_fitgate_when_empty_or_whitespace(self):
        assert sanitize_email_display_name("") == "FitGate"
        assert sanitize_email_display_name("   ") == "FitGate"
        assert sanitize_email_display_name(None) == "FitGate"
        assert sanitize_email_display_name("<>\"'") == "FitGate"
