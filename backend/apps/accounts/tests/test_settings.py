"""Tests for project settings contracts (DEFAULT_FROM_EMAIL fail-fast, local defaults)."""

import importlib
import sys
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured


class TestDefaultFromEmailSettings:
    """Ensure DEFAULT_FROM_EMAIL fails fast in production and defaults safely in local."""

    def test_production_settings_fail_fast_without_default_from_email(
        self, monkeypatch
    ):
        """Production settings must raise ImproperlyConfigured if DEFAULT_FROM_EMAIL is unset."""
        monkeypatch.delenv("DEFAULT_FROM_EMAIL", raising=False)
        with patch("environ.Env.read_env"):
            with pytest.raises(ImproperlyConfigured):
                if "fitgate.settings.prod" in sys.modules:
                    importlib.reload(sys.modules["fitgate.settings.prod"])
                else:
                    importlib.import_module("fitgate.settings.prod")

        # When DEFAULT_FROM_EMAIL is set (and QR keys present), prod settings load successfully
        monkeypatch.setenv("DEFAULT_FROM_EMAIL", "prod@fitgate.org")
        monkeypatch.setenv("QR_JWT_PRIVATE_KEY", "dummy-private-key")
        monkeypatch.setenv("QR_JWT_PUBLIC_KEY", "dummy-public-key")
        prod = importlib.import_module("fitgate.settings.prod")
        importlib.reload(prod)
        assert prod.DEFAULT_FROM_EMAIL == "prod@fitgate.org"
        assert prod.QR_JWT_PRIVATE_KEY == "dummy-private-key"

    @pytest.mark.parametrize("missing_key", ["QR_JWT_PRIVATE_KEY", "QR_JWT_PUBLIC_KEY"])
    def test_production_settings_fail_fast_without_qr_keys(
        self, monkeypatch, missing_key
    ):
        """Production settings must raise ImproperlyConfigured if either QR_JWT key is unset."""
        monkeypatch.setenv("DEFAULT_FROM_EMAIL", "prod@fitgate.org")
        monkeypatch.setenv("QR_JWT_PRIVATE_KEY", "dummy-private-key")
        monkeypatch.setenv("QR_JWT_PUBLIC_KEY", "dummy-public-key")
        monkeypatch.delenv(missing_key, raising=False)
        with patch("environ.Env.read_env"):
            with pytest.raises(ImproperlyConfigured):
                if "fitgate.settings.prod" in sys.modules:
                    importlib.reload(sys.modules["fitgate.settings.prod"])
                else:
                    importlib.import_module("fitgate.settings.prod")

    def test_local_settings_has_console_default_from_email(self, monkeypatch):
        """Local settings provide a default console value when DEFAULT_FROM_EMAIL is unset."""
        monkeypatch.delenv("DEFAULT_FROM_EMAIL", raising=False)
        with patch("environ.Env.read_env"):
            if "fitgate.settings.local" in sys.modules:
                local = importlib.reload(sys.modules["fitgate.settings.local"])
            else:
                local = importlib.import_module("fitgate.settings.local")

        assert local.DEFAULT_FROM_EMAIL == "webmaster@localhost"

    def test_notifications_use_settings_default_from_email_directly(self):
        """notifications.py functions must use settings.DEFAULT_FROM_EMAIL directly."""
        import inspect

        from apps.accounts import notifications

        source = inspect.getsource(notifications)
        assert 'getattr(settings, "DEFAULT_FROM_EMAIL"' not in source
        assert "settings.DEFAULT_FROM_EMAIL" in source
        assert "noreply@fitgate.org" not in source
