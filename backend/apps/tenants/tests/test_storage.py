"""
Tests for Sprint 4b: File storage layer.

Covers:
- Image validation (Pillow inspection, format whitelist, <= 2MB size, non-image rejection).
- Metadata/EXIF stripping and resizing.
- FitGateStorage abstraction (local FileSystemStorage fallback and Cloudinary integration).
- Tenant scoping and security for authenticated member photos:
  - Users can access photos for their own gym.
  - Users accessing another gym's photos receive 403 Forbidden.
  - Super Admin can access photos for any gym.
  - Non-existent photos return 404.
  - Path traversal attempts return 400.
- Public gym logo upload and serving.
"""

import io
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.tenants.models import GymTenant
from apps.tenants.storage import (
    FitGateStorage,
    get_authenticated_photo_stream,
    save_gym_logo,
    save_member_photo,
    validate_and_process_image,
)


def make_test_image(
    fmt: str = "PNG",
    size: tuple = (100, 100),
    color: tuple = (255, 0, 0),
    exif_tag_val: str | None = None,
) -> io.BytesIO:
    """Create an in-memory image buffer with optional EXIF metadata."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    if exif_tag_val:
        exif = img.getexif()
        # 0x010E is ImageDescription
        exif[0x010E] = exif_tag_val
        img.save(buf, format=fmt, exif=exif)
    else:
        img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def make_uploaded_image(
    name: str = "test.png",
    fmt: str = "PNG",
    size: tuple = (100, 100),
    color: tuple = (255, 0, 0),
    exif_tag_val: str | None = None,
) -> SimpleUploadedFile:
    """Wrap make_test_image in SimpleUploadedFile."""
    buf = make_test_image(fmt=fmt, size=size, color=color, exif_tag_val=exif_tag_val)
    content_type = (
        "image/jpeg" if fmt.upper() in ("JPEG", "JPG") else f"image/{fmt.lower()}"
    )
    return SimpleUploadedFile(name, buf.getvalue(), content_type=content_type)


@pytest.mark.django_db
class TestImageValidationAndProcessing:
    """Unit tests for validate_and_process_image."""

    def test_valid_png_converts_to_webp(self):
        upload = make_uploaded_image("sample.png", fmt="PNG", size=(200, 150))
        content_file, filename = validate_and_process_image(upload)

        assert filename.endswith(".webp")
        with Image.open(content_file) as out_img:
            assert out_img.format == "WEBP"
            assert out_img.size == (200, 150)

    def test_valid_jpeg_converts_to_webp(self):
        upload = make_uploaded_image("sample.jpg", fmt="JPEG", size=(300, 200))
        content_file, filename = validate_and_process_image(upload)

        assert filename.endswith(".webp")
        with Image.open(content_file) as out_img:
            assert out_img.format == "WEBP"
            assert out_img.size == (300, 200)

    def test_rejects_file_exceeding_max_size(self):
        # 2 MB limit is 2 * 1024 * 1024 bytes. Test with 2.1 MB dummy data
        huge_data = b"x" * (2 * 1024 * 1024 + 1024)
        upload = SimpleUploadedFile("huge.png", huge_data, content_type="image/png")

        with pytest.raises(ValidationError) as exc:
            validate_and_process_image(upload)
        assert "exceeds maximum allowed 2 MB" in str(exc.value)

    def test_rejects_non_image_content(self):
        fake_image = SimpleUploadedFile(
            "virus.png",
            b"MZ\x90\x00\x03\x00\x00\x00plain binary content",
            content_type="image/png",
        )
        with pytest.raises(ValidationError) as exc:
            validate_and_process_image(fake_image)
        assert "not a valid image" in str(exc.value)

    def test_rejects_unsupported_image_format(self):
        # GIF is not in whitelist (JPEG, PNG, WEBP)
        upload = make_uploaded_image("animation.gif", fmt="GIF", size=(50, 50))
        with pytest.raises(ValidationError) as exc:
            validate_and_process_image(upload)
        assert "Unsupported image format" in str(exc.value)

    def test_resizes_large_dimensions(self):
        # 1600x1200 with max_dimensions (800, 800) should scale down to 800x600
        upload = make_uploaded_image("large.png", fmt="PNG", size=(1600, 1200))
        content_file, _ = validate_and_process_image(upload, max_dimensions=(800, 800))

        with Image.open(content_file) as out_img:
            assert out_img.size == (800, 600)

    def test_strips_exif_metadata(self):
        upload = make_uploaded_image(
            "photo.jpg",
            fmt="JPEG",
            size=(200, 200),
            exif_tag_val="Sensitive Camera & Location Data",
        )
        content_file, _ = validate_and_process_image(upload)

        with Image.open(content_file) as out_img:
            exif = out_img.getexif()
            assert 0x010E not in exif


@pytest.mark.django_db
class TestStorageAbstraction:
    """Tests for FitGateStorage local and Cloudinary behavior."""

    @pytest.fixture
    def gym(self):
        return GymTenant.objects.create(name="Alpha Gym", subdomain="alpha-gym")

    def test_local_storage_member_photo_and_retrieval(self, gym, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("member.jpg", fmt="JPEG", size=(120, 120))

        relative_path = save_member_photo(gym.id, upload)
        assert relative_path.startswith(f"gyms/{gym.id}/member_photos/")
        assert relative_path.endswith(".webp")

        filename = relative_path.split("/")[-1]
        stream, content_type = get_authenticated_photo_stream(gym.id, filename)
        assert content_type == "image/webp"
        assert len(stream.read()) > 0

    def test_local_storage_gym_logo(self, gym, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("logo.png", fmt="PNG", size=(300, 300))

        url = save_gym_logo(gym.id, upload)
        assert url.startswith("/media/logos/") or "logos/" in url

    def test_path_traversal_in_filename_rejected(self, gym):
        with pytest.raises(ValidationError) as exc:
            get_authenticated_photo_stream(gym.id, "../../../etc/passwd")
        assert "Invalid filename format" in str(exc.value)

    def test_nonexistent_photo_raises_not_found(self, gym, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        with pytest.raises(FileNotFoundError):
            get_authenticated_photo_stream(
                gym.id, "00000000000000000000000000000000.webp"
            )

    def test_cloudinary_save_and_authenticated_access(self, gym, settings):
        settings.CLOUDINARY_CLOUD_NAME = "test-cloud"
        settings.CLOUDINARY_API_KEY = "test-key"
        settings.CLOUDINARY_API_SECRET = "test-secret"

        storage = FitGateStorage()
        assert storage.is_cloudinary is True

        upload = make_uploaded_image("photo.jpg", fmt="JPEG")
        content_file, _ = validate_and_process_image(upload)

        with (
            patch("cloudinary.uploader.upload") as mock_upload,
            patch(
                "cloudinary.utils.cloudinary_url",
                return_value=("https://res.cloudinary.com/signed-url", {}),
            ),
            patch("urllib.request.urlopen") as mock_urlopen,
        ):
            mock_upload.return_value = {
                "secure_url": "https://res.cloudinary.com/test-cloud/image/upload/sample.webp"
            }
            mock_resp = MagicMock()
            mock_resp.read.return_value = b"fake-webp-bytes"
            mock_urlopen.return_value = mock_resp

            # Authenticated asset save: returns internal relative path, NOT Cloudinary URL
            path = storage.save_authenticated_asset(
                "gyms/123/member_photos/test.webp", content_file
            )
            assert path == "gyms/123/member_photos/test.webp"
            mock_upload.assert_called_with(
                content_file,
                public_id="gyms/123/member_photos/test",
                resource_type="image",
                type="authenticated",
                overwrite=True,
            )

            # Public asset save: returns secure Cloudinary URL
            logo_url = storage.save_public_asset("logos/test_logo.webp", content_file)
            assert (
                logo_url
                == "https://res.cloudinary.com/test-cloud/image/upload/sample.webp"
            )

            # Authenticated stream retrieval: signs URL and reads stream
            stream, ctype = storage.get_authenticated_asset(
                "gyms/123/member_photos/test.webp"
            )
            assert ctype == "image/webp"
            assert stream.read() == b"fake-webp-bytes"


@pytest.mark.django_db
class TestMediaEndpointsSuite:
    """Integration tests for media serve and upload endpoints."""

    @pytest.fixture
    def gym_a(self):
        from django.utils import timezone

        return GymTenant.objects.create(
            name="Gym Alpha", subdomain="gym-alpha", tls_confirmed_at=timezone.now()
        )

    @pytest.fixture
    def gym_b(self):
        from django.utils import timezone

        return GymTenant.objects.create(
            name="Gym Beta", subdomain="gym-beta", tls_confirmed_at=timezone.now()
        )

    @pytest.fixture
    def user_gym_a(self, gym_a):
        return User.objects.create_user(
            email="member-a@alpha.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_a,
            must_change_password=False,
        )

    @pytest.fixture
    def owner_gym_a(self, gym_a):
        return User.objects.create_user(
            email="owner@alpha.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_a,
            must_change_password=False,
        )

    @pytest.fixture
    def user_gym_b(self, gym_b):
        return User.objects.create_user(
            email="member-b@beta.com",
            password="MemberPassword123!",
            role=User.ROLE_MEMBER,
            gym=gym_b,
            must_change_password=False,
        )

    @pytest.fixture
    def owner_gym_b(self, gym_b):
        return User.objects.create_user(
            email="owner@beta.com",
            password="OwnerPassword123!",
            role=User.ROLE_OWNER,
            gym=gym_b,
            must_change_password=False,
        )

    @pytest.fixture
    def super_admin(self):
        return User.objects.create_superuser(
            email="superadmin@fitgate.org",
            password="AdminPassword123!",
            must_change_password=False,
        )

    def auth_client(self, user):
        client = APIClient()
        tokens = get_tokens_for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        if user.gym:
            client.defaults["HTTP_HOST"] = f"{user.gym.subdomain}.localhost"
        else:
            client.defaults["HTTP_HOST"] = "localhost"
        return client

    def test_serve_photo_unauthenticated_returns_401(self, gym_a):
        client = APIClient()
        url = f"/api/media/member-photos/{gym_a.id}/photo.webp/"
        resp = client.get(url, HTTP_HOST=f"{gym_a.subdomain}.localhost")
        assert resp.status_code == 401

    def test_serve_photo_same_gym_staff_returns_200(
        self, gym_a, owner_gym_a, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("pic.png", fmt="PNG")
        rel_path = save_member_photo(gym_a.id, upload)
        filename = rel_path.split("/")[-1]

        client = self.auth_client(owner_gym_a)
        url = f"/api/media/member-photos/{gym_a.id}/{filename}/"
        resp = client.get(url)

        assert resp.status_code == 200
        assert resp["Content-Type"] == "image/webp"
        assert "private" in resp["Cache-Control"]

    def test_serve_photo_cross_tenant_denied_with_404(
        self, gym_a, user_gym_b, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("pic.png", fmt="PNG")
        rel_path = save_member_photo(gym_a.id, upload)
        filename = rel_path.split("/")[-1]

        # User B belongs to Gym B, attempts to access Gym A photo (host is betagym, URL has gym_a.id)
        client = self.auth_client(user_gym_b)
        url = f"/api/media/member-photos/{gym_a.id}/{filename}/"
        resp = client.get(url)

        assert resp.status_code == 404

    def test_serve_photo_super_admin_at_apex_returns_404(
        self, gym_a, super_admin, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("pic.png", fmt="PNG")
        rel_path = save_member_photo(gym_a.id, upload)
        filename = rel_path.split("/")[-1]

        # Super Admin at apex has no tenant context -> IDOR rule returns 404
        client = self.auth_client(super_admin)
        url = f"/api/media/member-photos/{gym_a.id}/{filename}/"
        resp = client.get(url)

        assert resp.status_code == 404

    def test_serve_photo_missing_file_returns_404(
        self, gym_a, owner_gym_a, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        client = self.auth_client(owner_gym_a)
        url = f"/api/media/member-photos/{gym_a.id}/00000000000000000000000000000000.webp/"
        resp = client.get(url)

        assert resp.status_code == 404
        assert "Photo not found" in resp.data["detail"]

    def test_serve_photo_invalid_filename_returns_400(self, gym_a, owner_gym_a):
        client = self.auth_client(owner_gym_a)
        url = f"/api/media/member-photos/{gym_a.id}/malicious..filename.php/"
        resp = client.get(url)

        assert resp.status_code == 400

    def test_upload_member_photo_success(self, gym_a, owner_gym_a, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        client = self.auth_client(owner_gym_a)
        upload = make_uploaded_image("avatar.jpg", fmt="JPEG", size=(250, 250))

        url = f"/api/media/member-photos/{gym_a.id}/"
        resp = client.post(url, {"photo": upload}, format="multipart")

        assert resp.status_code == 201
        assert "filename" in resp.data
        assert resp.data["filename"].endswith(".webp")
        assert f"/api/media/member-photos/{gym_a.id}/" in resp.data["url"]

    def test_upload_member_photo_cross_tenant_denied(self, gym_a, user_gym_b):
        client = self.auth_client(user_gym_b)
        upload = make_uploaded_image("avatar.jpg", fmt="JPEG")

        url = f"/api/media/member-photos/{gym_a.id}/"
        resp = client.post(url, {"photo": upload}, format="multipart")

        assert resp.status_code == 404

    def test_upload_member_photo_invalid_image_rejected(self, gym_a, owner_gym_a):
        client = self.auth_client(owner_gym_a)
        bad_file = SimpleUploadedFile(
            "bad.txt", b"plain text is not an image", content_type="text/plain"
        )

        url = f"/api/media/member-photos/{gym_a.id}/"
        resp = client.post(url, {"photo": bad_file}, format="multipart")

        assert resp.status_code == 400
        assert "not a valid image" in resp.data["detail"]

    def test_upload_gym_logo_permissions(
        self, gym_a, owner_gym_a, user_gym_a, super_admin, tmp_path, settings
    ):
        settings.MEDIA_ROOT = tmp_path
        url = f"/api/media/gym-logo/{gym_a.id}/"

        # Member gets 403
        upload_mem = make_uploaded_image("logo1.png", fmt="PNG", size=(200, 200))
        client_member = self.auth_client(user_gym_a)
        resp_mem = client_member.post(url, {"logo": upload_mem}, format="multipart")
        assert resp_mem.status_code == 403

        # Owner gets 200
        upload_owner = make_uploaded_image("logo2.png", fmt="PNG", size=(200, 200))
        client_owner = self.auth_client(owner_gym_a)
        resp_owner = client_owner.post(url, {"logo": upload_owner}, format="multipart")
        assert resp_owner.status_code == 200
        assert "url" in resp_owner.data

        # Super Admin gets 403 (only Gym Owner is permitted to upload logo)
        upload_admin = make_uploaded_image("logo3.png", fmt="PNG", size=(200, 200))
        client_admin = self.auth_client(super_admin)
        resp_admin = client_admin.post(url, {"logo": upload_admin}, format="multipart")
        assert resp_admin.status_code == 403

    def test_cross_gym_idor_protection_returns_404_and_does_nothing(
        self, gym_a, gym_b, owner_gym_a, tmp_path, settings
    ):
        """
        A1 Contract Test:
        Owner of gym A at gym A's host using gym B's gym_id in URL:
        - Logo upload -> 404, nothing written to disk or config
        - Photo read -> 404, nothing returned
        - Photo list -> 404, nothing returned
        """
        settings.MEDIA_ROOT = tmp_path
        client = self.auth_client(owner_gym_a)

        # 1. Logo upload to gym B's id on gym A's host -> 404 with nothing written
        upload = make_uploaded_image("fake_logo.png", fmt="PNG", size=(200, 200))
        resp_logo = client.post(
            f"/api/media/gym-logo/{gym_b.id}/",
            {"logo": upload},
            format="multipart",
        )
        assert resp_logo.status_code == 404
        gym_b.config.refresh_from_db()
        assert gym_b.config.logo is None

        # 2. Photo read of gym B's id on gym A's host -> 404 with nothing returned
        resp_read = client.get(f"/api/media/member-photos/{gym_b.id}/nonexistent.webp/")
        assert resp_read.status_code == 404

        # 3. Photo list of gym B's id on gym A's host -> 404 with nothing returned
        resp_list = client.get(f"/api/media/member-photos/{gym_b.id}/")
        assert resp_list.status_code == 404

    def test_idor_read_with_real_file_returns_404_and_no_bytes(
        self, gym_a, gym_b, owner_gym_a, owner_gym_b, tmp_path, settings
    ):
        """
        3. IDOR read test with a real file:
        Create a real photo in gym B's storage.
        From gym A's Owner at gym A's host request gym B's gym_id + that real filename:
          -> 404 and no bytes returned.
        The same file from gym B's own Owner at gym B's host:
          -> 200 with real bytes returned (control).
        """
        settings.MEDIA_ROOT = tmp_path
        upload = make_uploaded_image("pic_b.png", fmt="PNG")
        rel_path = save_member_photo(gym_b.id, upload)
        filename = rel_path.split("/")[-1]

        # 1. From gym A's Owner at gym A's host, request gym B's gym_id + filename
        client_a = self.auth_client(owner_gym_a)
        url_cross = f"/api/media/member-photos/{gym_b.id}/{filename}/"
        resp_cross = client_a.get(url_cross)
        assert resp_cross.status_code == 404
        assert resp_cross.content == b'{"detail":"Gym tenant not found."}'

        # 2. Control: Same file from gym B's own Owner at gym B's host -> 200
        client_b = self.auth_client(owner_gym_b)
        url_own = f"/api/media/member-photos/{gym_b.id}/{filename}/"
        resp_own = client_b.get(url_own)
        assert resp_own.status_code == 200
        assert resp_own["Content-Type"] == "image/webp"
        file_bytes = b"".join(resp_own.streaming_content)
        assert len(file_bytes) > 0

    def test_member_role_denied_read_list_upload(
        self, gym_a, user_gym_a, owner_gym_a, tmp_path, settings
    ):
        """
        4. Staff-only until Member model in Sprint 7:
        A Member role gets 403 on read, list, and upload.
        """
        settings.MEDIA_ROOT = tmp_path
        upload_owner = make_uploaded_image("staff_pic.png", fmt="PNG")
        rel_path = save_member_photo(gym_a.id, upload_owner)
        filename = rel_path.split("/")[-1]

        client_member = self.auth_client(user_gym_a)

        # 1. Read -> 403
        resp_read = client_member.get(
            f"/api/media/member-photos/{gym_a.id}/{filename}/"
        )
        assert resp_read.status_code == 403

        # 2. List -> 403
        resp_list = client_member.get(f"/api/media/member-photos/{gym_a.id}/")
        assert resp_list.status_code == 403

        # 3. Upload -> 403
        upload_member = make_uploaded_image("mem_pic.png", fmt="PNG")
        resp_upload = client_member.post(
            f"/api/media/member-photos/{gym_a.id}/",
            {"photo": upload_member},
            format="multipart",
        )
        assert resp_upload.status_code == 403

    def test_path_traversal_on_read(
        self, gym_a, gym_b, owner_gym_a, tmp_path, settings
    ):
        """
        4. Path traversal tests on read:
        filename "..", "%2e%2e", "a..b", encoded slash, another gym's directory
        -> 400 or 404, never file content.
        """
        settings.MEDIA_ROOT = tmp_path
        client = self.auth_client(owner_gym_a)

        traversal_filenames = [
            "..",
            "%2e%2e",
            "a..b",
            "foo%2fbar.webp",
            f"../../gyms/{gym_b.id}/member_photos/stolen.webp",
            f"../{gym_b.id}/photo.webp",
        ]
        for tf in traversal_filenames:
            url = f"/api/media/member-photos/{gym_a.id}/{tf}/"
            resp = client.get(url)
            assert resp.status_code in (
                400,
                404,
            ), f"Filename '{tf}' returned {resp.status_code}"
            assert resp.get("Content-Type") != "image/webp"

    def test_anonymous_photo_read_returns_401(self, gym_a):
        anon_client = APIClient()
        anon_client.defaults["HTTP_HOST"] = f"{gym_a.subdomain}.localhost"
        url = f"/api/media/member-photos/{gym_a.id}/somefile.webp/"
        resp = anon_client.get(url)
        assert resp.status_code == 401
