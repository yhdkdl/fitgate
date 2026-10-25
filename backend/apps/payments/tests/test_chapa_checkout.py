"""Tests for online Chapa checkout session initiation and restrictions."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.memberships.models import Member, MembershipPlan
from apps.payments.models import GymPaymentConfig, Payment
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestChapaCheckout:
    """Test suite for member online checkout initiation."""

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
        member_user = User.objects.create_user(
            email="member@alpha.test",
            password="MemberPassword123!",
            gym=gym_a,
            role=User.ROLE_MEMBER,
        )
        member = Member.objects.create(
            gym=gym_a,
            user=member_user,
            full_name="Abebe Bikila",
            phone="+251911000001",
            gender="M",
            date_of_birth=timezone.localdate() - timezone.timedelta(days=365 * 25),
            waiver_accepted_at=timezone.now(),
        )

        plan_active = MembershipPlan.objects.create(
            gym=gym_a,
            name="Monthly Standard",
            price_etb=Decimal("1500.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
            is_active=True,
        )
        plan_deactivated = MembershipPlan.objects.create(
            gym=gym_a,
            name="Old Plan",
            price_etb=Decimal("1000.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
            is_active=False,
        )
        plan_b = MembershipPlan.objects.create(
            gym=gym_b,
            name="Beta Plan",
            price_etb=Decimal("1200.00"),
            duration_value=1,
            duration_unit=MembershipPlan.DURATION_MONTHS,
            is_active=True,
        )

        return {
            "gym_a": gym_a,
            "gym_b": gym_b,
            "member_user": member_user,
            "member": member,
            "plan_active": plan_active,
            "plan_deactivated": plan_deactivated,
            "plan_b": plan_b,
        }

    def test_checkout_refused_when_payment_config_unverified(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["member_user"])
        plan = setup_data["plan_active"]

        # No GymPaymentConfig exists yet
        resp = client.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(plan.id)},
            format="json",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "Online payment is not enabled for this gym" in resp.json()["detail"]

    def test_checkout_succeeds_when_config_is_verified(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["member_user"])
        gym = setup_data["gym_a"]
        plan = setup_data["plan_active"]

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.is_verified = True
        config.save()

        with patch(
            "apps.payments.chapa_client.ChapaClient.initialize_transaction"
        ) as mock_init:
            mock_init.return_value = {
                "status": "success",
                "data": {
                    "checkout_url": "https://checkout.chapa.co/checkout/payment/mock-tx-123",
                    "tx_ref": "mock-tx-123",
                },
            }
            resp = client.post(
                "/api/payments/checkout/chapa/",
                {"plan_id": str(plan.id)},
                format="json",
                HTTP_HOST="alpha.localhost",
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert (
            data["checkout_url"]
            == "https://checkout.chapa.co/checkout/payment/mock-tx-123"
        )
        assert "FG-alpha-" in data["tx_ref"]

        # Verify Payment record was created in database
        payment = Payment.all_objects.get(id=data["payment_id"])
        assert payment.status == Payment.STATUS_PENDING
        assert payment.amount_etb == Decimal("1500.00")
        assert payment.currency == "ETB"
        assert payment.method == Payment.METHOD_CHAPA
        assert payment.payer_type == Payment.PAYER_TYPE_MEMBER
        assert payment.member == setup_data["member"]
        assert payment.plan == plan

    def test_checkout_refuses_deactivated_plan(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["member_user"])
        gym = setup_data["gym_a"]
        plan = setup_data["plan_deactivated"]

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.is_verified = True
        config.save()

        resp = client.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(plan.id)},
            format="json",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "deactivated" in resp.json()["detail"].lower()

    def test_checkout_refuses_cross_gym_plan(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data["member_user"])
        gym = setup_data["gym_a"]
        plan_b = setup_data["plan_b"]

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.is_verified = True
        config.save()

        resp = client.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(plan_b.id)},
            format="json",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
