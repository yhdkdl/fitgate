"""
Tests for Item 12: Integrated staff registration with payment in ONE atomic transaction.
Verifies all-or-nothing behavior: if payment recording fails, no User, Member, or Receipt is created.
"""

import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member, MembershipPlan
from apps.payments.models import Receipt
from apps.tenants.models import GymTenant


def make_test_image(filename="screenshot.png"):
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.getvalue(), content_type="image/png")


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    user = User.objects.create_user(
        email="owner@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Bole Owner",
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def active_plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1500.00"),
        is_active=True,
    )


@pytest.fixture
def deactivated_plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Legacy Discontinued",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1200.00"),
        is_active=False,
    )


@pytest.fixture
def auth_client(owner_user, gym_tenant):
    client = APIClient()
    tokens = get_tokens_for_user(owner_user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
class TestStaffRegistrationAtomic:
    def test_staff_registration_with_cash_success(
        self, auth_client, gym_tenant, active_plan
    ):
        email = "new_cash_member@test.com"
        resp = auth_client.post(
            "/api/gym/members/",
            {
                "full_name": "Abebe Cash",
                "email": email,
                "phone": "+251911112233",
                "emergency_contact": "+251911998877",
                "gender": "male",
                "waiver_accepted": True,
                "plan_id": str(active_plan.id),
                "payment_method": "cash",
                "notes": "Paid in full at counter",
            },
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "receipt" in data
        assert data["receipt"]["amount_etb"] == "1500.00"

        member = Member.all_objects.filter(user__email=email).first()
        assert member is not None
        assert member.status == Member.STATUS_ACTIVE
        assert Receipt.all_objects.filter(member_name="Abebe Cash").exists()

    def test_staff_registration_failed_payment_rolls_back_all(
        self, auth_client, gym_tenant, deactivated_plan
    ):
        email = "fail_rollback_member@test.com"
        resp = auth_client.post(
            "/api/gym/members/",
            {
                "full_name": "Rollback Member",
                "email": email,
                "phone": "+251911334455",
                "emergency_contact": "+251911998877",
                "gender": "female",
                "waiver_accepted": True,
                "plan_id": str(deactivated_plan.id),
                "payment_method": "cash",
            },
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 400

        # Assert all-or-nothing rollback: neither User nor Member nor Receipt created
        assert not User.objects.filter(email=email).exists()
        assert not Member.all_objects.filter(user__email=email).exists()
        assert not Receipt.all_objects.filter(member_name="Rollback Member").exists()

    def test_staff_registration_bank_transfer_duplicate_ref_rolls_back(
        self, auth_client, gym_tenant, active_plan
    ):
        img1 = make_test_image("proof1.png")
        img2 = make_test_image("proof2.png")

        # 1. Register first member with bank transfer
        email1 = "bt_member_1@test.com"
        resp1 = auth_client.post(
            "/api/gym/members/",
            {
                "full_name": "First Bank Member",
                "email": email1,
                "phone": "+251911445566",
                "emergency_contact": "+251911998877",
                "gender": "male",
                "waiver_accepted": True,
                "plan_id": str(active_plan.id),
                "payment_method": "bank_transfer",
                "bank_reference": "REF-UNIQUE-12345",
                "transfer_date": str(timezone.localdate()),
                "screenshot": img1,
            },
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp1.status_code == 201

        # 2. Register second member with identical bank reference -> must fail and rollback
        email2 = "bt_member_2@test.com"
        resp2 = auth_client.post(
            "/api/gym/members/",
            {
                "full_name": "Second Bank Member",
                "email": email2,
                "phone": "+251911556677",
                "emergency_contact": "+251911998877",
                "gender": "female",
                "waiver_accepted": True,
                "plan_id": str(active_plan.id),
                "payment_method": "bank_transfer",
                "bank_reference": "ref-unique-12345",
                "transfer_date": str(timezone.localdate()),
                "screenshot": img2,
            },
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp2.status_code == 400

        # All-or-nothing rollback check for second member
        assert not User.objects.filter(email=email2).exists()
        assert not Member.all_objects.filter(user__email=email2).exists()
        assert not Receipt.all_objects.filter(member_name="Second Bank Member").exists()
