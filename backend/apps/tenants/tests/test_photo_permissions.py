"""
Security tests for member photo uploads and permissions (fix/member-photo-upload).

Covers:
- A member cannot change another member's photo (403 Forbidden).
- A member can change their own photo (201 Created).
- Trainers cannot upload or change member photos (403 Forbidden).
- Other gym staff cannot upload to another gym or change photos of another gym's members (403 Forbidden).
- Authorized staff (Owner, Manager, Reception) can upload and change member photos for their gym.
- Corrupt/unsupported file types and files exceeding 2 MB are rejected (400 Bad Request).
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


def make_test_image(
    name: str = "test.webp", fmt: str = "WEBP", size: tuple = (100, 100)
) -> SimpleUploadedFile:
    img = Image.new("RGB", size, color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    content_type = "image/webp" if fmt.upper() == "WEBP" else f"image/{fmt.lower()}"
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


def auth_client(user: User, subdomain: str) -> APIClient:
    client = APIClient()
    client.defaults["HTTP_HOST"] = f"{subdomain}.localhost"
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    return client


@pytest.fixture
def gym_a(db):
    return GymTenant.objects.create(
        name="Gym Alpha",
        subdomain="alpha",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911111111",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def gym_b(db):
    return GymTenant.objects.create(
        name="Gym Beta",
        subdomain="beta",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922222222",
        tls_confirmed_at=timezone.now(),
    )


@pytest.fixture
def owner_gym_a(db, gym_a):
    return User.objects.create_user(
        email="owner@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def manager_gym_a(db, gym_a):
    return User.objects.create_user(
        email="manager@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_MANAGER,
        must_change_password=False,
    )


@pytest.fixture
def reception_gym_a(db, gym_a):
    return User.objects.create_user(
        email="reception@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def trainer_gym_a(db, gym_a):
    return User.objects.create_user(
        email="trainer@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )


@pytest.fixture
def owner_gym_b(db, gym_b):
    return User.objects.create_user(
        email="owner@beta.com",
        password="Password123!",
        gym=gym_b,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def member_a1(db, gym_a):
    u = User.objects.create_user(
        email="m1@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_MEMBER,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return Member.objects.create(
        gym=gym_a,
        user=u,
        full_name="Member One Alpha",
        phone="+251911000001",
        photo_url="/api/media/member-photos/alpha/original_m1.webp/",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )


@pytest.fixture
def member_a2(db, gym_a):
    u = User.objects.create_user(
        email="m2@alpha.com",
        password="Password123!",
        gym=gym_a,
        role=User.ROLE_MEMBER,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return Member.objects.create(
        gym=gym_a,
        user=u,
        full_name="Member Two Alpha",
        phone="+251911000002",
        photo_url="/api/media/member-photos/alpha/original_m2.webp/",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )


@pytest.fixture
def member_b1(db, gym_b):
    u = User.objects.create_user(
        email="m1@beta.com",
        password="Password123!",
        gym=gym_b,
        role=User.ROLE_MEMBER,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )
    return Member.objects.create(
        gym=gym_b,
        user=u,
        full_name="Member One Beta",
        phone="+251922000001",
        photo_url="/api/media/member-photos/beta/original_b1.webp/",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
    )


@pytest.mark.django_db
class TestMemberPhotoSecurity:
    """Security permissions test suite for member photo uploads."""

    def test_member_cannot_change_another_members_photo(
        self, gym_a, member_a1, member_a2, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        client = auth_client(member_a1.user, gym_a.subdomain)
        image = make_test_image("hacked.webp")

        # Member A1 attempts to change Member A2's photo by specifying member_id
        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image, "member_id": str(member_a2.id)},
            format="multipart",
        )
        assert resp.status_code == 403
        assert "Members cannot change another member's photo" in resp.data["detail"]

        # Verify A2's photo was not changed
        member_a2.refresh_from_db()
        assert member_a2.photo_url == "/api/media/member-photos/alpha/original_m2.webp/"

    def test_member_can_change_own_photo(self, gym_a, member_a1, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        client = auth_client(member_a1.user, gym_a.subdomain)
        image = make_test_image("new_me.webp")

        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image},
            format="multipart",
        )
        assert resp.status_code == 201
        assert "url" in resp.data

        member_a1.refresh_from_db()
        assert resp.data["filename"] in member_a1.photo_url

    def test_trainer_cannot_upload_or_change_photo(
        self, gym_a, trainer_gym_a, member_a1, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        client = auth_client(trainer_gym_a, gym_a.subdomain)
        image = make_test_image("trainer_attempt.webp")

        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image, "member_id": str(member_a1.id)},
            format="multipart",
        )
        assert resp.status_code == 403
        assert "Trainers cannot upload or change member photos" in resp.data["detail"]

        # Verify photo untouched
        member_a1.refresh_from_db()
        assert member_a1.photo_url == "/api/media/member-photos/alpha/original_m1.webp/"

    def test_other_gym_staff_cannot_upload_to_foreign_gym(
        self, gym_a, gym_b, owner_gym_b, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        image = make_test_image("foreign.webp")

        # 1. Foreign staff presenting token on gym A's subdomain is refused (401/403)
        client_a = auth_client(owner_gym_b, gym_a.subdomain)
        resp_cross_subdomain = client_a.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image},
            format="multipart",
        )
        assert resp_cross_subdomain.status_code in (401, 403)

        # 2. Staff on own subdomain (beta) attempting to target gym A's id gets 404 tenant mismatch
        client_b = auth_client(owner_gym_b, gym_b.subdomain)
        resp_mismatch = client_b.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image},
            format="multipart",
        )
        assert resp_mismatch.status_code in (403, 404)

    def test_staff_cannot_change_photo_of_other_gym_member(
        self, gym_a, gym_b, owner_gym_a, member_b1, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        client = auth_client(owner_gym_a, gym_a.subdomain)
        image = make_test_image("cross_member.webp")

        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image, "member_id": str(member_b1.id)},
            format="multipart",
        )
        assert resp.status_code == 403
        assert "another gym" in resp.data["detail"].lower()

        # Member in Gym B remains untouched
        member_b1.refresh_from_db()
        assert member_b1.photo_url == "/api/media/member-photos/beta/original_b1.webp/"

    @pytest.mark.parametrize(
        "staff_fixture", ["owner_gym_a", "manager_gym_a", "reception_gym_a"]
    )
    def test_authorized_staff_can_change_member_photo(
        self, request, gym_a, staff_fixture, member_a1, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        staff_user = request.getfixturevalue(staff_fixture)
        client = auth_client(staff_user, gym_a.subdomain)
        image = make_test_image(f"{staff_fixture}.webp")

        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": image, "member_id": str(member_a1.id)},
            format="multipart",
        )
        assert resp.status_code == 201
        member_a1.refresh_from_db()
        assert resp.data["filename"] in member_a1.photo_url

    def test_bad_file_types_and_size_rejected(
        self, gym_a, owner_gym_a, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        client = auth_client(owner_gym_a, gym_a.subdomain)

        # 1. Non-image file (e.g. text/pdf)
        fake_file = SimpleUploadedFile(
            "script.py", b"print('hello world')", content_type="text/x-python"
        )
        resp = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": fake_file},
            format="multipart",
        )
        assert resp.status_code == 400

        # 2. File exceeding 2 MB
        oversized = SimpleUploadedFile(
            "big.png", b"x" * (2 * 1024 * 1024 + 1024), content_type="image/png"
        )
        resp_size = client.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": oversized},
            format="multipart",
        )
        assert resp_size.status_code == 400
        assert "exceeds" in resp_size.data["detail"].lower()
