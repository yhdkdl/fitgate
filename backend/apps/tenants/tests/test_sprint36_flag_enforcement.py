"""
Sprint 36 Regression and Entitlement Enforcement Tests.

Covers:
1. Entitlement Rule:
   - Owner can edit freeze_days_allowed (up to freeze_days_cap), Chapa switch, equipment-complete,
     and receipt verification settings.
   - Owner CANNOT edit tier, feature flags (has_*), freeze_days_cap, payment_grace_days,
     or subscription_reminder_days (strictly 403 Forbidden).
   - freeze_days_allowed cannot exceed freeze_days_cap (400), and Starter tier cannot enable freeze (400).
2. Tier-Gated Feature Regression:
   - Trainer module (trainers, assignments, My clients, measurements, fitness profile) -> 403 when flag is off.
   - AI plans (generate, review, member plans) -> 403 when flag is off.
   - Analytics (revenue by plan) -> hidden with upgrade prompt on Starter tier / has_analytics=False.
   - Freeze -> blocked on Starter tier.
   - Group classes -> 403 when flag is off.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Expense, GymPaymentConfig
from apps.tenants.models import GymConfig, GymNotice, GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def growth_gym(db):
    gym = GymTenant.objects.create(
        name="Growth Gym",
        subdomain="growthgym",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": True,
            "has_ai_plans": True,
            "has_analytics": True,
            "has_group_classes": True,
            "has_notices": True,
            "has_expenses": True,
            "freeze_days_cap": 30,
            "freeze_days_allowed": 14,
            "is_equipment_list_complete": False,
        },
    )
    return gym


@pytest.fixture
def starter_gym(db):
    gym = GymTenant.objects.create(
        name="Starter Gym",
        subdomain="startergym",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Piassa, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": False,
            "has_ai_plans": False,
            "has_analytics": False,
            "has_group_classes": False,
            "has_notices": False,
            "has_expenses": False,
            "freeze_days_cap": 30,
            "freeze_days_allowed": 0,
            "is_equipment_list_complete": False,
        },
    )
    return gym


def create_user(gym, role, email, full_name=None):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=full_name or f"Test {role.capitalize()}",
        is_active=True,
    )
    user.force_password_change = False
    user.must_change_password = False
    user.save()
    return user


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


def make_member(gym, full_name, email, phone):
    user = create_user(gym, User.ROLE_MEMBER, email, full_name=full_name)
    member = Member.all_objects.create(
        gym=gym,
        user=user,
        full_name=full_name,
        phone=phone,
        gender="male",
        date_of_birth="1995-05-15",
        waiver_accepted_at=timezone.now(),
    )
    plan = MembershipPlan.all_objects.create(
        gym=gym,
        name=f"Standard Monthly {phone}",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1500.00"),
        trainer_inclusive=True,
    )
    now = timezone.now()
    MemberSubscription.all_objects.create(
        gym=gym,
        member=member,
        plan=plan,
        start_date=now.date(),
        end_date=now.date() + timedelta(days=30),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member, user


@pytest.mark.django_db
class TestEntitlementRuleEnforcement:
    """Verifies that Gym Owners cannot edit entitlements, but can edit allowed settings."""

    @pytest.mark.parametrize(
        "field,value",
        [
            ("tier", "growth"),
            ("has_trainer_module", True),
            ("has_ai_plans", True),
            ("has_analytics", True),
            ("has_group_classes", True),
            ("has_multi_branch", True),
            ("freeze_days_cap", 45),
            ("payment_grace_days", 14),
            ("subscription_reminder_days", [14, 7]),
        ],
    )
    def test_owner_cannot_edit_entitlements_returns_403(
        self, api_client, growth_gym, field, value
    ):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        resp = client.patch("/api/gym/settings/", {field: value}, format="json")
        assert resp.status_code == 403
        assert "Only Super Admin can modify gym entitlements." in str(resp.data)

    def test_owner_can_edit_freeze_days_allowed_up_to_cap(self, api_client, growth_gym):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        # Cap is 30 in growth_gym fixture; setting to 20 should succeed
        resp = client.patch(
            "/api/gym/settings/", {"freeze_days_allowed": 20}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["freeze_days_allowed"] == 20

    def test_owner_cannot_exceed_freeze_days_cap_returns_400(
        self, api_client, growth_gym
    ):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        # Cap is 30; setting to 31 must fail
        resp = client.patch(
            "/api/gym/settings/", {"freeze_days_allowed": 31}, format="json"
        )
        assert resp.status_code == 400
        assert "Cannot exceed maximum freeze allowance cap" in str(resp.data)

    def test_starter_owner_cannot_enable_freeze_returns_400(
        self, api_client, starter_gym
    ):
        owner = create_user(starter_gym, User.ROLE_OWNER, "owner@startergym.com")
        client = auth_client(api_client, owner, starter_gym)

        resp = client.patch(
            "/api/gym/settings/", {"freeze_days_allowed": 5}, format="json"
        )
        assert resp.status_code == 400
        assert "Starter gyms cannot use membership freeze" in str(resp.data)

    def test_owner_can_edit_equipment_list_complete(self, api_client, growth_gym):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        resp = client.patch(
            "/api/gym/settings/", {"is_equipment_list_complete": True}, format="json"
        )
        assert resp.status_code == 200
        assert resp.data["is_equipment_list_complete"] is True

    def test_owner_can_toggle_chapa_switch(self, api_client, growth_gym):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        # Create verified payment config
        cfg, _ = GymPaymentConfig.objects.get_or_create(gym=growth_gym)
        cfg.is_verified = True
        cfg.is_enabled = True
        cfg.save()

        # Turning off is allowed
        resp = client.patch(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code == 200
        cfg.refresh_from_db()
        assert cfg.is_enabled is False

    def test_owner_can_update_receipt_verification_settings(
        self, api_client, growth_gym
    ):
        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, owner, growth_gym)

        cfg, _ = GymPaymentConfig.objects.get_or_create(gym=growth_gym)
        resp = client.patch(
            "/api/gym/payment-config/",
            {
                "receipt_verification_failure_policy": GymPaymentConfig.POLICY_HOLD_FOR_APPROVAL
            },
            format="json",
        )
        assert resp.status_code == 200
        cfg.refresh_from_db()
        assert (
            cfg.receipt_verification_failure_policy
            == GymPaymentConfig.POLICY_HOLD_FOR_APPROVAL
        )


@pytest.mark.django_db
class TestTierGatedFeatureRegression:
    """Verifies that every tier-gated feature refuses access when its flag is missing or disabled."""

    def test_trainer_module_regression_when_disabled(self, api_client, starter_gym):
        """When has_trainer_module=False, all trainer endpoints return 403."""
        owner = create_user(starter_gym, User.ROLE_OWNER, "owner@startergym.com")
        owner_client = auth_client(api_client, owner, starter_gym)

        member, member_user = make_member(
            starter_gym, "Abebe Bikila", "abebe@starter.local", "+251911000001"
        )
        member_client = auth_client(APIClient(), member_user, starter_gym)

        # 1. Trainers list
        r1 = owner_client.get("/api/gym/trainers/")
        assert r1.status_code == 403

        # 2. Assignments list
        r2 = owner_client.get("/api/gym/assignments/")
        assert r2.status_code == 403

        # 3. Member metrics (view/record)
        r3 = owner_client.get(f"/api/gym/members/{member.id}/metrics/")
        assert r3.status_code == 403

        # 4. Member self metrics
        r4 = member_client.get("/api/members/me/metrics/")
        assert r4.status_code == 403

        # 5. Member fitness profile
        r5 = owner_client.get(f"/api/gym/members/{member.id}/fitness-profile/")
        assert r5.status_code == 403

        # 6. Member self fitness profile
        r6 = member_client.get("/api/members/me/fitness-profile/")
        assert r6.status_code == 403

    def test_ai_plans_regression_when_disabled(self, api_client, growth_gym):
        """When has_ai_plans=False, all AI plan endpoints return 403."""
        # Turn off AI plans flag
        growth_gym.config.has_ai_plans = False
        growth_gym.config.save(update_fields=["has_ai_plans"])

        owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        owner_client = auth_client(api_client, owner, growth_gym)

        member, member_user = make_member(
            growth_gym, "Derartu Tulu", "derartu@growth.local", "+251911000002"
        )
        member_client = auth_client(APIClient(), member_user, growth_gym)

        # 1. Plan status prerequisites
        r1 = owner_client.get(f"/api/gym/members/{member.id}/plans/status/")
        assert r1.status_code == 403

        # 2. Plan list / generate
        r2 = owner_client.get(f"/api/gym/members/{member.id}/plans/")
        assert r2.status_code == 403

        r3 = owner_client.post(
            f"/api/gym/members/{member.id}/plans/", {}, format="json"
        )
        assert r3.status_code == 403

        # 3. Member self approved plans
        r4 = member_client.get("/api/members/me/plans/")
        assert r4.status_code == 403

    def test_group_classes_regression_when_disabled(self, api_client, starter_gym):
        """When has_group_classes=False, group class endpoints return 403."""
        owner = create_user(starter_gym, User.ROLE_OWNER, "owner@startergym.com")
        client = auth_client(api_client, owner, starter_gym)

        # 1. Sessions list
        r1 = client.get("/api/gym/classes/")
        assert r1.status_code == 403

        # 2. Session create
        r2 = client.post(
            "/api/gym/classes/",
            {
                "title": "yoga",
                "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
                "duration_minutes": 60,
                "capacity": 20,
            },
            format="json",
        )
        assert r2.status_code == 403

    def test_analytics_regression_starter_vs_growth(
        self, api_client, starter_gym, growth_gym
    ):
        """Starter gym has revenue_by_plan hidden with upgrade prompt; Growth gym returns data."""
        # 1. Starter Gym: has_analytics is False
        starter_owner = create_user(
            starter_gym, User.ROLE_OWNER, "owner@startergym.com"
        )
        client_starter = auth_client(api_client, starter_owner, starter_gym)
        r_starter = client_starter.get("/api/gym/analytics/overview/")
        assert r_starter.status_code == 200
        assert r_starter.data["has_analytics"] is False
        assert r_starter.data["revenue_by_plan"] is None
        assert "Upgrade to Growth" in r_starter.data["upgrade_prompt"]

        # 2. Growth Gym: has_analytics is True
        growth_owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client_growth = auth_client(APIClient(), growth_owner, growth_gym)
        r_growth = client_growth.get("/api/gym/analytics/overview/")
        assert r_growth.status_code == 200
        assert r_growth.data["has_analytics"] is True
        assert isinstance(r_growth.data["revenue_by_plan"], list)

    def test_freeze_regression_starter_tier(self, api_client, starter_gym):
        """Starter gym rejects freeze requests and reports 0 freeze allowance."""
        member, member_user = make_member(
            starter_gym, "Kenenisa Bekele", "kenenisa@starter.local", "+251911000003"
        )
        client = auth_client(api_client, member_user, starter_gym)

        # 1. Freeze allowance check
        r_allowance = client.get("/api/memberships/freezes/allowance/")
        assert r_allowance.status_code == 200
        assert r_allowance.data["total_allowed"] == 0
        assert r_allowance.data["remaining_days"] == 0
        assert r_allowance.data["freeze_allowed"] is False

        # 2. Freeze request submission
        today = timezone.localdate()
        r_freeze = client.post(
            "/api/memberships/freezes/",
            {
                "start_date": today.isoformat(),
                "end_date": (today + timedelta(days=7)).isoformat(),
                "reason": "Family vacation traveling out of town",
            },
            format="json",
        )
        assert r_freeze.status_code == 400
        assert "Starter gyms cannot use membership freeze" in str(r_freeze.data)

    def test_notices_and_telegram_regression(self, api_client, starter_gym, growth_gym):
        """When has_notices=False, gym notices and telegram are refused, but platform notices reach starter owner."""
        starter_owner = create_user(
            starter_gym, User.ROLE_OWNER, "owner@startergym.com"
        )
        starter_client = auth_client(api_client, starter_owner, starter_gym)

        # 1. Creating gym notice on Starter returns 403
        r_create = starter_client.post(
            "/api/gym/notices/",
            {"title": "Closed Sunday", "body": "Water maintenance"},
            format="json",
        )
        assert r_create.status_code == 403
        assert "Notice board is not available" in str(r_create.data)

        # 2. Telegram test message returns 403
        r_tg = starter_client.post("/api/gym/settings/telegram/test/")
        assert r_tg.status_code == 403
        assert "Telegram integration is not available" in str(r_tg.data)

        # 3. Super Admin creates a platform-wide notice (gym=None)
        _ = GymNotice.all_objects.create(
            gym=None,
            title="Scheduled Platform Maintenance",
            body="FitGate will perform maintenance on Sunday night.",
            posted_by=starter_owner,
        )

        # 4. Starter owner DOES receive the platform notice on /api/gym/notices/
        r_list = starter_client.get("/api/gym/notices/")
        assert r_list.status_code == 200
        titles = [n["title"] for n in r_list.data]
        assert "Scheduled Platform Maintenance" in titles

        # 5. Growth gym with has_notices=True can create gym notices
        growth_owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        growth_client = auth_client(APIClient(), growth_owner, growth_gym)
        r_growth_create = growth_client.post(
            "/api/gym/notices/",
            {"title": "Growth Class Notice", "body": "Zumba tonight"},
            format="json",
        )
        assert r_growth_create.status_code == 201

    def test_expenses_and_reports_regression(self, api_client, starter_gym, growth_gym):
        """When has_expenses=False, expense endpoints and reports return 403."""
        starter_owner = create_user(
            starter_gym, User.ROLE_OWNER, "owner@startergym.com"
        )
        client = auth_client(api_client, starter_owner, starter_gym)

        # 1. Expenses list & create -> 403
        r1 = client.get("/api/gym/expenses/")
        assert r1.status_code == 403

        r2 = client.post(
            "/api/gym/expenses/",
            {
                "amount_etb": "500.00",
                "category": "utilities",
                "incurred_on": timezone.localdate().isoformat(),
            },
            format="json",
        )
        assert r2.status_code == 403

        # 2. Financial report -> 403
        r3 = client.get("/api/gym/reports/financial/")
        assert r3.status_code == 403

        # 3. Attendance report -> 403
        r4 = client.get("/api/gym/reports/attendance/")
        assert r4.status_code == 403

        # 4. Equipment record_as_expense -> 403
        r5 = client.post(
            "/api/gym/equipment/",
            {
                "name": "Treadmill Pro",
                "category": "cardio_machines",
                "quantity": 1,
                "min_qty_threshold": 1,
                "condition": "good",
                "unit_purchase_price_etb": "50000.00",
                "record_as_expense": True,
            },
            format="json",
        )
        assert r5.status_code == 403
        assert "Expense tracking is not available" in str(r5.data)

    def test_trainer_staff_invite_refused_on_starter(self, api_client, starter_gym):
        """Inviting role=trainer on Starter gym returns 403."""
        owner = create_user(starter_gym, User.ROLE_OWNER, "owner@startergym.com")
        client = auth_client(api_client, owner, starter_gym)

        resp = client.post(
            "/api/gym/staff/",
            {
                "email": "trainer_new@starter.local",
                "role": "trainer",
                "full_name": "Test Candidate",
                "phone": "+251911998877",
            },
            format="json",
        )
        assert resp.status_code == 403
        assert "Trainer accounts are not available" in str(resp.data)

    def test_trainer_inclusive_plans_restricted_on_starter(
        self, api_client, starter_gym
    ):
        """Starter gym cannot create or sell trainer-inclusive plans; existing ones are flagged tier_unavailable."""
        owner = create_user(starter_gym, User.ROLE_OWNER, "owner@startergym.com")
        client = auth_client(api_client, owner, starter_gym)

        # 1. Creating trainer-inclusive plan returns 403
        r_create = client.post(
            "/api/gym/plans/",
            {
                "name": "Trainer Plan Attempt",
                "duration_value": 1,
                "duration_unit": "months",
                "price_etb": "2000.00",
                "trainer_inclusive": True,
            },
            format="json",
        )
        assert r_create.status_code == 403
        assert "Trainer-inclusive plans are not available" in str(r_create.data)

        # 2. Existing trainer-inclusive plan (e.g. from prior downgrade) is flagged for staff
        existing_plan = MembershipPlan.all_objects.create(
            gym=starter_gym,
            name="Grandfathered Trainer Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=Decimal("2500.00"),
            trainer_inclusive=True,
            is_active=True,
        )
        r_list = client.get("/api/gym/plans/")
        assert r_list.status_code == 200
        found = [p for p in r_list.data if p["id"] == str(existing_plan.id)]
        assert len(found) == 1
        assert found[0]["tier_unavailable"] is True
        assert found[0]["tier_message"] == "Not available on your tier"

        # 3. Public plan listing excludes trainer-inclusive plan
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{starter_gym.subdomain}.localhost"
        r_public = anon_client.get(
            f"/api/public/gym-entry/?subdomain={starter_gym.subdomain}"
        )
        assert r_public.status_code == 200
        public_plan_ids = [p["id"] for p in r_public.data["plans"]]
        assert str(existing_plan.id) not in public_plan_ids

        # 4. Selling trainer-inclusive plan is refused on server (400 or 403)
        member, _ = make_member(
            starter_gym, "Test Member", "tm@starter.local", "+251911333333"
        )
        r_cash = client.post(
            "/api/gym/payments/cash/",
            {
                "member_id": str(member.id),
                "plan_id": str(existing_plan.id),
                "amount_etb": "2500.00",
            },
            format="json",
        )
        assert r_cash.status_code in (400, 403)
        assert "not available on your gym's current tier" in str(r_cash.data)

    def test_downgrade_preserves_data_and_upgrade_restores(
        self, api_client, growth_gym
    ):
        """Downgrading a Growth gym to Starter does NOT delete data, and upgrading restores full access."""
        growth_owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growthgym.com")
        client = auth_client(api_client, growth_owner, growth_gym)

        # Create notice and expense while on Growth
        notice = GymNotice.all_objects.create(
            gym=growth_gym,
            title="Notice To Preserve",
            body="Keep safe",
            posted_by=growth_owner,
        )
        expense = Expense.all_objects.create(
            gym=growth_gym,
            amount_etb=Decimal("1200.00"),
            category="maintenance",
            incurred_on=timezone.localdate(),
            logged_by=growth_owner,
        )

        # Downgrade to Starter
        growth_gym.tier = GymTenant.TIER_STARTER
        growth_gym.config.has_trainer_module = False
        growth_gym.config.has_ai_plans = False
        growth_gym.config.has_analytics = False
        growth_gym.config.has_group_classes = False
        growth_gym.config.has_notices = False
        growth_gym.config.has_expenses = False
        growth_gym.save()
        growth_gym.config.save()

        # Data is NOT deleted
        assert GymNotice.all_objects.filter(id=notice.id).exists()
        assert Expense.all_objects.filter(id=expense.id).exists()

        # Access refused while on Starter
        r_notice = client.get("/api/gym/notices/")
        assert r_notice.status_code == 200
        # Platform notices only, gym notices excluded
        notice_ids = [n["id"] for n in r_notice.data]
        assert str(notice.id) not in notice_ids

        r_exp = client.get("/api/gym/expenses/")
        assert r_exp.status_code == 403

        # Upgrade back to Growth
        growth_gym.tier = GymTenant.TIER_GROWTH
        growth_gym.config.has_trainer_module = True
        growth_gym.config.has_ai_plans = True
        growth_gym.config.has_analytics = True
        growth_gym.config.has_group_classes = True
        growth_gym.config.has_notices = True
        growth_gym.config.has_expenses = True
        growth_gym.save()
        growth_gym.config.save()

        # Access restored!
        r_notice_restored = client.get("/api/gym/notices/")
        assert r_notice_restored.status_code == 200
        restored_ids = [n["id"] for n in r_notice_restored.data]
        assert str(notice.id) in restored_ids

        r_exp_restored = client.get("/api/gym/expenses/")
        assert r_exp_restored.status_code == 200
