"""Tests for online Chapa checkout session initiation and restrictions."""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
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
            # Confirm callback_url sent to Chapa uses apex domain
            call_args = mock_init.call_args[0][0]
            assert "/api/webhooks/chapa/" in call_args["callback_url"]
            assert "alpha." not in call_args["callback_url"]
            assert "alpha." in call_args["return_url"]
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

        # Verify audit log recorded for checkout started with member actor
        audit = AuditLog.all_objects.filter(
            gym=gym, action_type="payment_checkout_started"
        ).first()
        assert audit is not None
        assert audit.actor == setup_data["member_user"]
        assert audit.metadata["amount_etb"] == "1500.00"

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

    def test_staff_roles_and_super_admin_denied_online_checkout(self, setup_data):
        """Online checkout is restricted to members only; staff use cash flow in Sprint 12."""
        gym = setup_data["gym_a"]
        plan = setup_data["plan_active"]

        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-abc"
        config.secret_key = "CHASECK_TEST-sec"
        config.is_verified = True
        config.save()

        staff_roles = [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
            User.ROLE_TRAINER,
        ]

        for role in staff_roles:
            staff_user = User.objects.create_user(
                email=f"staff_{role}@alpha.test",
                password="StaffPassword123!",
                gym=gym,
                role=role,
            )
            client = APIClient()
            client.force_authenticate(user=staff_user)
            resp = client.post(
                "/api/payments/checkout/chapa/",
                {"plan_id": str(plan.id)},
                format="json",
                HTTP_HOST="alpha.localhost",
            )
            assert resp.status_code == status.HTTP_403_FORBIDDEN

        super_admin = User.objects.create_superuser(
            email="platform_admin@fitgate.org",
            password="AdminPassword123!",
        )
        client = APIClient()
        client.force_authenticate(user=super_admin)
        resp = client.post(
            "/api/payments/checkout/chapa/",
            {"plan_id": str(plan.id)},
            format="json",
            HTTP_HOST="alpha.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestMemberPaymentStatus:
    """Test suite for member payment status check by reference."""

    def test_member_can_check_own_payment_status(self):
        gym = GymTenant.objects.create(
            name="Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        member_user = User.objects.create_user(
            email="mem@alpha.test", password="Pass123!", gym=gym, role=User.ROLE_MEMBER
        )
        member = Member.objects.create(
            gym=gym,
            user=member_user,
            full_name="Mem Test",
            phone="+251911223344",
            waiver_accepted_at=timezone.now(),
        )
        plan = MembershipPlan.objects.create(
            gym=gym,
            name="1 Month",
            duration_value=1,
            duration_unit="months",
            price_etb=500,
        )
        Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=member,
            plan=plan,
            method=Payment.METHOD_CHAPA,
            amount_etb=500,
            chapa_ref="FG-alpha-test12345",
            status=Payment.STATUS_CONFIRMED,
        )

        client = APIClient()
        client.force_authenticate(user=member_user)
        resp = client.get(
            "/api/payments/status/FG-alpha-test12345/", HTTP_HOST="alpha.localhost"
        )
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["status"] == "confirmed"
        assert resp.data["plan_name"] == "1 Month"
        # Only status, receipt_id, and plan_name exposed
        assert set(resp.data.keys()) == {"status", "receipt_id", "plan_name"}

    def test_other_member_and_unknown_reference_denied_with_uniform_404(self):
        gym = GymTenant.objects.create(
            name="Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        u1 = User.objects.create_user(
            email="mem1@alpha.test", password="Pass123!", gym=gym, role=User.ROLE_MEMBER
        )
        m1 = Member.objects.create(
            gym=gym,
            user=u1,
            full_name="Mem 1",
            phone="+251911111111",
            waiver_accepted_at=timezone.now(),
        )
        u2 = User.objects.create_user(
            email="mem2@alpha.test", password="Pass123!", gym=gym, role=User.ROLE_MEMBER
        )
        Member.objects.create(
            gym=gym,
            user=u2,
            full_name="Mem 2",
            phone="+251911222222",
            waiver_accepted_at=timezone.now(),
        )

        p1 = Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=m1,
            method=Payment.METHOD_CHAPA,
            amount_etb=500,
            chapa_ref="FG-alpha-mem1ref",
            status=Payment.STATUS_PENDING,
        )

        client = APIClient()
        client.force_authenticate(user=u2)
        # Other member querying m1's payment
        resp = client.get(
            f"/api/payments/status/{p1.chapa_ref}/", HTTP_HOST="alpha.localhost"
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND
        assert resp.data["detail"] == "We could not find this payment."

        # Unknown reference
        resp2 = client.get(
            "/api/payments/status/FG-nonexistent/", HTTP_HOST="alpha.localhost"
        )
        assert resp2.status_code == status.HTTP_404_NOT_FOUND
        assert resp2.data["detail"] == "We could not find this payment."

    def test_staff_roles_and_super_admin_denied_status_endpoint(self):
        gym = GymTenant.objects.create(
            name="Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        mem_user = User.objects.create_user(
            email="mem@alpha.test", password="Pass123!", gym=gym, role=User.ROLE_MEMBER
        )
        member = Member.objects.create(
            gym=gym,
            user=mem_user,
            full_name="Mem Test",
            phone="+251911223344",
            waiver_accepted_at=timezone.now(),
        )
        p = Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_MEMBER,
            member=member,
            method=Payment.METHOD_CHAPA,
            amount_etb=500,
            chapa_ref="FG-alpha-stafftest",
            status=Payment.STATUS_PENDING,
        )

        for role in [
            User.ROLE_OWNER,
            User.ROLE_MANAGER,
            User.ROLE_RECEPTION,
            User.ROLE_TRAINER,
        ]:
            staff_user = User.objects.create_user(
                email=f"staff_{role}@alpha.test",
                password="Pass123!",
                gym=gym,
                role=role,
            )
            client = APIClient()
            client.force_authenticate(user=staff_user)
            resp = client.get(
                f"/api/payments/status/{p.chapa_ref}/", HTTP_HOST="alpha.localhost"
            )
            assert resp.status_code == status.HTTP_403_FORBIDDEN

        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org", password="Pass123!"
        )
        client = APIClient()
        client.force_authenticate(user=super_admin)
        resp = client.get(f"/api/payments/status/{p.chapa_ref}/", HTTP_HOST="localhost")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_return_url_constructed_with_domain_scheme_port_and_membership_route(self):
        gym = GymTenant.objects.create(
            name="Alpha", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        config = GymPaymentConfig.all_objects.create(gym=gym)
        config.public_key = "CHAPUBK_TEST-pub"
        config.secret_key = "CHASECK_TEST-sec"
        config.is_verified = True
        config.save()
        mem_user = User.objects.create_user(
            email="mem@alpha.test", password="Pass123!", gym=gym, role=User.ROLE_MEMBER
        )
        Member.objects.create(
            gym=gym,
            user=mem_user,
            full_name="Mem Test",
            phone="+251911223344",
            waiver_accepted_at=timezone.now(),
        )
        plan = MembershipPlan.objects.create(
            gym=gym,
            name="1 Month",
            duration_value=1,
            duration_unit="months",
            price_etb=500,
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=mem_user)

        with patch(
            "apps.payments.views.ChapaClient.initialize_transaction"
        ) as mock_init:
            mock_init.return_value = {
                "status": "success",
                "data": {
                    "checkout_url": "https://checkout.chapa.co/test",
                    "tx_ref": "tx-123",
                },
            }
            resp = client.post(
                "/api/payments/checkout/chapa/",
                {"plan_id": str(plan.id)},
                format="json",
                HTTP_HOST="alpha.localhost",
            )
            assert resp.status_code == status.HTTP_200_OK
            assert mock_init.called
            payload = mock_init.call_args[0][0]
            # Verify return_url has scheme, subdomain, domain, port, and /membership/payment-complete
            assert payload["return_url"].startswith(
                "http://alpha.localhost:5173/membership/payment-complete?tx_ref="
            )
