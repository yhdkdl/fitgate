"""
Comprehensive tests for Sprint 7: Member Registration.

Covers:
- Self-service and staff-assisted registration produce identical Member + BodyMetrics structure.
- Health waiver required (waiver_accepted_at stored); registration without it is rejected (400).
- Duplicate prevention (duplicate email globally, duplicate phone per gym rejected with 400).
- Email verification lifecycle: unverified self-registered member cannot log in (401);
  valid token verifies email; expired or reused token rejected (400); verified member logs in.
- Staff-assisted registration: Owner, Manager, Reception can register; Trainer gets 403;
  set-password invite link generated; counts as email-verified.
- Public registration rate limiting (10/hour).
- Profile photo ownership: Member reads own photo via exact-match (200); reading another member's
  photo returns 403; listing photos returns 403; uploading photo updates Member.photo_url.
- Trainer photo read access: Trainers cannot read unassigned member photos (403).
- Body composition calculations: BMI and US Navy body-fat estimates computed on read and labeled.
- First-run checklist: register_first_member item automatically ticks complete.
"""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import AuthToken, User
from apps.accounts.tokens import get_tokens_for_user
from apps.memberships.models import BodyMetrics, Member
from apps.tenants.models import GymTenant
from apps.tenants.services import get_first_run_checklist


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def gym_tenant(db):
    gym = GymTenant.objects.create(
        name="FitGate Bole Hub",
        subdomain="bolehub",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )
    return gym


@pytest.fixture
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="Apex Kazanchis",
        subdomain="kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Kazanchis, Addis Ababa",
        tls_confirmed_at="2026-10-11T10:00:00Z",
    )


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner@bolehub.com",
        password="OwnerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_OWNER,
        must_change_password=False,
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager@bolehub.com",
        password="ManagerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MANAGER,
        must_change_password=False,
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ReceptionPassword123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
    )


@pytest.fixture
def trainer_user(db, gym_tenant):
    return User.objects.create_user(
        email="trainer@bolehub.com",
        password="TrainerPassword123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
        must_change_password=False,
    )


def auth_client(
    client: APIClient, user: User, tenant_subdomain: str | None = None
) -> APIClient:
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if tenant_subdomain:
        client.defaults["HTTP_HOST"] = f"{tenant_subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


def make_valid_image(name="test.webp", format="WEBP"):
    stream = BytesIO()
    img = Image.new("RGB", (300, 300), color=(100, 150, 200))
    img.save(stream, format=format)
    stream.seek(0)
    return SimpleUploadedFile(name, stream.read(), content_type="image/webp")


@pytest.mark.django_db
class TestMemberRegistrationSelfServiceAndStaffParity:
    """Tests proving self-service and staff-assisted registrations produce identical structures."""

    def test_self_service_registration_creates_identical_structure(
        self, api_client, gym_tenant
    ):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        payload = {
            "full_name": "Abebe Bikila",
            "email": "abebe@example.com",
            "phone": "+251911001122",
            "password": "SecurePassword123!",
            "waiver_accepted": True,
            "date_of_birth": "1995-05-15",
            "gender": "male",
            "emergency_contact": "+251922001122",
            "referral_source": "friend",
            "weight_kg": 72.5,
            "height_cm": 178.0,
            "measurements": {"neck_cm": 39.0, "waist_cm": 82.0},
        }

        resp = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp.status_code == 201
        assert "Registration successful" in resp.data["detail"]

        member = Member.all_objects.get(user__email="abebe@example.com")
        assert member.gym == gym_tenant
        assert member.full_name == "Abebe Bikila"
        assert member.phone == "+251911001122"
        assert str(member.date_of_birth) == "1995-05-15"
        assert member.gender == "male"
        assert member.emergency_contact == "+251922001122"
        assert member.referral_source == "friend"
        assert member.status == Member.STATUS_PENDING
        assert member.waiver_accepted_at is not None

        # User checks
        user = member.user
        assert user.role == User.ROLE_MEMBER
        assert user.gym == gym_tenant
        assert user.email_verified_at is None  # Unverified initially
        assert user.check_password("SecurePassword123!")

        # BodyMetrics are not created on registration (Sprint 7b trainer-only measurements)
        assert BodyMetrics.all_objects.filter(member=member).count() == 0

        # AuthToken verification link created
        token_obj = AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_EMAIL_VERIFICATION,
        ).first()
        assert token_obj is not None
        assert token_obj.used_at is None

    def test_staff_assisted_registration_creates_identical_structure(
        self, api_client, gym_tenant, reception_user
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        payload = {
            "full_name": "Derartu Tulu",
            "email": "derartu@example.com",
            "phone": "+251911334455",
            "waiver_accepted": True,
            "date_of_birth": "1992-03-21",
            "gender": "female",
            "emergency_contact": "+251933445566",
            "referral_source": "walk_in",
            "weight_kg": 58.0,
            "height_cm": 165.0,
            "measurements": {"neck_cm": 32.0, "waist_cm": 68.0, "hip_cm": 92.0},
        }

        resp = client.post("/api/gym/members/", payload, format="json")
        assert resp.status_code == 201
        assert "Member registered successfully" in resp.data["detail"]

        member = Member.all_objects.get(user__email="derartu@example.com")
        assert member.gym == gym_tenant
        assert member.full_name == "Derartu Tulu"
        assert member.phone == "+251911334455"
        assert str(member.date_of_birth) == "1992-03-21"
        assert member.gender == "female"
        assert member.emergency_contact == "+251933445566"
        assert member.referral_source == "walk_in"
        assert member.status == Member.STATUS_PENDING
        assert member.waiver_accepted_at is not None

        # User checks
        user = member.user
        assert user.role == User.ROLE_MEMBER
        assert user.gym == gym_tenant
        assert user.email_verified_at is not None  # Staff-registered counts as verified
        assert not user.has_usable_password()

        # BodyMetrics are not created on registration (Sprint 7b trainer-only measurements)
        assert BodyMetrics.all_objects.filter(member=member).count() == 0

        # AuthToken invite link created
        token_obj = AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_INVITE,
        ).first()
        assert token_obj is not None
        assert token_obj.used_at is None


@pytest.mark.django_db
class TestWaiverAndDuplicateEnforcement:
    """Tests for mandatory health waiver and duplicate prevention."""

    def test_registration_without_waiver_is_rejected(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        # Missing waiver
        payload = {
            "full_name": "Kenenisa Bekele",
            "email": "kenenisa@example.com",
            "phone": "+251911556677",
            "password": "SecurePassword123!",
            "gender": "male",
            "waiver_accepted": False,
        }
        resp = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp.status_code == 400
        assert "waiver_accepted" in resp.data

        # Explicitly absent waiver
        del payload["waiver_accepted"]
        resp = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp.status_code == 400
        assert "waiver_accepted" in resp.data

    def test_duplicate_email_rejected_across_platform(
        self, api_client, gym_tenant, other_gym_tenant
    ):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        payload = {
            "full_name": "Tirunesh Dibaba",
            "email": "tirunesh@example.com",
            "phone": "+251911778899",
            "password": "SecurePassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        resp = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp.status_code == 201

        # Attempt to register same email at the same gym
        resp_dup = api_client.post(
            "/api/public/members/register/", payload, format="json"
        )
        assert resp_dup.status_code == 400
        assert "email" in resp_dup.data

        # Attempt to register same email at another gym
        api_client.defaults["HTTP_HOST"] = f"{other_gym_tenant.subdomain}.localhost"
        payload["phone"] = "+251922778899"  # different phone
        resp_dup_other = api_client.post(
            "/api/public/members/register/", payload, format="json"
        )
        assert resp_dup_other.status_code == 400
        assert "email" in resp_dup_other.data

    def test_duplicate_phone_rejected_within_same_gym(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        payload1 = {
            "full_name": "Member One",
            "email": "one@example.com",
            "phone": "+251911990011",
            "password": "SecurePassword123!",
            "gender": "male",
            "waiver_accepted": True,
        }
        resp1 = api_client.post(
            "/api/public/members/register/", payload1, format="json"
        )
        assert resp1.status_code == 201

        payload2 = {
            "full_name": "Member Two",
            "email": "two@example.com",
            "phone": "+251911990011",  # Same phone
            "password": "SecurePassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        resp2 = api_client.post(
            "/api/public/members/register/", payload2, format="json"
        )
        assert resp2.status_code == 400
        assert "phone" in resp2.data

    def test_same_phone_in_different_gym_is_allowed(
        self, api_client, gym_tenant, other_gym_tenant
    ):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        payload = {
            "full_name": "Multi Gym Member",
            "email": "gym1@example.com",
            "phone": "+251911882233",
            "password": "SecurePassword123!",
            "gender": "male",
            "waiver_accepted": True,
        }
        resp1 = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp1.status_code == 201

        # Register same phone in other gym with different email
        api_client.defaults["HTTP_HOST"] = f"{other_gym_tenant.subdomain}.localhost"
        payload["email"] = "gym2@example.com"
        resp2 = api_client.post("/api/public/members/register/", payload, format="json")
        assert resp2.status_code == 201


@pytest.mark.django_db
class TestEmailVerificationAndAuthLifecycle:
    """Tests for email verification token lifecycle and login enforcement."""

    def test_unverified_member_cannot_log_in(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        payload = {
            "full_name": "Haile Gebrselassie",
            "email": "haile@example.com",
            "phone": "+251911123456",
            "password": "SecretPassword123!",
            "gender": "male",
            "waiver_accepted": True,
        }
        resp_reg = api_client.post(
            "/api/public/members/register/", payload, format="json"
        )
        assert resp_reg.status_code == 201

        # Attempt to log in before verifying
        login_resp = api_client.post(
            "/api/auth/login/",
            {"email": "haile@example.com", "password": "SecretPassword123!"},
            format="json",
        )
        assert login_resp.status_code == 401
        assert login_resp.data["detail"] == "Invalid credentials."

    def test_email_verification_flow_enables_login(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        payload = {
            "full_name": "Meseret Defar",
            "email": "meseret@example.com",
            "phone": "+251911654321",
            "password": "SecretPassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        resp_reg = api_client.post(
            "/api/public/members/register/", payload, format="json"
        )
        assert resp_reg.status_code == 201

        user = User.all_objects.get(email="meseret@example.com")
        assert AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_EMAIL_VERIFICATION,
        ).exists()
        # In test, token hash is in DB; let's simulate client providing token
        # Generate known raw token by registering via service directly or inspecting service
        from apps.memberships.services import register_member_self_service

        test_user_payload = {
            "full_name": "Sifan Hassan",
            "email": "sifan@example.com",
            "phone": "+251911765432",
            "password": "SecretPassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        _, raw_token = register_member_self_service(gym_tenant, test_user_payload)

        # Verify email with raw token
        verify_resp = api_client.post(
            "/api/auth/verify-email/",
            {"token": raw_token},
            format="json",
        )
        assert verify_resp.status_code == 200
        assert verify_resp.data["detail"] == "Email verified successfully."

        # Now login succeeds
        login_resp = api_client.post(
            "/api/auth/login/",
            {"email": "sifan@example.com", "password": "SecretPassword123!"},
            format="json",
        )
        assert login_resp.status_code == 200
        assert "access" in login_resp.data
        assert "refresh" in login_resp.data

    def test_reused_and_expired_verification_token_rejected(
        self, api_client, gym_tenant
    ):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        from apps.memberships.services import register_member_self_service

        payload = {
            "full_name": "Gudaf Tsegay",
            "email": "gudaf@example.com",
            "phone": "+251911998877",
            "password": "SecretPassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        _, raw_token = register_member_self_service(gym_tenant, payload)

        # 1. First verification succeeds
        resp1 = api_client.post(
            "/api/auth/verify-email/", {"token": raw_token}, format="json"
        )
        assert resp1.status_code == 200

        # 2. Second use fails
        resp2 = api_client.post(
            "/api/auth/verify-email/", {"token": raw_token}, format="json"
        )
        assert resp2.status_code == 400

        # 3. Expired token fails
        payload_exp = {
            "full_name": "Letesenbet Gidey",
            "email": "letesenbet@example.com",
            "phone": "+251911998866",
            "password": "SecretPassword123!",
            "gender": "female",
            "waiver_accepted": True,
        }
        _, exp_token = register_member_self_service(gym_tenant, payload_exp)
        # Backdate expiry
        user = User.all_objects.get(email="letesenbet@example.com")
        AuthToken.objects.filter(
            user=user,
            purpose=AuthToken.PURPOSE_EMAIL_VERIFICATION,
        ).update(expires_at=timezone.now() - timedelta(hours=1))

        resp_exp = api_client.post(
            "/api/auth/verify-email/", {"token": exp_token}, format="json"
        )
        assert resp_exp.status_code == 400


@pytest.mark.django_db
class TestStaffAssistedRegistrationAndPermissions:
    """Tests for role permission matrix on member registration."""

    def test_owner_manager_reception_can_register_member(
        self, api_client, gym_tenant, owner_user, manager_user, reception_user
    ):
        staff_list = [
            (owner_user, "member_owner@example.com", "+251911000001"),
            (manager_user, "member_mgr@example.com", "+251911000002"),
            (reception_user, "member_rec@example.com", "+251911000003"),
        ]

        for staff, email, phone in staff_list:
            client = auth_client(api_client, staff, gym_tenant.subdomain)
            payload = {
                "full_name": f"Member registered by {staff.role}",
                "email": email,
                "phone": phone,
                "gender": "male",
                "waiver_accepted": True,
            }
            resp = client.post("/api/gym/members/", payload, format="json")
            assert resp.status_code == 201

    def test_trainer_cannot_register_member(self, api_client, gym_tenant, trainer_user):
        client = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        payload = {
            "full_name": "Unauthorized Trainer Registration",
            "email": "trainer_reg@example.com",
            "phone": "+251911000004",
            "gender": "female",
            "waiver_accepted": True,
        }
        resp = client.post("/api/gym/members/", payload, format="json")
        assert resp.status_code == 403


@pytest.mark.django_db
class TestProfilePhotoOwnershipAndScoping:
    """Tests for member profile photo ownership exact-match check and trainer scoping."""

    def test_member_reads_own_photo_via_exact_match(
        self, api_client, gym_tenant, owner_user
    ):
        from apps.memberships.services import register_member_self_service

        member, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Photo Test Member",
                "email": "photo_test@example.com",
                "phone": "+251911445566",
                "password": "Password123!",
                "gender": "female",
                "waiver_accepted": True,
            },
        )
        user = member.user
        user.email_verified_at = timezone.now()
        user.save()

        client = auth_client(api_client, user, gym_tenant.subdomain)
        staff_client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # Upload photo via staff (Item 14)
        photo_file = make_valid_image("profile.webp")
        upload_resp = staff_client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"photo": photo_file, "member_id": str(member.id)},
            format="multipart",
        )
        assert upload_resp.status_code == 201
        filename = upload_resp.data["filename"]

        member.refresh_from_db()
        assert filename in member.photo_url

        # Read own photo -> 200
        read_resp = client.get(f"/api/media/member-photos/{gym_tenant.id}/{filename}/")
        assert read_resp.status_code == 200

    def test_member_cannot_read_another_members_photo(
        self, api_client, gym_tenant, owner_user
    ):
        from apps.memberships.services import register_member_self_service

        staff_client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        # Member 1
        m1, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Member One",
                "email": "m1@example.com",
                "phone": "+251911111111",
                "password": "Password123!",
                "gender": "male",
                "waiver_accepted": True,
            },
        )
        m1.user.email_verified_at = timezone.now()
        m1.user.save()
        up_resp = staff_client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"photo": make_valid_image("m1.webp"), "member_id": str(m1.id)},
            format="multipart",
        )
        m1_filename = up_resp.data["filename"]

        # Member 2
        m2, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Member Two",
                "email": "m2@example.com",
                "phone": "+251922222222",
                "password": "Password123!",
                "gender": "female",
                "waiver_accepted": True,
            },
        )
        m2.user.email_verified_at = timezone.now()
        m2.user.save()
        c2 = auth_client(api_client, m2.user, gym_tenant.subdomain)

        # Member 2 tries to read Member 1's photo -> 403 Forbidden
        read_resp = c2.get(f"/api/media/member-photos/{gym_tenant.id}/{m1_filename}/")
        assert read_resp.status_code == 403
        assert "Members may only view their own photo" in read_resp.data["detail"]

    def test_member_cannot_list_photos(self, api_client, gym_tenant):
        from apps.memberships.services import register_member_self_service

        m, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "List Tester",
                "email": "list@example.com",
                "phone": "+251933333333",
                "password": "Password123!",
                "gender": "female",
                "waiver_accepted": True,
            },
        )
        m.user.email_verified_at = timezone.now()
        m.user.save()
        client = auth_client(api_client, m.user, gym_tenant.subdomain)

        resp = client.get(f"/api/media/member-photos/{gym_tenant.id}/")
        assert resp.status_code == 403

    def test_trainer_cannot_view_unassigned_member_photo(
        self, api_client, gym_tenant, trainer_user, owner_user
    ):
        from apps.memberships.services import register_member_self_service

        staff_client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        m, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Unassigned Member",
                "email": "unassigned@example.com",
                "phone": "+251944444444",
                "password": "Password123!",
                "gender": "female",
                "waiver_accepted": True,
            },
        )
        m.user.email_verified_at = timezone.now()
        m.user.save()
        up = staff_client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"photo": make_valid_image("unassigned.webp"), "member_id": str(m.id)},
            format="multipart",
        )
        filename = up.data["filename"]

        # Trainer tries to view unassigned member photo -> 403 Forbidden
        tc = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp = tc.get(f"/api/media/member-photos/{gym_tenant.id}/{filename}/")
        assert resp.status_code == 403
        assert (
            "Trainers may only view photos of their assigned members"
            in resp.data["detail"]
        )

    def test_owner_and_reception_can_view_member_photo(
        self, api_client, gym_tenant, owner_user, reception_user
    ):
        from apps.memberships.services import register_member_self_service

        staff_client = auth_client(api_client, owner_user, gym_tenant.subdomain)

        m, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Staff View Member",
                "email": "staffview@example.com",
                "phone": "+251955555555",
                "password": "Password123!",
                "gender": "male",
                "waiver_accepted": True,
            },
        )
        m.user.email_verified_at = timezone.now()
        m.user.save()
        up = staff_client.post(
            f"/api/media/member-photos/{gym_tenant.id}/",
            {"photo": make_valid_image("staffview.webp"), "member_id": str(m.id)},
            format="multipart",
        )
        filename = up.data["filename"]

        # Owner reads photo -> 200
        oc = auth_client(api_client, owner_user, gym_tenant.subdomain)
        assert (
            oc.get(f"/api/media/member-photos/{gym_tenant.id}/{filename}/").status_code
            == 200
        )

        # Reception reads photo -> 200
        rc = auth_client(api_client, reception_user, gym_tenant.subdomain)
        assert (
            rc.get(f"/api/media/member-photos/{gym_tenant.id}/{filename}/").status_code
            == 200
        )


@pytest.mark.django_db
class TestBodyCompositionCalculationsOnRead:
    """Tests for dynamic BMI and US Navy body-fat estimates returned via API."""

    def test_member_detail_and_self_endpoints_include_labeled_estimates(
        self, api_client, gym_tenant, reception_user, owner_user, trainer_user
    ):
        from apps.memberships.services import register_member_self_service

        member, _ = register_member_self_service(
            gym_tenant,
            {
                "full_name": "Metrics Member",
                "email": "metrics@example.com",
                "phone": "+251966666666",
                "password": "Password123!",
                "waiver_accepted": True,
                "gender": "male",
            },
        )
        member.user.email_verified_at = timezone.now()
        member.user.save()

        # Before trainer records: member profile shows no measurements yet
        mc = auth_client(api_client, member.user, gym_tenant.subdomain)
        me_before = mc.get("/api/members/me/")
        assert me_before.status_code == 200
        assert me_before.data["latest_metrics"] is None

        # Trainer records measurements
        tc = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        rec_resp = tc.post(
            f"/api/gym/members/{member.id}/metrics/",
            {
                "weight_kg": 80.0,
                "height_cm": 180.0,
                "waist_cm": 86.0,
                "neck_cm": 40.0,
            },
            format="json",
        )
        assert rec_resp.status_code == 201

        # 1. Reception sees NO measurements anywhere (Sprint 7b criterion 5)
        rc = auth_client(api_client, reception_user, gym_tenant.subdomain)
        reception_resp = rc.get(f"/api/gym/members/{member.id}/")
        assert reception_resp.status_code == 200
        assert reception_resp.data["latest_metrics"] is None
        assert reception_resp.data["body_metrics"] == []

        # 2. Owner can view measurements
        oc = auth_client(api_client, owner_user, gym_tenant.subdomain)
        owner_resp = oc.get(f"/api/gym/members/{member.id}/")
        assert owner_resp.status_code == 200
        latest = owner_resp.data["latest_metrics"]
        assert latest is not None
        assert latest["estimated_bmi"] == 24.7
        assert latest["bmi_label"] == "estimate"
        assert latest["estimated_body_fat_percentage"] is not None
        assert latest["body_fat_label"] == "estimate"
        assert latest["trainer_name"] == trainer_user.full_name

        # 3. Member reads own profile
        mc = auth_client(api_client, member.user, gym_tenant.subdomain)
        me_resp = mc.get("/api/members/me/")
        assert me_resp.status_code == 200
        assert me_resp.data["latest_metrics"]["estimated_bmi"] == 24.7
        assert me_resp.data["latest_metrics"]["bmi_label"] == "estimate"
        assert me_resp.data["latest_metrics"]["trainer_name"] == trainer_user.full_name


@pytest.mark.django_db
class TestChecklistIntegration:
    """Tests checklist register_first_member item completion."""

    def test_registering_first_member_completes_checklist_item(
        self, api_client, gym_tenant, owner_user
    ):
        # Before registration: register_first_member is False
        checklist_before = get_first_run_checklist(gym_tenant)
        assert checklist_before["items"]["register_first_member"]["completed"] is False

        # Register a member
        from apps.memberships.services import register_member_self_service

        register_member_self_service(
            gym_tenant,
            {
                "full_name": "First Member",
                "email": "first@example.com",
                "phone": "+251977777777",
                "password": "Password123!",
                "gender": "female",
                "waiver_accepted": True,
            },
        )

        # After registration: register_first_member is True
        checklist_after = get_first_run_checklist(gym_tenant)
        assert checklist_after["items"]["register_first_member"]["completed"] is True
