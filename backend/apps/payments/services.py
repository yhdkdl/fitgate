"""Service layer for payment processing, Chapa webhooks, and abandoned payment flagging."""

import hashlib
import hmac
import json
import logging
import re
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from django.conf import settings
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
    BankReceiptLookupCounter,
    GymPaymentConfig,
    GymReceiptCounter,
    GymReceivingAccount,
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


_CBE_FT_REGEX = re.compile(r"^FT[A-Za-z0-9]{8,14}$")
_CBE_RECEIPT_ID_REGEX = re.compile(r"^(?:v\d{1,2}-)?[A-Za-z0-9]{10,64}$")
_TELEBIRR_REGEX = re.compile(r"^[A-Za-z0-9]{8,35}$")


def validate_bank_receipt_format(bank: str, reference: str) -> Tuple[bool, str]:
    """
    Validates bank receipt reference format before any lookup or rate counter increment.
    Rejects malformed references (with spaces, invalid characters, or mismatching bank patterns).
    Supports test prefixes starting with MOCK- for test suites.
    """
    ref = (reference or "").strip()
    bank_clean = (bank or "").lower().strip()

    if not ref:
        return False, "Bank reference is required."

    if " " in ref:
        return False, "Receipt reference cannot contain spaces."

    if ref.upper().startswith("MOCK-"):
        return True, ""

    if bank_clean == GymReceivingAccount.BANK_CBE:
        if not (_CBE_FT_REGEX.match(ref) or _CBE_RECEIPT_ID_REGEX.match(ref)):
            return (
                False,
                "Invalid CBE receipt reference format. Must be a valid Receipt ID or FT reference.",
            )
        return True, ""
    elif bank_clean == GymReceivingAccount.BANK_TELEBIRR:
        if not _TELEBIRR_REGEX.match(ref):
            return False, "Invalid Telebirr transaction reference format."
        return True, ""
    else:
        if (
            _CBE_FT_REGEX.match(ref)
            or _CBE_RECEIPT_ID_REGEX.match(ref)
            or _TELEBIRR_REGEX.match(ref)
        ):
            return True, ""
        return False, "Invalid bank receipt reference format."


def check_and_increment_bank_lookup_rate_limit() -> bool:
    """
    Atomically increments the rate counter for the current minute.
    Returns True if within limit (<= 20 lookups per minute platform-wide), False if rate limit exceeded.
    """
    now = timezone.now()
    minute_bucket = now.replace(second=0, microsecond=0)
    with transaction.atomic():
        counter, _ = BankReceiptLookupCounter.objects.select_for_update().get_or_create(
            minute_timestamp=minute_bucket,
            defaults={"lookup_count": 0},
        )
        if counter.lookup_count >= 20:
            return False
        counter.lookup_count += 1
        counter.save(update_fields=["lookup_count"])
        return True


def verify_member_bank_receipt(
    gym: GymTenant,
    bank: str,
    reference: str,
    expected_amount: Decimal,
) -> Any:
    """
    Executes bank receipt verification.
    Runs one lookup with total timeout 8s, without holding locks.
    Platform kill switch RECEIPT_VERIFICATION_ENABLED disables the feature.
    Platform rate limit is capped at 20 lookups per minute.
    """
    from apps.payments.verifiers import (
        BankReceiptVerificationResult,
        get_bank_receipt_verifier,
    )

    bank_clean = (bank or "").lower().strip()
    ref_clean = (reference or "").strip()

    if not getattr(settings, "RECEIPT_VERIFICATION_ENABLED", False):
        return BankReceiptVerificationResult(
            status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
            bank=bank_clean,
            reference=ref_clean,
            error_message="Bank receipt verification is disabled at platform level.",
        )

    # Check and increment 20/min rate counter
    if not check_and_increment_bank_lookup_rate_limit():
        return BankReceiptVerificationResult(
            status=BankReceiptVerificationResult.STATUS_COULD_NOT_CHECK,
            bank=bank_clean,
            reference=ref_clean,
            error_message="Platform bank receipt lookup rate limit exceeded.",
        )

    # Fetch active gym receiving accounts
    receiving_accounts = list(
        GymReceivingAccount.all_objects.filter(
            gym=gym,
            is_active=True,
        ).values_list("account_number", flat=True)
    )

    verifier = get_bank_receipt_verifier()
    return verifier.verify(
        bank=bank_clean,
        reference=ref_clean,
        expected_amount=expected_amount,
        receiving_accounts=receiving_accounts,
    )


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
        payment.metadata["unresolved"] = True
        payment.metadata["flagged_for_owner_review"] = True
        payment.metadata["unresolved_reason"] = (
            f"Payment amount mismatch: expected {payment.amount_etb} ETB, received {received_amount} {received_currency}"
        )
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

            if locked_payment.is_upgrade or locked_payment.metadata.get("is_upgrade"):
                today = timezone.localdate()
                locked_member = Member.all_objects.select_for_update().get(
                    id=locked_payment.member_id
                )
                old_sub_id = locked_payment.metadata.get("superseded_subscription_id")
                old_sub = None
                if old_sub_id:
                    old_sub = (
                        MemberSubscription.all_objects.select_for_update()
                        .filter(
                            gym=gym,
                            member=locked_member,
                            id=old_sub_id,
                            status=MemberSubscription.STATUS_ACTIVE,
                            end_date__gte=today,
                        )
                        .first()
                    )

                from apps.memberships.models import MemberFreeze

                has_approved_freeze = MemberFreeze.all_objects.filter(
                    member=locked_member,
                    status=MemberFreeze.STATUS_APPROVED,
                    start_date__gt=today,
                ).exists()

                situation_changed = (
                    not old_sub
                    or locked_member.status
                    in [Member.STATUS_FROZEN, Member.STATUS_SUSPENDED]
                    or has_approved_freeze
                )

                if situation_changed:
                    locked_payment.metadata["unresolved"] = True
                    locked_payment.metadata["flagged_for_owner_review"] = True
                    locked_payment.metadata["unresolved_reason"] = (
                        "Member status or subscription changed while payment was in-flight"
                    )
                    locked_payment.save(
                        update_fields=["status", "metadata", "updated_at"]
                    )

                    staff_users = User.all_objects.filter(
                        gym=gym,
                        is_active=True,
                        role__in=[User.ROLE_OWNER, User.ROLE_MANAGER],
                    )
                    member_name = (
                        locked_member.full_name if locked_member else "A member"
                    )
                    for staff in staff_users:
                        create_notification(
                            recipient=staff,
                            notification_type="payment_unresolved_alert",
                            message=(
                                f"Paid upgrade of {locked_payment.amount_etb} ETB for {member_name} "
                                f"could not be activated automatically because the member's subscription status changed. "
                                f"Review payment record for manual resolution."
                            ),
                            gym=gym,
                        )

                    if (
                        locked_member
                        and hasattr(locked_member, "user")
                        and locked_member.user
                    ):
                        create_notification(
                            recipient=locked_member.user,
                            notification_type="payment_unresolved",
                            message=(
                                f"Your payment of {locked_payment.amount_etb} ETB for upgrading to "
                                f"{locked_payment.plan.name if locked_payment.plan else 'membership'} "
                                f"was received, but could not be activated automatically because your membership status changed. "
                                f"Please contact the front desk."
                            ),
                            gym=gym,
                        )

                    record_audit_log(
                        actor=None,
                        gym=gym,
                        action_type="payment_upgrade_unresolved_alert",
                        affected_record_type="Payment",
                        affected_record_id=str(locked_payment.id),
                        metadata={
                            "tx_ref": tx_ref,
                            "actor": "system",
                            "reason": "Member status changed while payment was in-flight",
                        },
                    )
                    return (
                        True,
                        "Payment recorded but upgrade held for staff resolution due to status change.",
                        200,
                    )

                old_sub.status = MemberSubscription.STATUS_SUPERSEDED
                old_sub.save(update_fields=["status"])

                subscription = create_or_renew_subscription(
                    member=locked_member,
                    plan=locked_payment.plan,
                    start_date=today,
                    allow_deactivated_plan=True,
                )

                from apps.memberships.services import calculate_plan_end_date

                queued_subs = (
                    MemberSubscription.all_objects.filter(
                        gym=gym,
                        member=locked_member,
                        status=MemberSubscription.STATUS_ACTIVE,
                        start_date__gt=today,
                    )
                    .exclude(id=subscription.id)
                    .order_by("start_date")
                )
                prev_end = subscription.end_date
                for qsub in queued_subs:
                    q_start = prev_end + timedelta(days=1)
                    q_end = calculate_plan_end_date(
                        q_start, qsub.plan.duration_value, qsub.plan.duration_unit
                    )
                    qsub.start_date = q_start
                    qsub.end_date = q_end
                    qsub.save(update_fields=["start_date", "end_date"])
                    prev_end = q_end

                locked_payment.subscription = subscription
                locked_payment.save(
                    update_fields=["status", "subscription", "metadata", "updated_at"]
                )

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
                    gross_amount_etb=locked_payment.gross_amount_etb,
                    credit_amount_etb=locked_payment.credit_amount_etb,
                    currency="ETB",
                    payment_method=Payment.METHOD_CHAPA,
                    member_name=(
                        locked_payment.member.full_name if locked_payment.member else ""
                    ),
                    member_phone=(
                        locked_payment.member.phone if locked_payment.member else ""
                    ),
                    plan_name=locked_payment.plan.name if locked_payment.plan else "",
                    plan_duration=duration_str,
                    notes=f"Chapa online plan upgrade tx_ref: {tx_ref}",
                )

                if (
                    locked_payment.member
                    and hasattr(locked_payment.member, "user")
                    and locked_payment.member.user
                ):
                    create_notification(
                        recipient=locked_payment.member.user,
                        notification_type="plan_upgraded",
                        message=(
                            f"Your membership was upgraded to {locked_payment.plan.name}. "
                            f"Prorated credit of {locked_payment.credit_amount_etb} ETB was applied. "
                            f"Amount paid: {locked_payment.amount_etb} ETB. Receipt #{receipt_number}. "
                            f"Your new plan is active until {subscription.end_date}."
                        ),
                        gym=locked_payment.gym,
                    )

                record_audit_log(
                    actor=None,
                    gym=locked_payment.gym,
                    action_type="plan_upgrade_confirmed",
                    affected_record_type="Payment",
                    affected_record_id=str(locked_payment.id),
                    metadata={
                        "method": "chapa",
                        "amount_etb": str(locked_payment.amount_etb),
                        "tx_ref": tx_ref,
                        "actor": "system",
                        "subscription_id": str(subscription.id),
                        "superseded_subscription_id": str(old_sub_id),
                    },
                )
                return True, "Plan upgrade confirmed and activated successfully.", 200

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


def calculate_subscription_days(sub, today=None):
    """
    Calculate (total_days, used_days, remaining_days) for a subscription using
    authoritative upgrade-quote whole-day rules.
    """
    from django.utils import timezone

    if today is None:
        today = timezone.localdate()
    used_days = max(0, (today - sub.start_date).days)
    raw_diff = (sub.end_date - sub.start_date).days
    if sub.plan and sub.plan.duration_unit == "days":
        total_days = max(1, sub.plan.duration_value)
    else:
        if raw_diff in (28, 29) or sub.end_date.day == sub.start_date.day - 1:
            total_days = 30
        else:
            total_days = max(1, raw_diff)
    remaining_days = max(0, total_days - used_days)
    return total_days, used_days, remaining_days


def calculate_plan_upgrade_quote(
    member: Member,
    new_plan: MembershipPlan,
    today: Optional[date] = None,
) -> dict:
    """
    Server-authoritative calculation of plan upgrade credit and net amount to pay.

    Rule 1 & 2:
    - Credit = net amount actually paid for member's current subscription * remaining days / total days.
    - Whole days. Used days = today minus start date.
    - Round DOWN to 2 decimals. Credit never exceeds the new plan's price.
    - Client-submitted credit or net amounts are strictly ignored.

    Rule 3:
    - Upgrade means new_plan.price_etb > current_sub.plan.price_etb.
    - Cheaper or equal-price different plan:
      refused with "This plan costs less than your current one. It can start when your current plan ends on <date>."
    - Same plan is renewal (handled elsewhere).

    Rule 4:
    - Refused while member is frozen, has approved freeze scheduled, is suspended, or is pending.

    Rule 5:
    - No cash refunds ever. If new net amount <= 0, refuse.
    """
    from decimal import ROUND_DOWN, Decimal

    from apps.memberships.models import MemberFreeze, MemberSubscription
    from apps.memberships.services import calculate_plan_end_date

    if today is None:
        today = timezone.localdate()

    if member.gym_id != new_plan.gym_id:
        raise ValidationError("Plan and member belong to different gym tenants.")

    if not new_plan.is_active:
        raise ValidationError("Cannot upgrade to a deactivated plan.")

    if new_plan.trainer_inclusive:
        config = getattr(member.gym, "config", None)
        if not config or not config.has_trainer_module:
            raise ValidationError(
                {
                    "new_plan_id": [
                        "This plan includes a trainer, which is not available on your gym's current tier."
                    ]
                }
            )

    # Rule 4: Refused while member is frozen, suspended, or pending
    if member.status == Member.STATUS_FROZEN:
        raise ValidationError(
            "Member subscription is frozen. Please resolve this before upgrading."
        )

    if member.status == Member.STATUS_SUSPENDED:
        raise ValidationError(
            "Member subscription is suspended. Please resolve this before upgrading."
        )

    if member.status == Member.STATUS_PENDING:
        raise ValidationError(
            "Member has no active subscription. Please purchase a plan first."
        )

    has_approved_freeze = MemberFreeze.all_objects.filter(
        member=member,
        status=MemberFreeze.STATUS_APPROVED,
        start_date__gt=today,
    ).exists()
    if has_approved_freeze:
        raise ValidationError(
            "Member has an approved freeze scheduled. Please resolve this first."
        )

    # Resolve member's current active subscription covering today
    current_sub = (
        MemberSubscription.all_objects.select_related("plan")
        .filter(
            gym=member.gym,
            member=member,
            status=MemberSubscription.STATUS_ACTIVE,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("-end_date", "-created_at")
        .first()
    )

    if not current_sub or not current_sub.plan:
        raise ValidationError(
            "Member has no active subscription covering today to upgrade."
        )

    # Rule 3: Same plan is renewal
    if current_sub.plan_id == new_plan.id:
        raise ValidationError(
            "Selected plan is the same as the current plan. Use the renewal option instead."
        )

    # Rule 3: Upgrade means new plan price is strictly higher than current plan price
    if new_plan.price_etb <= current_sub.plan.price_etb:
        raise ValidationError(
            f"This plan costs less than your current one. It can start when your current plan ends on {current_sub.end_date}."
        )

    # Entitlement check: new plan must include everything current plan includes (trainer-inclusive)
    if current_sub.plan.trainer_inclusive and not new_plan.trainer_inclusive:
        raise ValidationError(
            f"This plan does not include a trainer. You can choose it when your current plan ends on {current_sub.end_date}."
        )

    # Net amount actually paid for member's current subscription
    confirmed_payments = Payment.all_objects.filter(
        subscription=current_sub,
        status=Payment.STATUS_CONFIRMED,
    )
    if confirmed_payments.exists():
        net_paid = sum(p.amount_etb for p in confirmed_payments)
    else:
        net_paid = current_sub.plan.price_etb

    total_days, used_days, remaining_days = calculate_subscription_days(
        current_sub, today=today
    )

    # Credit = net_paid * remaining_days / total_days, round DOWN to 2 decimals
    raw_credit = Decimal(str(net_paid)) * Decimal(remaining_days) / Decimal(total_days)
    credit_amount = raw_credit.quantize(Decimal("0.01"), rounding=ROUND_DOWN)

    # Credit never exceeds the new plan's price
    credit_amount = min(credit_amount, new_plan.price_etb)

    # Gross and net amounts
    gross_amount = new_plan.price_etb
    net_amount = gross_amount - credit_amount

    # Rule 5: No cash refunds ever. If new net amount <= 0, refuse
    if net_amount <= Decimal("0.00"):
        raise ValidationError(
            "Upgrade credit equals or exceeds new plan price. Upgrades cannot result in zero or negative payment."
        )

    new_start_date = today
    new_end_date = calculate_plan_end_date(
        new_start_date, new_plan.duration_value, new_plan.duration_unit
    )

    return {
        "current_subscription_id": str(current_sub.id),
        "current_plan_id": str(current_sub.plan_id),
        "current_plan_name": current_sub.plan.name,
        "current_plan_price_etb": str(current_sub.plan.price_etb),
        "current_start_date": str(current_sub.start_date),
        "current_end_date": str(current_sub.end_date),
        "new_plan_id": str(new_plan.id),
        "new_plan_name": new_plan.name,
        "new_plan_price_etb": str(new_plan.price_etb),
        "total_days": total_days,
        "used_days": used_days,
        "remaining_days": remaining_days,
        "net_paid_etb": str(net_paid),
        "credit_amount_etb": str(credit_amount),
        "gross_amount_etb": str(gross_amount),
        "net_amount_etb": str(net_amount),
        "new_start_date": str(new_start_date),
        "new_end_date": str(new_end_date),
    }


def record_plan_upgrade_cash_payment(
    gym: GymTenant,
    member: Member,
    new_plan: MembershipPlan,
    recorded_by: User,
    notes: str = "",
    idempotency_key: Optional[str] = None,
    today: Optional[date] = None,
) -> Tuple[Payment, Receipt, MemberSubscription]:
    """
    Executes a plan upgrade paid by cash in ONE database transaction:
    - Validates quote
    - Locks gym, member, and current subscription
    - Marks current subscription superseded
    - Creates new subscription starting today for full duration
    - Shifts queued future subscriptions if present
    - Creates Payment recording gross, credit, and net received
    - Creates sequential Receipt displaying gross, credit, and net received
    - Derives member status via update_member_status
    - Records audit log and member notification
    """
    if recorded_by.role not in (
        User.ROLE_OWNER,
        User.ROLE_MANAGER,
        User.ROLE_RECEPTION,
    ):
        raise PermissionDenied(
            "Only gym owner, manager, or reception can record cash upgrade payments."
        )

    if recorded_by.gym_id != gym.id:
        raise PermissionDenied("Staff does not belong to this gym.")

    if member.gym_id != gym.id:
        raise ValidationError("Member does not belong to this gym.")

    if new_plan.gym_id != gym.id:
        raise ValidationError("Plan does not belong to this gym.")

    if not new_plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    # Idempotency fast path check
    if idempotency_key:
        existing = (
            Payment.all_objects.select_related("receipt", "subscription")
            .filter(gym=gym, idempotency_key=idempotency_key)
            .first()
        )
        if existing and existing.status == Payment.STATUS_CONFIRMED:
            return existing, getattr(existing, "receipt", None), existing.subscription

    calc_today = today or timezone.localdate()

    with transaction.atomic():
        # Lock gym row for sequential receipt safety
        GymTenant.objects.select_for_update().get(id=gym.id)
        locked_member = Member.all_objects.select_for_update().get(id=member.id)

        # Re-check idempotency under lock
        if idempotency_key:
            existing = (
                Payment.all_objects.select_related("receipt", "subscription")
                .filter(gym=gym, idempotency_key=idempotency_key)
                .first()
            )
            if existing and existing.status == Payment.STATUS_CONFIRMED:
                return (
                    existing,
                    getattr(existing, "receipt", None),
                    existing.subscription,
                )

        quote = calculate_plan_upgrade_quote(
            member=locked_member, new_plan=new_plan, today=calc_today
        )
        current_sub = MemberSubscription.all_objects.select_for_update().get(
            id=quote["current_subscription_id"]
        )

        # Mark old subscription superseded
        current_sub.status = MemberSubscription.STATUS_SUPERSEDED
        current_sub.save(update_fields=["status"])

        # Create new subscription starting today for full period
        new_sub = create_or_renew_subscription(
            member=locked_member,
            plan=new_plan,
            start_date=calc_today,
            actor=recorded_by,
        )

        # Rule 13: Shift queued subscriptions if any
        from apps.memberships.services import calculate_plan_end_date

        queued_subs = (
            MemberSubscription.all_objects.filter(
                gym=gym,
                member=locked_member,
                status=MemberSubscription.STATUS_ACTIVE,
                start_date__gt=calc_today,
            )
            .exclude(id=new_sub.id)
            .order_by("start_date")
        )
        prev_end = new_sub.end_date
        for qsub in queued_subs:
            q_start = prev_end + timedelta(days=1)
            q_end = calculate_plan_end_date(
                q_start, qsub.plan.duration_value, qsub.plan.duration_unit
            )
            qsub.start_date = q_start
            qsub.end_date = q_end
            qsub.save(update_fields=["start_date", "end_date"])
            prev_end = q_end

        # Create Payment record with gross, credit, and net received
        payment = Payment.all_objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=locked_member,
            plan=new_plan,
            subscription=new_sub,
            method=Payment.METHOD_CASH,
            amount_etb=Decimal(quote["net_amount_etb"]),
            gross_amount_etb=Decimal(quote["gross_amount_etb"]),
            credit_amount_etb=Decimal(quote["credit_amount_etb"]),
            is_upgrade=True,
            currency="ETB",
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=recorded_by,
            idempotency_key=idempotency_key or None,
            metadata={
                "is_upgrade": True,
                "quote": quote,
                "notes": notes,
                "recorded_by": recorded_by.email,
                "superseded_subscription_id": quote["current_subscription_id"],
            },
        )

        # Generate sequential receipt
        sequence, receipt_number = get_next_receipt_sequence_and_number(gym)
        receipt = Receipt.all_objects.create(
            gym=gym,
            payment=payment,
            receipt_number=receipt_number,
            sequence_number=sequence,
            issued_by=recorded_by,
            amount_etb=payment.amount_etb,
            gross_amount_etb=payment.gross_amount_etb,
            credit_amount_etb=payment.credit_amount_etb,
            currency="ETB",
            payment_method=Payment.METHOD_CASH,
            member_name=locked_member.full_name,
            member_phone=locked_member.phone or "",
            plan_name=new_plan.name,
            plan_duration=f"{new_plan.duration_value} {new_plan.duration_unit}",
            notes=notes,
        )

        record_audit_log(
            actor=recorded_by,
            gym=gym,
            action_type="plan_upgrade_confirmed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "member_id": str(locked_member.id),
                "member_name": locked_member.full_name,
                "old_plan_id": quote["current_plan_id"],
                "old_plan_name": quote["current_plan_name"],
                "new_plan_id": quote["new_plan_id"],
                "new_plan_name": quote["new_plan_name"],
                "days_remaining": quote["remaining_days"],
                "credit_etb": quote["credit_amount_etb"],
                "gross_etb": quote["gross_amount_etb"],
                "net_etb": quote["net_amount_etb"],
                "method": "cash",
                "receipt_number": receipt.receipt_number,
                "superseded_subscription_id": quote["current_subscription_id"],
            },
        )

        if locked_member.user:
            create_notification(
                recipient=locked_member.user,
                notification_type="plan_upgraded",
                message=(
                    f"Your membership was upgraded to {new_plan.name}. "
                    f"Prorated credit of {payment.credit_amount_etb} ETB was applied from your previous plan. "
                    f"Amount paid: {payment.amount_etb} ETB. Receipt #{receipt.receipt_number}. "
                    f"Your new plan is active until {new_sub.end_date}."
                ),
                gym=gym,
            )

        return payment, receipt, new_sub


def record_plan_upgrade_bank_transfer_payment(
    gym: GymTenant,
    member: Member,
    new_plan: MembershipPlan,
    recorded_by: User,
    bank_reference: str,
    transfer_date,
    channel: str = "",
    notes: str = "",
    transfer_screenshot: str = "",
    idempotency_key: Optional[str] = None,
    today: Optional[date] = None,
    is_receipt_verified: bool = False,
    receipt_verification_data: Optional[dict] = None,
) -> Tuple[Payment, Receipt, MemberSubscription]:
    """
    Executes a plan upgrade paid by bank transfer in ONE database transaction.
    """
    if recorded_by.role not in (
        User.ROLE_OWNER,
        User.ROLE_MANAGER,
        User.ROLE_RECEPTION,
    ):
        raise PermissionDenied(
            "Only gym owner, manager, or reception can record bank transfer upgrade payments."
        )

    if recorded_by.gym_id != gym.id:
        raise PermissionDenied("Staff does not belong to this gym.")

    if member.gym_id != gym.id:
        raise ValidationError("Member does not belong to this gym.")

    if new_plan.gym_id != gym.id:
        raise ValidationError("Plan does not belong to this gym.")

    if not new_plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    cleaned_ref = str(bank_reference or "").strip()
    if len(cleaned_ref) < 3 or len(cleaned_ref) > 100:
        raise ValidationError("Bank reference must be between 3 and 100 characters.")
    norm_ref = cleaned_ref.lower()

    existing_ref = Payment.all_objects.filter(
        gym=gym, bank_reference_normalized=norm_ref
    ).first()
    if existing_ref:
        raise ValidationError(
            f"Bank reference '{cleaned_ref}' has already been used for this gym."
        )

    # Idempotency fast path check
    if idempotency_key:
        existing = (
            Payment.all_objects.select_related("receipt", "subscription")
            .filter(gym=gym, idempotency_key=idempotency_key)
            .first()
        )
        if existing and existing.status == Payment.STATUS_CONFIRMED:
            return existing, getattr(existing, "receipt", None), existing.subscription

    calc_today = today or timezone.localdate()

    with transaction.atomic():
        GymTenant.objects.select_for_update().get(id=gym.id)
        locked_member = Member.all_objects.select_for_update().get(id=member.id)

        if idempotency_key:
            existing = (
                Payment.all_objects.select_related("receipt", "subscription")
                .filter(gym=gym, idempotency_key=idempotency_key)
                .first()
            )
            if existing and existing.status == Payment.STATUS_CONFIRMED:
                return (
                    existing,
                    getattr(existing, "receipt", None),
                    existing.subscription,
                )

        quote = calculate_plan_upgrade_quote(
            member=locked_member, new_plan=new_plan, today=calc_today
        )
        current_sub = MemberSubscription.all_objects.select_for_update().get(
            id=quote["current_subscription_id"]
        )

        current_sub.status = MemberSubscription.STATUS_SUPERSEDED
        current_sub.save(update_fields=["status"])

        new_sub = create_or_renew_subscription(
            member=locked_member,
            plan=new_plan,
            start_date=calc_today,
            actor=recorded_by,
        )

        from apps.memberships.services import calculate_plan_end_date

        queued_subs = (
            MemberSubscription.all_objects.filter(
                gym=gym,
                member=locked_member,
                status=MemberSubscription.STATUS_ACTIVE,
                start_date__gt=calc_today,
            )
            .exclude(id=new_sub.id)
            .order_by("start_date")
        )
        prev_end = new_sub.end_date
        for qsub in queued_subs:
            q_start = prev_end + timedelta(days=1)
            q_end = calculate_plan_end_date(
                q_start, qsub.plan.duration_value, qsub.plan.duration_unit
            )
            qsub.start_date = q_start
            qsub.end_date = q_end
            qsub.save(update_fields=["start_date", "end_date"])
            prev_end = q_end

        is_owner = recorded_by.role == User.ROLE_OWNER
        is_reconciled = is_owner or is_receipt_verified
        reconciled_at = timezone.now() if is_reconciled else None
        reconciled_by = recorded_by if is_reconciled else None

        payment = Payment.all_objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=locked_member,
            plan=new_plan,
            subscription=new_sub,
            method=Payment.METHOD_BANK_TRANSFER,
            amount_etb=Decimal(quote["net_amount_etb"]),
            gross_amount_etb=Decimal(quote["gross_amount_etb"]),
            credit_amount_etb=Decimal(quote["credit_amount_etb"]),
            is_upgrade=True,
            currency="ETB",
            bank_reference=cleaned_ref,
            bank_reference_normalized=norm_ref,
            transfer_date=transfer_date,
            channel=str(channel or "").strip(),
            transfer_screenshot=transfer_screenshot,
            is_reconciled=is_reconciled,
            reconciled_at=reconciled_at,
            reconciled_by=reconciled_by,
            is_receipt_verified=is_receipt_verified,
            receipt_verification_data=receipt_verification_data or {},
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=recorded_by,
            idempotency_key=idempotency_key or None,
            metadata={
                "is_upgrade": True,
                "quote": quote,
                "notes": notes,
                "recorded_by": recorded_by.email,
                "superseded_subscription_id": quote["current_subscription_id"],
                **(
                    {"auto_reconciled_by": "receipt_verification"}
                    if is_receipt_verified and not is_owner
                    else {}
                ),
            },
        )

        sequence, receipt_number = get_next_receipt_sequence_and_number(gym)
        receipt = Receipt.all_objects.create(
            gym=gym,
            payment=payment,
            receipt_number=receipt_number,
            sequence_number=sequence,
            issued_by=recorded_by,
            amount_etb=payment.amount_etb,
            gross_amount_etb=payment.gross_amount_etb,
            credit_amount_etb=payment.credit_amount_etb,
            currency="ETB",
            payment_method=Payment.METHOD_BANK_TRANSFER,
            member_name=locked_member.full_name,
            member_phone=locked_member.phone or "",
            plan_name=new_plan.name,
            plan_duration=f"{new_plan.duration_value} {new_plan.duration_unit}",
            notes=notes,
        )

        record_audit_log(
            actor=recorded_by,
            gym=gym,
            action_type="plan_upgrade_confirmed",
            affected_record_type="Payment",
            affected_record_id=str(payment.id),
            metadata={
                "member_id": str(locked_member.id),
                "member_name": locked_member.full_name,
                "old_plan_id": quote["current_plan_id"],
                "old_plan_name": quote["current_plan_name"],
                "new_plan_id": quote["new_plan_id"],
                "new_plan_name": quote["new_plan_name"],
                "days_remaining": quote["remaining_days"],
                "credit_etb": quote["credit_amount_etb"],
                "gross_etb": quote["gross_amount_etb"],
                "net_etb": quote["net_amount_etb"],
                "method": "bank_transfer",
                "bank_reference": cleaned_ref,
                "receipt_number": receipt.receipt_number,
                "superseded_subscription_id": quote["current_subscription_id"],
            },
        )

        if is_owner or is_receipt_verified:
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
                    "reason": (
                        "auto-reconciled by receipt verification"
                        if is_receipt_verified
                        else "owner_recorded"
                    ),
                },
            )

        if locked_member.user:
            create_notification(
                recipient=locked_member.user,
                notification_type="plan_upgraded",
                message=(
                    f"Your membership was upgraded to {new_plan.name}. "
                    f"Prorated credit of {payment.credit_amount_etb} ETB was applied from your previous plan. "
                    f"Amount paid: {payment.amount_etb} ETB. Receipt #{receipt.receipt_number}. "
                    f"Your new plan is active until {new_sub.end_date}."
                ),
                gym=gym,
            )

        return payment, receipt, new_sub


def record_cash_payment(
    gym: GymTenant,
    member: Member,
    plan: MembershipPlan,
    recorded_by: User,
    notes: str = "",
    idempotency_key: Optional[str] = None,
    today: Optional[date] = None,
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

    if plan.trainer_inclusive:
        config = getattr(gym, "config", None)
        if not config or not config.has_trainer_module:
            raise PermissionDenied(
                "This plan includes a trainer, which is not available on your gym's current tier."
            )

    if not plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    if plan.trainer_inclusive:
        config = getattr(gym, "config", None)
        if not config or not config.has_trainer_module:
            raise PermissionDenied(
                "This plan includes a trainer, which is not available on your gym's current tier."
            )

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

        # 4. Check if member has an active subscription covering today
        calc_today = today or timezone.localdate()
        current_sub = (
            MemberSubscription.all_objects.select_related("plan")
            .filter(
                gym=gym,
                member=locked_member,
                status=MemberSubscription.STATUS_ACTIVE,
                start_date__lte=calc_today,
                end_date__gte=calc_today,
            )
            .order_by("-end_date", "-created_at")
            .first()
        )
        if current_sub and current_sub.plan_id != plan.id:
            if plan.price_etb > current_sub.plan.price_etb:
                return record_plan_upgrade_cash_payment(
                    gym=gym,
                    member=locked_member,
                    new_plan=plan,
                    recorded_by=recorded_by,
                    notes=notes,
                    idempotency_key=idempotency_key,
                    today=calc_today,
                )
            else:
                raise ValidationError(
                    f"This plan costs less than your current one. It can start when your current plan ends on {current_sub.end_date}."
                )

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
    transfer_screenshot: str = "",
    today: Optional[date] = None,
    is_receipt_verified: bool = False,
    receipt_verification_data: Optional[dict] = None,
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

    if plan.trainer_inclusive:
        config = getattr(gym, "config", None)
        if not config or not config.has_trainer_module:
            raise PermissionDenied(
                "This plan includes a trainer, which is not available on your gym's current tier."
            )

    if not plan.is_active:
        raise ValidationError("Cannot record payment for a deactivated plan.")

    if plan.trainer_inclusive:
        config = getattr(gym, "config", None)
        if not config or not config.has_trainer_module:
            raise PermissionDenied(
                "This plan includes a trainer, which is not available on your gym's current tier."
            )

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

        # 5. Check if member has an active subscription covering today
        calc_today = today or timezone.localdate()
        current_sub = (
            MemberSubscription.all_objects.select_related("plan")
            .filter(
                gym=gym,
                member=locked_member,
                status=MemberSubscription.STATUS_ACTIVE,
                start_date__lte=calc_today,
                end_date__gte=calc_today,
            )
            .order_by("-end_date", "-created_at")
            .first()
        )
        if current_sub and current_sub.plan_id != plan.id:
            if plan.price_etb > current_sub.plan.price_etb:
                return record_plan_upgrade_bank_transfer_payment(
                    gym=gym,
                    member=locked_member,
                    new_plan=plan,
                    recorded_by=recorded_by,
                    bank_reference=bank_reference,
                    transfer_date=transfer_date,
                    channel=channel,
                    notes=notes,
                    transfer_screenshot=transfer_screenshot,
                    idempotency_key=idempotency_key,
                    today=calc_today,
                    is_receipt_verified=is_receipt_verified,
                    receipt_verification_data=receipt_verification_data,
                )
            else:
                raise ValidationError(
                    f"This plan costs less than your current one. It can start when your current plan ends on {current_sub.end_date}."
                )

        subscription = create_or_renew_subscription(
            member=locked_member,
            plan=plan,
            actor=recorded_by,
        )

        # 6. Auto-reconcile if recorded by Owner or verified by receipt
        is_owner = recorded_by.role == User.ROLE_OWNER
        is_reconciled = is_owner or is_receipt_verified
        reconciled_at = timezone.now() if is_reconciled else None
        reconciled_by = recorded_by if is_reconciled else None

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
            transfer_screenshot=transfer_screenshot,
            is_reconciled=is_reconciled,
            reconciled_at=reconciled_at,
            reconciled_by=reconciled_by,
            is_receipt_verified=is_receipt_verified,
            receipt_verification_data=receipt_verification_data or {},
            previous_subscription_state=prev_sub_state,
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=recorded_by,
            idempotency_key=idempotency_key or None,
            metadata={
                "notes": notes,
                "recorded_by": recorded_by.email,
                "channel": str(channel or "").strip(),
                **(
                    {"auto_reconciled_by": "receipt_verification"}
                    if is_receipt_verified and not is_owner
                    else {}
                ),
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

        if is_owner or is_receipt_verified:
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
                    "reason": (
                        "auto-reconciled by receipt verification"
                        if is_receipt_verified
                        else "owner_recorded"
                    ),
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

        if payment.is_upgrade or payment.metadata.get("is_upgrade"):
            raise ValidationError("Plan upgrade payments cannot be reversed.")

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
