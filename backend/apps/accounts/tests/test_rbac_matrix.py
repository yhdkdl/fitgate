"""
Tests for Sprint 5: RBAC framework (GATE).

Covers:
- Enforcement of Owner/Manager permission matrix (SPEC §2).
- For every role in the matrix (Super Admin, Owner, Manager, Trainer, Reception, Member):
  - Both an allowed action (succeeds with 200/201) and a denied action (fails with 403, not 200).
- Entitlements vs. Settings:
  - Super Admin can change entitlements (tier, has_* flags, freeze_days_allowed, payment_grace_days, subscription_reminder_days).
  - Owner attempting to change any entitlement field receives 403 Forbidden at the API level.
  - Owner can change brand_color, member_reminder_days, logo, and show_unavailable_equipment (200).
  - Manager attempting to change any gym setting or entitlement receives 403 Forbidden.
- Cross-tenant isolation enforcement across all tenant roles.
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bole-hub",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    config = gym.config
    config.brand_color = "#2563EB"
    config.save()
    return gym


@pytest.fixture
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="Apex Kazanchis",
        subdomain="apex-kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_superuser(
        email="superadmin@fitgate.org",
        password="SuperPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner@bolehub.com",
        password="OwnerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager@bolehub.com",
        password="ManagerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MANAGER,
        must_change_password=False,
    )


@pytest.fixture
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ReceptionPassword123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def member_user(db, gym_tenant):
    return User.objects.create_user(
        email="member@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )


def auth_client(
    client: APIClient, user: User, tenant_subdomain: str | None = None
) -> APIClient:
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if tenant_subdomain:
        client.defaults["HTTP_HOST"] = f"{tenant_subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.mark.django_db
class TestRBACPermissionMatrixEveryRole:
    """
    Covers every role in SPEC §2 permission matrix:
    Both an allowed action (succeeds) and a denied action (403, not 200).
    """

    def test_super_admin_allowed_and_denied_actions(
        self, api_client, super_admin_user, gym_tenant
    ):
        client = auth_client(api_client, super_admin_user)

        # Allowed: View and modify gym entitlements at platform level
        url = f"/api/platform/gyms/{gym_tenant.id}/config/"
        resp = client.patch(
            url,
            {"has_trainer_module": True, "freeze_days_allowed": 15},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["has_trainer_module"] is True
        assert resp.data["freeze_days_allowed"] == 15

        # Denied: Unauthenticated access is rejected (401)
        unauth_client = APIClient()
        resp_unauth = unauth_client.patch(
            url, {"has_trainer_module": False}, format="json"
        )
        assert resp_unauth.status_code == 401

        # Denied: Super Admin with must_change_password=True gets 403 password_change_required
        super_admin_user.must_change_password = True
        super_admin_user.save(update_fields=["must_change_password"])
        resp_pw = client.patch(url, {"has_trainer_module": False}, format="json")
        assert resp_pw.status_code == 403
        assert resp_pw.data["detail"] == "password_change_required"

    def test_owner_allowed_and_denied_actions(self, api_client, owner_user, gym_tenant):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # Allowed: View and update gym settings (branding, reminders)
        resp_get = client.get("/api/gym/settings/")
        assert resp_get.status_code == 200

        resp_patch = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#1E40AF", "member_reminder_days": [5, 1]},
            format="json",
        )
        assert resp_patch.status_code == 200
        assert resp_patch.data["brand_color"] == "#1E40AF"

        # Allowed: View and dismiss first-run onboarding checklist
        resp_check = client.get("/api/gym/checklist/")
        assert resp_check.status_code == 200

        # Denied (403): Attempt to change entitlements
        resp_entitlement = client.patch(
            "/api/gym/settings/",
            {"has_trainer_module": True},
            format="json",
        )
        assert resp_entitlement.status_code == 403
        assert "entitlements" in resp_entitlement.data["detail"].lower()

        # Denied (403): Attempt to access platform Super Admin endpoints
        resp_platform = client.get("/api/platform/gyms/")
        assert resp_platform.status_code == 403

    def test_manager_allowed_and_denied_actions(
        self, api_client, manager_user, gym_tenant
    ):
        client = auth_client(api_client, manager_user, gym_tenant.subdomain)

        # Allowed: Read own profile and change profile info
        resp_profile = client.get("/api/auth/me/")
        assert resp_profile.status_code == 200
        assert resp_profile.data["email"] == manager_user.email

        # Denied (403): Attempt to update gym settings
        resp_settings = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#000000"},
            format="json",
        )
        assert resp_settings.status_code == 403

        # Denied (403): Attempt to access or dismiss first-run checklist
        resp_checklist = client.get("/api/gym/checklist/")
        assert resp_checklist.status_code == 403

        resp_dismiss = client.post("/api/gym/checklist/dismiss/")
        assert resp_dismiss.status_code == 403

        # Denied (403): Attempt to access platform endpoints
        resp_platform = client.get("/api/platform/gyms/")
        assert resp_platform.status_code == 403

    def test_trainer_allowed_and_denied_actions(
        self, api_client, trainer_user, gym_tenant
    ):
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)

        # Allowed: Read profile
        resp_me = client.get("/api/auth/me/")
        assert resp_me.status_code == 200

        # Denied (403): Attempt to update gym settings
        resp_settings = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#111111"},
            format="json",
        )
        assert resp_settings.status_code == 403

        # Denied (403): Attempt to view first-run checklist
        resp_checklist = client.get("/api/gym/checklist/")
        assert resp_checklist.status_code == 403

        # Denied (403): Attempt to upload gym logo
        resp_logo = client.post(f"/api/media/gym-logo/{gym_tenant.id}/")
        assert resp_logo.status_code == 403

    def test_reception_allowed_and_denied_actions(
        self, api_client, reception_user, gym_tenant
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        # Allowed: Read profile
        resp_me = client.get("/api/auth/me/")
        assert resp_me.status_code == 200

        # Denied (403): Attempt to update gym settings
        resp_settings = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#222222"},
            format="json",
        )
        assert resp_settings.status_code == 403

        # Denied (403): Attempt to access checklist
        resp_checklist = client.get("/api/gym/checklist/")
        assert resp_checklist.status_code == 403

    def test_member_allowed_and_denied_actions(
        self, api_client, member_user, gym_tenant
    ):
        client = auth_client(api_client, member_user, gym_tenant.subdomain)

        # Allowed: Read own profile
        resp_me = client.get("/api/auth/me/")
        assert resp_me.status_code == 200

        # Denied (403): Attempt to modify gym settings
        resp_settings = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#333333"},
            format="json",
        )
        assert resp_settings.status_code == 403

        # Denied (403): Attempt to view onboarding checklist
        resp_checklist = client.get("/api/gym/checklist/")
        assert resp_checklist.status_code == 403

        # Denied (403): Attempt to access platform Super Admin endpoints
        resp_platform = client.get("/api/platform/gyms/")
        assert resp_platform.status_code == 403


@pytest.mark.django_db
class TestEntitlementsVsSettingsEnforcement:
    """
    Detailed tests for Entitlements vs. Settings:
    - Owner attempting to change tier, any has_* flag, freeze_days_allowed,
      payment_grace_days, or subscription_reminder_days is rejected with 403.
    - Owner can change brand_color, member_reminder_days, logo, show_unavailable_equipment.
    - Manager cannot change any of them.
    - Super Admin can change entitlements.
    """

    ENTITLEMENT_ATTEMPTS = [
        ({"tier": "pro"}, "tier"),
        ({"has_trainer_module": True}, "has_trainer_module"),
        ({"has_ai_plans": True}, "has_ai_plans"),
        ({"has_analytics": True}, "has_analytics"),
        ({"has_group_classes": True}, "has_group_classes"),
        ({"has_multi_branch": True}, "has_multi_branch"),
        ({"freeze_days_allowed": 30}, "freeze_days_allowed"),
        ({"payment_grace_days": 14}, "payment_grace_days"),
        ({"subscription_reminder_days": [30, 15]}, "subscription_reminder_days"),
    ]

    @pytest.mark.parametrize("payload,field_name", ENTITLEMENT_ATTEMPTS)
    def test_owner_attempt_to_change_entitlement_is_rejected_with_403(
        self, api_client, owner_user, gym_tenant, payload, field_name
    ):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.patch("/api/gym/settings/", payload, format="json")
        assert resp.status_code == 403
        assert "entitlements" in resp.data["detail"].lower()

    def test_owner_allowed_settings_changes_succeed(
        self, api_client, owner_user, gym_tenant
    ):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        payload = {
            "brand_color": "#059669",
            "member_reminder_days": [10, 3],
            "show_unavailable_equipment": True,
        }
        resp = client.patch("/api/gym/settings/", payload, format="json")
        assert resp.status_code == 200
        assert resp.data["brand_color"] == "#059669"
        assert resp.data["member_reminder_days"] == [10, 3]
        assert resp.data["show_unavailable_equipment"] is True

    @pytest.mark.parametrize("payload,field_name", ENTITLEMENT_ATTEMPTS)
    def test_manager_attempt_to_change_entitlements_or_settings_is_rejected_with_403(
        self, api_client, manager_user, gym_tenant, payload, field_name
    ):
        client = auth_client(api_client, manager_user, gym_tenant.subdomain)
        resp = client.patch("/api/gym/settings/", payload, format="json")
        assert resp.status_code == 403

    def test_super_admin_can_change_all_entitlements(
        self, api_client, super_admin_user, gym_tenant
    ):
        client = auth_client(api_client, super_admin_user)
        url = f"/api/platform/gyms/{gym_tenant.id}/config/"
        payload = {
            "has_trainer_module": True,
            "has_ai_plans": True,
            "has_analytics": True,
            "has_group_classes": True,
            "has_multi_branch": True,
            "freeze_days_allowed": 45,
            "payment_grace_days": 10,
            "subscription_reminder_days": [21, 14, 7],
        }
        resp = client.patch(url, payload, format="json")
        assert resp.status_code == 200
        assert resp.data["has_trainer_module"] is True
        assert resp.data["has_ai_plans"] is True
        assert resp.data["has_analytics"] is True
        assert resp.data["has_group_classes"] is True
        assert resp.data["has_multi_branch"] is True
        assert resp.data["freeze_days_allowed"] == 45
        assert resp.data["payment_grace_days"] == 10
        assert resp.data["subscription_reminder_days"] == [21, 14, 7]


@pytest.mark.django_db
class TestCrossTenantRBACIsolation:
    """Verifies that an Owner cannot access or modify settings of another gym tenant."""

    def test_owner_cannot_modify_other_gym_settings(
        self, api_client, owner_user, gym_tenant, other_gym_tenant
    ):
        # Accessing another gym's subdomain with Gym A's token is rejected by tenant auth (401)
        client_sub = auth_client(api_client, owner_user, other_gym_tenant.subdomain)
        resp_sub = client_sub.patch(
            "/api/gym/settings/",
            {"brand_color": "#EF4444"},
            format="json",
        )
        assert resp_sub.status_code == 401

        # Attempting to modify another gym's config from own subdomain returns 403 Forbidden
        client_own_sub = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp_cross = client_own_sub.patch(
            f"/api/platform/gyms/{other_gym_tenant.id}/config/",
            {"brand_color": "#EF4444"},
            format="json",
        )
        assert resp_cross.status_code == 403

        # Apex platform access with gym user token is rejected by authentication (401)
        client_apex = auth_client(api_client, owner_user, None)
        resp_apex = client_apex.patch(
            f"/api/platform/gyms/{other_gym_tenant.id}/config/",
            {"brand_color": "#EF4444"},
            format="json",
        )
        assert resp_apex.status_code == 401
