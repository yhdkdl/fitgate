"""Tests for Sprint 27: Gym Dashboard and Analytics Overview."""

import time as time_mod
import uuid
from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.memberships.services import update_member_status
from apps.payments.models import Payment
from apps.tenants.analytics import get_gym_analytics_overview
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="FitGate Bole",
        subdomain="fitgate-bole",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config = tenant.config
    config.has_analytics = False
    config.save()
    return tenant


@pytest.fixture
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="fitgate-kazanchis",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )


def create_user(gym, role, email):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=f"Test {role.capitalize()}",
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


def make_member(gym, full_name, phone):
    user = User.objects.create_user(
        email=f"member_{uuid.uuid4().hex[:8]}@test.com",
        password="MemberPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym,
        full_name=full_name,
        phone=phone,
        is_active=True,
    )
    user.force_password_change = False
    user.must_change_password = False
    user.save()
    return Member.objects.create(
        gym=gym,
        user=user,
        full_name=full_name,
        phone=phone,
        waiver_accepted_at=timezone.now(),
    )


@pytest.mark.django_db
class TestAnalyticsPermissions:
    URL = "/api/gym/analytics/overview/"

    def test_owner_can_access_analytics(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert "active_members" in response.data
        assert "today_checkins" in response.data
        assert "monthly_net_revenue" in response.data
        assert "expiring_memberships_count" in response.data

    def test_manager_can_access_analytics(self, api_client, gym_tenant):
        manager = create_user(gym_tenant, User.ROLE_MANAGER, "manager@fitgate.com")
        auth_client(api_client, manager, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 200

    def test_trainer_refused(self, api_client, gym_tenant):
        trainer = create_user(gym_tenant, User.ROLE_TRAINER, "trainer@fitgate.com")
        auth_client(api_client, trainer, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 403

    def test_reception_refused(self, api_client, gym_tenant):
        reception = create_user(
            gym_tenant, User.ROLE_RECEPTION, "reception@fitgate.com"
        )
        auth_client(api_client, reception, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 403

    def test_member_refused(self, api_client, gym_tenant):
        member_user = create_user(gym_tenant, User.ROLE_MEMBER, "member@fitgate.com")
        auth_client(api_client, member_user, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 403

    def test_superadmin_refused_on_apex_and_gym_domain(self, api_client, gym_tenant):
        admin = User.objects.create_superuser(
            email="admin@fitgate.com",
            password="AdminPassword123!",
        )
        auth_client(api_client, admin)
        response_apex = api_client.get(self.URL)
        assert response_apex.status_code == 403

        auth_client(api_client, admin, gym_tenant)
        response_gym = api_client.get(self.URL)
        assert response_gym.status_code == 401

    def test_other_gym_owner_refused(self, api_client, gym_tenant, other_gym_tenant):
        other_owner = create_user(
            other_gym_tenant, User.ROLE_OWNER, "otherowner@fitgate.com"
        )
        auth_client(api_client, other_owner, gym_tenant)

        response = api_client.get(self.URL)
        assert response.status_code == 401

    def test_unauthenticated_refused(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        response = api_client.get(self.URL)
        assert response.status_code == 401


@pytest.mark.django_db
class TestAnalyticsMetrics:
    URL = "/api/gym/analytics/overview/"

    def test_active_and_frozen_members_counts(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        plan = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Standard Monthly",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )

        today = timezone.localdate()

        # 2 active members
        m1 = make_member(gym_tenant, "Active Member 1", "+251911000001")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m1,
            plan=plan,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        update_member_status(m1)

        m2 = make_member(gym_tenant, "Active Member 2", "+251911000002")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m2,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        update_member_status(m2)

        # 1 frozen member
        m3 = make_member(gym_tenant, "Frozen Member", "+251911000003")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m3,
            plan=plan,
            start_date=today - timedelta(days=15),
            end_date=today + timedelta(days=15),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        m3.status = Member.STATUS_FROZEN
        m3._status_update_allowed = True
        m3.save()

        # 1 expired member
        m4 = make_member(gym_tenant, "Expired Member", "+251911000004")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m4,
            plan=plan,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=10),
            status=MemberSubscription.STATUS_EXPIRED,
        )
        update_member_status(m4)

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["active_members"] == 2
        assert response.data["frozen_members"] == 1

    def test_today_checkins_in_addis_ababa_timezone(
        self, api_client, gym_tenant, other_gym_tenant
    ):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        tz_addis = ZoneInfo("Africa/Addis_Ababa")
        today_addis = timezone.now().astimezone(tz_addis).date()

        m1 = make_member(gym_tenant, "Checkin Member 1", "+251911000011")
        m2 = make_member(gym_tenant, "Checkin Member 2", "+251911000012")
        other_m = make_member(other_gym_tenant, "Other Gym Member", "+251911000013")

        # Today's check-ins at gym_tenant
        Attendance.objects.create(gym=gym_tenant, member=m1, date=today_addis)
        Attendance.objects.create(gym=gym_tenant, member=m2, date=today_addis)

        # Yesterday's check-in
        Attendance.objects.create(
            gym=gym_tenant, member=m1, date=today_addis - timedelta(days=1)
        )

        # Check-in at other gym today
        Attendance.objects.create(
            gym=other_gym_tenant, member=other_m, date=today_addis
        )

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["today_checkins"] == 2

    def test_monthly_net_revenue_calculations(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        plan = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Standard Plan",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )
        m = make_member(gym_tenant, "Paying Member", "+251911000021")

        tz_addis = ZoneInfo("Africa/Addis_Ababa")
        now_addis = timezone.now().astimezone(tz_addis)
        start_of_month = now_addis.date().replace(day=1)
        this_month_dt = timezone.make_aware(
            datetime.combine(start_of_month, time(12, 0)), tz_addis
        )
        last_month_dt = this_month_dt - timedelta(days=35)

        # Confirmed payment this month (1,000 ETB)
        p1 = Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("1000.00"),
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )
        Payment.all_objects.filter(id=p1.id).update(created_at=this_month_dt)

        # Confirmed upgrade payment this month: gross 3,000, credit 1,300, net (amount_etb) 1,700
        p2 = Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            gross_amount_etb=Decimal("3000.00"),
            credit_amount_etb=Decimal("1300.00"),
            amount_etb=Decimal("1700.00"),
            is_upgrade=True,
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )
        Payment.all_objects.filter(id=p2.id).update(created_at=this_month_dt)

        # Reversed payment this month (500 ETB) - must be excluded
        p3 = Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_BANK_TRANSFER,
            bank_reference="REV-REF-12345",
            amount_etb=Decimal("500.00"),
            confirmed_by=owner,
            status=Payment.STATUS_REVERSED,
        )
        Payment.all_objects.filter(id=p3.id).update(created_at=this_month_dt)

        # Pending payment this month (800 ETB) - must be excluded
        p4 = Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CHAPA,
            chapa_ref="chapa_test_ref_4",
            amount_etb=Decimal("800.00"),
            status=Payment.STATUS_PENDING,
        )
        Payment.all_objects.filter(id=p4.id).update(created_at=this_month_dt)

        # Confirmed payment last month (2,000 ETB) - must be excluded from monthly revenue
        p5 = Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("2000.00"),
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )
        Payment.all_objects.filter(id=p5.id).update(created_at=last_month_dt)

        response = api_client.get(self.URL)
        assert response.status_code == 200
        # Expected: 1000 + 1700 = 2700.00
        assert Decimal(response.data["monthly_net_revenue"]) == Decimal("2700.00")

    def test_memberships_expiring_within_7_days(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        plan = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Standard Plan",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )

        today = timezone.localdate()

        # Member 1: expiring in 3 days, NO queued renewal -> should be included
        m1 = make_member(gym_tenant, "Expiring Member 1", "+251911000031")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m1,
            plan=plan,
            start_date=today - timedelta(days=27),
            end_date=today + timedelta(days=3),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Member 2: expiring in 5 days, WITH queued renewal -> should be EXCLUDED
        m2 = make_member(gym_tenant, "Renewing Member 2", "+251911000032")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m2,
            plan=plan,
            start_date=today - timedelta(days=25),
            end_date=today + timedelta(days=5),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m2,
            plan=plan,
            start_date=today + timedelta(days=6),
            end_date=today + timedelta(days=36),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Member 3: expiring in 15 days (> 7 days) -> should be EXCLUDED
        m3 = make_member(gym_tenant, "Future Expiring Member 3", "+251911000033")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m3,
            plan=plan,
            start_date=today - timedelta(days=15),
            end_date=today + timedelta(days=15),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Member 4: subscription ended in 3 days, but status is SUPERSEDED -> should be EXCLUDED
        m4 = make_member(gym_tenant, "Superseded Sub Member 4", "+251911000034")
        MemberSubscription.objects.create(
            gym=gym_tenant,
            member=m4,
            plan=plan,
            start_date=today - timedelta(days=27),
            end_date=today + timedelta(days=3),
            status=MemberSubscription.STATUS_SUPERSEDED,
        )

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["expiring_memberships_count"] == 1
        expiring = response.data["expiring_memberships"]
        assert len(expiring) == 1
        assert expiring[0]["member_id"] == str(m1.id)
        assert expiring[0]["days_remaining"] == 3


@pytest.mark.django_db
class TestAnalyticsTierGating:
    URL = "/api/gym/analytics/overview/"

    def test_starter_tier_sees_upgrade_prompt(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        # Ensure has_analytics is False
        config = gym_tenant.config
        config.has_analytics = False
        config.save()

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["has_analytics"] is False
        assert response.data["revenue_by_plan"] is None
        assert "Upgrade to Growth or Pro" in response.data["upgrade_prompt"]

    def test_growth_pro_tier_returns_revenue_by_plan(self, api_client, gym_tenant):
        owner = create_user(gym_tenant, User.ROLE_OWNER, "owner@fitgate.com")
        auth_client(api_client, owner, gym_tenant)

        # Enable has_analytics
        config = gym_tenant.config
        config.has_analytics = True
        config.save()

        plan1 = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Standard Plan",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )
        plan2 = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="VIP Plan",
            price_etb=Decimal("3500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )

        m = make_member(gym_tenant, "Member Paying Plans", "+251911000041")

        # 2 payments for plan1 = 3000
        Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan1,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("1500.00"),
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )
        Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan1,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("1500.00"),
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )

        # 1 payment for plan2 = 3500
        Payment.objects.create(
            gym=gym_tenant,
            member=m,
            plan=plan2,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("3500.00"),
            confirmed_by=owner,
            status=Payment.STATUS_CONFIRMED,
        )

        response = api_client.get(self.URL)
        assert response.status_code == 200
        assert response.data["has_analytics"] is True
        assert response.data["upgrade_prompt"] is None

        revenue_by_plan = response.data["revenue_by_plan"]
        assert len(revenue_by_plan) == 2
        # Highest revenue first (VIP: 3500 > Standard: 3000)
        assert revenue_by_plan[0]["plan_name"] == "VIP Plan"
        assert Decimal(revenue_by_plan[0]["revenue"]) == Decimal("3500.00")
        assert revenue_by_plan[0]["payment_count"] == 1

        assert revenue_by_plan[1]["plan_name"] == "Standard Plan"
        assert Decimal(revenue_by_plan[1]["revenue"]) == Decimal("3000.00")
        assert revenue_by_plan[1]["payment_count"] == 2


@pytest.mark.django_db
class TestAnalyticsPerformanceBenchmark:
    def test_analytics_query_under_3_seconds_with_1000_members_and_yearly_attendance(
        self, gym_tenant
    ):
        """
        Timing check against a seeded dataset (1,000 members, a year of attendance)
        must execute in under 3 seconds.
        """
        config = gym_tenant.config
        config.has_analytics = True
        config.save()

        plan = MembershipPlan.objects.create(
            gym=gym_tenant,
            name="Annual Plan",
            price_etb=Decimal("12000.00"),
            duration_value=12,
            duration_unit=MembershipPlan.DURATION_MONTHS,
        )

        today = timezone.localdate()

        # Seed 1,000 members via bulk_create
        users = [
            User(
                id=uuid.uuid4(),
                email=f"bench_user_{i}@bench.com",
                role=User.ROLE_MEMBER,
                gym=gym_tenant,
                full_name=f"Bench Member {i}",
                phone=f"+251912{i:06d}",
                is_active=True,
                password="hashed_placeholder",
            )
            for i in range(1000)
        ]
        User.objects.bulk_create(users)

        members = [
            Member(
                id=uuid.uuid4(),
                gym=gym_tenant,
                user=users[i],
                full_name=users[i].full_name,
                phone=users[i].phone,
                status=Member.STATUS_ACTIVE if i % 10 != 0 else Member.STATUS_FROZEN,
                waiver_accepted_at=timezone.now(),
            )
            for i in range(1000)
        ]
        Member.objects.bulk_create(members)

        # Seed subscriptions
        subs = [
            MemberSubscription(
                id=uuid.uuid4(),
                gym=gym_tenant,
                member=members[i],
                plan=plan,
                start_date=today - timedelta(days=100),
                end_date=today + timedelta(days=265),
                status=MemberSubscription.STATUS_ACTIVE,
            )
            for i in range(1000)
        ]
        MemberSubscription.objects.bulk_create(subs)

        # Seed a year of attendance (e.g. 5,000 check-in rows across the year)
        attendances = [
            Attendance(
                id=uuid.uuid4(),
                gym=gym_tenant,
                member=members[i % 1000],
                date=today - timedelta(days=i % 365),
                status=Attendance.STATUS_CHECKED_IN,
                method=Attendance.METHOD_QR,
            )
            for i in range(5000)
        ]
        Attendance.objects.bulk_create(attendances)

        # Benchmark get_gym_analytics_overview
        start_time = time_mod.perf_counter()
        result = get_gym_analytics_overview(gym_tenant)
        elapsed = time_mod.perf_counter() - start_time

        assert (
            elapsed < 3.0
        ), f"Analytics query took {elapsed:.2f}s, exceeding 3.0s budget!"
        assert result["active_members"] == 900
        assert result["frozen_members"] == 100
        assert result["today_checkins"] > 0
