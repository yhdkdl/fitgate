"""
Tests for Sprint 9a: Audit Log Viewer API endpoints.

Covers:
- Gym audit log view (/api/gym/audit-logs/) permissions: Owner & Manager allowed; Trainer, Reception, Member denied (403); unauthenticated denied (401).
- Platform audit log view (/api/platform/audit-logs/) permissions: Super Admin at apex allowed; others denied (403).
- Tenant isolation: Gym staff never see logs from other gyms or platform-level logs.
- Super Admin platform view: sees all gyms + platform rows; can filter by gym_id.
- Read-only enforcement: POST, PUT, PATCH, DELETE return 405 Method Not Allowed.
- Pagination: count, next, previous, results, custom page_size and page.
- Ordering: newest first (-timestamp).
- Filtering: date_from, date_to, action_type, actor_id, search query.
- Unified /api/audit-logs/ endpoint routing.
- RequirePasswordChanged enforcement.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="FitZone Bole",
        subdomain="fitzone",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    return tenant


@pytest.fixture
def other_gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="Apex Power Gym",
        subdomain="apexpower",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    return tenant


@pytest.fixture
def super_admin(db):
    return User.objects.create(
        email="superadmin@fitgate.com",
        role=User.ROLE_SUPER_ADMIN,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def gym_owner(db, gym_tenant):
    return User.objects.create(
        email="owner@fitzone.com",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def gym_manager(db, gym_tenant):
    return User.objects.create(
        email="manager@fitzone.com",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def gym_trainer(db, gym_tenant):
    return User.objects.create(
        email="trainer@fitzone.com",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def gym_reception(db, gym_tenant):
    return User.objects.create(
        email="reception@fitzone.com",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def gym_member(db, gym_tenant):
    return User.objects.create(
        email="member@fitzone.com",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


@pytest.fixture
def other_gym_owner(db, other_gym_tenant):
    return User.objects.create(
        email="owner@apexpower.com",
        role=User.ROLE_OWNER,
        gym=other_gym_tenant,
        is_active=True,
        email_verified_at=timezone.now(),
        must_change_password=False,
    )


def auth_client(client, user):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


# -------------------------------------------------------------------------
# RBAC & Access Control Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogPermissions:
    def test_unauthenticated_requests_receive_401(self, api_client, gym_tenant):
        resp_gym = api_client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_gym.status_code == 401

        resp_platform = api_client.get(
            "/api/platform/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp_platform.status_code == 401

    def test_owner_can_view_gym_audit_logs(self, api_client, gym_tenant, gym_owner):
        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert "results" in resp.data
        assert "count" in resp.data

    def test_manager_can_view_gym_audit_logs(self, api_client, gym_tenant, gym_manager):
        client = auth_client(api_client, gym_manager)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert "results" in resp.data

    def test_trainer_cannot_view_gym_audit_logs(
        self, api_client, gym_tenant, gym_trainer
    ):
        client = auth_client(api_client, gym_trainer)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_reception_cannot_view_gym_audit_logs(
        self, api_client, gym_tenant, gym_reception
    ):
        client = auth_client(api_client, gym_reception)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_member_cannot_view_gym_audit_logs(
        self, api_client, gym_tenant, gym_member
    ):
        client = auth_client(api_client, gym_member)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_super_admin_can_view_platform_audit_logs(self, api_client, super_admin):
        client = auth_client(api_client, super_admin)
        resp = client.get(
            "/api/platform/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert "results" in resp.data

    def test_super_admin_denied_on_gym_subdomain_for_platform_endpoint(
        self, api_client, super_admin, gym_tenant
    ):
        client = auth_client(api_client, super_admin)
        resp = client.get(
            "/api/platform/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code in (401, 403)

    def test_gym_owner_denied_on_platform_audit_logs(self, api_client, gym_owner):
        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/platform/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code in (401, 403)

    def test_require_password_changed_blocks_access(
        self, api_client, gym_tenant, gym_owner
    ):
        gym_owner.must_change_password = True
        gym_owner.save(update_fields=["must_change_password"])

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403
        assert resp.data.get("detail") == "password_change_required"


# -------------------------------------------------------------------------
# Tenant Isolation Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogTenantIsolation:
    def test_owner_only_sees_own_gym_audit_logs(
        self,
        api_client,
        gym_tenant,
        other_gym_tenant,
        gym_owner,
        other_gym_owner,
        super_admin,
    ):
        # Create log for Gym A
        log_a = AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-1",
        )
        # Create log for Gym B
        AuditLog.all_objects.create(
            gym=other_gym_tenant,
            actor=other_gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-2",
        )
        # Create platform log
        AuditLog.all_objects.create(
            gym=None,
            actor=super_admin,
            action_type="gym_created",
            affected_record_type="GymTenant",
            affected_record_id=str(gym_tenant.id),
        )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["id"] == str(log_a.id)
        assert resp.data["results"][0]["gym_id"] == str(gym_tenant.id)

    def test_super_admin_sees_all_gyms_and_platform_logs(
        self,
        api_client,
        gym_tenant,
        other_gym_tenant,
        gym_owner,
        other_gym_owner,
        super_admin,
    ):
        log_a = AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-1",
        )
        log_b = AuditLog.all_objects.create(
            gym=other_gym_tenant,
            actor=other_gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-2",
        )
        log_platform = AuditLog.all_objects.create(
            gym=None,
            actor=super_admin,
            action_type="gym_created",
            affected_record_type="GymTenant",
            affected_record_id=str(gym_tenant.id),
        )

        client = auth_client(api_client, super_admin)
        resp = client.get(
            "/api/platform/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 3
        ids = [row["id"] for row in resp.data["results"]]
        assert str(log_a.id) in ids
        assert str(log_b.id) in ids
        assert str(log_platform.id) in ids

    def test_super_admin_filter_by_gym_id(
        self,
        api_client,
        gym_tenant,
        other_gym_tenant,
        gym_owner,
        other_gym_owner,
        super_admin,
    ):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-1",
        )
        AuditLog.all_objects.create(
            gym=other_gym_tenant,
            actor=other_gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="mem-2",
        )

        client = auth_client(api_client, super_admin)
        resp = client.get(
            f"/api/platform/audit-logs/?gym_id={gym_tenant.id}",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["gym_id"] == str(gym_tenant.id)


# -------------------------------------------------------------------------
# Read-Only Enforcement Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogReadOnly:
    def test_mutation_methods_return_405_on_gym_endpoint(
        self, api_client, gym_tenant, gym_owner
    ):
        client = auth_client(api_client, gym_owner)
        host = f"{gym_tenant.subdomain}.localhost"

        assert (
            client.post("/api/gym/audit-logs/", {}, HTTP_HOST=host).status_code == 405
        )
        assert client.put("/api/gym/audit-logs/", {}, HTTP_HOST=host).status_code == 405
        assert (
            client.patch("/api/gym/audit-logs/", {}, HTTP_HOST=host).status_code == 405
        )
        assert client.delete("/api/gym/audit-logs/", HTTP_HOST=host).status_code == 405

    def test_mutation_methods_return_405_on_platform_endpoint(
        self, api_client, super_admin
    ):
        client = auth_client(api_client, super_admin)
        host = "localhost"

        assert (
            client.post("/api/platform/audit-logs/", {}, HTTP_HOST=host).status_code
            == 405
        )
        assert (
            client.put("/api/platform/audit-logs/", {}, HTTP_HOST=host).status_code
            == 405
        )
        assert (
            client.patch("/api/platform/audit-logs/", {}, HTTP_HOST=host).status_code
            == 405
        )
        assert (
            client.delete("/api/platform/audit-logs/", HTTP_HOST=host).status_code
            == 405
        )


# -------------------------------------------------------------------------
# Pagination & Ordering Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogPaginationAndOrdering:
    def test_newest_first_ordering(self, api_client, gym_tenant, gym_owner):
        base_time = timezone.now() - timedelta(hours=5)

        # Create 3 logs with sequential timestamps using mock patch
        with patch("django.utils.timezone.now", return_value=base_time):
            log1 = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="first_action",
                affected_record_type="Record",
                affected_record_id="1",
            )

        with patch(
            "django.utils.timezone.now", return_value=base_time + timedelta(hours=1)
        ):
            log2 = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="second_action",
                affected_record_type="Record",
                affected_record_id="2",
            )

        with patch(
            "django.utils.timezone.now", return_value=base_time + timedelta(hours=2)
        ):
            log3 = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="third_action",
                affected_record_type="Record",
                affected_record_id="3",
            )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        results = resp.data["results"]
        assert len(results) == 3
        # Should be ordered descending: log3, log2, log1
        assert results[0]["id"] == str(log3.id)
        assert results[1]["id"] == str(log2.id)
        assert results[2]["id"] == str(log1.id)

    def test_custom_page_size_and_navigation(self, api_client, gym_tenant, gym_owner):
        for i in range(5):
            AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type=f"action_{i}",
                affected_record_type="Record",
                affected_record_id=str(i),
            )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/?page_size=2&page=1",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 5
        assert len(resp.data["results"]) == 2
        assert resp.data["next"] is not None
        assert resp.data["previous"] is None

        # Next page
        resp_p2 = client.get(
            "/api/gym/audit-logs/?page_size=2&page=2",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_p2.status_code == 200
        assert len(resp_p2.data["results"]) == 2
        assert resp_p2.data["previous"] is not None


# -------------------------------------------------------------------------
# Filtering Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestAuditLogFiltering:
    def test_filter_by_action_type(self, api_client, gym_tenant, gym_owner):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="user_login",
            affected_record_type="User",
            affected_record_id=str(gym_owner.id),
        )
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="attendance_qr_scan",
            affected_record_type="Attendance",
            affected_record_id="att-1",
        )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/?action_type=attendance_qr_scan",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["action_type"] == "attendance_qr_scan"

    def test_filter_by_actor_id(self, api_client, gym_tenant, gym_owner, gym_manager):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="owner_action",
            affected_record_type="Config",
            affected_record_id="1",
        )
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_manager,
            action_type="manager_action",
            affected_record_type="Member",
            affected_record_id="2",
        )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            f"/api/gym/audit-logs/?actor_id={gym_manager.id}",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["actor"]["id"] == str(gym_manager.id)

    def test_filter_by_date_range(self, api_client, gym_tenant, gym_owner):
        now = timezone.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)

        with patch("django.utils.timezone.now", return_value=two_days_ago):
            log_old = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="old_event",
                affected_record_type="Record",
                affected_record_id="old",
            )

        with patch("django.utils.timezone.now", return_value=yesterday):
            log_mid = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="mid_event",
                affected_record_type="Record",
                affected_record_id="mid",
            )

        with patch("django.utils.timezone.now", return_value=now):
            log_now = AuditLog.all_objects.create(
                gym=gym_tenant,
                actor=gym_owner,
                action_type="now_event",
                affected_record_type="Record",
                affected_record_id="now",
            )

        client = auth_client(api_client, gym_owner)

        # Filter date_from yesterday
        resp = client.get(
            f"/api/gym/audit-logs/?date_from={(yesterday - timedelta(hours=1)).isoformat()}",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 2
        ids = [r["id"] for r in resp.data["results"]]
        assert str(log_now.id) in ids
        assert str(log_mid.id) in ids
        assert str(log_old.id) not in ids

        # Filter date_to yesterday
        resp_to = client.get(
            f"/api/gym/audit-logs/?date_to={(yesterday + timedelta(hours=1)).isoformat()}",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp_to.status_code == 200
        assert resp_to.data["count"] == 2
        ids_to = [r["id"] for r in resp_to.data["results"]]
        assert str(log_old.id) in ids_to
        assert str(log_mid.id) in ids_to
        assert str(log_now.id) not in ids_to

    def test_filter_by_search_query(self, api_client, gym_tenant, gym_owner):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="staff_provisioned",
            affected_record_type="User",
            affected_record_id="target-trainer-uuid",
        )
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="member_registered",
            affected_record_type="Member",
            affected_record_id="target-member-uuid",
        )

        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/gym/audit-logs/?search=provisioned",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["action_type"] == "staff_provisioned"


# -------------------------------------------------------------------------
# Unified /api/audit-logs/ Endpoint Tests
# -------------------------------------------------------------------------


@pytest.mark.django_db
class TestUnifiedAuditLogEndpoint:
    def test_unified_endpoint_on_gym_subdomain_for_owner(
        self, api_client, gym_tenant, gym_owner
    ):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="test_event",
            affected_record_type="Record",
            affected_record_id="1",
        )
        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/audit-logs/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_unified_endpoint_on_apex_for_super_admin(
        self, api_client, gym_tenant, gym_owner, super_admin
    ):
        AuditLog.all_objects.create(
            gym=gym_tenant,
            actor=gym_owner,
            action_type="test_event",
            affected_record_type="Record",
            affected_record_id="1",
        )
        client = auth_client(api_client, super_admin)
        resp = client.get(
            "/api/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == 200
        assert resp.data["count"] == 1

    def test_unified_endpoint_on_apex_denied_for_gym_owner(self, api_client, gym_owner):
        client = auth_client(api_client, gym_owner)
        resp = client.get(
            "/api/audit-logs/",
            HTTP_HOST="localhost",
        )
        assert resp.status_code in (401, 403)
