"""
Tests for Sprint 4c: Gym branding, entry page, and first-run checklist.

Covers:
- GymConfig branding fields and hex color validation.
- First-run checklist automatic item ticking from database records.
- First-run checklist dismissal and persistent state.
- RBAC on checklist: Owner and Super Admin allowed, Manager and other roles receive 403.
- Gym settings update:
  - Owner can edit brand_color, logo, show_unavailable_equipment, member_reminder_days.
  - Owner attempting to edit entitlements (tier, has_*, freeze_days_allowed, grace days) receives 403.
  - Manager attempting to edit settings receives 403.
  - Super Admin can edit entitlements.
- Public entry page:
  - Publicly accessible without auth.
  - Returns 503 "still being secured" when tls_confirmed_at is null.
  - Returns 200 with branding and contact details when tls_confirmed_at is set.
  - Never leaks another gym's details.
"""

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymTenant, validate_hex_color
from apps.tenants.services import (
    dismiss_first_run_checklist,
    get_first_run_checklist,
)


@pytest.mark.django_db
class TestBrandingValidationAndModels:
    """Tests for hex color validation and GymConfig model enhancements."""

    def test_validate_hex_color_valid_values(self):
        for valid_hex in ["#000000", "#FFFFFF", "#ff5733", "#1A2B3C", "#abcdef"]:
            validate_hex_color(valid_hex)

    def test_validate_hex_color_invalid_values(self):
        for invalid_hex in ["red", "#FFF", "#1234567", "#GGGGGG", "123456", "#12345"]:
            with pytest.raises(ValidationError) as exc:
                validate_hex_color(invalid_hex)
            assert "valid 6-character hex code" in str(exc.value)

    def test_gym_config_defaults(self):
        gym = GymTenant.objects.create(name="Fit Zone", subdomain="fit-zone")
        config = gym.config

        assert config.brand_color is None
        assert config.logo is None
        assert config.show_unavailable_equipment is False
        assert config.first_run_dismissed_at is None


@pytest.mark.django_db
class TestFirstRunChecklistService:
    """Tests for get_first_run_checklist and dismiss_first_run_checklist."""

    @pytest.fixture
    def gym(self):
        return GymTenant.objects.create(name="Bole Gym", subdomain="bole-gym")

    def test_checklist_initially_all_uncompleted(self, gym):
        data = get_first_run_checklist(gym)

        assert data["is_dismissed"] is False
        assert data["dismissed_at"] is None
        assert data["all_completed"] is False
        assert data["items"]["add_branding"]["completed"] is False
        assert data["items"]["create_first_plan"]["completed"] is False
        assert data["items"]["add_staff"]["completed"] is False
        assert data["items"]["register_first_member"]["completed"] is False

    def test_checklist_ticks_branding_from_color_or_logo(self, gym):
        config, _ = GymConfig.objects.get_or_create(gym=gym)
        config.brand_color = "#FF5500"
        config.save()

        data = get_first_run_checklist(gym)
        assert data["items"]["add_branding"]["completed"] is True

        config.brand_color = None
        config.logo = "logos/gym_logo.webp"
        config.save()

        data2 = get_first_run_checklist(gym)
        assert data2["items"]["add_branding"]["completed"] is True

    def test_checklist_ticks_staff_when_manager_or_trainer_added(self, gym):
        User.objects.create_user(
            email="manager@bole.com",
            password="Password123!",
            role=User.ROLE_MANAGER,
            gym=gym,
        )

        data = get_first_run_checklist(gym)
        assert data["items"]["add_staff"]["completed"] is True

    def test_checklist_ticks_member_when_member_registered(self, gym):
        User.objects.create_user(
            email="member@bole.com",
            password="Password123!",
            role=User.ROLE_MEMBER,
            gym=gym,
        )

        data = get_first_run_checklist(gym)
        assert data["items"]["register_first_member"]["completed"] is True

    def test_checklist_dismissal_persists(self, gym):
        data_before = get_first_run_checklist(gym)
        assert data_before["is_dismissed"] is False

        dismiss_first_run_checklist(gym)

        data_after = get_first_run_checklist(gym)
        assert data_after["is_dismissed"] is True
        assert data_after["dismissed_at"] is not None


@pytest.mark.django_db
class TestGymBrandingAndChecklistEndpoints:
    """Integration tests for checklist, settings, and public entry endpoints."""

    @pytest.fixture
    def gym_a(self):
        return GymTenant.objects.create(
            name="Gym Alpha",
            subdomain="gym-alpha",
            location="Bole, Addis Ababa",
            contact_phone="+251911223344",
            contact_email="contact@alpha.com",
            tls_confirmed_at=timezone.now(),
        )

    @pytest.fixture
    def gym_b(self):
        return GymTenant.objects.create(
            name="Gym Beta", subdomain="gym-beta", tls_confirmed_at=timezone.now()
        )

    @pytest.fixture
    def owner_a(self, gym_a):
        return User.objects.create_user(
            email="owner@alpha.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_a,
            must_change_password=False,
        )

    @pytest.fixture
    def manager_a(self, gym_a):
        return User.objects.create_user(
            email="manager@alpha.com",
            password="ManagerPassword123!",
            role=User.ROLE_MANAGER,
            gym=gym_a,
            must_change_password=False,
        )

    @pytest.fixture
    def member_a(self, gym_a):
        return User.objects.create_user(
            email="member@alpha.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
            must_change_password=False,
        )

    @pytest.fixture
    def super_admin(self):
        return User.objects.create_superuser(
            email="superadmin@fitgate.org",
            password="AdminPassword123!",
            must_change_password=False,
        )

    def auth_client(self, user):
        client = APIClient()
        tokens = get_tokens_for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        if user.gym:
            client.defaults["HTTP_HOST"] = f"{user.gym.subdomain}.localhost"
        else:
            client.defaults["HTTP_HOST"] = "localhost"
        return client

    # 1. Checklist access & dismissal
    def test_checklist_endpoint_owner_success(self, gym_a, owner_a):
        client = self.auth_client(owner_a)
        resp = client.get("/api/gym/checklist/")

        assert resp.status_code == 200
        assert "items" in resp.data
        assert resp.data["is_dismissed"] is False
        assert "add_branding" in resp.data["items"]

    def test_checklist_endpoint_manager_denied_with_403(self, gym_a, manager_a):
        client = self.auth_client(manager_a)
        resp = client.get("/api/gym/checklist/")

        assert resp.status_code == 403

    def test_checklist_dismiss_endpoint_owner_success(self, gym_a, owner_a):
        client = self.auth_client(owner_a)
        resp = client.post("/api/gym/checklist/dismiss/")

        assert resp.status_code == 200
        assert resp.data["is_dismissed"] is True
        assert resp.data["dismissed_at"] is not None

        # Verify subsequent GET returns is_dismissed = True
        get_resp = client.get("/api/gym/checklist/")
        assert get_resp.data["is_dismissed"] is True

    def test_checklist_dismiss_endpoint_manager_denied_with_403(self, gym_a, manager_a):
        client = self.auth_client(manager_a)
        resp = client.post("/api/gym/checklist/dismiss/")

        assert resp.status_code == 403

    # 2. Gym settings & branding updates
    def test_owner_can_update_branding_settings(self, gym_a, owner_a):
        client = self.auth_client(owner_a)
        payload = {
            "brand_color": "#1E90FF",
            "logo": "/media/logos/gym_a.webp",
            "show_unavailable_equipment": True,
            "member_reminder_days": [5, 1],
        }
        resp = client.patch("/api/gym/settings/", payload, format="json")

        assert resp.status_code == 200
        assert resp.data["brand_color"] == "#1E90FF"
        assert resp.data["logo"] == "/media/logos/gym_a.webp"
        assert resp.data["show_unavailable_equipment"] is True
        assert resp.data["member_reminder_days"] == [5, 1]

    def test_owner_cannot_update_entitlements_returns_403(self, gym_a, owner_a):
        client = self.auth_client(owner_a)

        # Attempt to modify tier
        resp_tier = client.patch(
            "/api/gym/settings/", {"tier": GymTenant.TIER_PRO}, format="json"
        )
        assert resp_tier.status_code == 403
        assert "entitlements" in resp_tier.data["detail"].lower()

        # Attempt to modify feature flag
        resp_flag = client.patch(
            "/api/gym/settings/", {"has_trainer_module": True}, format="json"
        )
        assert resp_flag.status_code == 403

        # Attempt to modify payment grace days
        resp_grace = client.patch(
            "/api/gym/settings/", {"payment_grace_days": 30}, format="json"
        )
        assert resp_grace.status_code == 403

    def test_manager_cannot_update_gym_settings_returns_403(self, gym_a, manager_a):
        client = self.auth_client(manager_a)
        resp = client.patch(
            "/api/gym/settings/", {"brand_color": "#00FF00"}, format="json"
        )
        assert resp.status_code == 403

    def test_invalid_hex_brand_color_returns_400(self, gym_a, owner_a):
        client = self.auth_client(owner_a)
        resp = client.patch(
            "/api/gym/settings/", {"brand_color": "not-a-color"}, format="json"
        )
        assert resp.status_code == 400

    def test_super_admin_can_update_entitlements(self, gym_a, super_admin):
        client = self.auth_client(super_admin)
        url = f"/api/platform/gyms/{gym_a.id}/config/"
        payload = {
            "has_trainer_module": True,
            "has_analytics": True,
            "freeze_days_allowed": 14,
        }
        resp = client.patch(url, payload, format="json")

        assert resp.status_code == 200
        assert resp.data["has_trainer_module"] is True
        assert resp.data["has_analytics"] is True
        assert resp.data["freeze_days_allowed"] == 14

    # 3. Public entry page
    def test_public_entry_before_tls_confirmation_returns_503(self, gym_a):
        client = APIClient()
        gym_a.tls_confirmed_at = None
        gym_a.save()

        resp = client.get(
            "/api/public/gym-entry/", HTTP_HOST=f"{gym_a.subdomain}.localhost"
        )
        assert resp.status_code == 503
        assert resp.data["still_securing"] is True
        assert resp.data["name"] == gym_a.name

    def test_public_entry_after_tls_confirmation_returns_200(self, gym_a):
        gym_a.tls_confirmed_at = timezone.now()
        gym_a.save()

        config, _ = GymConfig.objects.get_or_create(gym=gym_a)
        config.brand_color = "#3B82F6"
        config.logo = "/media/logos/gym_logo.webp"
        config.save()

        client = APIClient()
        resp = client.get(
            "/api/public/gym-entry/", HTTP_HOST=f"{gym_a.subdomain}.localhost"
        )

        assert resp.status_code == 200
        assert resp.data["still_securing"] is False
        assert resp.data["name"] == gym_a.name
        assert resp.data["subdomain"] == gym_a.subdomain
        assert resp.data["brand_color"] == "#3B82F6"
        assert resp.data["logo"] == "/media/logos/gym_logo.webp"
        assert resp.data["phone"] == gym_a.contact_phone
        assert resp.data["location"] == gym_a.location
        assert resp.data["currency"] == gym_a.currency
        assert resp.data["plans"] == []

    def test_public_entry_never_returns_another_gyms_data(self, gym_a, gym_b):
        gym_a.tls_confirmed_at = timezone.now()
        gym_a.save()
        gym_b.tls_confirmed_at = timezone.now()
        gym_b.save()

        client = APIClient()
        resp_a = client.get(
            "/api/public/gym-entry/", HTTP_HOST=f"{gym_a.subdomain}.localhost"
        )
        resp_b = client.get(
            "/api/public/gym-entry/", HTTP_HOST=f"{gym_b.subdomain}.localhost"
        )

        assert resp_a.data["name"] == gym_a.name
        assert resp_b.data["name"] == gym_b.name
        assert resp_a.data["name"] != resp_b.data["name"]
