"""
Tests for Item 14: Member self-profile edit restrictions.
A member can change ONLY their password; calling profile endpoints with name, phone, or photo is refused (403).
Owner, Manager, and Reception can edit member details (name, phone, emergency contact, gender, photo).
Staff and Super Admin can edit their own profiles as before.
"""

import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import Member
from apps.tenants.models import GymTenant


def make_test_image(filename="photo.jpg"):
    img = Image.new("RGB", (100, 100), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.getvalue(), content_type="image/jpeg")


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
        email="owner_prof@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_OWNER,
        gym=gym_tenant,
        full_name="Gym Owner",
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def member_user(db, gym_tenant):
    user = User.objects.create_user(
        email="member_prof@bolehub.com",
        password="ValidPassword123!",
        role=User.ROLE_MEMBER,
        gym=gym_tenant,
        full_name="Regular Member",
    )
    user.password_changed_at = timezone.now()
    user.save()
    return user


@pytest.fixture
def member_record(db, gym_tenant, member_user):
    return Member.all_objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name=member_user.full_name,
        phone="+251911223344",
        gender="male",
        waiver_accepted_at=timezone.now(),
        status=Member.STATUS_ACTIVE,
    )


def auth_client_for(user):
    client = APIClient()
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.mark.django_db
class TestMemberProfileRestrictions:
    def test_member_refused_profile_update_via_auth_me(self, gym_tenant, member_user):
        client = auth_client_for(member_user)
        resp = client.patch(
            "/api/auth/me/",
            {"full_name": "New Name Attempt", "phone": "+251922000000"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403
        assert "Members cannot edit profile details" in resp.json().get("detail", "")

    def test_member_refused_update_via_member_me(
        self, gym_tenant, member_user, member_record
    ):
        client = auth_client_for(member_user)
        resp = client.patch(
            "/api/members/me/",
            {"full_name": "New Name Attempt"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_member_refused_upload_member_photo(
        self, gym_tenant, member_user, member_record
    ):
        client = auth_client_for(member_user)
        img = make_test_image("avatar.jpg")
        resp = client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"photo": img},
            format="multipart",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 403

    def test_owner_can_update_member_profile(
        self, gym_tenant, owner_user, member_record
    ):
        client = auth_client_for(owner_user)
        resp = client.patch(
            f"/api/gym/members/{member_record.id}/",
            {
                "full_name": "Updated By Staff",
                "phone": "+251911998877",
                "emergency_contact": "+251911332211",
                "gender": "female",
            },
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        member_record.refresh_from_db()
        assert member_record.full_name == "Updated By Staff"
        assert member_record.phone == "+251911998877"
        assert member_record.gender == "female"

    def test_staff_can_still_edit_their_own_profile(self, gym_tenant, owner_user):
        client = auth_client_for(owner_user)
        resp = client.patch(
            "/api/auth/me/",
            {"full_name": "Owner Updated Name"},
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == 200
        owner_user.refresh_from_db()
        assert owner_user.full_name == "Owner Updated Name"
