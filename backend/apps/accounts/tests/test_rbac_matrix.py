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
from apps.accounts.permissions import (
    CanEditGymEntitlements,
    CanEditGymSettings,
    IsGymManager,
    IsGymOwner,
    IsGymStaff,
    IsMember,
    IsOwnerOrManager,
    IsOwnerOrSuperAdmin,
    IsReception,
    IsSuperAdmin,
    IsTrainer,
)
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymConfig, GymTenant
from apps.tenants.serializers import GymSettingsUpdateSerializer


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
    user = User.objects.create_user(
        email="member@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    from django.utils import timezone

    from apps.memberships.models import Member

    Member.objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Bole Member",
        phone="+251911999888",
        waiver_accepted_at=timezone.now(),
    )
    return user


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

        # Allowed (Sprint 6): Invite a Manager account
        resp_invite = client.post(
            "/api/gym/staff/",
            {"email": "invited_mgr@bolehub.com", "role": "manager"},
            format="json",
        )
        assert resp_invite.status_code == 201
        assert resp_invite.data["user"]["role"] == "manager"

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

        # Allowed (Sprint 6): Invite a Trainer account
        resp_invite_trainer = client.post(
            "/api/gym/staff/",
            {"email": "invited_trainer@bolehub.com", "role": "trainer"},
            format="json",
        )
        assert resp_invite_trainer.status_code == 201
        assert resp_invite_trainer.data["user"]["role"] == "trainer"

        # Denied (403, Sprint 6): Manager cannot invite a Manager account
        resp_invite_mgr = client.post(
            "/api/gym/staff/",
            {"email": "forbidden_mgr@bolehub.com", "role": "manager"},
            format="json",
        )
        assert resp_invite_mgr.status_code == 403

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

        # Allowed: Read own member profile
        resp_member_me = client.get("/api/members/me/")
        assert resp_member_me.status_code == 200

        # Denied (403): Attempt to register staff or members
        resp_reg = client.post("/api/gym/members/", {}, format="json")
        assert resp_reg.status_code == 403

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


@pytest.mark.django_db
class TestDirectPermissionClassTenantIsolation:
    """
    Direct invocation of permission classes with mock requests:
    - tenant None + gym user -> False
    - tenant of another gym -> False
    - matching tenant -> True
    - Super Admin on a gym host -> False
    """

    class FakeRequest:
        def __init__(self, user, tenant=None):
            self.user = user
            self.tenant = tenant

    GYM_PERMISSION_CASES = [
        (IsGymOwner, User.ROLE_OWNER),
        (IsGymManager, User.ROLE_MANAGER),
        (IsOwnerOrManager, User.ROLE_OWNER),
        (IsOwnerOrManager, User.ROLE_MANAGER),
        (IsGymStaff, User.ROLE_OWNER),
        (IsGymStaff, User.ROLE_MANAGER),
        (IsGymStaff, User.ROLE_TRAINER),
        (IsGymStaff, User.ROLE_RECEPTION),
        (IsTrainer, User.ROLE_TRAINER),
        (IsReception, User.ROLE_RECEPTION),
        (IsMember, User.ROLE_MEMBER),
        (CanEditGymSettings, User.ROLE_OWNER),
        (IsOwnerOrSuperAdmin, User.ROLE_OWNER),
    ]

    @pytest.mark.parametrize("perm_cls,role", GYM_PERMISSION_CASES)
    def test_gym_permission_classes_fail_closed_tenant_checks(
        self, perm_cls, role, gym_tenant, other_gym_tenant, super_admin_user
    ):
        perm = perm_cls()
        view = None
        user = User.objects.create_user(
            email=f"perm_{role}_{perm_cls.__name__}@bolehub.com",
            password="Password123!",
            gym=gym_tenant,
            role=role,
        )

        # 1. Matching tenant -> True
        req_match = self.FakeRequest(user=user, tenant=gym_tenant)
        assert perm.has_permission(req_match, view) is True

        # 2. tenant None (apex) + gym user -> False
        req_apex = self.FakeRequest(user=user, tenant=None)
        assert perm.has_permission(req_apex, view) is False

        # 3. tenant of another gym -> False
        req_other = self.FakeRequest(user=user, tenant=other_gym_tenant)
        assert perm.has_permission(req_other, view) is False

        # 4. Super Admin on a gym host -> False
        req_super_gym = self.FakeRequest(user=super_admin_user, tenant=gym_tenant)
        assert perm.has_permission(req_super_gym, view) is False

    def test_super_admin_classes_require_tenant_none(
        self, super_admin_user, gym_tenant, owner_user
    ):
        for perm_cls in [IsSuperAdmin, CanEditGymEntitlements]:
            perm = perm_cls()
            view = None

            # Super Admin at apex (tenant is None) -> True
            assert (
                perm.has_permission(
                    self.FakeRequest(super_admin_user, tenant=None), view
                )
                is True
            )

            # Super Admin on gym host (tenant is set) -> False
            assert (
                perm.has_permission(
                    self.FakeRequest(super_admin_user, tenant=gym_tenant), view
                )
                is False
            )

            # Gym user at apex -> False
            assert (
                perm.has_permission(self.FakeRequest(owner_user, tenant=None), view)
                is False
            )

            # Gym user on gym host -> False
            assert (
                perm.has_permission(
                    self.FakeRequest(owner_user, tenant=gym_tenant), view
                )
                is False
            )


@pytest.mark.django_db
class TestOwnerSettingsAllowListAndIntrospection:
    """
    Tests for Owner settings allow-list enforcement, mixed payload atomicity,
    and model field classification introspection.
    """

    def test_unknown_field_rejected_with_400(self, api_client, owner_user, gym_tenant):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#123456", "custom_unrecognized_field": "exploit"},
            format="json",
        )
        assert resp.status_code == 400
        assert "custom_unrecognized_field" in resp.data

    def test_entitlement_field_rejected_with_403(
        self, api_client, owner_user, gym_tenant
    ):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.patch(
            "/api/gym/settings/",
            {"tier": "pro"},
            format="json",
        )
        assert resp.status_code == 403
        assert "entitlements" in resp.data["detail"].lower()

    def test_mixed_payload_changes_nothing_in_database(
        self, api_client, owner_user, gym_tenant
    ):
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        original_brand = gym_tenant.config.brand_color
        original_tier = gym_tenant.tier

        resp = client.patch(
            "/api/gym/settings/",
            {"brand_color": "#FF0000", "tier": "pro"},
            format="json",
        )
        assert resp.status_code == 403

        gym_tenant.refresh_from_db()
        gym_tenant.config.refresh_from_db()

        assert gym_tenant.config.brand_color == original_brand
        assert gym_tenant.tier == original_tier

    def test_model_fields_are_exhaustively_classified(self):
        """
        Introspects GymConfig and GymTenant model fields.
        Fails if any field is added that is neither on the allow-list nor explicitly
        marked entitlement or infrastructure, preventing future flags from becoming
        Owner-editable by accident.
        """
        allowlist = GymSettingsUpdateSerializer.ALLOWED_FIELDS
        entitlements = GymSettingsUpdateSerializer.ENTITLEMENT_FIELDS

        # GymConfig concrete fields:
        system_config_fields = {
            "gym",
            "logo",  # Managed exclusively via dedicated upload endpoint POST /api/media/gym-logo/<gym_id>/
            "chapa_merchant_id",
            "first_run_dismissed_at",
        }
        gym_config_fields = {f.name for f in GymConfig._meta.concrete_fields}
        unclassified_config_fields = (
            gym_config_fields - allowlist - entitlements - system_config_fields
        )
        assert not unclassified_config_fields, (
            f"Found unclassified fields on GymConfig: {unclassified_config_fields}. "
            f"Every field must be explicitly classified in ALLOWED_FIELDS, ENTITLEMENT_FIELDS, or system fields."
        )

        # GymTenant concrete fields:
        system_tenant_fields = {
            "id",
            "name",
            "subdomain",
            "status",
            "currency",
            "location",
            "contact_name",
            "contact_phone",
            "contact_email",
            "subscription_expires_at",
            "tls_confirmed_at",
            "lapse_flagged_at",
            "suspended_at",
            "is_demo",
            "created_at",
            "updated_at",
        }
        gym_tenant_fields = {f.name for f in GymTenant._meta.concrete_fields}
        unclassified_tenant_fields = (
            gym_tenant_fields - entitlements - system_tenant_fields
        )
        assert (
            not unclassified_tenant_fields
        ), f"Found unclassified fields on GymTenant: {unclassified_tenant_fields}."


@pytest.mark.django_db
class TestSpec2PermissionMatrixParametrizedTable:
    """
    Encodes the exact 11 rows of SPEC §2's permission matrix (Table 3.1a):
    Actions x (Super Admin, Owner, Manager, Trainer, Reception, Member).
    Includes a wired_in_sprint column cross-referenced with docs/SPRINTS.md.
    Rows without a real endpoint yet are skipped with an explicit reason.
    Rows with real endpoints are tested directly against those endpoints.
    """

    SPEC_2_ROWS = [
        {
            "row_name": "Edit entitlements: tier, has_* flags, freeze allowance, grace and subscription-reminder days",
            "spec_super_admin": "Yes",
            "spec_owner": "No",
            "spec_manager": "No",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": True,
            "owner": False,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 5,
        },
        {
            "row_name": "Edit gym settings: branding, member reminder days, payment credentials",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "No",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 5,
        },
        {
            "row_name": "Create or deactivate Manager accounts",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "No",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 6,
        },
        {
            "row_name": "Create or deactivate Trainer/Reception accounts",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 6,
        },
        {
            "row_name": "Create/edit membership plans and pricing",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 10,
        },
        {
            "row_name": "Suspend or reactivate a member",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 10,
        },
        {
            "row_name": "Approve or reject a freeze request",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 13,
        },
        {
            "row_name": "Manually reassign a trainer",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 17,
        },
        {
            "row_name": "View audit log",
            "spec_super_admin": "All gyms",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": True,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": "9a",
        },
        {
            "row_name": "View payment history",
            "spec_super_admin": "All gyms",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": True,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 12,
        },
        {
            "row_name": "View analytics dashboard",
            "spec_super_admin": "All gyms",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "see SPEC §5",
            "spec_member": "see SPEC §5",
            "super_admin": True,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 27,
        },
        {
            "row_name": "Confirm a manual cash payment",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5",
            "spec_reception": "Yes (see SPEC §5: 'Manual cash payment by Reception/Manager: amount and optional reference note; activates immediately and generates a digital receipt.')",
            "spec_member": "see SPEC §5",
            "super_admin": False,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": True,
            "member": False,
            "wired_in_sprint": 12,
        },
        {
            "row_name": "Post a notice board announcement",
            "spec_super_admin": "Platform notices",
            "spec_owner": "Yes",
            "spec_manager": "Yes",
            "spec_trainer": "see SPEC §5 (see SPEC §5: 'Owner/Manager notice-board announcements visible to all members of the gym.')",
            "spec_reception": "see SPEC §5 (see SPEC §5: 'Owner/Manager notice-board announcements visible to all members of the gym.')",
            "spec_member": "see SPEC §5 (see SPEC §5: 'Owner/Manager notice-board announcements visible to all members of the gym.')",
            "super_admin": True,
            "owner": True,
            "manager": True,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 28,
        },
        {
            "row_name": "Configure payment gateway credentials",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "No",
            "spec_trainer": "No",
            "spec_reception": "No",
            "spec_member": "No",
            "super_admin": False,
            "owner": True,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 11,
        },
        {
            "row_name": "Test payment gateway connection",
            "spec_super_admin": "—",
            "spec_owner": "Yes",
            "spec_manager": "No",
            "spec_trainer": "No",
            "spec_reception": "No",
            "spec_member": "No",
            "super_admin": False,
            "owner": True,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 11,
        },
        {
            "row_name": "Initiate online Chapa checkout session",
            "spec_super_admin": "—",
            "spec_owner": "No (Members only; staff use cash flow in Sprint 12)",
            "spec_manager": "No (Members only; staff use cash flow in Sprint 12)",
            "spec_trainer": "No",
            "spec_reception": "No (Members only; staff use cash flow in Sprint 12)",
            "spec_member": "Yes",
            "super_admin": False,
            "owner": False,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": True,
            "wired_in_sprint": 11,
        },
        {
            "row_name": "View platform-wide payment status for gyms",
            "spec_super_admin": "Yes",
            "spec_owner": "No",
            "spec_manager": "No",
            "spec_trainer": "No",
            "spec_reception": "No",
            "spec_member": "No",
            "super_admin": True,
            "owner": False,
            "manager": False,
            "trainer": False,
            "reception": False,
            "member": False,
            "wired_in_sprint": 11,
        },
    ]

    MATRIX_TEST_CASES = []
    for row in SPEC_2_ROWS:
        for r_name in [
            User.ROLE_SUPER_ADMIN,
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_TRAINER,
            User.ROLE_RECEPTION,
            User.ROLE_MEMBER,
        ]:
            expected = row[r_name]
            MATRIX_TEST_CASES.append(
                (row["row_name"], r_name, expected, row["wired_in_sprint"])
            )

    @pytest.mark.parametrize(
        "row_name,role,expected_allowed,wired_sprint",
        MATRIX_TEST_CASES,
    )
    def test_spec_2_permission_matrix_endpoint_enforcement(
        self,
        row_name,
        role,
        expected_allowed,
        wired_sprint,
        gym_tenant,
        super_admin_user,
        owner_user,
        manager_user,
        trainer_user,
        reception_user,
        member_user,
    ):
        """
        Verify every row of SPEC §2 Table 3.1a.
        Rows not yet wired skip with an explicit reason.
        Wired rows (Sprint 5) assert directly against real HTTP endpoints.
        """
        if wired_sprint not in (5, 6, "9a", 10, 11):
            pytest.skip(
                f"Row '{row_name}' has no real endpoint yet (scheduled for Sprint {wired_sprint} in docs/SPRINTS.md)"
            )

        users_by_role = {
            User.ROLE_SUPER_ADMIN: super_admin_user,
            User.ROLE_OWNER: owner_user,
            User.ROLE_MANAGER: manager_user,
            User.ROLE_TRAINER: trainer_user,
            User.ROLE_RECEPTION: reception_user,
            User.ROLE_MEMBER: member_user,
        }
        acting_user = users_by_role[role]
        tokens = get_tokens_for_user(acting_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        if (
            row_name
            == "Edit entitlements: tier, has_* flags, freeze allowance, grace and subscription-reminder days"
        ):
            url = f"/api/platform/gyms/{gym_tenant.id}/config/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.patch(
                url, {"has_ai_plans": True}, format="json", HTTP_HOST=host
            )
            if expected_allowed:
                assert resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif (
            row_name
            == "Edit gym settings: branding, member reminder days, payment credentials"
        ):
            url = "/api/gym/settings/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.patch(
                url, {"brand_color": "#10B981"}, format="json", HTTP_HOST=host
            )
            if expected_allowed:
                assert resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Create or deactivate Manager accounts":
            url = "/api/gym/staff/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.post(
                url,
                {"email": f"matrix_mgr_{role}@bolehub.com", "role": "manager"},
                format="json",
                HTTP_HOST=host,
            )
            if expected_allowed:
                assert resp.status_code == 201
                new_id = resp.data["user"]["id"]
                deact_resp = client.post(
                    f"/api/gym/staff/{new_id}/deactivate/",
                    format="json",
                    HTTP_HOST=host,
                )
                assert deact_resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Create or deactivate Trainer/Reception accounts":
            url = "/api/gym/staff/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.post(
                url,
                {
                    "email": f"matrix_rec_{role}@bolehub.com",
                    "role": "reception",
                },
                format="json",
                HTTP_HOST=host,
            )
            if expected_allowed:
                assert resp.status_code == 201
                new_id = resp.data["user"]["id"]
                deact_resp = client.post(
                    f"/api/gym/staff/{new_id}/deactivate/",
                    format="json",
                    HTTP_HOST=host,
                )
                assert deact_resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "View audit log":
            if role == User.ROLE_SUPER_ADMIN:
                url = "/api/platform/audit-logs/"
                host = "localhost"
            else:
                url = "/api/gym/audit-logs/"
                host = f"{gym_tenant.subdomain}.localhost"

            resp = client.get(url, HTTP_HOST=host)
            if expected_allowed:
                assert resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Create/edit membership plans and pricing":
            url = "/api/gym/plans/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.post(
                url,
                {
                    "name": f"Matrix Plan {role}",
                    "duration_value": 1,
                    "duration_unit": "months",
                    "price_etb": "1500.00",
                },
                format="json",
                HTTP_HOST=host,
            )
            if expected_allowed:
                assert resp.status_code == 201
                plan_id = resp.data["id"]
                patch_resp = client.patch(
                    f"/api/gym/plans/{plan_id}/",
                    {"price_etb": "1800.00"},
                    format="json",
                    HTTP_HOST=host,
                )
                assert patch_resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Suspend or reactivate a member":
            url = f"/api/gym/members/{member_user.member_profile.id}/suspend/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.post(
                url,
                {"reason": "Testing matrix suspension"},
                format="json",
                HTTP_HOST=host,
            )
            if expected_allowed:
                assert resp.status_code == 200
                react_resp = client.post(
                    f"/api/gym/members/{member_user.member_profile.id}/reactivate/",
                    format="json",
                    HTTP_HOST=host,
                )
                assert react_resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Configure payment gateway credentials":
            url = "/api/gym/payment-config/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.get(url, HTTP_HOST=host)
            if expected_allowed:
                assert resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Test payment gateway connection":
            url = "/api/gym/payment-config/test/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.post(url, HTTP_HOST=host)
            if expected_allowed:
                # 400 because unconfigured credentials in matrix fixture, but authorized past RBAC check
                assert resp.status_code in (200, 400)
                assert resp.status_code not in (401, 403, 404)
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "Initiate online Chapa checkout session":
            from apps.memberships.models import MembershipPlan

            plan = MembershipPlan.objects.filter(gym=gym_tenant).first()
            if not plan:
                plan = MembershipPlan.objects.create(
                    gym=gym_tenant,
                    name="RBAC Matrix Plan",
                    duration_value=1,
                    duration_unit="months",
                    price_etb=1200,
                )
            url = "/api/payments/checkout/chapa/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            payload = {"plan_id": str(plan.id)}
            resp = client.post(url, payload, format="json", HTTP_HOST=host)
            if expected_allowed:
                # 400 because payment config is unverified, but authorized past RBAC check
                assert resp.status_code in (200, 400)
                assert resp.status_code not in (401, 403, 404)
            else:
                assert resp.status_code in (403, 404)
        elif row_name == "View platform-wide payment status for gyms":
            url = f"/api/platform/gyms/{gym_tenant.id}/payment-status/"
            host = (
                "localhost"
                if role == User.ROLE_SUPER_ADMIN
                else f"{gym_tenant.subdomain}.localhost"
            )
            resp = client.get(url, HTTP_HOST=host)
            if expected_allowed:
                assert resp.status_code == 200
            else:
                assert resp.status_code in (403, 404)

    def test_chapa_webhook_endpoint_is_public_with_signature_check(self, gym_tenant):
        """Webhook endpoint is public at transport layer and rejects bad payload without JWT."""
        client = APIClient()
        resp = client.post(
            "/api/webhooks/chapa/",
            data=b"{}",
            content_type="application/json",
            HTTP_HOST="localhost",
        )
        # Unauthenticated request is processed without JWT auth; missing/bad signature gives 401 signature error
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid webhook signature."
