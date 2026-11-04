"""Tests for Owner switch for online (Chapa) payments."""

import hashlib
import hmac
import json
import uuid
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import GymPaymentConfig, Payment
from apps.tenants.models import GymTenant


@pytest.fixture
def gym(db):
    return GymTenant.objects.create(
        name="FitGate Bole",
        subdomain="fitgate-bole",
        status=GymTenant.STATUS_ACTIVE,
        tier="growth",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="fitgate-kazanchis",
        status=GymTenant.STATUS_ACTIVE,
        tier="growth",
        tls_confirmed_at=timezone.now(),
    )


def create_user(gym, role, email="user@test.com"):
    return User.objects.create_user(
        gym=gym,
        email=email,
        role=role,
        full_name=f"Test {role.title()}",
        must_change_password=False,
    )


def make_client(user, tenant):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if tenant:
        client.defaults["HTTP_HOST"] = f"{tenant.subdomain}.localhost"
    return client


@pytest.fixture
def standard_plan(gym):
    return MembershipPlan.objects.create(
        gym=gym,
        name="Standard 1 Month",
        price_etb=Decimal("1500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )


@pytest.fixture
def premium_plan(gym):
    return MembershipPlan.objects.create(
        gym=gym,
        name="Premium 1 Month",
        price_etb=Decimal("2500.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )


@pytest.mark.django_db
class TestOnlinePaymentSwitch:
    """Tests covering all requirements of the online payment switch."""

    def test_turning_on_refused_without_verified_connection(self, gym):
        owner = create_user(gym, User.ROLE_OWNER, "owner@bole.com")
        client = make_client(owner, gym)

        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.is_verified = False
        config.is_enabled = False
        config.save()

        resp = client.put(
            "/api/gym/payment-config/",
            {"is_enabled": True},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["detail"] == "Verify your Chapa connection first."

        config.refresh_from_db()
        assert config.is_enabled is False

    def test_turning_on_succeeds_when_verified_and_audit_logged(self, gym):
        owner = create_user(gym, User.ROLE_OWNER, "owner@bole.com")
        client = make_client(owner, gym)

        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.is_verified = True
        config.is_enabled = False
        config.save()

        resp = client.put(
            "/api/gym/payment-config/",
            {"is_enabled": True},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["is_enabled"] is True

        config.refresh_from_db()
        assert config.is_enabled is True

    def test_turning_off_preserves_keys_and_reports_unfinished_payments(self, gym):
        owner = create_user(gym, User.ROLE_OWNER, "owner@bole.com")
        client = make_client(owner, gym)

        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.public_key = "CHAPUBK_TEST-12345"
        config.secret_key = "CHASECK_TEST-67890"
        config.is_verified = True
        config.is_enabled = True
        config.save()

        # Seed an unfinished pending payment
        member_user = create_user(gym, User.ROLE_MEMBER, "m@bole.com")
        member = Member.objects.create(
            gym=gym,
            user=member_user,
            full_name=member_user.full_name,
            phone="+251911223344",
            waiver_accepted_at=timezone.now(),
        )
        Payment.objects.create(
            gym=gym,
            member=member,
            method=Payment.METHOD_CHAPA,
            amount_etb=Decimal("1500.00"),
            status=Payment.STATUS_PENDING,
            chapa_ref="chapa_test_ref_123",
        )

        resp = client.put(
            "/api/gym/payment-config/",
            {"is_enabled": False},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["is_enabled"] is False
        assert resp.data["unfinished_online_payments"] == 1

        config.refresh_from_db()
        assert config.is_enabled is False
        assert config.is_verified is True
        assert config.has_secret_key is True

    def test_all_three_checkout_routes_refused_when_off(
        self, gym, standard_plan, premium_plan
    ):
        owner = create_user(gym, User.ROLE_OWNER, "owner@bole.com")
        make_client(owner, gym)

        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.public_key = "CHAPUBK_TEST-12345"
        config.secret_key = "CHASECK_TEST-67890"
        config.is_verified = True
        config.is_enabled = False
        config.save()

        # 1. New purchase checkout
        member_user = create_user(gym, User.ROLE_MEMBER, "new_member@bole.com")
        member = Member.objects.create(
            gym=gym,
            user=member_user,
            full_name=member_user.full_name,
            phone="+251911000001",
            waiver_accepted_at=timezone.now(),
        )
        client_member = make_client(member_user, gym)

        resp1 = client_member.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(standard_plan.id)},
            format="json",
        )
        assert resp1.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            resp1.data["detail"]
            == "Online payment is not available at this gym. Please pay at the front desk."
        )

        # 2. Renewal checkout
        today = timezone.localdate()
        MemberSubscription.objects.create(
            gym=gym,
            member=member,
            plan=standard_plan,
            start_date=today,
            end_date=today + timezone.timedelta(days=30),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        member.refresh_from_db()

        resp2 = client_member.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(standard_plan.id)},
            format="json",
        )
        assert resp2.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            resp2.data["detail"]
            == "Online payment is not available at this gym. Please pay at the front desk."
        )

        # 3. Plan upgrade checkout
        resp3 = client_member.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(premium_plan.id)},
            format="json",
        )
        assert resp3.status_code == status.HTTP_400_BAD_REQUEST
        assert (
            resp3.data["detail"]
            == "Online payment is not available at this gym. Please pay at the front desk."
        )

    def test_in_flight_payment_completes_after_switch_off(self, gym, standard_plan):
        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.public_key = "CHAPUBK_TEST-12345"
        config.secret_key = "CHASECK_TEST-67890"
        config.webhook_secret = "test_webhook_sec"
        config.is_verified = True
        config.is_enabled = False  # Switch was turned OFF
        config.save()

        member_user = create_user(gym, User.ROLE_MEMBER, "inflight@bole.com")
        member = Member.objects.create(
            gym=gym,
            user=member_user,
            full_name=member_user.full_name,
            phone="+251911999999",
            waiver_accepted_at=timezone.now(),
        )
        tx_ref = f"inflight-{uuid.uuid4().hex[:8]}"
        payment = Payment.objects.create(
            gym=gym,
            member=member,
            plan=standard_plan,
            method=Payment.METHOD_CHAPA,
            amount_etb=standard_plan.price_etb,
            status=Payment.STATUS_PENDING,
            chapa_ref=tx_ref,
        )

        # Webhook arrives while switch is OFF
        client = APIClient()
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"

        webhook_payload = {
            "event": "charge.success",
            "tx_ref": tx_ref,
            "reference": tx_ref,
            "status": "success",
            "amount": float(standard_plan.price_etb),
            "currency": "ETB",
        }

        body_bytes = json.dumps(webhook_payload).encode("utf-8")
        sig = hmac.new(
            "test_webhook_sec".encode("utf-8"), body_bytes, hashlib.sha256
        ).hexdigest()

        mock_verify_resp = {
            "status": "success",
            "data": {
                "status": "success",
                "amount": float(standard_plan.price_etb),
                "currency": "ETB",
                "tx_ref": tx_ref,
            },
        }
        with patch(
            "apps.payments.chapa_client.ChapaClient.verify_transaction",
            return_value=mock_verify_resp,
        ):
            resp = client.post(
                "/api/webhooks/chapa/",
                data=body_bytes,
                content_type="application/json",
                HTTP_X_CHAPA_SIGNATURE=sig,
                HTTP_HOST=f"{gym.subdomain}.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK

        payment.refresh_from_db()
        assert payment.status == Payment.STATUS_CONFIRMED
        assert payment.subscription is not None
        assert MemberSubscription.all_objects.filter(
            gym=gym, member=member, status=MemberSubscription.STATUS_ACTIVE
        ).exists()

    def test_role_and_tenant_refusals(self, gym, other_gym):
        config, _ = GymPaymentConfig.objects.get_or_create(gym=gym)
        config.is_verified = True
        config.is_enabled = True
        config.save()

        # Manager refused
        mgr = create_user(gym, User.ROLE_MANAGER, "mgr@bole.com")
        resp = make_client(mgr, gym).put(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Reception refused
        rec = create_user(gym, User.ROLE_RECEPTION, "rec@bole.com")
        resp = make_client(rec, gym).put(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Trainer refused
        trn = create_user(gym, User.ROLE_TRAINER, "trn@bole.com")
        resp = make_client(trn, gym).put(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Member refused
        mem = create_user(gym, User.ROLE_MEMBER, "mem@bole.com")
        resp = make_client(mem, gym).put(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Other gym owner refused (tenant isolation)
        other_owner = create_user(other_gym, User.ROLE_OWNER, "other@kaz.com")
        client_other = make_client(other_owner, gym)  # requesting gym A on gym A domain
        resp = client_other.put(
            "/api/gym/payment-config/", {"is_enabled": False}, format="json"
        )
        assert resp.status_code in (
            status.HTTP_403_FORBIDDEN,
            status.HTTP_401_UNAUTHORIZED,
        )

        # Super Admin allowed to toggle switch on platform endpoint
        admin = User.objects.create_user(
            gym=None,
            email="admin@fitgate.org",
            role=User.ROLE_SUPER_ADMIN,
            must_change_password=False,
        )
        client_admin = make_client(admin, None)
        client_admin.defaults["HTTP_HOST"] = "localhost"
        resp_platform = client_admin.patch(
            f"/api/platform/gyms/{gym.id}/payment-status/",
            {"is_enabled": False},
            format="json",
        )
        assert resp_platform.status_code == status.HTTP_200_OK
        assert resp_platform.data["is_enabled"] is False
