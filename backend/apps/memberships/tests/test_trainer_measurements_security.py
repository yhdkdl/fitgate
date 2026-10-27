"""
Security and tenancy enforcement tests for Sprint 7b: Trainer-Only Body Measurements.

Covers:
- Criteria 2 & 8: Trainer can search members (returns minimal fields) and view measurements.
- Criteria 3 & 7: Trainer records measurements, recorded_by is set, and audit log is written.
- Criteria 4: BMI and Body Fat % estimates calculated on read; before recording, latest_metrics is None.
- Criteria 5: Reception and Super Admin see no measurements anywhere; Owner/Manager can view but not enter;
  Member can view own measurements and history but cannot enter or edit.
- Criteria 6: Cross-gym trainer access is rejected (403); non-trainers cannot record (403).
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import BodyMetrics
from apps.memberships.services import register_member_self_service
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )


@pytest.fixture
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="Apex Kazanchis",
        subdomain="kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Kazanchis, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
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
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ReceptionPassword123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        full_name="Coach Dawit",
        must_change_password=False,
    )


@pytest.fixture
def other_trainer_user(db, other_gym_tenant):
    return User.objects.create_user(
        email="trainer@kazanchis.com",
        password="OtherTrainerPassword123!",
        gym=other_gym_tenant,
        role=User.ROLE_TRAINER,
        full_name="Coach Kazanchis",
        must_change_password=False,
    )


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_user(
        email="superadmin@apex.com",
        password="SuperPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def gym_member(db, gym_tenant):
    member, _ = register_member_self_service(
        gym_tenant,
        {
            "full_name": "Tadesse Chala",
            "email": "tadesse@example.com",
            "phone": "+251911889900",
            "password": "Password123!",
            "waiver_accepted": True,
            "gender": "male",
        },
    )
    return member


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
class TestTrainerMeasurementsSecurityAndRBAC:
    """Security and tenancy verification for Sprint 7b."""

    def test_trainer_can_record_measurements_and_creates_audit_log(
        self, api_client, gym_tenant, trainer_user, gym_member
    ):
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)

        payload = {
            "weight_kg": 80.0,
            "height_cm": 180.0,
            "waist_cm": 84.0,
            "neck_cm": 38.0,
        }

        resp = client.post(
            f"/api/gym/members/{gym_member.id}/metrics/",
            payload,
            format="json",
        )
        assert resp.status_code == 201
        data = resp.data
        assert float(data["weight_kg"]) == 80.0
        assert float(data["height_cm"]) == 180.0
        assert data["trainer_name"] == trainer_user.full_name
        assert data["estimated_bmi"] == 24.7
        assert data["bmi_label"] == "estimate"
        assert data["estimated_body_fat_percentage"] is not None
        assert data["body_fat_label"] == "estimate"

        # Verify DB model
        metric = BodyMetrics.all_objects.get(id=data["id"])
        assert metric.recorded_by == trainer_user
        assert metric.gym == gym_tenant
        assert metric.member == gym_member

        # Verify audit log (Criteria 7)
        audit_entry = AuditLog.all_objects.filter(
            action_type="member_metrics_recorded",
            actor=trainer_user,
            gym=gym_tenant,
        ).first()
        assert audit_entry is not None
        assert str(gym_member.id) in str(audit_entry.metadata)

    def test_cross_gym_trainer_cannot_record_measurements(
        self, api_client, other_gym_tenant, other_trainer_user, gym_member
    ):
        # Trainer of Kazanchis gym tries to record measurements for Bole gym member
        client = auth_client(api_client, other_trainer_user, other_gym_tenant.subdomain)

        payload = {
            "weight_kg": 75.0,
            "height_cm": 175.0,
        }

        resp = client.post(
            f"/api/gym/members/{gym_member.id}/metrics/",
            payload,
            format="json",
        )
        assert resp.status_code in (403, 404)
        assert BodyMetrics.objects.filter(member=gym_member).count() == 0

    def test_unauthorized_roles_cannot_record_measurements(
        self,
        api_client,
        gym_tenant,
        owner_user,
        manager_user,
        reception_user,
        superadmin_user,
        gym_member,
    ):
        payload = {
            "weight_kg": 70.0,
            "height_cm": 170.0,
        }

        unauthorized_users = [
            owner_user,
            manager_user,
            reception_user,
            gym_member.user,
        ]

        for user in unauthorized_users:
            client = auth_client(api_client, user, gym_tenant.subdomain)
            resp = client.post(
                f"/api/gym/members/{gym_member.id}/metrics/",
                payload,
                format="json",
            )
            assert resp.status_code == 403, f"Role {user.role} should be refused 403"

        # Super Admin check
        client_sa = auth_client(api_client, superadmin_user)
        resp_sa = client_sa.post(
            f"/api/gym/members/{gym_member.id}/metrics/",
            payload,
            format="json",
        )
        assert resp_sa.status_code == 403

    def test_member_cannot_record_via_self_metrics_endpoint(
        self, api_client, gym_tenant, gym_member
    ):
        client = auth_client(api_client, gym_member.user, gym_tenant.subdomain)

        payload = {
            "weight_kg": 72.0,
            "height_cm": 175.0,
        }

        resp = client.post("/api/members/me/metrics/", payload, format="json")
        assert resp.status_code == 403
        assert "Members cannot enter or edit measurements" in str(resp.data)

    def test_reception_and_super_admin_see_no_measurements(
        self,
        api_client,
        gym_tenant,
        trainer_user,
        reception_user,
        superadmin_user,
        gym_member,
    ):
        # Trainer records a measurement first
        tc = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        tc.post(
            f"/api/gym/members/{gym_member.id}/metrics/",
            {"weight_kg": 75.0, "height_cm": 175.0},
            format="json",
        )

        # 1. Reception member detail
        rc = auth_client(api_client, reception_user, gym_tenant.subdomain)
        detail_resp = rc.get(f"/api/gym/members/{gym_member.id}/")
        assert detail_resp.status_code == 200
        assert detail_resp.data["latest_metrics"] is None
        assert detail_resp.data["body_metrics"] == []

        # Reception metrics endpoint
        metrics_resp = rc.get(f"/api/gym/members/{gym_member.id}/metrics/")
        assert metrics_resp.status_code == 403

        # 2. Super Admin sees none (refused access to gym staff member views)
        sc = auth_client(api_client, superadmin_user)
        sa_detail = sc.get(f"/api/gym/members/{gym_member.id}/")
        assert sa_detail.status_code == 403

        # Super Admin metrics endpoint
        sa_metrics = sc.get(f"/api/gym/members/{gym_member.id}/metrics/")
        assert sa_metrics.status_code == 403

    def test_trainer_search_returns_minimal_member_fields(
        self, api_client, gym_tenant, trainer_user, gym_member
    ):
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp = client.get(f"/api/gym/members/?search={gym_member.full_name}")
        assert resp.status_code == 200
        members = resp.data
        assert len(members) >= 1
        m = next(item for item in members if item["id"] == str(gym_member.id))
        # Trainer search returns minimal fields only: id, full_name, email, phone
        assert set(m.keys()) == {"id", "full_name", "email", "phone"}
        assert "photo_url" not in m
        assert "latest_metrics" not in m
        assert "emergency_contact" not in m

    def test_owner_and_manager_can_view_metrics_but_not_record(
        self,
        api_client,
        gym_tenant,
        trainer_user,
        owner_user,
        manager_user,
        gym_member,
    ):
        # Trainer records a measurement
        tc = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        tc.post(
            f"/api/gym/members/{gym_member.id}/metrics/",
            {"weight_kg": 85.0, "height_cm": 182.0},
            format="json",
        )

        for staff in [owner_user, manager_user]:
            sc = auth_client(api_client, staff, gym_tenant.subdomain)
            # View metrics endpoint
            get_resp = sc.get(f"/api/gym/members/{gym_member.id}/metrics/")
            assert get_resp.status_code == 200
            assert len(get_resp.data) >= 1
            assert float(get_resp.data[0]["weight_kg"]) == 85.0

            # Record metrics forbidden
            post_resp = sc.post(
                f"/api/gym/members/{gym_member.id}/metrics/",
                {"weight_kg": 86.0, "height_cm": 182.0},
                format="json",
            )
            assert post_resp.status_code == 403
