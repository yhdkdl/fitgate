"""Service layer for payment processing, Chapa webhooks, and abandoned payment flagging."""

import hashlib
import hmac
import json
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Tuple

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.notifications import create_notification
from apps.accounts.services import record_audit_log
from apps.memberships.services import create_or_renew_subscription
from apps.payments.chapa_client import ChapaAPIError, ChapaClient
from apps.payments.models import GymPaymentConfig, Payment

logger = logging.getLogger(__name__)


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
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        logger.warning("Chapa webhook rejected: malformed JSON payload.")
        return False, "Malformed JSON payload.", 400

    tx_ref = payload.get("tx_ref")
    if not tx_ref:
        logger.warning("Chapa webhook rejected: missing tx_ref in payload.")
        return False, "Missing tx_ref in payload.", 400

    # Locate stored payment record by tx_ref
    payment = (
        Payment.all_objects.filter(chapa_ref=tx_ref)
        .select_related("gym", "member", "plan")
        .first()
    )
    if not payment:
        logger.warning("Chapa webhook rejected: unknown tx_ref '%s'.", tx_ref)
        return False, "Payment record not found for transaction reference.", 400

    # Tenancy resolved exclusively from stored payment
    gym = payment.gym
    config = GymPaymentConfig.all_objects.filter(gym=gym).first()
    if not config or not config.is_configured:

        logger.warning(
            "Chapa webhook rejected: gym %s has no active payment configuration.",
            gym.subdomain,
        )
        return False, "Gym payment configuration unavailable.", 401

    # Verify HMAC SHA256 signature
    secret = config.webhook_secret or config.secret_key
    if not signature_header or not secret:
        logger.warning("Chapa webhook rejected: missing signature or secret key.")
        return False, "Missing signature or webhook secret.", 401

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig.lower(), signature_header.strip().lower()):
        logger.warning(
            "Chapa webhook rejected: forged or invalid signature for tx_ref %s.",
            tx_ref,
        )
        return False, "Invalid webhook signature.", 401

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
            "Chapa verification returned non-success for %s: %s", tx_ref, verify_resp
        )
        payment.status = Payment.STATUS_FAILED
        payment.metadata["chapa_verification_failure"] = verify_resp
        payment.save(update_fields=["status", "metadata", "updated_at"])

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
        payment.metadata["chapa_verification_failure"] = data
        payment.save(update_fields=["status", "metadata", "updated_at"])

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
        return False, "Amount or currency mismatch.", 400

    # Idempotency: repeated webhook never creates duplicate payment or subscription
    if payment.status == Payment.STATUS_CONFIRMED:
        logger.info("Chapa webhook idempotency: tx_ref %s already confirmed.", tx_ref)
        return True, "Payment already confirmed.", 200

    # Execute in ONE atomic database transaction strictly bound to stored payment's gym tenant
    from apps.tenants.context import reset_current_tenant, set_current_tenant

    tenant_token = set_current_tenant(gym)
    try:
        with transaction.atomic():
            locked_payment = Payment.all_objects.select_for_update().get(id=payment.id)
            if locked_payment.status == Payment.STATUS_CONFIRMED:
                return True, "Payment already confirmed.", 200

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
            count += 1
    return count
