"""Tests for Chapa webhook safety, HMAC signature verification, idempotency, and money rules."""

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.chapa_client import ChapaAPIError
from apps.payments.models import GymPaymentConfig, Payment
from apps.payments.services import flag_unfinished_payments
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestChapaWebhookSafety:
    """Comprehensive test suite for Chapa webhook security and money rules."""

    @pytest.fixture
    def setup_data(self):
        gym_a = GymTenant.objects.create(
            name="Gym Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        gym_b = GymTenant.objects.create(
            name="Gym Beta", subdomain="beta", tls_confirmed_at=timezone.now()
        )

        User.objects.create_user(
            email="owner@alpha.test",
            password="OwnerPassword123!",
            gym=gym_a,
            role=User.ROLE_OWNER,
        )
        member_user_a = User.objects.create_user(
            email="member@alpha.test",
            password="MemberPassword123!",
            gym=gym_a,
            role=User.ROLE_MEMBER,
        )
        member_a = Member.objects.create(
            gym=gym_a,
            user=member_user_a,
            full_name="Derartu Tulu",
            phone="+251911000002",
            gender="F",
            date_of_birth=timezone.localdate() - timedelta(days=365 * 24),
            waiver_accepted_at=timezone.now(),
        )

        plan = MembershipPlan.objects.create(
            gym=gym_a,
            name="Monthly Pro",
            price_etb=Decimal("1800.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
            is_active=True,
        )

        # Gym payment configuration with known secrets
        config = GymPaymentConfig.all_objects.create(gym=gym_a)
        config.public_key = "CHAPUBK_TEST-alpha123"
        config.secret_key = "CHASECK_TEST-sec123"
        config.webhook_secret = "whsec_alpha_key_998877"
        config.is_verified = True
        config.save()

        # Stored pending payment
        tx_ref = "FG-alpha-txref12345"
        payment = Payment.all_objects.create(
            gym=gym_a,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=member_a,
            plan=plan,
            method=Payment.METHOD_CHAPA,
            amount_etb=Decimal("1800.00"),
            currency="ETB",
            chapa_ref=tx_ref,
            status=Payment.STATUS_PENDING,
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "member_user_a": member_user_a,
            "member_a": member_a,
            "plan": plan,
            "config": config,
            "payment": payment,
            "tx_ref": tx_ref,
        }

    def _sign_payload(self, payload_dict: dict, secret: str) -> tuple[bytes, str]:
        body_bytes = json.dumps(payload_dict).encode("utf-8")
        sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        return body_bytes, sig

    def test_forged_signature_rejected_and_changes_nothing(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, _ = self._sign_payload(payload, "wrong_attacker_secret")

        resp = client.post(
            "/api/webhooks/chapa/",
            data=body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE="forged_signature_value",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_PENDING
        assert (
            MemberSubscription.all_objects.filter(member=setup_data["member_a"]).count()
            == 0
        )

    def test_missing_signature_rejected(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body = json.dumps(payload).encode("utf-8")

        resp = client.post(
            "/api/webhooks/chapa/",
            data=body,
            content_type="application/json",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_PENDING

    def test_successful_confirmation_and_atomic_subscription_activation(
        self, setup_data
    ):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]
        plan = setup_data["plan"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK

        # Payment status moved to confirmed
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.subscription is not None

        # Member status and subscription active
        member.refresh_from_db()
        assert member.status == Member.STATUS_ACTIVE
        sub = payment.subscription
        assert sub.status == MemberSubscription.STATUS_ACTIVE
        assert sub.plan == plan

        # Member notification recorded
        notif = Notification.all_objects.filter(recipient=member.user).first()
        assert notif is not None
        assert notif.type == "payment_confirmed"
        assert "1800.00 ETB" in notif.message

        # Audit log with actor "system"
        audit = AuditLog.all_objects.filter(
            gym=setup_data["gym_a"],
            action_type="payment_confirmed",
        ).first()
        assert audit is not None
        assert audit.actor is None
        assert audit.metadata["actor"] == "system"
        assert audit.metadata["method"] == "chapa"

    def test_repeated_webhook_idempotency_no_duplicate_subscription(self, setup_data):
        client = APIClient()
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            # First webhook confirmation
            resp1 = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
            assert resp1.status_code == status.HTTP_200_OK

            sub_count_after_first = MemberSubscription.all_objects.filter(
                member=member
            ).count()
            assert sub_count_after_first == 1

            # Second duplicate webhook call
            resp2 = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
            assert resp2.status_code == status.HTTP_200_OK
            assert "already confirmed" in resp2.json()["detail"].lower()

            # No second subscription or extension created
            sub_count_after_second = MemberSubscription.all_objects.filter(
                member=member
            ).count()
            assert sub_count_after_second == 1

    def test_wrong_amount_mismatch_rejected_and_recorded(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        # Chapa reported 100.00 ETB instead of 1800.00 ETB
        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "100.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_FAILED
        assert "mismatch" in payment.metadata
        # Zero subscriptions created
        assert MemberSubscription.all_objects.filter(member=member).count() == 0

        # Mismatch notification to member
        notif = Notification.all_objects.filter(
            recipient=member.user, type="payment_mismatch"
        ).first()
        assert notif is not None

        # Staff alert notification (paid-but-not-activated is never silent)
        staff_alert = Notification.all_objects.filter(
            type="payment_mismatch_alert"
        ).first()
        assert staff_alert is not None
        assert "mismatch" in staff_alert.message.lower()

        # Audit log entry with actor system
        audit = AuditLog.all_objects.filter(
            action_type="payment_mismatch_detected"
        ).first()
        assert audit is not None
        assert audit.actor is None
        assert audit.metadata["actor"] == "system"

    def test_wrong_currency_rejected_and_recorded(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "USD",  # Wrong currency
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_FAILED
        assert MemberSubscription.all_objects.filter(member=member).count() == 0

    def test_server_side_verification_failure_or_timeout_returns_502(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            side_effect=ChapaAPIError("Connection timed out"),
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_502_BAD_GATEWAY
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_PENDING
        assert MemberSubscription.all_objects.filter(member=member).count() == 0

    def test_payment_confirmed_after_plan_deactivated_in_flight(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        plan = setup_data["plan"]

        # Owner deactivates the plan while payment is in flight
        plan.is_active = False
        plan.save(update_fields=["is_active"])

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED
        sub = payment.subscription
        assert sub is not None
        assert sub.plan == plan
        assert sub.status == MemberSubscription.STATUS_ACTIVE

    def test_tenancy_identified_strictly_from_stored_payment(self, setup_data):
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        # Even if request arrives with Gym Beta host header, it must only activate for Gym Alpha
        payload = {"event": "charge.success", "tx_ref": tx_ref, "gym_subdomain": "beta"}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="beta.localhost",  # Attacker hits beta subdomain
            )
        assert resp.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.gym == setup_data["gym_a"]
        assert payment.subscription.gym == setup_data["gym_a"]

    def test_flag_unfinished_payments_records_notifications(self, setup_data):
        payment = setup_data["payment"]
        member = setup_data["member_a"]
        gym = setup_data["gym_a"]

        # Set payment creation time to 40 minutes ago
        Payment.all_objects.filter(id=payment.id).update(
            created_at=timezone.now() - timedelta(minutes=40)
        )

        flagged_count = flag_unfinished_payments(window_minutes=30)
        assert flagged_count == 1

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_ABANDONED

        # Member notification
        member_notif = Notification.all_objects.filter(
            recipient=member.user,
            type="payment_abandoned",
        ).first()
        assert member_notif is not None
        assert "timed out" in member_notif.message.lower()

        # Staff notification
        owner_user = User.all_objects.get(gym=gym, role=User.ROLE_OWNER)
        staff_notif = Notification.all_objects.filter(
            recipient=owner_user,
            type="payment_unfinished_alert",
        ).first()
        assert staff_notif is not None
        assert "unfinished beyond 30 minutes" in staff_notif.message

        # Abandoned sweep audit log
        audit = AuditLog.all_objects.filter(
            action_type="payment_flagged_abandoned"
        ).first()
        assert audit is not None
        assert audit.actor is None
        assert audit.metadata["actor"] == "system"

    @pytest.mark.django_db(transaction=True)
    def test_two_simultaneous_webhook_deliveries_prevents_double_activation(
        self, setup_data
    ):
        """Simultaneous deliveries serialized via row-level lock; prevents double activation."""
        import concurrent.futures

        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        def deliver():
            from django.db import connection

            from apps.payments.services import process_chapa_webhook

            try:
                with patch(
                    "apps.payments.chapa_client.ChapaClient.verify_transaction",
                    return_value=mock_verify_data,
                ):
                    return process_chapa_webhook(
                        raw_body=body,
                        signature_header=sig,
                    )
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            fut1 = executor.submit(deliver)
            fut2 = executor.submit(deliver)
            res1 = fut1.result()
            res2 = fut2.result()

        # Both calls succeed (one confirms payment, second detects already confirmed)
        assert res1[2] == status.HTTP_200_OK
        assert res2[2] == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED
        assert MemberSubscription.all_objects.filter(member=member).count() == 1

    def test_abandoned_payment_confirmed_later_by_chapa(self, setup_data):
        """A payment marked abandoned after 30 mins that is subsequently confirmed by Chapa is honored."""
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]
        member = setup_data["member_a"]

        payment.status = Payment.STATUS_ABANDONED
        payment.save(update_fields=["status"])

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.subscription is not None
        assert payment.subscription.status == MemberSubscription.STATUS_ACTIVE
        assert MemberSubscription.all_objects.filter(member=member).count() == 1

    def test_webhook_size_limit_rejects_oversized_payload(self):
        """Webhook rejects payloads larger than 64 KB."""
        client = APIClient()
        oversized_body = b"x" * 65537
        resp = client.post(
            "/api/webhooks/chapa/",
            data=oversized_body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE="fake_sig",
            HTTP_HOST="localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "64 KB" in resp.json()["detail"]

    def test_chapa_signature_constant_header_rejected_without_x_chapa_signature(
        self, setup_data
    ):
        """Header chapa-signature alone must never authenticate a request."""
        client = APIClient()
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        resp = client.post(
            "/api/webhooks/chapa/",
            data=body,
            content_type="application/json",
            HTTP_CHAPA_SIGNATURE=sig,  # Not x-chapa-signature
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp.json()["detail"] == "Invalid webhook signature."

    def test_unknown_tx_ref_missing_signature_and_wrong_signature_return_identical_response(
        self, setup_data
    ):
        """Unknown tx_ref, missing signature, and wrong signature return the exact same 401 response."""
        client = APIClient()
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        # Case 1: Unknown tx_ref with random signature
        unknown_body, unknown_sig = self._sign_payload(
            {"event": "charge.success", "tx_ref": "FG-alpha-nonexistent9999"},
            config.webhook_secret,
        )
        resp_unknown = client.post(
            "/api/webhooks/chapa/",
            data=unknown_body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE=unknown_sig,
            HTTP_HOST="alpha.localhost",
        )

        # Case 2: Missing signature header
        valid_body, _ = self._sign_payload(
            {"event": "charge.success", "tx_ref": tx_ref},
            config.webhook_secret,
        )
        resp_missing = client.post(
            "/api/webhooks/chapa/",
            data=valid_body,
            content_type="application/json",
            HTTP_HOST="alpha.localhost",
        )

        # Case 3: Wrong signature header
        resp_wrong = client.post(
            "/api/webhooks/chapa/",
            data=valid_body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE="invalid_tampered_signature_hex",
            HTTP_HOST="alpha.localhost",
        )

        # All three return the exact same HTTP status code and body
        assert resp_unknown.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp_missing.status_code == status.HTTP_401_UNAUTHORIZED
        assert resp_wrong.status_code == status.HTTP_401_UNAUTHORIZED

        expected_body = {"detail": "Invalid webhook signature."}
        assert resp_unknown.json() == expected_body
        assert resp_missing.json() == expected_body
        assert resp_wrong.json() == expected_body

    def test_webhook_signed_with_secret_key_succeeds_when_webhook_secret_not_set(
        self, setup_data
    ):
        """Gym with empty webhook_secret authenticates webhook signed with gym secret_key."""
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        # Clear webhook_secret so gym only has secret_key
        config.webhook_secret = ""
        config.save()

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.secret_key)

        mock_verify_data = {
            "status": "success",
            "data": {
                "status": "success",
                "tx_ref": tx_ref,
                "amount": "1800.00",
                "currency": "ETB",
            },
        }

        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_data,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED

    def test_webhook_does_not_modify_amount_member_or_plan_for_existing_payments(
        self, setup_data
    ):
        """Webhook for already confirmed or failed payment never changes its amount, member or plan."""
        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        original_amount = payment.amount_etb
        original_member = payment.member
        original_plan = payment.plan

        # Mark payment as failed
        payment.status = Payment.STATUS_FAILED
        payment.save(update_fields=["status"])

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        resp = client.post(
            "/api/webhooks/chapa/",
            data=body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE=sig,
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

        payment.refresh_from_db()
        assert payment.amount_etb == original_amount
        assert payment.member == original_member
        assert payment.plan == original_plan

    def test_dev_tunnel_host_allows_chapa_webhook_with_valid_signature(
        self, setup_data, settings
    ):
        """Requests via DEV_TUNNEL_HOST reach Chapa webhook and confirm payment upon valid signature."""
        settings.DEV_TUNNEL_HOST = "tunnel-abc.ngrok-free.app"
        if "tunnel-abc.ngrok-free.app" not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [
                "tunnel-abc.ngrok-free.app"
            ]

        client = APIClient()
        payment = setup_data["payment"]
        tx_ref = setup_data["tx_ref"]
        config = setup_data["config"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, sig = self._sign_payload(payload, config.webhook_secret)

        mock_verify_resp = {
            "status": "success",
            "message": "Payment verified",
            "data": {
                "status": "success",
                "amount": float(payment.amount_etb),
                "currency": "ETB",
                "tx_ref": tx_ref,
            },
        }

        with patch("apps.payments.services.ChapaClient") as mock_client_cls:
            mock_client_instance = mock_client_cls.return_value
            mock_client_instance.verify_transaction.return_value = mock_verify_resp

            resp = client.post(
                "/api/webhooks/chapa/",
                data=body,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST="tunnel-abc.ngrok-free.app",
            )

        assert resp.status_code == status.HTTP_200_OK
        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED

    def test_dev_tunnel_host_blocks_non_webhook_routes(self, setup_data, settings):
        """Requests via DEV_TUNNEL_HOST to any path other than /api/webhooks/chapa return 403."""
        settings.DEV_TUNNEL_HOST = "tunnel-abc.ngrok-free.app"
        if "tunnel-abc.ngrok-free.app" not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [
                "tunnel-abc.ngrok-free.app"
            ]

        client = APIClient()
        resp = client.get(
            "/api/auth/profile/",
            HTTP_HOST="tunnel-abc.ngrok-free.app",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
        assert resp.json() == {
            "detail": "Tunnel host only permitted for payment webhooks."
        }

    def test_dev_tunnel_host_enforces_signature_check(self, setup_data, settings):
        """Requests via DEV_TUNNEL_HOST with invalid or missing signature return 401."""
        settings.DEV_TUNNEL_HOST = "tunnel-abc.ngrok-free.app"
        if "tunnel-abc.ngrok-free.app" not in settings.ALLOWED_HOSTS:
            settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [
                "tunnel-abc.ngrok-free.app"
            ]

        client = APIClient()
        tx_ref = setup_data["tx_ref"]

        payload = {"event": "charge.success", "tx_ref": tx_ref}
        body, _ = self._sign_payload(payload, "wrong_secret")

        resp = client.post(
            "/api/webhooks/chapa/",
            data=body,
            content_type="application/json",
            HTTP_X_CHAPA_SIGNATURE="forged_signature",
            HTTP_HOST="tunnel-abc.ngrok-free.app",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
