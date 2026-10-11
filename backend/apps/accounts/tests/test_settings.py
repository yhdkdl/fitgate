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

        # When DEFAULT_FROM_EMAIL is set, prod settings load successfully
        monkeypatch.setenv("DEFAULT_FROM_EMAIL", "prod@fitgate.org")
        prod = importlib.import_module("fitgate.settings.prod")
        importlib.reload(prod)
        assert prod.DEFAULT_FROM_EMAIL == "prod@fitgate.org"

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
