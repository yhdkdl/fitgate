"""Tests for dashboard_config_for factory function."""

import pytest

from apps.accounts.dashboards import dashboard_config_for
from apps.accounts.models import User
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestDashboardConfigFactory:
    """Tests for role-specific dashboard configuration factory pattern."""

    @pytest.fixture
    def sample_gym(self):
        """Create a sample gym for user testing."""
        return GymTenant.objects.create(name="Dashboard Gym", subdomain="dashgym")

    def test_each_role_receives_distinct_dashboard_configuration(self, sample_gym):
        """Verify each of the 6 valid roles receives its own distinct configuration."""
        roles = [
            User.ROLE_SUPER_ADMIN,
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
            User.ROLE_MEMBER,
        ]

        seen_roles = set()
        seen_titles = set()

        for role in roles:
            if role == User.ROLE_SUPER_ADMIN:
                user = User.objects.create_superuser(
                    email=f"{role}@fitgate.org",
                    password="Password123!",
                )
            else:
                user = User.objects.create_user(
                    email=f"{role}@dashgym.com",
                    password="Password123!",
                    role=role,
                    gym=sample_gym,
                )

            config = dashboard_config_for(user)
            assert config["role"] == role
            assert "title" in config
            assert "widgets" in config
            assert len(config["widgets"]) > 0
            assert "navigation" in config
            assert len(config["navigation"]) > 0

            seen_roles.add(config["role"])
            seen_titles.add(config["title"])

        # All 6 roles and titles are distinct
        assert len(seen_roles) == 6
        assert len(seen_titles) == 6

    def test_unknown_role_raises_value_error(self, sample_gym):
        """An unknown user role raises ValueError."""
        user = User(
            email="unknown@dashgym.com", role="custom_unsupported_role", gym=sample_gym
        )
        with pytest.raises(ValueError, match="Unknown user role"):
            dashboard_config_for(user)

    def test_empty_role_raises_value_error(self, sample_gym):
        """A user without role attribute raises ValueError."""
        user = User(email="norole@dashgym.com", role="", gym=sample_gym)
        with pytest.raises(ValueError, match="User has no role defined"):
            dashboard_config_for(user)
