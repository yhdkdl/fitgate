"""Unit tests for GymTenant and GymConfig models, validators, and field specifications."""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.tenants.models import (
    RESERVED_SUBDOMAINS,
    GymConfig,
    GymTenant,
    validate_subdomain,
)


@pytest.mark.django_db
class TestGymTenantModel:
    """Test GymTenant model behaviors, defaults, validators, and constraints."""

    def test_create_gym_tenant_defaults(self):
        """Verify default fields upon GymTenant creation."""
        tenant = GymTenant.objects.create(name="Lion Gym", subdomain="liongym")

        assert tenant.status == GymTenant.STATUS_PENDING
        assert tenant.tier == GymTenant.TIER_STARTER
        assert tenant.currency == "ETB"
        assert str(tenant) == "Lion Gym (liongym)"

    def test_auto_creates_gym_config_with_all_flags_false(self):
        """Verify creating GymTenant auto-provisions GymConfig with all false flags."""
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

    def test_subdomain_is_not_null_and_unique(self):
        """Verify subdomain is NOT NULL and enforces database uniqueness."""
        from django.db import transaction

        GymTenant.objects.create(name="Gym 1", subdomain="unique-slug")
        with transaction.atomic():
            with pytest.raises(IntegrityError):
                GymTenant.objects.create(name="Gym 2", subdomain="unique-slug")

        with transaction.atomic():
            with pytest.raises(IntegrityError):
                GymTenant.objects.create(name="No Subdomain Gym", subdomain=None)

    def test_subdomain_validator_rejects_underscore(self):
        """Verify DNS label validator rejects subdomains containing underscores."""
        with pytest.raises(ValidationError):
            validate_subdomain("invalid_subdomain")

        tenant = GymTenant(name="Under Gym", subdomain="under_score")
        with pytest.raises(ValidationError):
            tenant.full_clean()

    def test_subdomain_validator_rejects_leading_hyphen(self):
        """Verify DNS label validator rejects subdomains with a leading hyphen."""
        with pytest.raises(ValidationError):
            validate_subdomain("-leadinghyphen")

        tenant = GymTenant(name="Lead Gym", subdomain="-leading")
        with pytest.raises(ValidationError):
            tenant.full_clean()

    def test_subdomain_validator_rejects_trailing_hyphen(self):
        """Verify DNS label validator rejects subdomains with a trailing hyphen."""
        with pytest.raises(ValidationError):
            validate_subdomain("trailinghyphen-")

        tenant = GymTenant(name="Trail Gym", subdomain="trailing-")
        with pytest.raises(ValidationError):
            tenant.full_clean()

    def test_subdomain_validator_rejects_reserved_names(self):
        """Verify reserved platform names are rejected via the field validator outside full_clean()."""
        for reserved in RESERVED_SUBDOMAINS:
            with pytest.raises(ValidationError) as exc_info:
                validate_subdomain(reserved)
            assert "reserved" in str(exc_info.value).lower()

    def test_subdomain_validator_accepts_valid_dns_labels(self):
        """Verify valid single DNS labels (1-63 chars) pass validation."""
        valid_examples = [
            "a",
            "lion",
            "fit-gate",
            "gym-123",
            "a" * 63,
        ]
        for name in valid_examples:
            validate_subdomain(name)

        # Longer than 63 characters must be rejected
        with pytest.raises(ValidationError):
            validate_subdomain("a" * 64)

    def test_subdomain_uppercase_and_whitespace_normalized(self):
        """Verify subdomain is normalized to lowercase and stripped of whitespace on clean and save."""
        tenant = GymTenant(name="Normalized Gym", subdomain="  AlphaGYM-1  ")
        tenant.full_clean()
        tenant.save()
        tenant.refresh_from_db()

        assert tenant.subdomain == "alphagym-1"

    def test_field_lengths_follow_spec_section_8(self):
        """Verify field lengths conform precisely to SPEC §8."""
        name_field = GymTenant._meta.get_field("name")
        assert name_field.max_length == 150

        subdomain_field = GymTenant._meta.get_field("subdomain")
        assert subdomain_field.max_length == 63

        chapa_field = GymConfig._meta.get_field("chapa_merchant_id")
        assert chapa_field.max_length == 100

    def test_dummy_tenant_model_not_in_production_models_or_migrations(self):
        """Verify DummyTenantModel is test-only and never registered in production models or migrations."""
        import importlib

        import apps.tenants.models as prod_models

        # DummyTenantModel must not be defined in apps.tenants.models
        assert not hasattr(prod_models, "DummyTenantModel")

        # Initial migration operations must only include GymTenant and GymConfig
        initial_migration = importlib.import_module(
            "apps.tenants.migrations.0001_initial"
        )
        migration_models = [
            op.name
            for op in initial_migration.Migration.operations
            if hasattr(op, "name")
        ]
        assert "DummyTenantModel" not in migration_models
        assert set(migration_models) == {"GymTenant", "GymConfig"}
