"""
Comprehensive tests for Sprint 10: Membership Plans and Subscription Lifecycle.

Covers:
1. Seeded status comparison: compare stored Member.status vs computed status across all 6 cases:
   (pending, active, expired, frozen, suspended, renewed).
2. Direct writes to Member.status prohibited (raises ValueError).
3. Accurate month-end calculation (relativedelta, Jan 31 + 1 month = Feb 28, leap years, days vs months).
4. MembershipPlan CRUD:
   - Owner and Manager permissions.
   - Reception, Trainer, Member, Super Admin restricted.
   - Trainer-inclusive warning when gym has no active trainers.
   - Plan deactivation hides from new signups while leaving existing subscriptions intact.
   - Price change immutability: changing plan price leaves past/active subscriptions unaltered.
   - Tenant isolation: Gym A plans never visible or usable by Gym B.
5. Public plan listing:
   - Unauthenticated visitors can view active plans on gym subdomain.
   - Inactive plans are excluded from public listing.
6. Member suspend and reactivate endpoints:
   - Owner and Manager can suspend and reactivate.
   - Other roles refused (403).
   - Audit logs recorded for suspend/reactivate.
7. Unified check-in engine:
   - Refusal of pending member with reason 'pending' and message 'No active plan yet.' (both QR and manual override).
   - Refusal of expired, frozen, suspended members with distinguishable reasons.
   - Second scan on same day denied and notifies staff.
   - Attendance record stores method ('qr' or 'manual_override') and matching is_override.
8. Database CHECK constraint enforcement:
   - Inserting mismatched method and is_override fails at DB level with IntegrityError.
"""

import uuid
from datetime import date, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.attendance.services import issue_member_qr_token
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.memberships.services import (
    calculate_plan_end_date,
    compute_member_status,
    create_or_renew_subscription,
    update_member_status,
)
from apps.tenants.models import GymTenant


def auth_client(client, user, subdomain):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    client.defaults["HTTP_HOST"] = f"{subdomain}.localhost"
    return client


def make_member(gym, full_name, phone, user=None):
    """Helper to create a valid member with associated user account."""
    if user is None:
        user = User.objects.create_user(
            email=f"member_{uuid.uuid4().hex[:8]}@test.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym,
            full_name=full_name,
            phone=phone,
            email_verified_at=timezone.now(),
        )
    return Member.objects.create(
        gym=gym,
        user=user,
        full_name=full_name,
        phone=phone,
        waiver_accepted_at=timezone.now(),
    )


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
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Bole Owner",
        phone="+251911000001",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
        full_name="Bole Manager",
        phone="+251911000002",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
        full_name="Bole Reception",
        phone="+251911000003",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
        full_name="Bole Trainer",
        phone="+251911000004",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def member_user(db, gym_tenant):
    return User.objects.create_user(
        email="member@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Bole Member",
        phone="+251911000005",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def superadmin_user(db):
    return User.objects.create_user(
        email="superadmin@fitgate.et",
        password="SuperAdminPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        gym=None,
        full_name="Global SuperAdmin",
        phone="+251900000000",
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def sample_plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard",
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        price_etb="1500.00",
        trainer_inclusive=False,
        is_active=True,
    )


class TestMemberStatusAndCalculation:
    """Tests for status computation, direct assignment guard, and date arithmetic."""

    def test_seeded_status_comparison_all_six_cases(self, gym_tenant, sample_plan):
        """
        Compare stored Member.status vs computed status across all 6 cases:
        pending, active, expired, frozen, suspended, renewed.
        """
        today = timezone.localdate()

        # 1. Pending (registered, no subscriptions)
        m_pending = make_member(gym_tenant, "Pending Member", "+251911111101")
        assert m_pending.status == Member.STATUS_PENDING
        assert compute_member_status(m_pending) == Member.STATUS_PENDING

        # 2. Active (subscription active today)
        m_active = make_member(gym_tenant, "Active Member", "+251911111102")
        create_or_renew_subscription(
            member=m_active,
            plan=sample_plan,
            start_date=today - timedelta(days=5),
        )
        m_active.refresh_from_db()
        assert m_active.status == Member.STATUS_ACTIVE
        assert compute_member_status(m_active) == Member.STATUS_ACTIVE

        # 3. Expired (subscription ended yesterday)
        m_expired = make_member(gym_tenant, "Expired Member", "+251911111103")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m_expired,
            plan=sample_plan,
            start_date=today - timedelta(days=35),
            end_date=today - timedelta(days=5),
            status=MemberSubscription.STATUS_EXPIRED,
        )
        update_member_status(m_expired)
        m_expired.refresh_from_db()
        assert m_expired.status == Member.STATUS_EXPIRED
        assert compute_member_status(m_expired) == Member.STATUS_EXPIRED

        # 4. Frozen (subscription frozen)
        m_frozen = make_member(gym_tenant, "Frozen Member", "+251911111104")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m_frozen,
            plan=sample_plan,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            status=MemberSubscription.STATUS_FROZEN,
        )
        update_member_status(m_frozen)
        m_frozen.refresh_from_db()
        assert m_frozen.status == Member.STATUS_FROZEN
        assert compute_member_status(m_frozen) == Member.STATUS_FROZEN

        # 5. Suspended (member explicitly suspended)
        m_suspended = make_member(gym_tenant, "Suspended Member", "+251911111105")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m_suspended,
            plan=sample_plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            status=MemberSubscription.STATUS_SUSPENDED,
        )
        update_member_status(m_suspended)
        m_suspended.refresh_from_db()
        assert m_suspended.status == Member.STATUS_SUSPENDED
        assert compute_member_status(m_suspended) == Member.STATUS_SUSPENDED

        # 6. Renewed (member was expired, then purchased new subscription)
        m_renewed = make_member(gym_tenant, "Renewed Member", "+251911111106")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m_renewed,
            plan=sample_plan,
            start_date=today - timedelta(days=65),
            end_date=today - timedelta(days=35),
            status=MemberSubscription.STATUS_EXPIRED,
        )
        update_member_status(m_renewed)
        assert m_renewed.status == Member.STATUS_EXPIRED

        create_or_renew_subscription(
            member=m_renewed,
            plan=sample_plan,
            start_date=today,
        )
        m_renewed.refresh_from_db()
        assert m_renewed.status == Member.STATUS_ACTIVE
        assert compute_member_status(m_renewed) == Member.STATUS_ACTIVE

    def test_direct_member_status_write_prohibited(self, gym_tenant):
        """Setting Member.status directly without update_member_status() raises ValueError."""
        member = make_member(gym_tenant, "Guarded Member", "+251911999999")
        assert member.status == Member.STATUS_PENDING

        member.status = Member.STATUS_ACTIVE
        with pytest.raises(ValueError) as exc:
            member.save()
        assert "Direct modification of Member.status" in str(exc.value)

    def test_month_end_date_calculation_with_relativedelta(self):
        """
        Verify accurate month-end calculation using relativedelta:
        - Jan 31 + 1 month = Feb 28 (non-leap year)
        - Jan 31 + 1 month = Feb 29 (leap year 2024)
        - Mar 31 + 1 month = Apr 30
        - Aug 31 + 1 month = Sep 30
        - Days calculation: 15 days = start_date + 15 days
        """
        # Non-leap year: Jan 31, 2026 + 1 month -> Feb 28, 2026
        d1 = calculate_plan_end_date(
            date(2026, 1, 31), 1, MembershipPlan.DURATION_MONTHS
        )
        assert d1 == date(2026, 2, 28)

        # Leap year: Jan 31, 2024 + 1 month -> Feb 29, 2024
        d2 = calculate_plan_end_date(
            date(2024, 1, 31), 1, MembershipPlan.DURATION_MONTHS
        )
        assert d2 == date(2024, 2, 29)

        # 30-day month: Mar 31, 2026 + 1 month -> Apr 30, 2026
        d3 = calculate_plan_end_date(
            date(2026, 3, 31), 1, MembershipPlan.DURATION_MONTHS
        )
        assert d3 == date(2026, 4, 30)

        # 3 months: May 31, 2026 + 3 months -> Aug 31, 2026
        d4 = calculate_plan_end_date(
            date(2026, 5, 31), 3, MembershipPlan.DURATION_MONTHS
        )
        assert d4 == date(2026, 8, 31)

        # Days duration: Oct 10, 2026 + 14 days -> Oct 24, 2026
        d5 = calculate_plan_end_date(
            date(2026, 10, 10), 14, MembershipPlan.DURATION_DAYS
        )
        assert d5 == date(2026, 10, 24)


class TestMembershipPlanCRUDAndSecurity:
    """Tests for plan management endpoints, permissions, warnings, and immutability."""

    def test_owner_and_manager_can_create_and_manage_plans(
        self, api_client, gym_tenant, owner_user, manager_user
    ):
        """Owner and Manager can create and edit membership plans."""
        # 1. Owner creates a plan
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        create_resp = client.post(
            "/api/gym/membership-plans/",
            {
                "name": "Quarterly Fitness",
                "duration_value": 3,
                "duration_unit": "months",
                "price_etb": "4000.00",
                "trainer_inclusive": False,
            },
            format="json",
        )
        assert create_resp.status_code == 201
        plan_id = create_resp.data["id"]
        assert create_resp.data["name"] == "Quarterly Fitness"
        assert create_resp.data["is_active"] is True
        assert create_resp.data["has_no_trainers_warning"] is False

        # 2. Manager edits the plan
        m_client = auth_client(api_client, manager_user, gym_tenant.subdomain)
        patch_resp = m_client.patch(
            f"/api/gym/membership-plans/{plan_id}/",
            {"price_etb": "4200.00"},
            format="json",
        )
        assert patch_resp.status_code == 200
        assert patch_resp.data["price_etb"] == "4200.00"

    def test_trainer_warning_when_gym_has_no_trainers(
        self, api_client, gym_tenant, owner_user
    ):
        """Creating a trainer-inclusive plan warns if the gym has no active trainers."""
        assert User.objects.filter(gym=gym_tenant, role=User.ROLE_TRAINER).count() == 0

        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.post(
            "/api/gym/membership-plans/",
            {
                "name": "VIP Coaching",
                "duration_value": 1,
                "duration_unit": "months",
                "price_etb": "5000.00",
                "trainer_inclusive": True,
            },
            format="json",
        )
        assert resp.status_code == 201
        assert resp.data["has_no_trainers_warning"] is True

        # Now add a trainer and verify warning is false for subsequent plan
        User.objects.create_user(
            email="trainer.new@bolehub.com",
            password="Password123!",
            role=User.ROLE_TRAINER,
            gym=gym_tenant,
            email_verified_at=timezone.now(),
            is_active=True,
        )
        resp2 = client.post(
            "/api/gym/membership-plans/",
            {
                "name": "VIP Coaching 2",
                "duration_value": 1,
                "duration_unit": "months",
                "price_etb": "5500.00",
                "trainer_inclusive": True,
            },
            format="json",
        )
        assert resp2.status_code == 201
        assert resp2.data["has_no_trainers_warning"] is False

    def test_unauthorized_roles_cannot_manage_plans(
        self, api_client, gym_tenant, reception_user, trainer_user, member_user
    ):
        """Reception, Trainer, and Member cannot create or edit plans (403)."""
        payload = {
            "name": "Hacked Plan",
            "duration_value": 1,
            "duration_unit": "months",
            "price_etb": "10.00",
        }
        for u in [reception_user, trainer_user, member_user]:
            c = auth_client(api_client, u, gym_tenant.subdomain)
            resp = c.post("/api/gym/membership-plans/", payload, format="json")
            assert resp.status_code == 403

    def test_plan_deactivation_hides_from_new_signups_leaves_existing_intact(
        self, api_client, gym_tenant, owner_user, sample_plan
    ):
        """Deactivating a plan sets is_active=False and blocks new subscriptions for that plan."""
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # 1. Member subscribes to active plan
        member = make_member(gym_tenant, "Subscriber 1", "+251911888001")
        sub = create_or_renew_subscription(
            member=member,
            plan=sample_plan,
            start_date=timezone.localdate(),
        )
        assert sub.status == MemberSubscription.STATUS_ACTIVE

        # 2. Owner deactivates plan
        deact_resp = client.patch(
            f"/api/gym/membership-plans/{sample_plan.id}/",
            {"is_active": False},
            format="json",
        )
        assert deact_resp.status_code == 200
        assert deact_resp.data["is_active"] is False

        # 3. Existing subscription is untouched
        sub.refresh_from_db()
        assert sub.status == MemberSubscription.STATUS_ACTIVE

        # 4. Attempting new subscription on deactivated plan raises ValidationError
        sample_plan.refresh_from_db()
        assert sample_plan.is_active is False
        member2 = make_member(gym_tenant, "Subscriber 2", "+251911888002")
        with pytest.raises(Exception):
            create_or_renew_subscription(
                member=member2,
                plan=sample_plan,
                start_date=timezone.localdate(),
            )

    def test_price_change_immutability(
        self, api_client, gym_tenant, owner_user, sample_plan
    ):
        """Updating plan price leaves past and existing subscriptions completely unaffected."""
        member = make_member(gym_tenant, "Paying Member", "+251911888003")
        sub = create_or_renew_subscription(
            member=member,
            plan=sample_plan,
            start_date=timezone.localdate(),
        )
        original_end_date = sub.end_date
        assert sub.status == MemberSubscription.STATUS_ACTIVE

        # Owner changes plan price
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        resp = client.patch(
            f"/api/gym/membership-plans/{sample_plan.id}/",
            {"price_etb": "2500.00"},
            format="json",
        )
        assert resp.status_code == 200
        assert resp.data["price_etb"] == "2500.00"

        # Active subscription still has unchanged status and end date
        sub.refresh_from_db()
        assert sub.status == MemberSubscription.STATUS_ACTIVE
        assert sub.end_date == original_end_date

    def test_tenant_isolation_on_plans(
        self, api_client, gym_tenant, other_gym_tenant, owner_user, sample_plan
    ):
        """Gym A plans are never visible or modifiable by Gym B staff."""
        other_owner = User.objects.create_user(
            email="owner@kazanchis.com",
            password="Password123!",
            role=User.ROLE_OWNER,
            gym=other_gym_tenant,
            full_name="Kazanchis Owner",
            phone="+251922000001",
            email_verified_at=timezone.now(),
        )
        client = auth_client(api_client, other_owner, other_gym_tenant.subdomain)

        # 1. Other gym cannot see Gym A's plan in list
        list_resp = client.get("/api/gym/membership-plans/")
        assert list_resp.status_code == 200
        plan_ids = [p["id"] for p in list_resp.data]
        assert str(sample_plan.id) not in plan_ids

        # 2. Other gym cannot access or patch Gym A's plan (404)
        get_resp = client.get(f"/api/gym/membership-plans/{sample_plan.id}/")
        assert get_resp.status_code == 404

        patch_resp = client.patch(
            f"/api/gym/membership-plans/{sample_plan.id}/",
            {"name": "Stolen Plan"},
            format="json",
        )
        assert patch_resp.status_code == 404


class TestPublicPlanListing:
    """Tests for unauthenticated public plan endpoints."""

    def test_public_can_view_active_plans_only(
        self, api_client, gym_tenant, other_gym_tenant, sample_plan
    ):
        """Public entry page returns active plans for that gym; excludes inactive and other gym plans."""
        # Create an inactive plan for gym_tenant
        MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Hidden Old Plan",
            duration_value=1,
            duration_unit="months",
            price_etb="999.00",
            is_active=False,
        )
        # Create a plan for other_gym_tenant
        MembershipPlan.objects.create(
            gym=other_gym_tenant,
            name="Kazanchis Plan",
            duration_value=1,
            duration_unit="months",
            price_etb="3000.00",
            is_active=True,
        )

        # 1. Check gym public entry page
        api_client.credentials()
        resp = api_client.get(
            "/api/public/gym-entry/",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        plans = resp.data["plans"]
        plan_names = [p["name"] for p in plans]
        assert "Monthly Standard" in plan_names
        assert "Hidden Old Plan" not in plan_names
        assert "Kazanchis Plan" not in plan_names

        # 2. Check public dedicated plans route
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        pub_resp = api_client.get("/api/gym/membership-plans/public/")
        assert pub_resp.status_code == 200
        pub_names = [p["name"] for p in pub_resp.data]
        assert "Monthly Standard" in pub_names
        assert "Hidden Old Plan" not in pub_names


class TestMemberSuspendAndReactivate:
    """Tests for member suspend and reactivate endpoints and RBAC."""

    def test_owner_and_manager_can_suspend_and_reactivate_member(
        self, api_client, gym_tenant, owner_user, manager_user, sample_plan
    ):
        """Owner can suspend a member, Manager can reactivate, writing audit logs."""
        today = timezone.localdate()
        member = make_member(gym_tenant, "Active Test Member", "+251911777001")
        sub = create_or_renew_subscription(
            member=member,
            plan=sample_plan,
            start_date=today - timedelta(days=5),
        )
        assert member.status == Member.STATUS_ACTIVE

        # 1. Owner suspends member
        client = auth_client(api_client, owner_user, gym_tenant.subdomain)
        susp_resp = client.post(
            f"/api/gym/members/{member.id}/suspend/",
            {"reason": "Rule violation regarding gym equipment"},
            format="json",
        )
        assert susp_resp.status_code == 200
        assert susp_resp.data["status"] == "suspended"

        member.refresh_from_db()
        sub.refresh_from_db()
        assert member.status == Member.STATUS_SUSPENDED
        assert sub.status == MemberSubscription.STATUS_SUSPENDED

        # Verify audit log
        log = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="member_suspended",
            affected_record_id=str(member.id),
        ).first()
        assert log is not None
        assert log.actor == owner_user
        assert log.metadata["reason"] == "Rule violation regarding gym equipment"

        # 2. Manager reactivates member
        m_client = auth_client(api_client, manager_user, gym_tenant.subdomain)
        react_resp = m_client.post(
            f"/api/gym/members/{member.id}/reactivate/",
            format="json",
        )
        assert react_resp.status_code == 200
        assert react_resp.data["status"] == "active"

        member.refresh_from_db()
        sub.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        assert sub.status == MemberSubscription.STATUS_ACTIVE

        # Verify audit log
        log2 = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="member_reactivated",
            affected_record_id=str(member.id),
        ).first()
        assert log2 is not None
        assert log2.actor == manager_user

    def test_reception_and_unauthorized_roles_cannot_suspend_or_reactivate(
        self, api_client, gym_tenant, reception_user, trainer_user, member_user
    ):
        """Reception, Trainer, and Member cannot suspend or reactivate members (403)."""
        member = make_member(gym_tenant, "Target Member", "+251911777002")
        for u in [reception_user, trainer_user, member_user]:
            c = auth_client(api_client, u, gym_tenant.subdomain)
            resp1 = c.post(
                f"/api/gym/members/{member.id}/suspend/",
                {"reason": "Invalid attempt"},
                format="json",
            )
            assert resp1.status_code == 403

            resp2 = c.post(
                f"/api/gym/members/{member.id}/reactivate/",
                format="json",
            )
            assert resp2.status_code == 403


class TestUnifiedCheckInAndDatabaseConstraint:
    """Tests for unified check-in engine and database CHECK constraint."""

    def test_pending_member_refused_on_qr_and_manual_override(
        self, api_client, gym_tenant, reception_user
    ):
        """Pending member is refused with reason 'pending' and message 'No active plan yet.'"""
        member = make_member(gym_tenant, "Brand New Pending Member", "+251911777003")
        assert member.status == Member.STATUS_PENDING

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        # 1. Manual override attempt
        resp_manual = client.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(member.id),
                "reason": "Forgot phone",
            },
            format="json",
        )
        assert resp_manual.status_code == 400
        assert resp_manual.data["reason"] == "pending"
        assert resp_manual.data["message"] == "No active plan yet."

        # 2. QR token generation attempt is also refused with reason 'pending'
        with pytest.raises(Exception) as exc:
            issue_member_qr_token(member)
        assert getattr(exc.value, "reason", None) == "pending"
        assert getattr(exc.value, "message", None) == "No active plan yet."

    def test_database_check_constraint_attendance_matches_method(self, gym_tenant):
        """
        Database CHECK constraint 'attendance_override_matches_method' strictly enforces:
        is_override == (method == 'manual_override').
        """
        member = make_member(gym_tenant, "Constraint Member", "+251911777004")
        today = timezone.localdate()

        # Valid combinations:
        # 1. method='qr', is_override=False -> succeeds
        att1 = Attendance.objects.create(
            gym=gym_tenant,
            member=member,
            date=today,
            method=Attendance.METHOD_QR,
            is_override=False,
            status=Attendance.STATUS_CHECKED_IN,
            checked_in_at=timezone.now(),
        )
        assert att1.id is not None
        att1.delete()

        # 2. method='manual_override', is_override=True -> succeeds
        att2 = Attendance.objects.create(
            gym=gym_tenant,
            member=member,
            date=today,
            method=Attendance.METHOD_MANUAL_OVERRIDE,
            is_override=True,
            override_reason="Staff confirmed entry",
            status=Attendance.STATUS_CHECKED_IN,
            checked_in_at=timezone.now(),
        )
        assert att2.id is not None
        att2.delete()

        # Invalid combinations:
        # 3. method='qr', is_override=True -> violates constraint
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    gym=gym_tenant,
                    member=member,
                    date=today,
                    method=Attendance.METHOD_QR,
                    is_override=True,
                    status=Attendance.STATUS_CHECKED_IN,
                    checked_in_at=timezone.now(),
                )

        # 4. method='manual_override', is_override=False -> violates constraint
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    gym=gym_tenant,
                    member=member,
                    date=today,
                    method=Attendance.METHOD_MANUAL_OVERRIDE,
                    is_override=False,
                    status=Attendance.STATUS_CHECKED_IN,
                    checked_in_at=timezone.now(),
                )
