"""
Targeted tests for:
(1) Gym subscription payment is absent from every gym-side figure and still counted in platform revenue.
(2) Gym isolation and role refusals for platform notices and support requests.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan
from apps.payments.models import Payment
from apps.payments.services import flag_unreconciled_transfers
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def gym_a():
    gym = GymTenant.objects.create(
        name="Alpha Fitness",
        subdomain="alpha",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config = getattr(gym, "config", None)
    if not config:
        config, _ = GymConfig.objects.get_or_create(gym=gym)
    return gym


@pytest.fixture
def gym_b():
    gym = GymTenant.objects.create(
        name="Beta Athletics",
        subdomain="beta",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config = getattr(gym, "config", None)
    if not config:
        config, _ = GymConfig.objects.get_or_create(gym=gym)
    config.has_notices = True
    config.has_expenses = True
    config.save()
    return gym


@pytest.fixture
def super_admin():
    return User.objects.create_superuser(
        email="superadmin@fitgate.org",
        password="Password123!",
    )


@pytest.fixture
def owner_a(gym_a):
    return User.objects.create_user(
        email="owner@alpha.com",
        password="Password123!",
        role=User.ROLE_OWNER,
        gym=gym_a,
    )


@pytest.fixture
def manager_a(gym_a):
    return User.objects.create_user(
        email="manager@alpha.com",
        password="Password123!",
        role=User.ROLE_MANAGER,
        gym=gym_a,
    )


@pytest.fixture
def reception_a(gym_a):
    return User.objects.create_user(
        email="reception@alpha.com",
        password="Password123!",
        role=User.ROLE_RECEPTION,
        gym=gym_a,
    )


@pytest.fixture
def trainer_a(gym_a):
    return User.objects.create_user(
        email="trainer@alpha.com",
        password="Password123!",
        role=User.ROLE_TRAINER,
        gym=gym_a,
    )


@pytest.fixture
def member_user_a(gym_a):
    u = User.objects.create_user(
        email="member@alpha.com",
        password="Password123!",
        role=User.ROLE_MEMBER,
        gym=gym_a,
    )
    Member.all_objects.create(
        user=u,
        gym=gym_a,
        full_name="John Doe",
        phone="+251911000001",
        waiver_accepted_at=timezone.now(),
    )
    return u


@pytest.fixture
def owner_b(gym_b):
    return User.objects.create_user(
        email="owner@beta.com",
        password="Password123!",
        role=User.ROLE_OWNER,
        gym=gym_b,
    )


def auth_client(user, gym=None):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.mark.django_db
class TestGymSubscriptionPaymentIsolation:
    """
    Verify gym subscription payment (payer_type='gym_subscription') is absent from
    every gym-side figure and still counted in platform revenue.
    """

    def test_gym_subscription_absent_from_gym_figures_and_counted_in_platform(
        self, gym_a, owner_a, manager_a, member_user_a, super_admin
    ):
        member = Member.all_objects.get(user=member_user_a)
        plan = MembershipPlan.all_objects.create(
            gym=gym_a,
            name="Monthly Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=Decimal("500.00"),
        )

        # 1. Member payment of 500 ETB
        member_payment = Payment.all_objects.create(
            gym=gym_a,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=member,
            plan=plan,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal("500.00"),
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=owner_a,
        )

        # 2. Gym platform subscription payment of 10,000 ETB
        sub_payment = Payment.all_objects.create(
            gym=gym_a,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            method=Payment.METHOD_BANK_TRANSFER,
            amount_etb=Decimal("10000.00"),
            bank_reference="PLATFORM-SUB-12345",
            bank_reference_normalized="PLATFORM-SUB-12345",
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=super_admin,
            is_reconciled=False,
        )

        client = auth_client(owner_a, gym=gym_a)

        # (a) Dashboard analytics overview
        res = client.get("/api/gym/analytics/overview/")
        assert res.status_code == 200
        # monthly_net_revenue should be exactly 500.00, not 10500.00
        assert res.data["monthly_net_revenue"] == "500.00"

        # (b) Payments list and confirmed revenue total
        res = client.get("/api/gym/payments/")
        assert res.status_code == 200
        assert res.data["total_confirmed_revenue_etb"] == "500.00"
        results = res.data["results"]
        payment_ids = [p["id"] for p in results]
        assert str(member_payment.id) in payment_ids
        assert str(sub_payment.id) not in payment_ids

        # (c) CSV payments export
        res = client.get("/api/gym/export/payments/")
        assert res.status_code == 200
        content = res.content.decode("utf-8")
        assert "500.00" in content
        assert "10000.00" not in content
        assert "PLATFORM-SUB-12345" not in content

        # (d) Unreconciled bank transfer list
        res = client.get("/api/gym/payments/bank-transfers/unreconciled/")
        assert res.status_code == 200
        unreconciled_ids = [item["id"] for item in res.data.get("results", [])]
        assert str(sub_payment.id) not in unreconciled_ids

        # (e) 7-day sweep should never flag gym platform subscription payments
        flag_unreconciled_transfers()
        sub_payment.refresh_from_db()
        assert sub_payment.flagged_unreconciled_at is None

        # (f) Read-only card 'Your FitGate subscription' in Gym Settings (Owner only)
        res = client.get("/api/gym/subscription/")
        assert res.status_code == 200
        assert res.data["tier"] == gym_a.tier
        assert res.data["status"] == gym_a.status
        past_payments = res.data["past_payments"]
        assert len(past_payments) == 1
        assert past_payments[0]["id"] == str(sub_payment.id)
        assert past_payments[0]["amount"] == "10000.00"
        assert past_payments[0]["reference"] == "PLATFORM-SUB-12345"

        # Manager is refused access to subscription endpoint (Owner only)
        mgr_client = auth_client(manager_a, gym=gym_a)
        res_mgr = mgr_client.get("/api/gym/subscription/")
        assert res_mgr.status_code == 403

        # (g) Platform revenue counts the gym subscription payment and excludes demo gyms
        admin_client = auth_client(super_admin, gym=None)
        res_admin = admin_client.get("/api/platform/analytics/overview/")
        assert res_admin.status_code == 200
        assert res_admin.data["platform_revenue_etb"] == "10000.00"


@pytest.mark.django_db
class TestPlatformNoticesGymIsolationAndRoleRefusal:
    """
    Verify gym isolation and role refusals for platform notices.
    """

    def test_platform_notice_targeted_delivery_isolation_and_role_refusal(
        self,
        gym_a,
        gym_b,
        owner_a,
        owner_b,
        manager_a,
        reception_a,
        trainer_a,
        member_user_a,
        super_admin,
    ):
        admin_client = auth_client(super_admin, gym=None)

        # 1. Super Admin posts targeted notice for Gym A only
        res_targeted = admin_client.post(
            "/api/platform/notices/",
            {
                "title": "Scheduled Maintenance for Gym A",
                "message": "Routine database maintenance will occur tonight.",
                "audience_type": "selected",
                "target_gym_ids": [str(gym_a.id)],
            },
            format="json",
        )
        assert res_targeted.status_code == 201
        targeted_id = res_targeted.data["id"]

        # 2. Super Admin posts global notice for all gyms
        res_global = admin_client.post(
            "/api/platform/notices/",
            {
                "title": "FitGate Platform Update 2.0",
                "message": "We have launched exciting new performance features.",
                "audience_type": "all",
            },
            format="json",
        )
        assert res_global.status_code == 201
        global_id = res_global.data["id"]

        # Bell notifications verified
        notifs_a = Notification.all_objects.filter(recipient=owner_a)
        assert notifs_a.count() == 2

        notifs_b = Notification.all_objects.filter(recipient=owner_b)
        assert notifs_b.count() == 1  # Only the global announcement

        # Gym A Owner views notices
        client_a = auth_client(owner_a, gym=gym_a)
        res = client_a.get("/api/gym/platform-notices/")
        assert res.status_code == 200
        ids_a = [n["id"] for n in res.data]
        assert targeted_id in ids_a
        assert global_id in ids_a

        # Gym B Owner views notices (Targeted notice for Gym A is isolated and invisible)
        client_b = auth_client(owner_b, gym=gym_b)
        res_b = client_b.get("/api/gym/platform-notices/")
        assert res_b.status_code == 200
        ids_b = [n["id"] for n in res_b.data]
        assert targeted_id not in ids_b
        assert global_id in ids_b

        # Role refusals on gym side (Only Owner may view platform notices)
        for non_owner in [manager_a, reception_a, trainer_a, member_user_a]:
            c = auth_client(non_owner, gym=gym_a)
            res_refusal = c.get("/api/gym/platform-notices/")
            assert res_refusal.status_code == 403

        # Super Admin withdraws global notice
        res_withdraw = admin_client.delete(f"/api/platform/notices/{global_id}/")
        assert res_withdraw.status_code == 204

        # Withdrawn notice disappears from Gym B Owner
        res_b_after = client_b.get("/api/gym/platform-notices/")
        ids_b_after = [n["id"] for n in res_b_after.data]
        assert global_id not in ids_b_after

        # But stays in Super Admin audit list with is_withdrawn=True
        res_admin_list = admin_client.get("/api/platform/notices/")
        withdrawn_item = next(
            item for item in res_admin_list.data if item["id"] == global_id
        )
        assert withdrawn_item["is_withdrawn"] is True


@pytest.mark.django_db
class TestSupportRequestsIsolationAndRoleRefusal:
    """
    Verify gym isolation and role refusals for support requests.
    """

    def test_support_request_lifecycle_isolation_and_permissions(
        self,
        gym_a,
        gym_b,
        owner_a,
        owner_b,
        manager_a,
        reception_a,
        trainer_a,
        member_user_a,
        super_admin,
    ):
        # 1. Role refusals: Reception, Trainer, Member cannot access support inbox or send requests
        for non_staff in [reception_a, trainer_a, member_user_a]:
            c = auth_client(non_staff, gym=gym_a)
            res_get = c.get("/api/gym/support-requests/")
            assert res_get.status_code == 403
            res_post = c.post(
                "/api/gym/support-requests/",
                {
                    "request_type": "question",
                    "subject": "Unauthorized request test",
                    "message": "This should be forbidden.",
                },
            )
            assert res_post.status_code == 403

        # 2. Manager creates support request
        mgr_client = auth_client(manager_a, gym=gym_a)
        res_create = mgr_client.post(
            "/api/gym/support-requests/",
            {
                "request_type": "system_problem",
                "subject": "Check-in scanner latency",
                "message": "Check-in scanners take several seconds to process member QR codes.",
            },
        )
        assert res_create.status_code == 201
        req_id = res_create.data["id"]

        # Super Admin receives platform alert notification
        admin_notifs = Notification.all_objects.filter(
            recipient=super_admin, type="support_request"
        )
        assert admin_notifs.exists()

        # 3. Gym isolation: Gym B Owner cannot see Gym A's support requests
        client_b = auth_client(owner_b, gym=gym_b)
        res_b = client_b.get("/api/gym/support-requests/")
        assert res_b.status_code == 200
        assert len(res_b.data) == 0

        # 4. Super Admin views and replies to support thread
        admin_client = auth_client(super_admin, gym=None)
        res_admin_get = admin_client.get(f"/api/platform/support-requests/{req_id}/")
        assert res_admin_get.status_code == 200
        assert res_admin_get.data["subject"] == "Check-in scanner latency"
        assert res_admin_get.data["gym_name"] == "Alpha Fitness"

        res_reply = admin_client.post(
            f"/api/platform/support-requests/{req_id}/reply/",
            {
                "message": "We have analyzed the network logs and deployed a cache update."
            },
        )
        assert res_reply.status_code == 200

        # Bell notifications dispatched to Owner A and creating Manager A
        assert Notification.all_objects.filter(
            recipient=owner_a, type="support_reply"
        ).exists()
        assert Notification.all_objects.filter(
            recipient=manager_a, type="support_reply"
        ).exists()

        # Super Admin resolves request
        res_status = admin_client.patch(
            f"/api/platform/support-requests/{req_id}/status/",
            {"status": "resolved"},
        )
        assert res_status.status_code == 200
        assert res_status.data["status"] == "resolved"

        # 5. Gym staff reply on resolved request automatically reopens it
        res_gym_reply = mgr_client.post(
            f"/api/gym/support-requests/{req_id}/reply/",
            {"message": "Thank you, confirming scanners are now working smoothly!"},
        )
        assert res_gym_reply.status_code == 200
        assert res_gym_reply.data["status"] == "open"
