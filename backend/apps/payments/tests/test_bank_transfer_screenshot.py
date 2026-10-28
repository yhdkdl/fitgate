"""
Tests for Item 17: Bank transfer screenshot upload validation and private retrieval permission matrix.
[TEST: wrong file type and oversize refused; Super Admin, member and another gym's staff denied on the real endpoint.]
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
from apps.tenants.models import GymTenant


def make_test_image(format="PNG", size=(200, 200), filename="proof.png"):
    img = Image.new("RGB", size, color="blue")
    buf = io.BytesIO()
    img.save(buf, format=format)
    buf.seek(0)
    return SimpleUploadedFile(
        filename,
        buf.getvalue(),
        content_type=f"image/{format.lower()}",
    )


@pytest.fixture
def gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def other_gym(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
        subdomain="kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Kazanchis, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    user = User.objects.create_user(
        email="owner_ss@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Bole Owner",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def manager_user(db, gym_tenant):
    user = User.objects.create_user(
        email="manager_ss@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MANAGER,
        gym=gym_tenant,
        full_name="Bole Manager",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def reception_user(db, gym_tenant):
    user = User.objects.create_user(
        email="reception_ss@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
        full_name="Bole Receptionist",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def other_reception_user(db, gym_tenant):
    user = User.objects.create_user(
        email="other_reception@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_RECEPTION,
        gym=gym_tenant,
        full_name="Second Receptionist",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def member_user(db, gym_tenant):
    user = User.objects.create_user(
        email="member_ss@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Bole Member",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def superadmin_user(db):
    user = User.objects.create_superuser(
        email="admin_ss@fitgate.org",
        password="ValidPassword123!",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def other_gym_owner(db, other_gym):
    user = User.objects.create_user(
        email="owner_other@kazanchis.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=other_gym,
        full_name="Kazanchis Owner",
        must_change_password=False,
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def plan(db, gym_tenant):
    return MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard",
        duration_value=1,
        duration_unit="months",
        price_etb=Decimal("1500.00"),
        is_active=True,
    )


@pytest.fixture
def member(db, gym_tenant, member_user):
    return Member.all_objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name=member_user.full_name,
        phone="+251911223344",
        status=Member.STATUS_PENDING,
        waiver_accepted_at=timezone.now(),
    )


def auth_client_for(user, host="bolehub.localhost"):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    client.defaults["HTTP_HOST"] = host
    return client


@pytest.mark.django_db
class TestBankTransferScreenshot:
    def test_wrong_file_type_refused(self, reception_user, gym_tenant, member, plan):
        client = auth_client_for(reception_user)
        # Upload a text file disguised as a screenshot
        fake_file = SimpleUploadedFile(
            "proof.txt", b"Fake text screenshot content", content_type="text/plain"
        )

        resp = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "BT-WRONG-TYPE-1",
                "transfer_date": str(timezone.localdate()),
                "screenshot": fake_file,
            },
            format="multipart",
        )
        assert resp.status_code == 400
        assert (
            "not a valid image" in str(resp.json()).lower()
            or "unsupported" in str(resp.json()).lower()
        )

    def test_oversize_screenshot_refused(
        self, reception_user, gym_tenant, member, plan
    ):
        client = auth_client_for(reception_user)
        # Create oversized file (5.5 MB)
        oversized_data = b"X" * (5500000)
        oversized_file = SimpleUploadedFile(
            "large_proof.png", oversized_data, content_type="image/png"
        )

        resp = client.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "BT-OVERSIZE-1",
                "transfer_date": str(timezone.localdate()),
                "screenshot": oversized_file,
            },
            format="multipart",
        )
        assert resp.status_code == 400
        assert (
            "exceeds maximum" in str(resp.json()).lower()
            or "5 mb" in str(resp.json()).lower()
        )

    def test_screenshot_access_matrix(
        self,
        reception_user,
        owner_user,
        manager_user,
        other_reception_user,
        member_user,
        superadmin_user,
        other_gym_owner,
        gym_tenant,
        member,
        plan,
    ):
        # 1. Record bank transfer payment with valid screenshot by reception_user
        client_rec = auth_client_for(reception_user)
        img = make_test_image()

        resp_create = client_rec.post(
            "/api/gym/payments/bank-transfer/",
            {
                "member_id": str(member.id),
                "plan_id": str(plan.id),
                "bank_reference": "BT-SCREENSHOT-OK",
                "transfer_date": str(timezone.localdate()),
                "screenshot": img,
            },
            format="multipart",
        )
        assert resp_create.status_code == 201
        payment_id = resp_create.json()["payment_id"]

        # 2. Allowed: The recording reception staff member
        resp = client_rec.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/webp"

        # 3. Allowed: Owner of the same gym
        client_owner = auth_client_for(owner_user)
        resp_owner = client_owner.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_owner.status_code == 200
        assert resp_owner["Content-Type"] == "image/webp"

        # 4. Allowed: Manager of the same gym
        client_manager = auth_client_for(manager_user)
        resp_mgr = client_manager.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_mgr.status_code == 200
        assert resp_mgr["Content-Type"] == "image/webp"

        # 5. Denied: Super Admin (403)
        client_sa = auth_client_for(superadmin_user, host="localhost")
        resp_sa = client_sa.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_sa.status_code == 403

        # 6. Denied: Member (403)
        client_mem = auth_client_for(member_user)
        resp_mem = client_mem.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_mem.status_code == 403

        # 7. Denied: Another gym's staff accessing Bole Hub payment (401/403)
        client_other = auth_client_for(other_gym_owner, host="bolehub.localhost")
        resp_other = client_other.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_other.status_code in (401, 403)

        # 8. Denied: Other receptionist from same gym who did not confirm this payment (403)
        client_other_rec = auth_client_for(other_reception_user)
        resp_other_rec = client_other_rec.get(
            f"/api/gym/payments/bank-transfers/{payment_id}/screenshot/"
        )
        assert resp_other_rec.status_code == 403
