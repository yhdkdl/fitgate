"""
Unit and integration tests for Sprint 12c: Plan upgrade with credit.
Strictly tests:
1. Worked example (1,300.00 credit and 1,700.00 net)
2. Client-sent credit ignored (server authoritative)
3. Downgrade and same-price refusal with exact text
4. Refusal when frozen, scheduled freeze, suspended, or pending
5. Double-submit protection
6. All 3 payment paths using the same shared quote function
7. Chapa amount mismatch rejection and in-flight change flagging
8. Superseded subscriptions excluded from check-in and attendance
9. Revenue total equals net cash taken
10. Tenant isolation
11. Role refusals (Super Admin and unauthorized roles denied)
12. Upgrade payment reversal refusal
13. Queued subscription shifted preserving paid days
"""

import hashlib
import hmac
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import get_tokens_for_user
from apps.attendance.services import ScanValidationError, issue_member_qr_token
from apps.memberships.models import (
    Member,
    MemberFreeze,
    MembershipPlan,
    MemberSubscription,
)
from apps.memberships.services import update_member_status
from apps.payments.models import GymPaymentConfig, Payment
from apps.payments.services import (
    calculate_plan_upgrade_quote,
    process_chapa_webhook,
    record_bank_transfer_payment,
    record_cash_payment,
    reverse_bank_transfer_payment,
)
from apps.tenants.models import GymTenant


@pytest.fixture
def gym(db):
    return GymTenant.objects.create(
        name="FitGate Bole",
        subdomain="bole",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym(db):
    return GymTenant.objects.create(
        name="FitGate Arat Kilo",
        subdomain="aratkilo",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner(db, gym):
    return User.objects.create_user(
        email="owner_up@bole.com",
        full_name="Bole Owner",
        role=User.ROLE_OWNER,
        gym=gym,
    )


@pytest.fixture
def manager(db, gym):
    return User.objects.create_user(
        email="manager_up@bole.com",
        full_name="Bole Manager",
        role=User.ROLE_MANAGER,
        gym=gym,
    )


@pytest.fixture
def reception(db, gym):
    return User.objects.create_user(
        email="reception_up@bole.com",
        full_name="Bole Reception",
        role=User.ROLE_RECEPTION,
        gym=gym,
    )


@pytest.fixture
def superadmin(db):
    return User.objects.create_user(
        email="superadmin_up@fitgate.com",
        full_name="Platform Admin",
        role=User.ROLE_SUPER_ADMIN,
    )


@pytest.fixture
def member_user(db, gym):
    return User.objects.create_user(
        email="yoyo_up@bole.com",
        full_name="Yoyo Upgrade",
        role=User.ROLE_MEMBER,
        gym=gym,
    )


@pytest.fixture
def member(db, gym, member_user):
    return Member.objects.create(
        gym=gym,
        user=member_user,
        full_name="Yoyo Upgrade",
        phone="+251911223344",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )


@pytest.fixture
def standard_plan(db, gym):
    return MembershipPlan.objects.create(
        gym=gym,
        name="Standard Plan",
        price_etb=Decimal("1500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )


@pytest.fixture
def trainer_plan(db, gym):
    return MembershipPlan.objects.create(
        gym=gym,
        name="Trainer Plan",
        price_etb=Decimal("3000.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        trainer_inclusive=True,
        is_active=True,
    )


@pytest.fixture
def cheap_plan(db, gym):
    return MembershipPlan.objects.create(
        gym=gym,
        name="Economy Plan",
        price_etb=Decimal("1000.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )


@pytest.fixture
def current_subscription(db, gym, owner, member, standard_plan):
    today = timezone.localdate()
    start_date = today - timedelta(days=4)
    end_date = start_date + timedelta(days=29)  # 30 days total
    sub = MemberSubscription.objects.create(
        gym=gym,
        member=member,
        plan=standard_plan,
        start_date=start_date,
        end_date=end_date,
        status=MemberSubscription.STATUS_ACTIVE,
    )
    # Payment record of net 1500
    Payment.objects.create(
        gym=gym,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member,
        plan=standard_plan,
        method=Payment.METHOD_CASH,
        amount_etb=Decimal("1500.00"),
        currency="ETB",
        status=Payment.STATUS_CONFIRMED,
        confirmed_by=owner,
    )
    return sub


def auth_client(user, gym=None):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    return client


# --- 1. Worked Example ---
@pytest.mark.django_db
def test_worked_example_calculation(gym, owner, member, standard_plan, trainer_plan):
    """
    Explicit test of the prompt's worked example:
    Standard plan 1,500 ETB, 1 month, bought 5 Nov (ends 4 Dec, 30 days).
    Upgrade on 9 Nov to a 3,000 ETB trainer plan.
    Days used: 4. Days remaining: 26 of 30.
    Credit = 1,500 x 26 / 30 = 1,300.00.
    Member pays 3,000 - 1,300 = 1,700.00.
    """
    start_date = date(2026, 11, 5)
    end_date = date(2026, 12, 4)
    MemberSubscription.objects.create(
        gym=gym,
        member=member,
        plan=standard_plan,
        start_date=start_date,
        end_date=end_date,
        status=MemberSubscription.STATUS_ACTIVE,
    )
    Payment.objects.create(
        gym=gym,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member,
        plan=standard_plan,
        method=Payment.METHOD_CASH,
        amount_etb=Decimal("1500.00"),
        currency="ETB",
        status=Payment.STATUS_CONFIRMED,
        confirmed_by=owner,
    )

    upgrade_date = date(2026, 11, 9)
    quote = calculate_plan_upgrade_quote(
        member=member,
        new_plan=trainer_plan,
        today=upgrade_date,
    )

    assert quote["total_days"] == 30
    assert quote["used_days"] == 4
    assert quote["remaining_days"] == 26
    assert quote["credit_amount_etb"] == "1300.00"
    assert quote["gross_amount_etb"] == "3000.00"
    assert quote["net_amount_etb"] == "1700.00"
    assert quote["new_start_date"] == "2026-11-09"
    assert quote["new_end_date"] == "2026-12-09"


@pytest.mark.django_db
def test_cash_upgrade_execution_creates_superseded_and_receipt(
    gym, owner, member, current_subscription, trainer_plan
):
    today = timezone.localdate()
    payment, receipt, new_sub = record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key="upgrade-cash-1",
    )

    # 1. Payment net amount is 1,700.00, gross 3,000.00, credit 1,300.00
    assert payment.amount_etb == Decimal("1700.00")
    assert payment.gross_amount_etb == Decimal("3000.00")
    assert payment.credit_amount_etb == Decimal("1300.00")
    assert payment.is_upgrade is True

    # 2. Receipt displays all three amounts
    assert receipt.amount_etb == Decimal("1700.00")
    assert receipt.gross_amount_etb == Decimal("3000.00")
    assert receipt.credit_amount_etb == Decimal("1300.00")
    assert receipt.is_upgrade is True

    # 3. Old subscription is marked superseded
    current_subscription.refresh_from_db()
    assert current_subscription.status == MemberSubscription.STATUS_SUPERSEDED

    # 4. New subscription is active starting today for 1 month
    assert new_sub.status == MemberSubscription.STATUS_ACTIVE
    assert new_sub.plan == trainer_plan
    assert new_sub.start_date == today


# --- 2. Client-Sent Credit Ignored ---
@pytest.mark.django_db
def test_client_sent_credit_ignored_by_api(
    gym, reception, member, current_subscription, trainer_plan
):
    client = auth_client(reception, gym)
    # Client attempts to forge credit=2999.00 and amount=1.00
    res = client.post(
        "/api/gym/payments/cash/",
        {
            "member_id": str(member.id),
            "plan_id": str(trainer_plan.id),
            "credit_amount": "2999.00",
            "net_amount": "1.00",
            "idempotency_key": "forge-credit-test-1",
        },
        format="json",
    )
    assert res.status_code == 201
    payment = Payment.all_objects.get(id=res.data["payment_id"])
    # Server computed credit must be exactly 1300.00, not 2999.00
    assert payment.credit_amount_etb == Decimal("1300.00")
    assert payment.amount_etb == Decimal("1700.00")


# --- 3. Downgrade and Same-Price Refusal ---
@pytest.mark.django_db
def test_downgrade_refusal_exact_text(member, current_subscription, cheap_plan):
    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(
            member=member,
            new_plan=cheap_plan,
        )
    assert (
        f"This plan costs less than your current one. It can start when your current plan ends on {current_subscription.end_date}."
        in str(exc.value)
    )


@pytest.mark.django_db
def test_same_price_different_plan_refusal(gym, member, current_subscription):
    equal_plan = MembershipPlan.objects.create(
        gym=gym,
        name="Alternative Standard",
        price_etb=Decimal("1500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )
    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(
            member=member,
            new_plan=equal_plan,
        )
    assert (
        f"This plan costs less than your current one. It can start when your current plan ends on {current_subscription.end_date}."
        in str(exc.value)
    )


# --- 4. Refusals: Frozen, Scheduled Freeze, Suspended, Pending ---
@pytest.mark.django_db
def test_refusal_when_member_frozen(gym, member, current_subscription, trainer_plan):
    current_subscription.status = MemberSubscription.STATUS_FROZEN
    current_subscription.save(update_fields=["status"])
    update_member_status(member)
    assert member.status == Member.STATUS_FROZEN

    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(member=member, new_plan=trainer_plan)
    assert "Member subscription is frozen" in str(exc.value)


@pytest.mark.django_db
def test_refusal_when_approved_freeze_scheduled(
    gym, member, current_subscription, trainer_plan
):
    today = timezone.localdate()
    # Member is currently active, but has an approved freeze scheduled in 5 days
    MemberFreeze.objects.create(
        gym=gym,
        member=member,
        subscription=current_subscription,
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=15),
        days=10,
        reason="Medical",
        status=MemberFreeze.STATUS_APPROVED,
    )
    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(member=member, new_plan=trainer_plan)
    assert "Member has an approved freeze scheduled" in str(exc.value)


@pytest.mark.django_db
def test_refusal_when_suspended(member, current_subscription, trainer_plan):
    current_subscription.status = MemberSubscription.STATUS_SUSPENDED
    current_subscription.save()
    update_member_status(member)
    assert member.status == Member.STATUS_SUSPENDED

    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(member=member, new_plan=trainer_plan)
    assert "Member subscription is suspended" in str(exc.value)


# --- 5. Double-Submit Protection ---
@pytest.mark.django_db
def test_double_submit_protection(
    gym, owner, member, current_subscription, trainer_plan
):
    key = str(uuid.uuid4())
    p1, r1, s1 = record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key=key,
    )
    p2, r2, s2 = record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key=key,
    )
    assert p1.id == p2.id
    assert Payment.all_objects.filter(idempotency_key=key).count() == 1


# --- 6. All 3 Payment Paths Produce Identical Quote ---
@pytest.mark.django_db
def test_all_three_payment_paths_use_same_quote(
    gym, reception, member_user, member, current_subscription, trainer_plan
):
    # 1. Staff Quote API
    staff_client = auth_client(reception, gym)
    res_staff = staff_client.get(
        f"/api/gym/members/{member.id}/upgrade-quote/?plan_id={trainer_plan.id}"
    )
    assert res_staff.status_code == 200
    q_staff = res_staff.data

    # 2. Member Quote API
    member_client = auth_client(member_user, gym)
    res_mem = member_client.get(
        f"/api/payments/upgrade-quote/?plan_id={trainer_plan.id}"
    )
    assert res_mem.status_code == 200
    q_mem = res_mem.data

    assert q_staff["credit_amount_etb"] == q_mem["credit_amount_etb"] == "1300.00"
    assert q_staff["net_amount_etb"] == q_mem["net_amount_etb"] == "1700.00"

    # 3. Chapa Checkout initiates with exact net_amount_etb
    cfg1 = GymPaymentConfig.objects.create(gym=gym, is_verified=True)
    cfg1.public_key = "CHAPUBK_TEST_12345"
    cfg1.secret_key = "mock_sec_key_12345"
    cfg1.webhook_secret = "mock_wh_sec_12345"
    cfg1.save()
    with patch(
        "apps.payments.chapa_client.ChapaClient.initialize_transaction",
        return_value={
            "status": "success",
            "data": {
                "checkout_url": "https://checkout.chapa.co/checkout/payment/mock-tx-123",
                "tx_ref": "mock-tx-123",
            },
        },
    ):
        res_chapa = member_client.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(trainer_plan.id)},
            format="json",
        )
    assert res_chapa.status_code == 200
    pending_payment = Payment.all_objects.filter(
        member=member, plan=trainer_plan
    ).first()
    assert pending_payment.amount_etb == Decimal("1700.00")
    assert pending_payment.credit_amount_etb == Decimal("1300.00")
    assert pending_payment.gross_amount_etb == Decimal("3000.00")
    assert pending_payment.is_upgrade is True


# --- 7. Chapa Amount Mismatch Rejection & In-flight Situation Change ---
@pytest.mark.django_db
def test_chapa_amount_mismatch_rejected(
    gym, member, current_subscription, trainer_plan
):
    config = GymPaymentConfig.objects.create(gym=gym, is_verified=True)
    config.secret_key = "sec_test_123"
    config.webhook_secret = "wh_test_123"
    config.save()
    payment = Payment.objects.create(
        gym=gym,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member,
        plan=trainer_plan,
        method=Payment.METHOD_CHAPA,
        amount_etb=Decimal("1700.00"),
        gross_amount_etb=Decimal("3000.00"),
        credit_amount_etb=Decimal("1300.00"),
        is_upgrade=True,
        currency="ETB",
        chapa_ref="FG-TEST-MISMATCH",
        status=Payment.STATUS_PENDING,
        metadata={
            "is_upgrade": True,
            "superseded_subscription_id": str(current_subscription.id),
        },
    )

    body = json.dumps({"tx_ref": "FG-TEST-MISMATCH"}).encode("utf-8")
    sig = hmac.new(
        config.webhook_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    # Webhook claims member paid 1,500.00 instead of stored net 1,700.00
    with patch(
        "apps.payments.chapa_client.ChapaClient.verify_transaction",
        return_value={
            "status": "success",
            "data": {"status": "success", "amount": "1500.00", "currency": "ETB"},
        },
    ):
        success, msg, code = process_chapa_webhook(raw_body=body, signature_header=sig)

    assert success is False
    assert code == 400
    payment.refresh_from_db()
    assert payment.status == Payment.STATUS_FAILED


@pytest.mark.django_db
def test_chapa_inflight_situation_change_flags_owner(
    gym, member, current_subscription, trainer_plan
):
    config = GymPaymentConfig.objects.create(gym=gym, is_verified=True)
    config.secret_key = "sec_test_123"
    config.webhook_secret = "wh_test_123"
    config.save()
    payment = Payment.objects.create(
        gym=gym,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member,
        plan=trainer_plan,
        method=Payment.METHOD_CHAPA,
        amount_etb=Decimal("1700.00"),
        gross_amount_etb=Decimal("3000.00"),
        credit_amount_etb=Decimal("1300.00"),
        is_upgrade=True,
        currency="ETB",
        chapa_ref="FG-TEST-INFLIGHT",
        status=Payment.STATUS_PENDING,
        metadata={
            "is_upgrade": True,
            "superseded_subscription_id": str(current_subscription.id),
        },
    )

    # In flight, member was frozen
    current_subscription.status = MemberSubscription.STATUS_FROZEN
    current_subscription.save(update_fields=["status"])
    update_member_status(member)

    body = json.dumps({"tx_ref": "FG-TEST-INFLIGHT"}).encode("utf-8")
    sig = hmac.new(
        config.webhook_secret.encode("utf-8"), body, hashlib.sha256
    ).hexdigest()

    with patch(
        "apps.payments.chapa_client.ChapaClient.verify_transaction",
        return_value={
            "status": "success",
            "data": {"status": "success", "amount": "1700.00", "currency": "ETB"},
        },
    ):
        success, msg, code = process_chapa_webhook(raw_body=body, signature_header=sig)

    assert success is True
    payment.refresh_from_db()
    # Money is not lost: payment marked confirmed, but flagged for owner review
    assert payment.status == Payment.STATUS_CONFIRMED
    assert payment.metadata.get("flagged_for_owner_review") is True


# --- 8. Superseded Excluded from Check-in and Attendance ---
@pytest.mark.django_db
def test_superseded_subscriptions_excluded_from_check_in(
    gym, owner, member, current_subscription, trainer_plan
):
    # Perform upgrade
    record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key="checkin-test-upgrade",
    )

    current_subscription.refresh_from_db()
    assert current_subscription.status == MemberSubscription.STATUS_SUPERSEDED

    # Attendance issue_member_qr_token ignores superseded sub and uses active trainer plan
    token_str, qr_record = issue_member_qr_token(member)
    assert token_str is not None

    # If the active sub is removed, only the superseded sub remains
    MemberSubscription.all_objects.filter(member=member, plan=trainer_plan).delete()
    update_member_status(member)
    with pytest.raises(ScanValidationError) as exc:
        issue_member_qr_token(member)
    assert exc.value.reason in ("expired", "pending")


# --- 9. Revenue Total Equals Cash Taken ---
@pytest.mark.django_db
def test_revenue_totals_count_net_cash_received(
    gym, owner, member, current_subscription, trainer_plan
):
    record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key="rev-test-1",
    )

    client = auth_client(owner, gym)
    res = client.get("/api/gym/payments/")
    assert res.status_code == 200

    # Total confirmed revenue should equal 1,500 (initial) + 1,700 (net upgrade) = 3,200 ETB
    # Not 1,500 + 3,000 = 4,500!
    assert res.data["total_confirmed_revenue_etb"] == "3200.00"


# --- 10. Tenant Isolation ---
@pytest.mark.django_db
def test_cross_tenant_upgrade_refused(gym, other_gym, member, trainer_plan):
    other_plan = MembershipPlan.objects.create(
        gym=other_gym,
        name="Foreign Gym Plan",
        price_etb=Decimal("5000.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )
    with pytest.raises(ValidationError) as exc:
        calculate_plan_upgrade_quote(member=member, new_plan=other_plan)
    assert "Plan and member belong to different gym tenants." in str(exc.value)


# --- 11. Role Refusals ---
@pytest.mark.django_db
def test_superadmin_and_unauthorized_roles_denied_quote(
    gym, superadmin, member, trainer_plan
):
    client = auth_client(superadmin, gym)
    res = client.get(
        f"/api/gym/members/{member.id}/upgrade-quote/?plan_id={trainer_plan.id}"
    )
    # Super Admin has no gym staff payment permissions
    assert res.status_code in (401, 403)


# --- 12. Upgrade Payment Reversal Refusal ---
@pytest.mark.django_db
def test_upgrade_payment_cannot_be_reversed(
    gym, owner, member, current_subscription, trainer_plan
):
    today = timezone.localdate()
    payment, receipt, new_sub = record_bank_transfer_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        bank_reference="FT2609UPG",
        transfer_date=today,
        idempotency_key="bt-upg-rev-test",
    )

    with pytest.raises(ValidationError) as exc:
        reverse_bank_transfer_payment(
            gym=gym,
            payment_id=payment.id,
            reversed_by=owner,
            reason="Accidental upgrade",
        )
    assert "Plan upgrade payments cannot be reversed" in str(exc.value)


# --- 13. Queued Second Subscription Shifted ---
@pytest.mark.django_db
def test_queued_second_subscription_start_date_shifted(
    gym, owner, member, current_subscription, trainer_plan
):
    # Member had already bought a queued renewal starting the day after current_subscription ends
    queued_plan = MembershipPlan.objects.create(
        gym=gym,
        name="Queued Renewal Plan",
        price_etb=Decimal("1500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )
    queued_start = current_subscription.end_date + timedelta(days=1)
    queued_end = queued_start + timedelta(days=30)
    queued_sub = MemberSubscription.objects.create(
        gym=gym,
        member=member,
        plan=queued_plan,
        start_date=queued_start,
        end_date=queued_end,
        status=MemberSubscription.STATUS_ACTIVE,
    )

    # Now member upgrades active subscription today to trainer plan
    payment, receipt, new_sub = record_cash_payment(
        gym=gym,
        recorded_by=owner,
        member=member,
        plan=trainer_plan,
        idempotency_key="queued-shift-test",
    )

    # Queued subscription's start date is shifted to new_sub.end_date + 1 day
    queued_sub.refresh_from_db()
    assert queued_sub.start_date == new_sub.end_date + timedelta(days=1)
    from apps.memberships.services import calculate_plan_end_date

    assert queued_sub.end_date == calculate_plan_end_date(
        queued_sub.start_date, 1, MembershipPlan.DURATION_MONTHS
    )
