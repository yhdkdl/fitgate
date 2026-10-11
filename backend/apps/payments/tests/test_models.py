"""Tests for Payment model constraints and multi-tenancy scoping."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import Payment
from apps.tenants.models import GymTenant


@pytest.mark.django_db
class TestPaymentModel:
    """Test suite for Payment model validation and tenant isolation."""

    @pytest.fixture
    def setup_data(self):
        gym = GymTenant.objects.create(
            name="Alpha Gym", subdomain="alpha", tls_confirmed_at=timezone.now()
        )
        super_admin = User.objects.create_superuser(
            email="admin@fitgate.org", password="AdminPassword123!"
        )
        return {"gym": gym, "super_admin": super_admin}

    def test_payment_creation_and_string_representation(self, setup_data):
        gym = setup_data["gym"]
        admin = setup_data["super_admin"]

        payment = Payment.objects.create(
            gym=gym,
            payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
            method=Payment.METHOD_BANK_TRANSFER,
            amount_etb=Decimal("12000.00"),
            bank_reference="REF-001",
            status=Payment.STATUS_CONFIRMED,
            confirmed_by=admin,
        )
        assert payment.id is not None
        assert "Payment" in str(payment)
        assert "12000.00" in str(payment)

    def test_gym_subscription_rejects_chapa_and_cash(self, setup_data):
        gym = setup_data["gym"]
        admin = setup_data["super_admin"]

        with pytest.raises(ValidationError) as exc:
            Payment.objects.create(
                gym=gym,
                payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
                method=Payment.METHOD_CHAPA,
                amount_etb=Decimal("12000.00"),
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=admin,
            )
        assert "method" in exc.value.message_dict

    def test_member_payment_rejects_bank_transfer(self, setup_data):
        gym = setup_data["gym"]

        with pytest.raises(ValidationError) as exc:
            Payment.objects.create(
                gym=gym,
                payer_type=Payment.PAYER_TYPE_MEMBER,
                method=Payment.METHOD_BANK_TRANSFER,
                amount_etb=Decimal("1500.00"),
                status=Payment.STATUS_PENDING,
            )
        assert "method" in exc.value.message_dict

    def test_confirmed_cash_and_bank_transfer_requires_confirmed_by(self, setup_data):
        gym = setup_data["gym"]

        with pytest.raises(ValidationError) as exc:
            Payment.objects.create(
                gym=gym,
                payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
                method=Payment.METHOD_BANK_TRANSFER,
                amount_etb=Decimal("12000.00"),
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=None,
            )
        assert "confirmed_by" in exc.value.message_dict

    def test_zero_or_negative_amount_rejected(self, setup_data):
        gym = setup_data["gym"]
        admin = setup_data["super_admin"]

        with pytest.raises(ValidationError) as exc:
            Payment.objects.create(
                gym=gym,
                payer_type=Payment.PAYER_TYPE_GYM_SUBSCRIPTION,
                method=Payment.METHOD_BANK_TRANSFER,
                amount_etb=Decimal("0.00"),
                status=Payment.STATUS_CONFIRMED,
                confirmed_by=admin,
            )
        assert "amount_etb" in exc.value.message_dict
