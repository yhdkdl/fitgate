"""Unit tests for GymTenant and GymConfig models."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.tenants.models import GymConfig, GymTenant


@pytest.mark.django_db
class TestGymTenantModel:
    """Test GymTenant model behaviors, defaults, and constraints."""

    def test_create_gym_tenant_defaults(self):
        """Verify default fields upon GymTenant creation."""
        tenant = GymTenant.objects.create(name="Lion Gym", subdomain="liongym")

        assert tenant.status == GymTenant.STATUS_PENDING
        assert tenant.tier == GymTenant.TIER_STARTER
        assert tenant.currency == "ETB"
        assert str(tenant) == "Lion Gym (liongym)"

    def test_auto_creates_gym_config_with_all_flags_false(self):
        """Verify creating GymTenant auto-provisions GymConfig with false flags."""
        tenant = GymTenant.objects.create(name="Tikus Gym", subdomain="tikus")

        # Config should be auto-created via post_save signal
        config = GymConfig.objects.get(gym=tenant)
        assert tenant.config == config
        assert config.has_trainer_module is False
        assert config.has_ai_plans is False
        assert config.has_analytics is False
        assert config.has_group_classes is False
        assert config.has_multi_branch is False
        assert config.freeze_days_allowed == 0
        assert config.chapa_merchant_id is None
        assert str(config) == "Config for Tikus Gym"

    def test_subdomain_is_lowercased_and_trimmed(self):
        """Verify subdomain is automatically cleaned to lowercase and trimmed."""
        tenant = GymTenant.objects.create(name="Alpha Gym", subdomain="  AlphaGYM  ")
        assert tenant.subdomain == "alphagym"

    def test_reserved_subdomain_raises_validation_error(self):
        """Verify reserved subdomains are rejected during clean()."""
        tenant = GymTenant(name="Admin Gym", subdomain="admin")
        with pytest.raises(ValidationError) as exc_info:
            tenant.clean()
        assert "subdomain" in exc_info.value.message_dict

    def test_subdomain_uniqueness(self):
        """Verify duplicate subdomains are rejected."""
        GymTenant.objects.create(name="Gym 1", subdomain="unique-slug")
        with pytest.raises(IntegrityError):
            GymTenant.objects.create(name="Gym 2", subdomain="unique-slug")
