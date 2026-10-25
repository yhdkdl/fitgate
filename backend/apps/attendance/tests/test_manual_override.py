"""
Tests for manual attendance check-in override by staff (Reception, Manager, Owner).
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant


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
        must_change_password=False,
    )


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin@fitgate.org",
        password="SuperAdminPassword123!",
        gym=None,
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def active_member(db, gym_tenant):
    user = User.objects.create_user(
        email="member1@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Abebe Bikila",
        phone="+251911001122",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
        photo_url="/media/member_photos/abebe.webp",
    )
    today = timezone.localdate()
    MemberSubscription.all_objects.create(
        gym=gym_tenant,
        member=member,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member


def create_extra_member(gym_tenant, email, full_name, phone):
    user = User.objects.create_user(
        email=email,
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name=full_name,
        phone=phone,
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
        photo_url=f"/media/member_photos/{phone}.webp",
    )
    today = timezone.localdate()
    MemberSubscription.all_objects.create(
        gym=gym_tenant,
        member=member,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member


@pytest.mark.django_db
class TestManualOverrideFlow:
    """Detailed test suite for manual attendance check-in override."""

    def test_manual_override_success_creates_attendance_and_audit_log(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        assert Attendance.all_objects.count() == 0
        assert AuditLog.all_objects.count() == 0

        payload = {
            "member_id": str(active_member.id),
            "reason": "Member phone battery died at entrance",
        }
        response = client.post(
            "/api/gym/attendance/manual-override/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["status"] == "success"
        assert response.data["attendance"]["is_override"] is True
        assert response.data["attendance"]["method"] == "manual_override"
        assert (
            response.data["attendance"]["override_reason"]
            == "Member phone battery died at entrance"
        )
        assert response.data["member"]["photo_url"].startswith(
            f"/api/media/member-photos/{gym_tenant.id}/"
        )

        # Exactly one Attendance row created
        assert Attendance.all_objects.count() == 1
        att = Attendance.all_objects.first()
        assert att.member == active_member
        assert att.is_override is True
        assert att.method == Attendance.METHOD_MANUAL_OVERRIDE
        assert att.override_reason == "Member phone battery died at entrance"
        assert att.recorded_by == reception_user

        # AuditLog entry created
        audit_entries = AuditLog.all_objects.filter(
            action_type="attendance_manual_override",
            affected_record_type="Attendance",
            affected_record_id=str(att.id),
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.actor == reception_user
        assert entry.gym == gym_tenant
        assert entry.metadata["reason"] == "Member phone battery died at entrance"

    def test_owner_manager_reception_each_allowed_on_override(
        self, api_client, gym_tenant, owner_user, manager_user, reception_user
    ):
        """Owner, Manager and Reception are each allowed on override (real 201)."""
        m_owner = create_extra_member(
            gym_tenant, "m_owner@bolehub.com", "Member Owner", "+251911111111"
        )
        m_mgr = create_extra_member(
            gym_tenant, "m_mgr@bolehub.com", "Member Mgr", "+251922222222"
        )
        m_rec = create_extra_member(
            gym_tenant, "m_rec@bolehub.com", "Member Rec", "+251933333333"
        )

        # 1. Owner override succeeds
        client_owner = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp_owner = client_owner.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(m_owner.id),
                "reason": "Owner authorized manual check-in",
            },
            format="json",
        )
        assert resp_owner.status_code == 201

        # 2. Manager override succeeds
        client_mgr = auth_client(api_client, manager_user, gym_tenant.subdomain)
        resp_mgr = client_mgr.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(m_mgr.id),
                "reason": "Manager authorized manual check-in",
            },
            format="json",
        )
        assert resp_mgr.status_code == 201

        # 3. Reception override succeeds
        client_rec = auth_client(api_client, reception_user, gym_tenant.subdomain)
        resp_rec = client_rec.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(m_rec.id),
                "reason": "Reception authorized manual check-in",
            },
            format="json",
        )
        assert resp_rec.status_code == 201

    def test_trainer_and_super_admin_get_403_on_manual_override(
        self, api_client, gym_tenant, trainer_user, super_admin_user, active_member
    ):
        """Trainer and Super Admin (at a gym host) get 403 on manual override."""
        payload = {
            "member_id": str(active_member.id),
            "reason": "Unauthorized override attempt",
        }

        # Trainer gets 403
        client_trainer = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp_trainer = client_trainer.post(
            "/api/gym/attendance/manual-override/", payload, format="json"
        )
        assert resp_trainer.status_code == 403

        # Super Admin at gym host gets 403 via CanManageAttendance
        client_sa = APIClient()
        client_sa.force_authenticate(user=super_admin_user)
        client_sa.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        resp_sa = client_sa.post(
            "/api/gym/attendance/manual-override/", payload, format="json"
        )
        assert resp_sa.status_code == 403

        assert Attendance.all_objects.count() == 0

    def test_must_change_password_blocked_on_manual_override(
        self, api_client, gym_tenant, active_member
    ):
        """A user with must_change_password=True is blocked on manual override."""
        reception_locked = User.objects.create_user(
            email="reception_locked@bolehub.com",
            password="ReceptionPassword123!",
            gym=gym_tenant,
            role=User.ROLE_RECEPTION,
            must_change_password=True,
        )
        client = auth_client(api_client, reception_locked, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/manual-override/",
            {"member_id": str(active_member.id), "reason": "Password change pending"},
            format="json",
        )
        assert response.status_code == 403
        assert response.data["detail"] == "password_change_required"
        assert Attendance.all_objects.count() == 0

    def test_manual_override_requires_non_empty_reason(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        response = client.post(
            "/api/gym/attendance/manual-override/",
            {"member_id": str(active_member.id), "reason": "   "},
            format="json",
        )
        assert response.status_code == 400
        assert Attendance.all_objects.count() == 0

    @pytest.mark.parametrize(
        "sub_status,expected_reason",
        [
            (MemberSubscription.STATUS_EXPIRED, "expired"),
            (MemberSubscription.STATUS_FROZEN, "frozen"),
            (MemberSubscription.STATUS_SUSPENDED, "suspended"),
        ],
    )
    def test_manual_override_refused_for_inactive_member(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        sub_status,
        expected_reason,
    ):
        """Manual override is refused for expired, frozen or suspended members."""
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        sub.status = sub_status
        sub.save()

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(active_member.id),
                "reason": "Testing inactive member override attempt",
            },
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == expected_reason
        assert Attendance.all_objects.count() == 0
        assert AuditLog.all_objects.count() == 0

    def test_manual_override_no_subscription_row_refused_no_attendance_or_audit(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
    ):
        """Manual override is refused with reason 'expired' when member has no subscription row; no Attendance or AuditLog created."""
        MemberSubscription.all_objects.filter(member=active_member).delete()
        assert MemberSubscription.all_objects.filter(member=active_member).count() == 0

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(active_member.id),
                "reason": "Override attempt without subscription",
            },
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "expired"
        assert Attendance.all_objects.count() == 0
        assert AuditLog.all_objects.count() == 0

    def test_manual_override_duplicate_same_day_denied(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """A second manual override for the same member on the same day is rejected."""
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        # First override succeeds
        resp1 = client.post(
            "/api/gym/attendance/manual-override/",
            {"member_id": str(active_member.id), "reason": "First override"},
            format="json",
        )
        assert resp1.status_code == 201
        assert Attendance.all_objects.count() == 1

        # Second override denied
        resp2 = client.post(
            "/api/gym/attendance/manual-override/",
            {"member_id": str(active_member.id), "reason": "Duplicate override"},
            format="json",
        )
        assert resp2.status_code == 400
        assert resp2.data["reason"] == "already_checked_in"
        assert Attendance.all_objects.count() == 1

    def test_manual_override_simulated_race_integrity_error_returns_already_checked_in(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """A simulated race / IntegrityError on duplicate check returns already_checked_in, not a 500."""
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        with patch.object(
            Attendance.all_objects,
            "create",
            side_effect=IntegrityError(
                "duplicate key value violates unique constraint"
            ),
        ):
            response = client.post(
                "/api/gym/attendance/manual-override/",
                {"member_id": str(active_member.id), "reason": "Simulated race test"},
                format="json",
            )

        assert response.status_code == 400
        assert response.data["reason"] == "already_checked_in"
        assert "has already checked in today" in response.data["detail"]
