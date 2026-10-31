"""
Table-driven unit tests for FitGate shared validation rules and representative endpoint checks.
"""

import datetime
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.core.validators import (
    clamp_page_size,
    validate_and_normalize_phone,
    validate_date_of_birth,
    validate_date_range,
    validate_email_address,
    validate_height,
    validate_hip,
    validate_name,
    validate_neck,
    validate_payment_amount,
    validate_waist,
    validate_weight,
)
from apps.memberships.models import Member
from apps.tenants.models import GymTenant


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="Test Gym",
        subdomain=f"testgym{uuid.uuid4().hex[:6]}",
        status=GymTenant.STATUS_ACTIVE,
        tier=GymTenant.TIER_PRO,
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    return gym


# 1. Phone validation & normalization table tests
@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("+251911223344", "+251911223344"),
        ("0911223344", "+251911223344"),
        ("0711223344", "+251711223344"),
        ("+251711223344", "+251711223344"),
        ("251911223344", "+251911223344"),
        ("0911-22-33-44", "+251911223344"),
        ("+251 91 122 3344", "+251911223344"),
        ("+12025550123", "+12025550123"),
        ("+442071838750", "+442071838750"),
    ],
)
def test_phone_valid_normalization(raw_input, expected):
    assert validate_and_normalize_phone(raw_input) == expected


@pytest.mark.parametrize(
    "invalid_input",
    [
        "0911abc",
        "+251911phone",
        "letters-only",
        "12345",  # Too short (< 9 digits)
        "1234567890123456",  # Too long (> 15 digits)
        "+25191122",  # Ethiopian too short
        "091122",  # Ethiopian local too short
        "+25191122334455",  # Ethiopian too long
        "",
        "   ",
        None,
    ],
)
def test_phone_invalid_rejection(invalid_input):
    with pytest.raises(ValidationError):
        validate_and_normalize_phone(invalid_input)


# 2. Name validation table tests
@pytest.mark.parametrize(
    "raw_name,expected",
    [
        ("Abebe Bikila", "Abebe Bikila"),
        ("አበበ በሰለ", "አበበ በሰለ"),
        ("ዮናስ", "ዮናስ"),
        ("O'Connor", "O'Connor"),
        ("Mary-Jane", "Mary-Jane"),
        ("Dr. Smith", "Dr. Smith"),
        ("  Leading and trailing  ", "Leading and trailing"),
    ],
)
def test_name_valid(raw_name, expected):
    assert validate_name(raw_name) == expected


@pytest.mark.parametrize(
    "invalid_name",
    [
        "John2",
        "Abebe123",
        "User@Gym",
        "Only!Symbols?",
        "   ",
        "A",  # Less than 2 characters
        "A" * 101,  # More than 100 characters
        None,
    ],
)
def test_name_invalid_rejection(invalid_name):
    with pytest.raises(ValidationError):
        validate_name(invalid_name)


# 3. Email validation table tests
@pytest.mark.parametrize(
    "raw_email,expected",
    [
        ("USER@EXAMPLE.COM", "user@example.com"),
        ("member@fitgate.org", "member@fitgate.org"),
        ("  test@domain.com  ", "test@domain.com"),
    ],
)
def test_email_valid(raw_email, expected):
    assert validate_email_address(raw_email) == expected


@pytest.mark.parametrize(
    "invalid_email",
    [
        "notanemail",
        "missing@domain",
        "@missinguser.com",
        "a" * 250 + "@example.com",
        "",
        None,
    ],
)
def test_email_invalid_rejection(invalid_email):
    with pytest.raises(ValidationError):
        validate_email_address(invalid_email)


# 4. Number ranges table tests
def test_number_ranges():
    # Weight (20 to 400 kg)
    assert validate_weight("75.50") == Decimal("75.50")
    with pytest.raises(ValidationError):
        validate_weight("19.99")
    with pytest.raises(ValidationError):
        validate_weight("400.01")
    with pytest.raises(ValidationError):
        validate_weight("75.555")

    # Height (50 to 260 cm)
    assert validate_height("175") == Decimal("175")
    with pytest.raises(ValidationError):
        validate_height("49.99")
    with pytest.raises(ValidationError):
        validate_height("260.01")

    # Waist (40 to 200 cm)
    assert validate_waist("85") == Decimal("85")
    assert validate_waist(None) is None
    with pytest.raises(ValidationError):
        validate_waist("39.99")
    with pytest.raises(ValidationError):
        validate_waist("200.01")

    # Neck (20 to 80 cm)
    assert validate_neck("38") == Decimal("38")
    with pytest.raises(ValidationError):
        validate_neck("19.99")
    with pytest.raises(ValidationError):
        validate_neck("80.01")

    # Hip (40 to 220 cm)
    assert validate_hip("95") == Decimal("95")
    with pytest.raises(ValidationError):
        validate_hip("39.99")
    with pytest.raises(ValidationError):
        validate_hip("220.01")

    # Payment amount (> 0, <= 10,000,000 ETB, max 2 decimals)
    assert validate_payment_amount("1500.50") == Decimal("1500.50")
    with pytest.raises(ValidationError):
        validate_payment_amount("0")
    with pytest.raises(ValidationError):
        validate_payment_amount("-50")
    with pytest.raises(ValidationError):
        validate_payment_amount("10000000.01")
    with pytest.raises(ValidationError):
        validate_payment_amount("50.123")

    # Page size clamp (1 to 100)
    assert clamp_page_size(0) == 1
    assert clamp_page_size(150) == 100
    assert clamp_page_size(25) == 25
    assert clamp_page_size(None) == 20


# 5. Date validation table tests
def test_date_validations():
    today = datetime.date.today()
    # DOB: valid
    assert validate_date_of_birth(today - datetime.timedelta(days=365 * 25))
    # DOB: future date rejected
    with pytest.raises(ValidationError):
        validate_date_of_birth(today + datetime.timedelta(days=1))
    # DOB: older than 120 years rejected
    with pytest.raises(ValidationError):
        validate_date_of_birth(today - datetime.timedelta(days=365 * 121))

    # Date range: valid
    validate_date_range(today - datetime.timedelta(days=7), today)
    # Date range: invalid (from after to)
    with pytest.raises(ValidationError):
        validate_date_range(today, today - datetime.timedelta(days=1))


# 6. Representative endpoints rejection checks
@pytest.mark.django_db
def test_representative_endpoint_1_member_registration_refuses_bad_values(
    api_client, gym_tenant
):
    """
    Representative endpoint 1: /api/memberships/staff-register/
    Verifies bad phone (letters) and bad full_name (digits) are refused with 400 Bad Request
    and clear per-field validation error messages.
    """
    owner = User.objects.create(
        email="owner_val@fitgate.org",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Valid Owner",
    )
    api_client.force_authenticate(user=owner)
    api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

    bad_payload = {
        "full_name": "Abebe123",  # Digits not allowed in name
        "email": "valid_email@fitgate.org",
        "phone": "0911abc",  # Letters not allowed in phone
        "waiver_accepted": True,
    }

    response = api_client.post(
        "/api/gym/members/",
        data=bad_payload,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "full_name" in response.data
    assert "phone" in response.data


@pytest.mark.django_db
def test_representative_endpoint_2_body_metrics_refuses_out_of_range_values(
    api_client, gym_tenant
):
    """
    Representative endpoint 2: /api/gym/members/{id}/metrics/
    Verifies out-of-range weight (10 kg) and height (300 cm) are refused with 400 Bad Request
    and clear per-field validation error messages.
    """
    gym_tenant.config.has_trainer_module = True
    gym_tenant.config.save(update_fields=["has_trainer_module"])

    trainer = User.objects.create(
        email="trainer_val@fitgate.org",
        role=User.ROLE_TRAINER,
        gym=gym_tenant,
        full_name="Valid Trainer",
    )
    member_user = User.objects.create(
        email="member_val@fitgate.org",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Valid Member",
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Valid Member",
        phone="+251911223344",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=datetime.datetime.now(datetime.timezone.utc),
    )

    from apps.trainers.models import TrainerAssignment

    TrainerAssignment.objects.create(
        gym=gym_tenant, member=member, trainer=trainer.trainer_profile
    )

    api_client.force_authenticate(user=trainer)
    api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

    bad_metrics_payload = {
        "weight_kg": 10.0,  # Below 20 kg
        "height_cm": 300.0,  # Above 260 cm
    }

    response = api_client.post(
        f"/api/gym/members/{member.id}/metrics/",
        data=bad_metrics_payload,
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "weight_kg" in response.data
    assert "height_cm" in response.data
