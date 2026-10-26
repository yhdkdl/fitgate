"""Service layer for payment processing, Chapa webhooks, and abandoned payment flagging."""

import hashlib
import hmac
import json
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.notifications import create_notification
from apps.accounts.services import record_audit_log
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.memberships.services import (
    create_or_renew_subscription,
    update_member_status,
)
from apps.payments.chapa_client import ChapaAPIError, ChapaClient
from apps.payments.models import (
    GymPaymentConfig,
    GymReceiptCounter,
    Payment,
    PaymentReversal,
    Receipt,
)
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


def _dummy_timing_compare(raw_body: bytes, signature_header: str) -> None:
    """Execute dummy constant-time HMAC comparison to match timing across failure modes."""
    dummy_secret = b"fitgate_constant_timing_dummy_00"
    dummy_sig = hmac.new(dummy_secret, raw_body, hashlib.sha256).hexdigest()
    hmac.compare_digest(
        dummy_sig, signature_header.strip().lower() if signature_header else "none"
    )


def get_next_receipt_sequence_and_number(gym: GymTenant) -> Tuple[int, str]:
    """
    Acquires an exclusive row lock on the gym's receipt counter inside an active transaction.
    Increments the counter by 1, persists it, and returns (sequence, receipt_number).
    Guarantees sequential, gapless numbering without duplicates under concurrency (starting at 1).
    Rolls back automatically if the payment transaction rolls back.
    """
    counter = GymReceiptCounter.all_objects.select_for_update().filter(gym=gym).first()
    if not counter:
        with transaction.atomic():
            GymReceiptCounter.all_objects.get_or_create(gym=gym)
        counter = GymReceiptCounter.all_objects.select_for_update().get(gym=gym)

    if counter.last_receipt_number == 0:
        max_existing = (
            Receipt.all_objects.filter(gym=gym)
            .order_by("-sequence_number")
            .values_list("sequence_number", flat=True)
            .first()
        )
        if max_existing:
            counter.last_receipt_number = max_existing

    counter.last_receipt_number += 1
    counter.save(update_fields=["last_receipt_number", "updated_at"])
    sequence = counter.last_receipt_number
    receipt_number = f"REC-{sequence:06d}"
    return sequence, receipt_number


def process_chapa_webhook(
    raw_body: bytes,
    signature_header: str,
) -> Tuple[bool, str, int]:
    """
    Process incoming Chapa webhook notification with strict security and money rules:
    1. Look up Payment by stored tx_ref (never trust gym or member info in payload).
    2. Tenant isolation: Gym is strictly identified from the stored Payment record.
    3. Verify HMAC-SHA256 signature against gym's configured webhook secret or secret key.
    4. Call Chapa server-side verification API to confirm real gateway transaction.
    5. Verify paid amount and currency match plan price at checkout.
    6. Repeated webhook handling (idempotency): never creates duplicate payment or subscription.
    7. Atomic DB transaction: payment confirmed + subscription activated + member notified + system audit log.
    """
    if not signature_header:
        _dummy_timing_compare(raw_body, signature_header)
        logger.warning("Chapa webhook rejected: missing signature header.")
        return False, "Invalid webhook signature.", 401

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        _dummy_timing_compare(raw_body, signature_header)
        logger.warning("Chapa webhook rejected: malformed JSON payload.")
        return False, "Invalid webhook signature.", 401

    tx_ref = payload.get("tx_ref")
    if not tx_ref:
        _dummy_timing_compare(raw_body, signature_header)
        logger.warning("Chapa webhook rejected: missing tx_ref in payload.")
        return False, "Invalid webhook signature.", 401

    # Locate stored payment record by tx_ref
    payment = (
        Payment.all_objects.filter(chapa_ref=tx_ref)
        .select_related("gym", "member", "plan")
        .first()
    )
    if not payment:
        _dummy_timing_compare(raw_body, signature_header)
        logger.warning("Chapa webhook rejected: unknown tx_ref '%s'.", tx_ref)
        return False, "Invalid webhook signature.", 401

    # Tenancy resolved exclusively from stored payment
    gym = payment.gym
    config = GymPaymentConfig.all_objects.filter(gym=gym).first()
    if not config or not (config.webhook_secret or config.secret_key):
        _dummy_timing_compare(raw_body, signature_header)
        logger.warning(
            "Chapa webhook rejected: gym %s has no active payment configuration or secrets.",
            gym.subdomain,
        )
        return False, "Invalid webhook signature.", 401

    # Verify HMAC SHA256 signature against gym's webhook secret or secret key (constant time)
    sig_header_clean = signature_header.strip().lower()
    wh_match = False
    if config.webhook_secret:
        expected_wh = (
            hmac.new(
                config.webhook_secret.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            )
            .hexdigest()
            .lower()
        )
        wh_match = hmac.compare_digest(expected_wh, sig_header_clean)

    sec_match = False
    if config.secret_key:
        expected_sec = (
            hmac.new(
                config.secret_key.encode("utf-8"),
                raw_body,
                hashlib.sha256,
            )
            .hexdigest()
            .lower()
        )
        sec_match = hmac.compare_digest(expected_sec, sig_header_clean)

    if not (wh_match or sec_match):
        logger.warning(
            "Chapa webhook rejected: forged or invalid signature for tx_ref %s.",
            tx_ref,
        )
        return False, "Invalid webhook signature.", 401

    # Idempotency: if already confirmed or failed, never alter payment, amount, member, or plan
    if payment.status == Payment.STATUS_CONFIRMED:
        logger.info("Chapa webhook idempotency: tx_ref %s already confirmed.", tx_ref)
        return True, "Payment already confirmed.", 200

    if payment.status == Payment.STATUS_FAILED:
        logger.info("Chapa webhook: tx_ref %s already failed.", tx_ref)
        return False, "Payment already marked failed.", 400

    # Server-side verification call to Chapa API
    client = ChapaClient(secret_key=config.secret_key)
    try:
        verify_resp = client.verify_transaction(tx_ref)
    except ChapaAPIError as exc:
        logger.error(
            "Chapa server-side verification failed for tx_ref %s: %s",
            tx_ref,
            exc.message,
        )
        return False, f"Chapa verification gateway error: {exc.message}", 502
    except Exception as exc:
        logger.error(
            "Unexpected error verifying Chapa transaction %s: %s",
            tx_ref,
            exc,
        )
        return False, "Unexpected error communicating with payment gateway.", 502

    if verify_resp.get("status") != "success":
        logger.warning(
            "Chapa verification returned non-success for %s: status=%s, message=%s",
            tx_ref,
            verify_resp.get("status"),
            verify_resp.get("message"),
        )
        payment.status = Payment.STATUS_FAILED
        payment.metadata["chapa_verification_failure"] = {
            "status": verify_resp.get("status"),
            "message": str(verify_resp.get("message", ""))[:200],
        }
        payment.save(update_fields=["status", "metadata", "updated_at"])

        record_audit_log(
            actor=None,
            gym=gym,
            action_type="payment_failed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "tx_ref": tx_ref,
                "actor": "system",
                "reason": str(verify_resp.get("message", "Verification non-success")),
            },
        )

        if payment.member and hasattr(payment.member, "user") and payment.member.user:
            create_notification(
                recipient=payment.member.user,
                notification_type="payment_failed",
                message=(
                    f"Your online payment of {payment.amount_etb} ETB was not completed. "
                    f"You can retry paying online or choose to pay cash at the gym reception desk."
                ),
                gym=gym,
            )
        return False, "Payment verification indicated non-success.", 400

    data = verify_resp.get("data", {})
    if data.get("status") != "success":
        payment.status = Payment.STATUS_FAILED
        payment.metadata["chapa_verification_failure"] = {
            "status": data.get("status"),
        }
        payment.save(update_fields=["status", "metadata", "updated_at"])

        record_audit_log(
            actor=None,
            gym=gym,
            action_type="payment_failed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "tx_ref": tx_ref,
                "actor": "system",
                "reason": f"Data status: {data.get('status')}",
            },
        )

        if payment.member and hasattr(payment.member, "user") and payment.member.user:
            create_notification(
                recipient=payment.member.user,
                notification_type="payment_failed",
                message=(
                    f"Your online payment of {payment.amount_etb} ETB was not completed. "
                    f"You can retry paying online or choose to pay cash at the gym reception desk."
                ),
                gym=gym,
            )
        return False, "Payment verification status is not success.", 400

    # Validate amount and currency match plan price at checkout
    try:
        received_amount = Decimal(str(data.get("amount", "0")))
    except Exception:
        received_amount = Decimal("0.00")
    received_currency = str(data.get("currency", "")).strip().upper()

    if received_amount != payment.amount_etb or received_currency != "ETB":
        logger.warning(
            "Chapa payment amount/currency mismatch on tx_ref %s: expected %s ETB, got %s %s",
            tx_ref,
            payment.amount_etb,
            received_amount,
            received_currency,
        )
        payment.status = Payment.STATUS_FAILED
        payment.metadata["mismatch"] = {
            "expected_amount": str(payment.amount_etb),
            "received_amount": str(received_amount),
            "expected_currency": "ETB",
            "received_currency": received_currency,
        }
        payment.save(update_fields=["status", "metadata", "updated_at"])

        # Notify member
        if payment.member and hasattr(payment.member, "user") and payment.member.user:
            create_notification(
                recipient=payment.member.user,
                notification_type="payment_mismatch",
                message=(
                    "A mismatch was detected between the paid amount/currency and the plan price. "
                    "Your subscription was not activated. Please contact reception."
                ),
                gym=gym,
            )

        # Notify gym staff so paid-but-not-activated payments are never silent
        staff_users = User.all_objects.filter(
            gym=gym,
            is_active=True,
            role__in=[User.ROLE_OWNER, User.ROLE_MANAGER, User.ROLE_RECEPTION],
        )
        for staff in staff_users:
            member_name = payment.member.full_name if payment.member else "A member"
            create_notification(
                recipient=staff,
                notification_type="payment_mismatch_alert",
                message=(
                    f"Payment mismatch detected for {member_name} (tx_ref: {tx_ref}): "
                    f"expected {payment.amount_etb} ETB, Chapa reported {received_amount} {received_currency}. "
                    f"Subscription was NOT activated. Review payment record for manual resolution."
                ),
                gym=gym,
            )

        # Record audit log
        record_audit_log(
            actor=None,
            gym=gym,
            action_type="payment_mismatch_detected",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "tx_ref": tx_ref,
                "actor": "system",
                "expected_amount": str(payment.amount_etb),
                "received_amount": str(received_amount),
                "expected_currency": "ETB",
                "received_currency": received_currency,
            },
        )
        return False, "Amount or currency mismatch.", 400

    # Idempotency: repeated webhook never creates duplicate payment or subscription
    if payment.status == Payment.STATUS_CONFIRMED:
        logger.info("Chapa webhook idempotency: tx_ref %s already confirmed.", tx_ref)
        return True, "Payment already confirmed.", 200

    if payment.status == Payment.STATUS_FAILED:
        logger.info("Chapa webhook: tx_ref %s already failed.", tx_ref)
        return False, "Payment already marked failed.", 400

    # Execute in ONE atomic database transaction strictly bound to stored payment's gym tenant
    from apps.tenants.context import reset_current_tenant, set_current_tenant

    tenant_token = set_current_tenant(gym)
    try:
        with transaction.atomic():
            locked_payment = Payment.all_objects.select_for_update().get(id=payment.id)
            if locked_payment.status == Payment.STATUS_CONFIRMED:
                return True, "Payment already confirmed.", 200

            if locked_payment.status == Payment.STATUS_FAILED:
                return False, "Payment already marked failed.", 400

            locked_payment.status = Payment.STATUS_CONFIRMED
            locked_payment.metadata["chapa_verified"] = data

            # Activate or extend subscription
            # allow_deactivated_plan=True ensures that if plan was deactivated in-flight,
            # the already-paid agreed plan is honored.
            subscription = create_or_renew_subscription(
                member=locked_payment.member,
                plan=locked_payment.plan,
                allow_deactivated_plan=True,
            )
            locked_payment.subscription = subscription
            locked_payment.save(
                update_fields=["status", "subscription", "metadata", "updated_at"]
            )

            # Generate immutable digital receipt with sequential number
            try:
                if not hasattr(locked_payment, "receipt"):
                    sequence, receipt_number = get_next_receipt_sequence_and_number(gym)
                    duration_str = (
                        f"{locked_payment.plan.duration_value} {locked_payment.plan.duration_unit}"
                        if locked_payment.plan
                        else ""
                    )
                    Receipt.all_objects.create(
                        gym=gym,
                        payment=locked_payment,
                        receipt_number=receipt_number,
                        sequence_number=sequence,
                        issued_by=None,
                        amount_etb=locked_payment.amount_etb,
                        currency="ETB",
                        payment_method=Payment.METHOD_CHAPA,
                        member_name=(
                            locked_payment.member.full_name
                            if locked_payment.member
                            else ""
                        ),
                        member_phone=(
                            locked_payment.member.phone if locked_payment.member else ""
                        ),
                        plan_name=(
                            locked_payment.plan.name if locked_payment.plan else ""
                        ),
                        plan_duration=duration_str,
                        notes=f"Chapa online payment tx_ref: {tx_ref}",
                    )
            except Exception as rx_err:
                logger.error(
                    "Failed to generate receipt for Chapa payment %s: %s",
                    tx_ref,
                    rx_err,
                )

            # Notify member
            if (
                locked_payment.member
                and hasattr(locked_payment.member, "user")
                and locked_payment.member.user
            ):
                create_notification(
                    recipient=locked_payment.member.user,
                    notification_type="payment_confirmed",
                    message=(
                        f"Your payment of {locked_payment.amount_etb} ETB for {locked_payment.plan.name} "
                        f"has been confirmed. Your subscription is active until {subscription.end_date}."
                    ),
                    gym=locked_payment.gym,
                )

            # Audit log entry with actor "system"
            record_audit_log(
                actor=None,
                gym=locked_payment.gym,
                action_type="payment_confirmed",
                affected_record_type="Payment",
                affected_record_id=str(locked_payment.id),
                metadata={
                    "method": "chapa",
                    "amount_etb": str(locked_payment.amount_etb),
                    "tx_ref": tx_ref,
                    "actor": "system",
                    "subscription_id": str(subscription.id),
                },
            )
    finally:
        reset_current_tenant(tenant_token)

    return True, "Payment confirmed and subscription activated successfully.", 200


def flag_unfinished_payments(window_minutes: int = 30) -> int:
    """
    Finds online Chapa payments left pending beyond window_minutes (default 30 mins).
    Flags them as abandoned and records notifications for staff follow-up and member.
    """
    cutoff = timezone.now() - timedelta(minutes=window_minutes)
    unfinished_payments = Payment.all_objects.filter(
        payer_type=Payment.PAYER_TYPE_MEMBER,
        method=Payment.METHOD_CHAPA,
        status=Payment.STATUS_PENDING,
        created_at__lte=cutoff,
    ).select_related("gym", "member", "plan")
    count = 0
    for p in unfinished_payments:
        with transaction.atomic():
            p.status = Payment.STATUS_ABANDONED
            p.metadata["abandoned_reason"] = (
                f"Unfinished beyond {window_minutes} minutes"
            )
            p.save(update_fields=["status", "metadata", "updated_at"])

            if p.member and hasattr(p.member, "user") and p.member.user:
                plan_name = p.plan.name if p.plan else "membership"
                create_notification(
                    recipient=p.member.user,
                    notification_type="payment_abandoned",
                    message=(
                        f"Your online payment checkout for {plan_name} timed out. "
                        f"You can retry paying online or choose to pay with cash at the gym reception desk."
                    ),
                    gym=p.gym,
                )

            staff_users = User.all_objects.filter(
                gym=p.gym,
                is_active=True,
                role__in=[User.ROLE_OWNER, User.ROLE_MANAGER],
            )

            for staff in staff_users:
                member_name = p.member.full_name if p.member else "A member"
                plan_name = p.plan.name if p.plan else "plan"
                create_notification(
                    recipient=staff,
                    notification_type="payment_unfinished_alert",
                    message=(
                        f"Online payment of {p.amount_etb} ETB for {member_name} ({plan_name}) "
                        f"was left unfinished beyond {window_minutes} minutes."
                    ),
                    gym=p.gym,
                )

            record_audit_log(
                actor=None,
                gym=p.gym,
                action_type="payment_flagged_abandoned",
                affected_record_type="Payment",
                affected_record_id=str(p.id),
                metadata={
                    "tx_ref": p.chapa_ref,
                    "actor": "system",
                    "window_minutes": window_minutes,
                },
            )
            count += 1
    return count


def record_cash_payment(
    gym: GymTenant,
    member: Member,
    plan: MembershipPlan,
    recorded_by: User,
    notes: str = "",
    idempotency_key: Optional[str] = None,
) -> Tuple[Payment, Receipt, MemberSubscription]:
    """
    Record and confirm a cash payment from a gym member.
    Executed in ONE database transaction:
    1. Validates staff permissions (Owner, Manager, Reception).
    2. Validates tenant scoping: member and plan must belong to gym.
    3. Locks gym tenant and member rows for race condition and sequence safety.
    4. Guards against double-submits at DB level via client request key and row lock.
    5. Amount is strictly plan.price_etb at that moment (immutable).
    6. Creates or renews subscription via shared create_or_renew_subscription.
    7. Creates confirmed Payment record with confirmed_by set to staff actor.
    8. Generates digital Receipt with sequential, immutable receipt number.
    9. Records permanent audit log and member notification.
    """
    if recorded_by.role not in (
        User.ROLE_OWNER,
        User.ROLE_MANAGER,
        User.ROLE_RECEPTION,
    ):
        raise PermissionDenied(
            "Only gym owner, manager, or reception can record cash payments."
        )

    if recorded_by.gym_id != gym.id:
        raise PermissionDenied("Staff does not belong to this gym.")

    if member.gym_id != gym.id:
        raise ValidationError("Member does not belong to this gym.")

    if plan.gym_id != gym.id:
        raise ValidationError("Plan does not belong to this gym.")

    if not plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    # Client request key double-submit pre-check (fast path)
    if idempotency_key:
        existing = (
            Payment.all_objects.select_related("receipt", "subscription")
            .filter(gym=gym, idempotency_key=idempotency_key)
            .first()
        )
        if existing and existing.status == Payment.STATUS_CONFIRMED:
            if existing.member_id != member.id or existing.plan_id != plan.id:
                raise ValidationError(
                    "Idempotency key has already been used for a different member or plan."
                )
            logger.info(
                "Idempotent cash payment request detected with key '%s'. Returning existing record.",
                idempotency_key,
            )
            return (
                existing,
                getattr(existing, "receipt", None),
                existing.subscription,
            )

    with transaction.atomic():
        # 1. Lock gym tenant row for sequence numbering concurrency
        GymTenant.objects.select_for_update().get(id=gym.id)

        # 2. Lock member row for subscription concurrency
        locked_member = Member.all_objects.select_for_update().get(id=member.id)

        # 3. Double-check idempotency key under lock
        if idempotency_key:
            existing = (
                Payment.all_objects.select_related("receipt", "subscription")
                .filter(gym=gym, idempotency_key=idempotency_key)
                .first()
            )
            if existing and existing.status == Payment.STATUS_CONFIRMED:
                if existing.member_id != member.id or existing.plan_id != plan.id:
                    raise ValidationError(
                        "Idempotency key has already been used for a different member or plan."
                    )
                return (
                    existing,
                    getattr(existing, "receipt", None),
                    existing.subscription,
                )

        # 4. Activate or renew subscription via shared service
        # (derives member.status and records audit log for subscription)
        subscription = create_or_renew_subscription(
            member=locked_member,
            plan=plan,
            actor=recorded_by,
        )

        # 5. Create Payment record with immutable plan price at this moment
        payment = Payment.all_objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=locked_member,
            plan=plan,
            subscription=subscription,
            method=Payment.METHOD_CASH,
            amount_etb=plan.price_etb,
            currency="ETB",
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=recorded_by,
            idempotency_key=idempotency_key or None,
            metadata={"notes": notes, "recorded_by": recorded_by.email},
        )

        # 6. Generate sequential Receipt unique per gym via locked per-gym counter
        sequence, receipt_number = get_next_receipt_sequence_and_number(gym)
        duration_str = f"{plan.duration_value} {plan.duration_unit}"

        receipt = Receipt.all_objects.create(
            gym=gym,
            payment=payment,
            receipt_number=receipt_number,
            sequence_number=sequence,
            issued_by=recorded_by,
            amount_etb=payment.amount_etb,
            currency="ETB",
            payment_method=Payment.METHOD_CASH,
            member_name=locked_member.full_name,
            member_phone=locked_member.phone or "",
            plan_name=plan.name,
            plan_duration=duration_str,
            notes=notes,
        )

        # 7. Audit log for cash payment confirmation
        record_audit_log(
            actor=recorded_by,
            gym=gym,
            action_type="cash_payment_confirmed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "member_id": str(locked_member.id),
                "member_name": locked_member.full_name,
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "amount_etb": str(payment.amount_etb),
                "receipt_number": receipt.receipt_number,
                "notes": notes,
            },
        )

        # 8. Notification to member
        if locked_member.user:
            create_notification(
                recipient=locked_member.user,
                notification_type="payment_confirmed",
                message=(
                    f"Your cash payment of {payment.amount_etb} ETB for {plan.name} was confirmed "
                    f"by {recorded_by.full_name or recorded_by.email}. "
                    f"Receipt #{receipt.receipt_number}. "
                    f"Your subscription is active until {subscription.end_date}."
                ),
                gym=gym,
            )

        return payment, receipt, subscription


def record_bank_transfer_payment(
    gym: GymTenant,
    member: Member,
    plan: MembershipPlan,
    recorded_by: User,
    bank_reference: str,
    transfer_date: Any,
    channel: str = "",
    notes: str = "",
    idempotency_key: Optional[str] = None,
) -> Tuple[Payment, Receipt, MemberSubscription]:
    """
    Record and confirm a bank-transfer payment for a gym member.
    Enforces money and tenancy rules:
    1. Only Gym Owner, Manager, or Reception of that gym can record.
    2. Member and plan must belong to the same gym.
    3. Bank reference (3 to 100 chars) is unique per gym FOREVER (case-insensitive).
    4. Transfer date cannot be in the future.
    5. Amount is strictly locked to plan.price_etb at confirmation.
    6. Double submit with the same idempotency key returns the original receipt.
    7. Owner recording is auto-reconciled with an audit log; staff starts unreconciled.
    8. Preserves previous subscription state for exact reversal restoration.
    9. Activates subscription immediately via single shared create_or_renew_subscription.
    10. Creates confirmed Payment and sequential immutable Receipt.
    11. Writes permanent audit log entries and notifies member.
    """
    if recorded_by.role not in (
        User.ROLE_OWNER,
        User.ROLE_MANAGER,
        User.ROLE_RECEPTION,
    ):
        raise PermissionDenied(
            "Only gym owner, manager, or reception can record bank-transfer payments."
        )

    if recorded_by.gym_id != gym.id:
        raise PermissionDenied("Staff does not belong to this gym.")

    if member.gym_id != gym.id:
        raise ValidationError("Member does not belong to this gym.")

    if plan.gym_id != gym.id:
        raise ValidationError("Plan does not belong to this gym.")

    if not plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    if not bank_reference:
        raise ValidationError({"bank_reference": ["Bank reference is required."]})

    cleaned_ref = str(bank_reference).strip()
    if len(cleaned_ref) < 3 or len(cleaned_ref) > 100:
        raise ValidationError(
            {"bank_reference": ["Bank reference must be between 3 and 100 characters."]}
        )
    norm_ref = cleaned_ref.lower()

    if isinstance(transfer_date, str):
        from datetime import date

        try:
            transfer_date = date.fromisoformat(transfer_date)
        except Exception:
            raise ValidationError({"transfer_date": ["Invalid transfer date format."]})

    if not transfer_date:
        raise ValidationError({"transfer_date": ["Transfer date is required."]})

    if transfer_date > timezone.localdate():
        raise ValidationError(
            {"transfer_date": ["Transfer date cannot be in the future."]}
        )

    # Idempotency key pre-check
    if idempotency_key:
        existing = (
            Payment.all_objects.select_related("receipt", "subscription")
            .filter(gym=gym, idempotency_key=idempotency_key)
            .first()
        )
        if existing and existing.status == Payment.STATUS_CONFIRMED:
            if existing.member_id != member.id or existing.plan_id != plan.id:
                raise ValidationError(
                    "Idempotency key has already been used for a different member or plan."
                )
            logger.info(
                "Idempotent bank transfer payment detected with key '%s'. Returning existing record.",
                idempotency_key,
            )
            return (
                existing,
                getattr(existing, "receipt", None),
                existing.subscription,
            )

    # Database-level unique constraint pre-check with plain message
    if Payment.all_objects.filter(gym=gym, bank_reference_normalized=norm_ref).exists():
        raise ValidationError("This bank transaction reference has already been used.")

    with transaction.atomic():
        # 1. Lock gym tenant row for receipt sequence and uniqueness concurrency
        GymTenant.objects.select_for_update().get(id=gym.id)

        # 2. Lock member row for subscription concurrency
        locked_member = Member.all_objects.select_for_update().get(id=member.id)

        # 3. Double-check idempotency key and reference under lock
        if idempotency_key:
            existing = (
                Payment.all_objects.select_related("receipt", "subscription")
                .filter(gym=gym, idempotency_key=idempotency_key)
                .first()
            )
            if existing and existing.status == Payment.STATUS_CONFIRMED:
                if existing.member_id != member.id or existing.plan_id != plan.id:
                    raise ValidationError(
                        "Idempotency key has already been used for a different member or plan."
                    )
                return (
                    existing,
                    getattr(existing, "receipt", None),
                    existing.subscription,
                )

        if Payment.all_objects.filter(
            gym=gym, bank_reference_normalized=norm_ref
        ).exists():
            raise ValidationError(
                "This bank transaction reference has already been used."
            )

        # 4. Capture previous subscription state before activation
        last_sub = (
            MemberSubscription.all_objects.filter(gym=gym, member=locked_member)
            .order_by("-end_date", "-created_at")
            .first()
        )
        if last_sub is None:
            prev_sub_state = {
                "was_first_purchase": True,
                "previous_member_status": locked_member.status,
            }
        else:
            prev_sub_state = {
                "was_first_purchase": False,
                "previous_subscription_id": str(last_sub.id),
                "previous_start_date": last_sub.start_date.isoformat(),
                "previous_end_date": last_sub.end_date.isoformat(),
                "previous_status": last_sub.status,
                "previous_member_status": locked_member.status,
            }

        # 5. Activate subscription immediately via shared service
        subscription = create_or_renew_subscription(
            member=locked_member,
            plan=plan,
            actor=recorded_by,
        )

        # 6. Auto-reconcile if recorded by Owner
        is_owner = recorded_by.role == User.ROLE_OWNER
        is_reconciled = is_owner
        reconciled_at = timezone.now() if is_owner else None
        reconciled_by = recorded_by if is_owner else None

        # 7. Create Payment record
        payment = Payment.all_objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=locked_member,
            plan=plan,
            subscription=subscription,
            method=Payment.METHOD_BANK_TRANSFER,
            amount_etb=plan.price_etb,
            currency="ETB",
            bank_reference=cleaned_ref,
            bank_reference_normalized=norm_ref,
            transfer_date=transfer_date,
            channel=str(channel or "").strip(),
            is_reconciled=is_reconciled,
            reconciled_at=reconciled_at,
            reconciled_by=reconciled_by,
            previous_subscription_state=prev_sub_state,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=recorded_by,
            idempotency_key=idempotency_key or None,
            metadata={
                "notes": notes,
                "recorded_by": recorded_by.email,
                "channel": str(channel or "").strip(),
            },
        )

        # 8. Generate sequential digital Receipt unique per gym via locked per-gym counter
        sequence, receipt_number = get_next_receipt_sequence_and_number(gym)
        duration_str = f"{plan.duration_value} {plan.duration_unit}"

        receipt = Receipt.all_objects.create(
            gym=gym,
            payment=payment,
            receipt_number=receipt_number,
            sequence_number=sequence,
            issued_by=recorded_by,
            amount_etb=payment.amount_etb,
            currency="ETB",
            payment_method=Payment.METHOD_BANK_TRANSFER,
            member_name=locked_member.full_name,
            member_phone=locked_member.phone or "",
            plan_name=plan.name,
            plan_duration=duration_str,
            notes=notes,
        )

        # 9. Audit log for bank transfer confirmation
        record_audit_log(
            actor=recorded_by,
            gym=gym,
            action_type="bank_transfer_payment_confirmed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "member_id": str(locked_member.id),
                "member_name": locked_member.full_name,
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "amount_etb": str(payment.amount_etb),
                "bank_reference": cleaned_ref,
                "transfer_date": str(transfer_date),
                "channel": str(channel or "").strip(),
                "receipt_number": receipt.receipt_number,
                "is_reconciled": is_reconciled,
                "notes": notes,
            },
        )

        if is_owner:
            record_audit_log(
                actor=recorded_by,
                gym=gym,
                action_type="bank_transfer_auto_reconciled",
                affected_record_type="Payment",
                affected_record_id=str(payment.id),
                metadata={
                    "bank_reference": cleaned_ref,
                    "amount_etb": str(payment.amount_etb),
                    "receipt_number": receipt.receipt_number,
                },
            )

        # 10. Member notification
        if locked_member.user:
            create_notification(
                recipient=locked_member.user,
                notification_type="payment_confirmed",
                message=(
                    f"Your bank transfer payment of {payment.amount_etb} ETB (Ref: {cleaned_ref}) for {plan.name} was confirmed "
                    f"by {recorded_by.full_name or recorded_by.email}. "
                    f"Receipt #{receipt.receipt_number}. "
                    f"Your subscription is active until {subscription.end_date}."
                ),
                gym=gym,
            )

        return payment, receipt, subscription


def reconcile_bank_transfers(
    payment_ids: list[str],
    cleared_by: User,
    gym: GymTenant,
) -> int:
    """
    Clear/reconcile bank transfers against bank statement.
    Owner only. Reconciles single transfer or bulk list.
    """
    if cleared_by.role != User.ROLE_OWNER:
        raise PermissionDenied("Only the gym owner can reconcile bank transfers.")

    if cleared_by.gym_id != gym.id:
        raise PermissionDenied("Owner does not belong to this gym.")

    if not payment_ids:
        return 0

    with transaction.atomic():
        payments = list(
            Payment.all_objects.select_for_update().filter(
                gym=gym,
                id__in=payment_ids,
                method=Payment.METHOD_BANK_TRANSFER,
                status=Payment.STATUS_CONFIRMED,
                is_reconciled=False,
            )
        )
        now = timezone.now()
        count = 0
        for p in payments:
            p.is_reconciled = True
            p.reconciled_at = now
            p.reconciled_by = cleared_by
            p.save(update_fields=["is_reconciled", "reconciled_at", "reconciled_by"])
            record_audit_log(
                actor=cleared_by,
                gym=gym,
                action_type="bank_transfer_reconciled",
                affected_record_type="Payment",
                affected_record_id=str(p.id),
                metadata={
                    "bank_reference": p.bank_reference,
                    "amount_etb": str(p.amount_etb),
                    "member_id": str(p.member_id) if p.member_id else None,
                },
            )
            count += 1

        return count


def reverse_bank_transfer_payment(
    payment_id: str,
    reversed_by: User,
    reason: str,
    gym: GymTenant,
) -> Tuple[Payment, PaymentReversal]:
    """
    Reverse an unreconciled bank-transfer payment (Owner only).
    Enforces rules:
    - Only Owner of that gym can reverse.
    - Only unreconciled bank transfers can be reversed.
    - Reversal reason must be between 5 and 500 characters.
    - Refused if member has had subsequent payment, freeze, or subscription change.
    - Restores member subscription to exact state before this payment:
      - First purchase: pending status, no active period.
      - Renewal: previous end date and previous status restored.
    - Runs through shared update_member_status function.
    - Payment status set to 'reversed' and excluded from revenue totals.
    - Creates immutable PaymentReversal record.
    - Writes permanent audit log and member notification.
    - Reversed payments cannot be reversed again.
    """
    if reversed_by.role != User.ROLE_OWNER:
        raise PermissionDenied("Only the gym owner can reverse bank transfers.")

    if reversed_by.gym_id != gym.id:
        raise PermissionDenied("Owner does not belong to this gym.")

    if not reason:
        raise ValidationError({"reason": ["Reversal reason is required."]})

    cleaned_reason = reason.strip()
    if len(cleaned_reason) < 5 or len(cleaned_reason) > 500:
        raise ValidationError(
            {"reason": ["Reversal reason must be between 5 and 500 characters."]}
        )

    with transaction.atomic():
        payment = (
            Payment.all_objects.select_for_update()
            .filter(gym=gym, id=payment_id)
            .first()
        )
        if not payment:
            raise ValidationError("Payment not found.")

        if payment.method != Payment.METHOD_BANK_TRANSFER:
            raise ValidationError("Only bank transfer payments can be reversed.")

        if payment.status == Payment.STATUS_REVERSED:
            raise ValidationError("Payment has already been reversed.")

        if payment.status != Payment.STATUS_CONFIRMED:
            raise ValidationError("Only confirmed payments can be reversed.")

        if payment.is_reconciled:
            raise ValidationError(
                "Only unreconciled bank transfer payments can be reversed."
            )

        # Check subsequent payments
        has_later_payments = Payment.all_objects.filter(
            gym=gym,
            member_id=payment.member_id,
            created_at__gt=payment.created_at,
            status=Payment.STATUS_CONFIRMED,
        ).exists()
        if has_later_payments:
            raise ValidationError(
                "Payment cannot be reversed because a later payment exists for this member."
            )

        # Check freeze
        has_freeze = MemberSubscription.all_objects.filter(
            gym=gym,
            member_id=payment.member_id,
            frozen_days_total__gt=0,
        ).exists()
        if has_freeze:
            raise ValidationError(
                "Payment cannot be reversed because a freeze has been applied to this member's subscription."
            )

        # Check subsequent subscription changes
        if payment.subscription_id:
            has_later_subs = MemberSubscription.all_objects.filter(
                gym=gym,
                member_id=payment.member_id,
                created_at__gt=payment.subscription.created_at,
            ).exists()
            if has_later_subs:
                raise ValidationError(
                    "Payment cannot be reversed because subsequent subscription changes exist for this member."
                )

        locked_member = Member.all_objects.select_for_update().get(id=payment.member_id)
        prev_state = payment.previous_subscription_state or {}

        # Restore subscription to exact state before this payment
        from datetime import date

        if prev_state.get("was_first_purchase"):
            if payment.subscription:
                sub_to_delete = payment.subscription
                payment.subscription = None
                payment.save(update_fields=["subscription"])
                sub_to_delete.delete()
        else:
            prev_sub_id = prev_state.get("previous_subscription_id")
            if payment.subscription:
                sub_to_delete = payment.subscription
                payment.subscription = None
                payment.save(update_fields=["subscription"])
                sub_to_delete.delete()

            if prev_sub_id:
                prev_sub = MemberSubscription.all_objects.filter(
                    id=prev_sub_id, gym=gym
                ).first()
                if prev_sub:
                    if "previous_end_date" in prev_state:
                        prev_sub.end_date = date.fromisoformat(
                            prev_state["previous_end_date"]
                        )
                    if "previous_status" in prev_state:
                        prev_sub.status = prev_state["previous_status"]
                    prev_sub.save(update_fields=["end_date", "status"])

        # Update member status via single shared status function
        update_member_status(locked_member)

        # Update payment status to reversed
        payment.status = Payment.STATUS_REVERSED
        payment.save(update_fields=["status"])

        # Create immutable reversal record
        reversal = PaymentReversal.objects.create(
            gym=gym,
            payment=payment,
            reversed_by=reversed_by,
            reason=cleaned_reason,
        )

        # Record audit log
        record_audit_log(
            actor=reversed_by,
            gym=gym,
            action_type="bank_transfer_payment_reversed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "member_id": str(locked_member.id),
                "member_name": locked_member.full_name,
                "amount_etb": str(payment.amount_etb),
                "bank_reference": payment.bank_reference,
                "reversal_reason": cleaned_reason,
                "reversal_id": str(reversal.id),
            },
        )

        # Member notification
        if locked_member.user:
            create_notification(
                recipient=locked_member.user,
                notification_type="payment_reversed",
                message=(
                    f"Your bank transfer payment of {payment.amount_etb} ETB (Ref: {payment.bank_reference}) "
                    f"has been reversed by gym management. Reason: {cleaned_reason}."
                ),
                gym=gym,
            )

        return payment, reversal


def flag_unreconciled_transfers(days: int = 7) -> Dict[str, int]:
    """
    Flags unreconciled bank-transfer payments older than `days` (default 7).
    - Sets `flagged_unreconciled_at` once per payment (never twice).
    - Sends the gym Owner ONE notification per run per gym with the count.
    - Writes an audit log entry per payment naming confirming staff member.
    - Nothing changes for the member automatically.
    """
    from datetime import timedelta
    from typing import Dict

    cutoff = timezone.now() - timedelta(days=days)
    flagged_per_gym: Dict[str, int] = {}

    with transaction.atomic():
        unreconciled_payments = list(
            Payment.all_objects.select_for_update().filter(
                method=Payment.METHOD_BANK_TRANSFER,
                status=Payment.STATUS_CONFIRMED,
                is_reconciled=False,
                flagged_unreconciled_at__isnull=True,
                created_at__lte=cutoff,
            )
        )

        now = timezone.now()
        for p in unreconciled_payments:
            p.flagged_unreconciled_at = now
            p.save(update_fields=["flagged_unreconciled_at"])

            gym = p.gym
            gym_id_str = str(gym.id)
            flagged_per_gym[gym_id_str] = flagged_per_gym.get(gym_id_str, 0) + 1

            confirming_staff_name = (
                p.confirmed_by.full_name or p.confirmed_by.email
                if p.confirmed_by
                else "Unknown Staff"
            )

            record_audit_log(
                actor=None,
                gym=gym,
                action_type="bank_transfer_unreconciled_flagged",
                affected_record_type="Payment",
                affected_record_id=str(p.id),
                metadata={
                    "payment_id": str(p.id),
                    "bank_reference": p.bank_reference,
                    "amount_etb": str(p.amount_etb),
                    "confirmed_by_id": (
                        str(p.confirmed_by_id) if p.confirmed_by_id else None
                    ),
                    "confirmed_by_name": confirming_staff_name,
                    "created_at": p.created_at.isoformat(),
                    "flagged_at": now.isoformat(),
                },
            )

        # Notify Owner ONE notification per gym per run
        for gym_id_str, count in flagged_per_gym.items():
            owner = (
                User.all_objects.filter(
                    gym_id=gym_id_str, role=User.ROLE_OWNER, is_active=True
                )
                .order_by("created_at")
                .first()
            )
            if owner:
                create_notification(
                    recipient=owner,
                    notification_type="unreconciled_transfers_flagged",
                    message=(
                        f"Daily reconciliation check: {count} bank transfer payment(s) remain unreconciled "
                        f"after 7 days and require your review."
                    ),
                    gym=owner.gym,
                )

    return flagged_per_gym
