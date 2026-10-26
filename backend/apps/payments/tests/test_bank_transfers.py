"""
Tests for Sprint 12b: Bank transfer payments, owner reconciliation, and reversal.

Points tested:
1. Duplicate reference (same gym, different case and spaces; other gym allowed).
2. Double submit (same idempotency key returns original receipt; mismatch rejected).
3. Manager and Reception cannot clear or reverse (Owner only).
4. Reversal restores the exact previous state for first purchase and renewal.
5. Reversal refused after a later payment.
6. 7-day flag fires once (sets timestamp once, single notification).
7. Super Admin and other gyms denied.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.services import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Payment, PaymentReversal
from apps.payments.services import (
    flag_unreconciled_transfers,
    record_bank_transfer_payment,
)
from apps.tenants.models import GymTenant


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bole-hub",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="kazanchis",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner_bt@bolehub.com",
        full_name="Bole Owner",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager_bt@bolehub.com",
        full_name="Bole Manager",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception_bt@bolehub.com",
        full_name="Bole Reception",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
    )


@pytest.fixture
def super_admin_user(db):
    u = User.objects.create_superuser(
        email="superadmin_bt@fitgate.com",
        password="SuperAdminPassword123!",
        full_name="Platform SuperAdmin",
    )
    u.must_change_password = False
    u.save()
    return u


@pytest.fixture
def plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Standard Monthly Plan",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1800.00"),
        is_active=True,
    )


@pytest.fixture
def member(db, gym_tenant):
    user = User.objects.create_user(
        email="member_bt@bolehub.com",
        full_name="Abebe Bikila",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
    )
    return Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name="Abebe Bikila",
        phone="+251911223344",
        status=Member.STATUS_PENDING,
        waiver_accepted_at=timezone.now(),
    )


def auth_client(user, host="bole-hub.localhost"):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    client.default_host = host
    return client


@pytest.mark.django_db
class TestBankTransferDuplicateReference:
    """Duplicate reference is unique per gym forever (case/space-insensitive); other gym allowed."""

    def test_duplicate_reference_same_gym_case_and_spaces_refused_other_gym_allowed(
        self, gym_tenant, other_gym, owner_user, member, plan
    ):
        client = auth_client(owner_user)

        # 1. Record first bank transfer payment
        resp1 = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "CBE-TX-998877",
                "transfer_date": str(timezone.localdate()),
                "channel": "CBE",
            },
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp1.status_code == 201

        # 2. Try recording same reference with different case and leading/trailing spaces
        resp_dup = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "  cbe-tx-998877  ",
                "transfer_date": str(timezone.localdate()),
                "channel": "CBE",
            },
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp_dup.status_code == 400
        # Plain message without leaking other member info
        assert "This bank transaction reference has already been used." in str(
            resp_dup.json()
        )

        # 3. Other gym uses the exact same reference -> allowed
        other_owner = User.objects.create_user(
            email="other_owner@kazanchis.com",
            full_name="Other Owner",
            role=User.ROLE_OWNER,
            gym=other_gym,
        )
        other_plan = MembershipPlan.objects.create(
            gym=other_gym,
            name="Other Plan",
            duration_value=1,
            duration_unit="months",
            price_etb=Decimal("2000.00"),
        )
        other_user = User.objects.create_user(
            email="other_member_bt@kazanchis.com",
            full_name="Other Member",
            role=User.ROLE_MEMBER,
            gym=other_gym,
        )
        other_member = Member.all_objects.create(
            gym=other_gym,
            user=other_user,
            full_name="Other Member",
            phone="+251922334455",
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )
        other_client = auth_client(other_owner, host="kazanchis.localhost")
        resp_other = other_client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(other_member.id),
                "plan_id": str(other_plan.id),
                "bank_reference": "CBE-TX-998877",
                "transfer_date": str(timezone.localdate()),
                "channel": "CBE",
            },
            format="json",
            HTTP_HOST="kazanchis.localhost",
        )
        assert resp_other.status_code == 201


@pytest.mark.django_db
class TestBankTransferDoubleSubmit:
    """Idempotency: same key returns original receipt; mismatch on member or plan is rejected."""

    def test_double_submit_same_key_returns_original_receipt(
        self, gym_tenant, reception_user, member, plan
    ):
        client = auth_client(reception_user)
        key = "idemp-bank-key-12345"

        payload = {
            "member_id": str(member.id),
            "plan_id": str(plan.id),
            "bank_reference": "AWASH-REF-100",
            "transfer_date": str(timezone.localdate()),
            "idempotency_key": key,
        }

        # First submit
        resp1 = client.post(
            "/api/gym/payments/bank-transfer/",
            payload,
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp1.status_code == 201
        receipt_1 = resp1.json()["receipt"]["receipt_number"]

        # Double submit with same key and data
        resp2 = client.post(
            "/api/gym/payments/bank-transfer/",
            payload,
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp2.status_code == 201
        assert resp2.json()["receipt"]["receipt_number"] == receipt_1
        assert resp2.json()["payment_id"] == resp1.json()["payment_id"]

        # Different member with same key is rejected
        kebede_user = User.objects.create_user(
            email="kebede_bt@bolehub.com",
            full_name="Kebede",
            role=User.ROLE_MEMBER,
            gym=gym_tenant,
        )
        other_member = Member.all_objects.create(
            gym=gym_tenant,
            user=kebede_user,
            full_name="Kebede",
            phone="+251933445566",
            status=Member.STATUS_PENDING,
            waiver_accepted_at=timezone.now(),
        )
        payload_diff = dict(payload)
        payload_diff["member_id"] = str(other_member.id)
        payload_diff["bank_reference"] = "AWASH-REF-200"

        resp_mismatch = client.post(
            "/api/gym/payments/bank-transfer/",
            payload_diff,
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp_mismatch.status_code == 400


@pytest.mark.django_db
class TestBankTransferPermissions:
    """Manager and Reception cannot clear or reverse bank transfers."""

    def test_manager_and_reception_cannot_clear_or_reverse(
        self, gym_tenant, manager_user, reception_user, member, plan
    ):
        # 1. Reception records bank transfer payment (starts unreconciled)
        payment, receipt, sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="TX-PERM-TEST-1",
            transfer_date=timezone.localdate(),
        )
        assert payment.is_reconciled is False

        # 2. Manager attempts to view unreconciled, clear, or reverse -> 403
        mgr_client = auth_client(manager_user)
        assert (
            mgr_client.get(
                "/api/gym/payments/bank-transfers/unreconciled/",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )

        assert (
            mgr_client.post(
                "/api/gym/payments/bank-transfers/reconcile/",
                {"payment_ids": [str(payment.id)]},
                format="json",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )

        assert (
            mgr_client.post(
                f"/api/gym/payments/{payment.id}/reverse/",
                {"reason": "Attempting manager reversal"},
                format="json",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )

        # 3. Reception attempts to view unreconciled, clear, or reverse -> 403
        rec_client = auth_client(reception_user)
        assert (
            rec_client.get(
                "/api/gym/payments/bank-transfers/unreconciled/",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )

        assert (
            rec_client.post(
                "/api/gym/payments/bank-transfers/reconcile/",
                {"payment_ids": [str(payment.id)]},
                format="json",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )

        assert (
            rec_client.post(
                f"/api/gym/payments/{payment.id}/reverse/",
                {"reason": "Attempting reception reversal"},
                format="json",
                HTTP_HOST="bole-hub.localhost",
            ).status_code
            == 403
        )


@pytest.mark.django_db
class TestBankTransferReversal:
    """Reversal restores exact previous state for first purchase and renewal; refused after later payment."""

    def test_reversal_restores_exact_previous_state_first_purchase(
        self, gym_tenant, owner_user, reception_user, member, plan
    ):
        assert member.status == Member.STATUS_PENDING
        assert member.subscriptions.count() == 0

        # Staff records first purchase
        payment, receipt, sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="FIRST-PURCHASE-TX",
            transfer_date=timezone.localdate(),
        )
        member.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        assert MemberSubscription.all_objects.filter(member=member).count() == 1
        assert payment.is_reconciled is False

        # Owner reverses payment
        owner_client = auth_client(owner_user)
        resp = owner_client.post(
            f"/api/gym/payments/{payment.id}/reverse/",
            {"reason": "Member paid the wrong gym account"},
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp.status_code == 200

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_REVERSED

        # Immutable reversal record created
        reversal = PaymentReversal.all_objects.get(payment=payment)
        assert reversal.reason == "Member paid the wrong gym account"
        assert reversal.reversed_by == owner_user

        # Receipt displays is_reversed
        receipt.refresh_from_db()
        assert receipt.is_reversed is True

        # Member restored to exact prior state: pending, no active period
        member.refresh_from_db()
        assert member.status == Member.STATUS_PENDING
        assert MemberSubscription.all_objects.filter(member=member).count() == 0
        assert member.active_subscription is None

    def test_reversal_restores_exact_previous_state_renewal(
        self, gym_tenant, owner_user, reception_user, member, plan
    ):
        today = timezone.localdate()
        # Prior active subscription
        prior_sub = MemberSubscription.all_objects.create(
            gym=gym_tenant,
            member=member,
            plan=plan,
            start_date=today - timedelta(days=15),
            end_date=today + timedelta(days=15),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        member.status = Member.STATUS_ACTIVE
        member._status_update_allowed = True
        member.save()

        # Renewal payment via bank transfer
        payment, receipt, renewed_sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="RENEWAL-PURCHASE-TX",
            transfer_date=today,
        )
        assert MemberSubscription.all_objects.filter(member=member).count() == 2

        # Owner reverses renewal
        owner_client = auth_client(owner_user)
        resp = owner_client.post(
            f"/api/gym/payments/{payment.id}/reverse/",
            {"reason": "Accidental duplicate renewal recorded"},
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp.status_code == 200

        member.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        assert MemberSubscription.all_objects.filter(member=member).count() == 1
        active_sub = member.active_subscription
        assert active_sub.id == prior_sub.id
        assert active_sub.end_date == today + timedelta(days=15)

    def test_reversal_refused_after_later_payment(
        self, gym_tenant, owner_user, reception_user, member, plan
    ):
        # 1. First bank transfer payment
        payment1, receipt1, sub1 = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="FIRST-TX-TO-REVERSE",
            transfer_date=timezone.localdate(),
        )

        # 2. Later payment occurs
        payment2, receipt2, sub2 = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="SECOND-LATER-TX",
            transfer_date=timezone.localdate(),
        )

        # 3. Owner attempts to reverse the earlier payment -> refused
        owner_client = auth_client(owner_user)
        resp = owner_client.post(
            f"/api/gym/payments/{payment1.id}/reverse/",
            {"reason": "Attempting reversal after subsequent payment"},
            format="json",
            HTTP_HOST="bole-hub.localhost",
        )
        assert resp.status_code == 400
        assert (
            "Payment cannot be reversed because a later payment exists for this member."
            in str(resp.json())
        )


@pytest.mark.django_db
class TestSevenDayFlagCron:
    """7-day flag cron sets timestamp once, notifies owner once, writes audit log."""

    def test_seven_day_flag_fires_once(
        self, gym_tenant, owner_user, reception_user, member, plan
    ):
        # Record bank transfer payment
        payment, receipt, sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="FLAG-CRON-TX-1",
            transfer_date=timezone.localdate() - timedelta(days=8),
        )
        # Backdate payment.created_at to 8 days ago
        Payment.all_objects.filter(id=payment.id).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        payment.refresh_from_db()
        assert payment.flagged_unreconciled_at is None

        # First run: flags payment
        summary1 = flag_unreconciled_transfers(days=7)
        assert summary1.get(str(gym_tenant.id)) == 1

        payment.refresh_from_db()
        assert payment.flagged_unreconciled_at is not None
        flagged_time = payment.flagged_unreconciled_at

        # Verify Owner received ONE notification
        notifications = Notification.all_objects.filter(
            recipient=owner_user,
            type="unreconciled_transfers_flagged",
        )
        assert notifications.count() == 1
        assert (
            "1 bank transfer payment(s) remain unreconciled"
            in notifications.first().message
        )

        # Verify audit log recorded naming confirming staff
        audit = AuditLog.all_objects.filter(
            gym=gym_tenant,
            action_type="bank_transfer_unreconciled_flagged",
        ).first()
        assert audit is not None
        assert audit.metadata["confirmed_by_id"] == str(reception_user.id)
        assert audit.metadata["confirmed_by_name"] == reception_user.full_name

        # Second run: does not re-flag or duplicate notification
        summary2 = flag_unreconciled_transfers(days=7)
        assert summary2.get(str(gym_tenant.id), 0) == 0

        payment.refresh_from_db()
        assert payment.flagged_unreconciled_at == flagged_time
        assert (
            Notification.all_objects.filter(
                recipient=owner_user,
                type="unreconciled_transfers_flagged",
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestSuperAdminAndOtherGymsDenied:
    """Super Admin and other gyms are denied access to bank transfer endpoints."""

    def test_super_admin_denied_on_bank_transfer_endpoints(
        self, gym_tenant, super_admin_user, reception_user, member, plan
    ):
        payment, receipt, sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="SUPERADMIN-TEST-REF",
            transfer_date=timezone.localdate(),
        )

        sa_client = auth_client(super_admin_user, host="localhost")

        # 1. Record bank transfer
        resp_rec = sa_client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "SA-REF-DENIED",
                "transfer_date": str(timezone.localdate()),
            },
            format="json",
        )
        assert resp_rec.status_code in (400, 401, 403)

        # 2. View unreconciled
        assert sa_client.get(
            "/api/gym/payments/bank-transfers/unreconciled/"
        ).status_code in (400, 401, 403)

        # 3. Reconcile
        assert sa_client.post(
            "/api/gym/payments/bank-transfers/reconcile/",
            {"payment_ids": [str(payment.id)]},
            format="json",
        ).status_code in (400, 401, 403)

        # 4. Reverse
        assert sa_client.post(
            f"/api/gym/payments/{payment.id}/reverse/",
            {"reason": "SuperAdmin trying to reverse"},
            format="json",
        ).status_code in (400, 401, 403)

    def test_other_gym_staff_denied_on_bank_transfer_endpoints(
        self, gym_tenant, other_gym, reception_user, member, plan
    ):
        payment, receipt, sub = record_bank_transfer_payment(
            gym=gym_tenant,
            member=member,
            plan=plan,
            recorded_by=reception_user,
            bank_reference="OTHER-GYM-TEST-REF",
            transfer_date=timezone.localdate(),
        )

        other_owner = User.objects.create_user(
            email="other_owner_cross@kazanchis.com",
            full_name="Kazanchis Owner",
            role=User.ROLE_OWNER,
            gym=other_gym,
        )
        other_client = auth_client(other_owner, host="kazanchis.localhost")

        # Other gym owner accessing Bole Hub payment
        resp_rev = other_client.post(
            f"/api/gym/payments/{payment.id}/reverse/",
            {"reason": "Cross-gym reversal attempt"},
            format="json",
            HTTP_HOST="kazanchis.localhost",
        )
        # Should be 400 Bad Request ("Payment not found.") or 403
        assert resp_rev.status_code in (400, 403, 404)
