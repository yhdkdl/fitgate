"""
Tests for Sprint 29 CSV Data Export.

Verifies:
- Role permissions: Owner and Manager allowed; Trainer, Reception, Member, Super Admin refused.
- Tenant isolation: only requesting gym's data is exported.
- Formula injection protection: =, +, -, @ cells prefixed with '.
- UTF-8 BOM (\xef\xbb\xbf) present and Amharic text decodes correctly.
- PII privacy: strictly no health, measurements, workout plans, or photos in members export.
- Date range filtering and 1-year max span constraint.
- Audit logging: data_exported action with export_type and row_count recorded.
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.payments.models import Payment, Receipt
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def api_client():
    return APIClient()


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


@pytest.fixture
def test_setup(db):
    gym_a = GymTenant.objects.create(
        name="FitGym Addis",
        subdomain="addis",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym_a)

    gym_b = GymTenant.objects.create(
        name="FitGym Hawassa",
        subdomain="hawassa",
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(gym=gym_b)

    owner_a = User.objects.create_user(
        email="owner_a@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_a,
        is_active=True,
    )
    manager_a = User.objects.create_user(
        email="manager_a@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_MANAGER,
        gym=gym_a,
        is_active=True,
    )
    trainer_a = User.objects.create_user(
        email="trainer_a@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_TRAINER,
        gym=gym_a,
        is_active=True,
    )
    reception_a = User.objects.create_user(
        email="reception_a@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_a,
        is_active=True,
    )
    member_user_a = User.objects.create_user(
        email="member_a@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_a,
        is_active=True,
    )
    super_admin = User.objects.create_user(
        email="superadmin@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        gym=None,
        is_active=True,
    )

    plan_a = MembershipPlan.objects.create(
        gym=gym_a,
        name="Monthly Gold",
        price_etb=Decimal("2000.00"),
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        is_active=True,
    )

    member_a = Member.objects.create(
        gym=gym_a,
        user=member_user_a,
        full_name="አበበ በቀለ",
        phone="+251911223344",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )

    sub_a = MemberSubscription.objects.create(
        gym=gym_a,
        member=member_a,
        plan=plan_a,
        start_date=timezone.localdate(),
        end_date=timezone.localdate() + timezone.timedelta(days=30),
        status=MemberSubscription.STATUS_ACTIVE,
    )

    payment_a = Payment.objects.create(
        gym=gym_a,
        payer_type=Payment.PAYER_TYPE_MEMBER,
        member=member_a,
        plan=plan_a,
        subscription=sub_a,
        method=Payment.METHOD_CASH,
        amount_etb=Decimal("2000.00"),
        gross_amount_etb=Decimal("2000.00"),
        credit_amount_etb=Decimal("0.00"),
        is_upgrade=False,
        status=Payment.STATUS_CONFIRMED,
        confirmed_by=owner_a,
    )
    Receipt.objects.create(
        gym=gym_a,
        payment=payment_a,
        receipt_number="REC-000001",
        sequence_number=1,
        amount_etb=Decimal("2000.00"),
        gross_amount_etb=Decimal("2000.00"),
        credit_amount_etb=Decimal("0.00"),
        payment_method="cash",
        issued_by=owner_a,
        member_name="አበበ በቀለ",
        member_phone="+251911223344",
        plan_name="Monthly Gold",
    )

    attendance_a = Attendance.objects.create(
        gym=gym_a,
        member=member_a,
        date=timezone.localdate(),
        checked_in_at=timezone.now(),
        method=Attendance.METHOD_QR,
    )

    # Gym B data
    member_user_b = User.objects.create_user(
        email="member_b@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_b,
        is_active=True,
    )
    member_b = Member.objects.create(
        gym=gym_b,
        user=member_user_b,
        full_name="Hawassa User",
        phone="+251922334455",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )

    return {
        "gym_a": gym_a,
        "gym_b": gym_b,
        "owner_a": owner_a,
        "manager_a": manager_a,
        "trainer_a": trainer_a,
        "reception_a": reception_a,
        "member_user_a": member_user_a,
        "super_admin": super_admin,
        "member_a": member_a,
        "member_b": member_b,
        "payment_a": payment_a,
        "attendance_a": attendance_a,
    }


@pytest.mark.django_db
def test_owner_can_export_members(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])
    url = "/api/gym/export/members/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment;" in response["Content-Disposition"]
    assert response.content.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM

    decoded = response.content.decode("utf-8-sig")
    lines = [line.strip() for line in decoded.splitlines() if line.strip()]
    assert len(lines) >= 2
    assert "Name,Phone,Email,Status,Plan,Start Date,End Date" in lines[0]
    assert "አበበ በቀለ" in decoded
    assert "+251911223344" in decoded
    # Gym B member must not be in export
    assert "Hawassa User" not in decoded

    # Audit log check
    audit = AuditLog.all_objects.filter(
        gym=test_setup["gym_a"],
        action_type="data_exported",
        affected_record_id="members",
    ).first()
    assert audit is not None
    assert audit.actor == test_setup["owner_a"]
    assert audit.metadata["row_count"] == 1


@pytest.mark.django_db
def test_manager_can_export_payments(api_client, test_setup):
    auth_client(api_client, test_setup["manager_a"], test_setup["gym_a"])
    url = "/api/gym/export/payments/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.content.startswith(b"\xef\xbb\xbf")

    decoded = response.content.decode("utf-8-sig")
    assert (
        "Receipt Number,Date,Payment Method,Plan,Gross Amount (ETB),Credit Amount (ETB),Net Received (ETB),Is Upgrade,Status,Bank Reference,Confirmed By"
        in decoded
    )
    assert "REC-000001" in decoded
    assert "2000.00" in decoded


@pytest.mark.django_db
def test_owner_can_export_attendance(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])
    url = "/api/gym/export/attendance/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    decoded = response.content.decode("utf-8-sig")
    assert "Date and Time,Member Name,Check-in Method" in decoded
    assert "አበበ በቀለ" in decoded


@pytest.mark.django_db
def test_unauthorized_roles_refused(api_client, test_setup):
    for role_user in [
        test_setup["trainer_a"],
        test_setup["reception_a"],
        test_setup["member_user_a"],
        test_setup["super_admin"],
    ]:
        auth_client(
            api_client, role_user, test_setup["gym_a"] if role_user.gym else None
        )
        url = "/api/gym/export/members/"
        response = api_client.get(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_unauthenticated_refused(api_client, test_setup):
    api_client.defaults["HTTP_HOST"] = f"{test_setup['gym_a'].subdomain}.localhost"
    url = "/api/gym/export/members/"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_formula_injection_protection(api_client, test_setup):
    # Create members with formula injection triggers: =, +, -, @
    injected_user = User.objects.create_user(
        email="formula@fitgate.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=test_setup["gym_a"],
        is_active=True,
    )
    Member.objects.create(
        gym=test_setup["gym_a"],
        user=injected_user,
        full_name="=cmd|'/C calc'!A0",
        phone="+251911999999",
        referral_source="@twitter",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )

    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])
    url = "/api/gym/export/members/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    decoded = response.content.decode("utf-8-sig")
    # Must be escaped with leading apostrophe
    assert "'=cmd|'/C calc'!A0" in decoded
    assert "'+251911999999" in decoded


@pytest.mark.django_db
def test_members_export_pii_safety(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])
    url = "/api/gym/export/members/"
    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    decoded = response.content.decode("utf-8-sig")

    # Strictly NO fitness profile, measurements, health data, or photos
    forbidden_terms = [
        "health_limitations",
        "dietary_notes",
        "chest_cm",
        "waist_cm",
        "hips_cm",
        "body_fat",
        "bmi",
        "photo_url",
        "workout",
        "injuries",
    ]
    for term in forbidden_terms:
        assert term not in decoded.lower()


@pytest.mark.django_db
def test_date_range_validation(api_client, test_setup):
    auth_client(api_client, test_setup["owner_a"], test_setup["gym_a"])

    # Valid date range
    url = "/api/gym/export/members/?start_date=2026-01-01&end_date=2026-06-01"
    response = api_client.get(url)
    assert response.status_code == status.HTTP_200_OK

    # Date range > 366 days (1 year)
    url_over = "/api/gym/export/members/?start_date=2025-01-01&end_date=2026-06-01"
    response_over = api_client.get(url_over)
    assert response_over.status_code == status.HTTP_400_BAD_REQUEST
    assert "cannot exceed 1 year" in response_over.json()["detail"]

    # Start date after end date
    url_inverted = "/api/gym/export/members/?start_date=2026-06-01&end_date=2026-01-01"
    response_inv = api_client.get(url_inverted)
    assert response_inv.status_code == status.HTTP_400_BAD_REQUEST
    assert "Start date cannot be after end date" in response_inv.json()["detail"]

    # Invalid export type
    url_bad = "/api/gym/export/invalid_type/"
    response_bad = api_client.get(url_bad)
    assert response_bad.status_code == status.HTTP_400_BAD_REQUEST
