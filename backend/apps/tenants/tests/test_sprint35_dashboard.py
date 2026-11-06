"""Tests for Sprint 35: Super Admin dashboard, platform notices, tier downgrades, and gym termination/reinstatement."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.classes.models import ClassSession
from apps.memberships.models import MembershipPlan
from apps.payments.models import Payment
from apps.tenants.analytics import get_gym_analytics_overview
from apps.tenants.models import GymConfig, GymNotice, GymTenant
from apps.trainers.models import Trainer


@pytest.fixture
def api_client():
    return APIClient()


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


@pytest.fixture
def super_admin(db):
    return create_user(None, User.ROLE_SUPER_ADMIN, "superadmin_s35@fitgate.com")


@pytest.fixture
def active_gym(db):
    gym = GymTenant.objects.create(
        name="Active Gym",
        subdomain="active-gym",
        status=GymTenant.STATUS_ACTIVE,
        tier=GymTenant.TIER_GROWTH,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": True,
            "has_ai_plans": True,
            "has_analytics": True,
            "has_group_classes": True,
            "freeze_days_allowed": 30,
            "freeze_days_cap": 30,
            "payment_grace_days": 7,
            "subscription_reminder_days": [14, 7],
            "member_reminder_days": [7, 2],
        },
    )
    return gym


@pytest.fixture
def suspended_gym(db):
    suspended_time = timezone.now() - timedelta(days=8)
    gym = GymTenant.objects.create(
        name="Suspended Gym",
        subdomain="suspended-gym",
        status=GymTenant.STATUS_SUSPENDED,
        tier=GymTenant.TIER_GROWTH,
        suspended_at=suspended_time,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": True,
            "has_ai_plans": True,
            "has_analytics": True,
            "has_group_classes": True,
        },
    )
    return gym


@pytest.mark.django_db
class TestGymTerminationAndReinstatement:
    def test_owner_cannot_terminate_or_reinstate(self, api_client, suspended_gym):
        owner = create_user(suspended_gym, User.ROLE_OWNER, "owner_term@gym.com")
        auth_client(api_client, owner, suspended_gym)

        # Attempt terminate
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/terminate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code in (403, 404)

        # Attempt reinstate
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/reinstate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code in (403, 404)

    def test_terminate_refused_for_active_gym(
        self, api_client, super_admin, active_gym
    ):
        auth_client(api_client, super_admin)
        res = api_client.post(
            f"/api/platform/gyms/{active_gym.id}/terminate/",
            {"subdomain_confirmation": active_gym.subdomain},
            format="json",
        )
        assert res.status_code == 400
        assert "must be suspended first" in res.data["detail"]

    def test_terminate_refused_if_suspension_less_than_7_days(
        self, api_client, super_admin, suspended_gym
    ):
        auth_client(api_client, super_admin)
        suspended_gym.suspended_at = timezone.now() - timedelta(days=3)
        suspended_gym.save()

        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/terminate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code == 400
        assert "must be at least 7 days old" in res.data["detail"]

    def test_terminate_refused_on_wrong_subdomain_confirmation(
        self, api_client, super_admin, suspended_gym
    ):
        auth_client(api_client, super_admin)
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/terminate/",
            {"subdomain_confirmation": "wrong-subdomain"},
            format="json",
        )
        assert res.status_code == 400
        assert "confirmation does not match" in res.data["detail"]

    def test_terminate_success_and_preserves_data_and_logs(
        self, api_client, super_admin, suspended_gym, active_gym
    ):
        auth_client(api_client, super_admin)
        # Create a sample user and payment in suspended gym
        owner = create_user(suspended_gym, User.ROLE_OWNER, "owner_stay@gym.com")
        payment = Payment.objects.create(
            gym=suspended_gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            amount_etb=Decimal("30000.00"),
            method=Payment.METHOD_BANK_TRANSFER,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
        )

        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/terminate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code == 200
        suspended_gym.refresh_from_db()
        assert suspended_gym.status == GymTenant.STATUS_TERMINATED

        # Assert data stays intact
        assert User.all_objects.filter(id=owner.id).exists()
        assert Payment.all_objects.filter(id=payment.id).exists()

        # Assert other gym unaffected
        active_gym.refresh_from_db()
        assert active_gym.status == GymTenant.STATUS_ACTIVE

        # Assert audit log
        audit = AuditLog.all_objects.filter(
            action_type="gym_terminated", affected_record_id=str(suspended_gym.id)
        ).latest("timestamp")
        assert audit.actor == super_admin

    def test_reinstate_refused_for_non_terminated_gym(
        self, api_client, super_admin, active_gym, suspended_gym
    ):
        auth_client(api_client, super_admin)
        # Active
        res = api_client.post(
            f"/api/platform/gyms/{active_gym.id}/reinstate/",
            {"subdomain_confirmation": active_gym.subdomain},
            format="json",
        )
        assert res.status_code == 400
        assert "Only terminated gyms can be reinstated" in res.data["detail"]

        # Suspended
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/reinstate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code == 400
        assert "Only terminated gyms can be reinstated" in res.data["detail"]

    def test_reinstate_refused_on_wrong_subdomain_confirmation(
        self, api_client, super_admin, suspended_gym
    ):
        suspended_gym.status = GymTenant.STATUS_TERMINATED
        suspended_gym.save()

        auth_client(api_client, super_admin)
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/reinstate/",
            {"subdomain_confirmation": "wrong-subdomain"},
            format="json",
        )
        assert res.status_code == 400
        assert "confirmation does not match" in res.data["detail"]

    def test_reinstate_success_goes_to_suspended_and_preserves_suspended_at(
        self, api_client, super_admin, suspended_gym
    ):
        orig_suspended_at = suspended_gym.suspended_at
        suspended_gym.status = GymTenant.STATUS_TERMINATED
        suspended_gym.save()

        auth_client(api_client, super_admin)
        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/reinstate/",
            {"subdomain_confirmation": suspended_gym.subdomain},
            format="json",
        )
        assert res.status_code == 200
        suspended_gym.refresh_from_db()
        assert suspended_gym.status == GymTenant.STATUS_SUSPENDED
        # Verify suspended_at was not reset to now
        assert suspended_gym.suspended_at == orig_suspended_at

        # Verify audit log
        audit = AuditLog.all_objects.filter(
            action_type="gym_reinstated", affected_record_id=str(suspended_gym.id)
        ).latest("timestamp")
        assert audit.actor == super_admin
        assert audit.metadata.get("reinstated_to") == "suspended"


@pytest.mark.django_db
class TestTerminatedAndSuspendedGymAccessEnforcement:
    def test_terminated_gym_refuses_login_for_all_roles(
        self, api_client, suspended_gym
    ):
        suspended_gym.status = GymTenant.STATUS_TERMINATED
        suspended_gym.save()

        roles = [
            (User.ROLE_OWNER, "owner_t@test.com"),
            (User.ROLE_MANAGER, "manager_t@test.com"),
            (User.ROLE_RECEPTION, "reception_t@test.com"),
            (User.ROLE_TRAINER, "trainer_t@test.com"),
            (User.ROLE_MEMBER, "member_t@test.com"),
        ]

        for role, email in roles:
            create_user(suspended_gym, role, email)
            import json

            res = api_client.post(
                "/api/auth/login/",
                {"email": email, "password": "ValidPassword123!"},
                HTTP_HOST=f"{suspended_gym.subdomain}.localhost",
                format="json",
            )
            assert res.status_code == 403
            data = json.loads(res.content) if hasattr(res, "content") else res.data
            assert "closed" in data["detail"]

    def test_suspended_gym_export_window_and_expiration(
        self, api_client, suspended_gym
    ):
        # 1. Within 7-day export window (suspended 2 days ago)
        suspended_gym.suspended_at = timezone.now() - timedelta(days=2)
        suspended_gym.save()

        owner = create_user(suspended_gym, User.ROLE_OWNER, "owner_susp@test.com")
        auth_client(api_client, owner, suspended_gym)

        # Operational API is forbidden
        res = api_client.get("/api/gym/members/")
        assert res.status_code == 403

        # 2. Past 7-day window (suspended 8 days ago)
        suspended_gym.suspended_at = timezone.now() - timedelta(days=8)
        suspended_gym.save()

        # Login blocked for owner past 7-day window
        res_login = api_client.post(
            "/api/auth/login/",
            {"email": "owner_susp@test.com", "password": "ValidPassword123!"},
            HTTP_HOST=f"{suspended_gym.subdomain}.localhost",
            format="json",
        )
        assert res_login.status_code == 403
        assert "expired" in res_login.data["detail"]


@pytest.mark.django_db
class TestPlatformAnalyticsAndNotices:
    def test_platform_analytics_counts_and_revenue(
        self, api_client, super_admin, active_gym, suspended_gym
    ):
        auth_client(api_client, super_admin)

        # Terminated gym
        GymTenant.objects.create(
            name="Terminated Gym",
            subdomain="terminated-gym",
            status=GymTenant.STATUS_TERMINATED,
        )

        # Demo gym (should be excluded from active and revenue)
        demo_gym = GymTenant.objects.create(
            name="Demo Gym",
            subdomain="demo",
            status=GymTenant.STATUS_ACTIVE,
            is_demo=True,
        )

        # Payment on active gym
        Payment.objects.create(
            gym=active_gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            amount_etb=Decimal("30000.00"),
            method=Payment.METHOD_BANK_TRANSFER,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
        )

        # Payment on demo gym (must be excluded)
        Payment.objects.create(
            gym=demo_gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            amount_etb=Decimal("12000.00"),
            method=Payment.METHOD_BANK_TRANSFER,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
        )

        # Non-gym-subscription payment on active gym (must be excluded)
        Payment.objects.create(
            gym=active_gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            amount_etb=Decimal("5000.00"),
            method=Payment.METHOD_BANK_TRANSFER,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
        )

        res = api_client.get("/api/platform/analytics/overview/")
        assert res.status_code == 200
        data = res.data
        assert data["active_gyms"] == 1
        assert data["suspended_gyms"] == 1
        assert data["terminated_gyms"] == 1
        assert data["platform_revenue_etb"] == "30000.00"

    def test_platform_wide_notices_crud_and_permissions(
        self, api_client, super_admin, active_gym
    ):
        # 1. Super Admin posts platform notice
        auth_client(api_client, super_admin)
        res = api_client.post(
            "/api/platform/notices/",
            {
                "title": "System Maintenance Notice",
                "body": "Planned maintenance scheduled for Sunday at 02:00 AM UTC.",
            },
            format="json",
        )
        assert res.status_code == 201
        assert res.data["is_platform_wide"] is True
        assert res.data["telegram_sent"] is False
        notice_id = res.data["id"]

        # 2. Gym Owner sees the platform notice in their notices list
        owner = create_user(active_gym, User.ROLE_OWNER, "owner_pnotice@gym.com")
        auth_client(api_client, owner, active_gym)
        res_list = api_client.get("/api/gym/notices/")
        assert res_list.status_code == 200
        titles = [n["title"] for n in res_list.data]
        assert "System Maintenance Notice" in titles

        # 3. Non-owner (trainer) does not see the platform notice
        trainer_user = create_user(
            active_gym, User.ROLE_TRAINER, "trainer_pnotice@gym.com"
        )
        auth_client(api_client, trainer_user, active_gym)
        res_trainer = api_client.get("/api/gym/notices/")
        assert res_trainer.status_code == 200
        trainer_titles = [n["title"] for n in res_trainer.data]
        assert "System Maintenance Notice" not in trainer_titles

        # 4. Gym Owner cannot delete platform notice
        auth_client(api_client, owner, active_gym)
        res_del = api_client.delete(f"/api/gym/notices/{notice_id}/")
        assert res_del.status_code == 403

        # 5. Super Admin can delete platform notice
        auth_client(api_client, super_admin)
        res_admin_del = api_client.delete(f"/api/platform/notices/{notice_id}/")
        assert res_admin_del.status_code in (200, 204)
        assert not GymNotice.all_objects.filter(id=notice_id).exists()


@pytest.mark.django_db
class TestTierLoweringPreservesDataAndRefusesAccess:
    def test_turning_off_group_classes_preserves_classes_and_refuses_access(
        self, api_client, active_gym
    ):
        owner = create_user(active_gym, User.ROLE_OWNER, "owner_gc@gym.com")
        auth_client(api_client, owner, active_gym)

        trainer_user = create_user(active_gym, User.ROLE_TRAINER, "trainer_gc@gym.com")
        trainer = Trainer.all_objects.get(user=trainer_user)
        start = timezone.now() + timedelta(days=1)
        session = ClassSession.objects.create(
            gym=active_gym,
            title="Yoga",
            trainer=trainer,
            start_time=start,
            end_time=start + timedelta(minutes=60),
            duration_minutes=60,
            capacity=15,
        )

        # Verify access works when flag is ON
        res = api_client.get("/api/gym/classes/")
        assert res.status_code == 200

        # Turn flag OFF (e.g. downgraded by Super Admin)
        active_gym.config.has_group_classes = False
        active_gym.config.save()

        # Access is refused
        res_refused = api_client.get("/api/gym/classes/")
        assert res_refused.status_code == 403

        # Data remains intact
        assert ClassSession.all_objects.filter(id=session.id).exists()

    def test_turning_off_trainer_module_preserves_data_and_refuses_access(
        self, api_client, active_gym
    ):
        owner = create_user(active_gym, User.ROLE_OWNER, "owner_tr@gym.com")
        trainer_user = create_user(active_gym, User.ROLE_TRAINER, "trainer_mod@gym.com")
        trainer = Trainer.all_objects.get(user=trainer_user)

        auth_client(api_client, owner, active_gym)

        # Access trainers list while flag is ON
        res = api_client.get("/api/gym/trainers/")
        assert res.status_code == 200

        # Turn flag OFF
        active_gym.config.has_trainer_module = False
        active_gym.config.save()
        active_gym.refresh_from_db()

        # Access is refused
        res_refused = api_client.get("/api/gym/trainers/")
        assert res_refused.status_code == 403

        # Data remains intact
        assert Trainer.all_objects.filter(id=trainer.id).exists()

    def test_turning_off_analytics_preserves_data_and_hides_revenue_by_plan(
        self, api_client, super_admin, active_gym
    ):
        active_gym.refresh_from_db()
        plan = MembershipPlan.objects.create(
            gym=active_gym,
            name="Monthly Plan",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit="months",
        )
        Payment.objects.create(
            gym=active_gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            plan=plan,
            amount_etb=Decimal("1500.00"),
            method=Payment.METHOD_BANK_TRANSFER,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
        )

        # Flag ON: revenue_by_plan is populated
        summary_on = get_gym_analytics_overview(active_gym)
        assert summary_on["revenue_by_plan"] is not None
        assert len(summary_on["revenue_by_plan"]) == 1
        assert summary_on["upgrade_prompt"] is None

        # Turn flag OFF
        active_gym.config.has_analytics = False
        active_gym.config.save()
        active_gym.refresh_from_db()

        # Flag OFF: revenue_by_plan is None and upgrade_prompt is present
        summary_off = get_gym_analytics_overview(active_gym)
        assert summary_off["revenue_by_plan"] is None
        assert "Upgrade to Growth or Pro" in summary_off["upgrade_prompt"]

        # Underlying data is intact
        assert Payment.all_objects.filter(gym=active_gym).count() == 1

    def test_super_admin_can_suspend_active_gym(
        self, api_client, super_admin, active_gym
    ):
        auth_client(api_client, super_admin, None)
        res = api_client.post(f"/api/platform/gyms/{active_gym.id}/suspend/")
        assert res.status_code == 200
        active_gym.refresh_from_db()
        assert active_gym.status == GymTenant.STATUS_SUSPENDED
        assert active_gym.suspended_at is not None

    def test_super_admin_can_renew_subscription_and_reactivate(
        self, api_client, super_admin, suspended_gym
    ):
        auth_client(api_client, super_admin, None)
        suspended_gym.lapse_flagged_at = timezone.now()
        suspended_gym.save()

        res = api_client.post(
            f"/api/platform/gyms/{suspended_gym.id}/renew/",
            {"amount_etb": "12000.00", "reference": "REF-RENEW-123"},
            format="json",
        )
        assert res.status_code == 200
        suspended_gym.refresh_from_db()
        assert suspended_gym.status == GymTenant.STATUS_ACTIVE
        assert suspended_gym.suspended_at is None
        assert suspended_gym.lapse_flagged_at is None
        assert suspended_gym.subscription_expires_at > timezone.now()

    def test_tenant_list_includes_lapse_flag(self, api_client, super_admin, active_gym):
        active_gym.lapse_flagged_at = timezone.now()
        active_gym.save()

        auth_client(api_client, super_admin, None)
        res = api_client.get("/api/platform/gyms/")
        assert res.status_code == 200
        data = res.json()
        item = next(g for g in data if g["id"] == str(active_gym.id))
        assert item["lapse_flagged_at"] is not None

    def test_super_admin_can_enable_disable_roles(
        self, api_client, super_admin, active_gym
    ):
        auth_client(api_client, super_admin, None)
        res = api_client.patch(
            f"/api/platform/gyms/{active_gym.id}/config/",
            {"disabled_roles": ["manager", "reception"]},
            format="json",
        )
        assert res.status_code == 200
        active_gym.config.refresh_from_db()
        assert set(active_gym.config.disabled_roles) == {"manager", "reception"}

    def test_disabled_role_refuses_login_and_staff_invitation(
        self, api_client, active_gym
    ):
        owner = create_user(active_gym, User.ROLE_OWNER, "owner_dis@gym.com")
        active_gym.config.disabled_roles = ["manager"]
        active_gym.config.save()

        User.objects.create_user(
            email="disabled_mgr@gym.com",
            password="ManagerPassword123!",
            role=User.ROLE_MANAGER,
            gym=active_gym,
            email_verified_at=timezone.now(),
        )

        # Login refused
        res_login = api_client.post(
            "/api/auth/login/",
            {"email": "disabled_mgr@gym.com", "password": "ManagerPassword123!"},
            HTTP_HOST=f"{active_gym.subdomain}.localhost",
        )
        assert res_login.status_code == 403
        assert "disabled" in res_login.json()["detail"].lower()

        # Staff invite refused
        auth_client(api_client, owner, active_gym)
        res_invite = api_client.post(
            "/api/gym/staff/",
            {
                "full_name": "New Manager",
                "email": "newmgr@gym.com",
                "role": "manager",
                "phone": "+251911223344",
            },
            format="json",
        )
        assert res_invite.status_code == 400
        assert "disabled" in str(res_invite.json()).lower()
