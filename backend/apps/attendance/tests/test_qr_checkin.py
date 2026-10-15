"""
Tests for Sprint 8: QR Check-in (GATE).

Covers:
1. Token issuance & rotation (90s window, asymmetric RS256).
2. Public key endpoint for offline verification (GET /api/attendance/public-key/).
3. Valid at 89s, rejected at 91s (tested with frozen clock through the scan endpoint).
4. Tampered token rejected.
5. Validly signed token without exp claim rejected.
6. Reusing already-consumed token rejected (single-use).
7. Next token issued after valid scan.
8. Scan rejected with distinguishable reasons for inactive subscription (expired vs frozen vs suspended).
9. Scan leaves QRToken unconsumed on gym_mismatch, inactive member, or simulated duplicate IntegrityError.
10. Scan success returns photo, name, status, attendance record, and replacement token.
    Photo must be a backend route path (/api/media/member-photos/{gym_id}/{filename}/), never Cloudinary/storage.
11. Exactly one Attendance row created; duplicate scan same day denied, produces no second row, notifies staff.
12. Simulated race / IntegrityError on duplicate check returns already_checked_in (HTTP 400, never 500).
13. RBAC & Password security:
    - Trainer & Super Admin (at gym host) get 403 on scan.
    - Owner, Manager, Reception each allowed (real 200).
    - User with must_change_password=True blocked on scan and member QR endpoint.
"""

import io
import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone
from freezegun import freeze_time
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.crypto import (
    InvalidTokenError,
    QRTokenCryptoError,
    generate_rsa_keypair,
    get_rsa_private_key_pem,
    get_rsa_public_key_pem,
    hash_token,
    sign_qr_payload,
    verify_qr_jwt,
)
from apps.attendance.models import Attendance, QRToken
from apps.attendance.services import issue_member_qr_token
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant
from apps.tenants.storage import save_member_photo


@pytest.fixture
def api_client():
    return APIClient()


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
def other_gym_tenant(db):
    return GymTenant.objects.create(
        name="FitGate Kazanchis",
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


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_user(
        email="superadmin@fitgate.org",
        password="SuperAdminPassword123!",
        gym=None,
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
    )


@pytest.fixture
def member_user(db, gym_tenant):
    return User.objects.create_user(
        email="member@bolehub.com",
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )


@pytest.fixture
def active_member(db, gym_tenant, member_user):
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Abebe Bikila",
        phone="+251911001122",
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
        photo_url="/media/member_photos/abebe.webp",
    )
    # Active subscription valid for 30 days
    today = timezone.localdate()
    MemberSubscription.all_objects.create(
        gym=gym_tenant,
        member=member,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member


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


def create_test_member(gym_tenant, email, full_name, phone):
    user = User.objects.create_user(
        email=email,
        password="MemberPassword123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        must_change_password=False,
    )
    member = Member.all_objects.create(
        gym=gym_tenant,
        user=user,
        full_name=full_name,
        phone=phone,
        status=Member.STATUS_ACTIVE,
        waiver_accepted_at=timezone.now(),
        photo_url=f"/media/member_photos/{phone}.webp",
    )
    today = timezone.localdate()
    MemberSubscription.all_objects.create(
        gym=gym_tenant,
        member=member,
        start_date=today - timedelta(days=5),
        end_date=today + timedelta(days=25),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    return member


@pytest.mark.django_db
class TestQRTokenIssuanceAndVerification:
    """Tests for asymmetric RS256 token issuance, public key, and offline verification."""

    def test_public_key_endpoint_returns_rsa_key(self, api_client, gym_tenant):
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        response = api_client.get("/api/attendance/public-key/")
        assert response.status_code == 200
        assert "public_key" in response.data
        assert "BEGIN PUBLIC KEY" in response.data["public_key"]
        assert response.data["algorithm"] == "RS256"

    def test_single_line_escaped_key_signs_and_verifies(self, settings):
        """Single-line escaped RSA keys (with literal \\n escapes) sign and verify correctly."""
        priv_pem, pub_pem = generate_rsa_keypair()
        priv_oneline = priv_pem.strip().replace("\n", "\\n")
        pub_oneline = pub_pem.strip().replace("\n", "\\n")

        settings.QR_JWT_PRIVATE_KEY = priv_oneline
        settings.QR_JWT_PUBLIC_KEY = pub_oneline

        # Verify crypto getters unescape properly
        assert "\n" in get_rsa_private_key_pem()
        assert "\\n" not in get_rsa_private_key_pem()
        assert "\n" in get_rsa_public_key_pem()
        assert "\\n" not in get_rsa_public_key_pem()

        now = timezone.now()
        payload = {
            "sub": "test-member",
            "gym_id": "test-gym",
            "exp": int((now + timedelta(seconds=90)).timestamp()),
        }
        token = sign_qr_payload(payload)
        verified = verify_qr_jwt(token)
        assert verified["sub"] == "test-member"
        assert verified["gym_id"] == "test-gym"

    def test_multi_line_key_still_works(self, settings):
        """Standard multi-line PEM format still works seamlessly without corruption."""
        priv_pem, pub_pem = generate_rsa_keypair()
        assert "\n" in priv_pem

        settings.QR_JWT_PRIVATE_KEY = priv_pem
        settings.QR_JWT_PUBLIC_KEY = pub_pem

        assert get_rsa_private_key_pem() == priv_pem.strip()
        assert get_rsa_public_key_pem() == pub_pem.strip()

        now = timezone.now()
        payload = {
            "sub": "test-member-2",
            "gym_id": "test-gym-2",
            "exp": int((now + timedelta(seconds=90)).timestamp()),
        }
        token = sign_qr_payload(payload)
        verified = verify_qr_jwt(token)
        assert verified["sub"] == "test-member-2"
        assert verified["gym_id"] == "test-gym-2"

    @pytest.mark.parametrize("empty_val", [None, "", "   ", "\n\n"])
    def test_empty_key_still_raises_crypto_error(self, settings, empty_val):
        """Unset or blank RSA keys raise QRTokenCryptoError."""
        settings.QR_JWT_PRIVATE_KEY = empty_val
        settings.QR_JWT_PUBLIC_KEY = empty_val

        with pytest.raises(
            QRTokenCryptoError, match="QR_JWT_PRIVATE_KEY is not configured"
        ):
            get_rsa_private_key_pem()

        with pytest.raises(
            QRTokenCryptoError, match="QR_JWT_PUBLIC_KEY is not configured"
        ):
            get_rsa_public_key_pem()

    def test_public_key_endpoint_returns_503_still_securing_on_unconfirmed_tls(
        self, api_client, db
    ):
        """The public-key route returns 503 still_securing on a gym host whose tls_confirmed_at is null."""
        unsecured_gym = GymTenant.objects.create(
            name="FitGate Unsecured",
            subdomain="unsecured",
            tier=GymTenant.TIER_STARTER,
            status=GymTenant.STATUS_ACTIVE,
            contact_phone="+251911998877",
            location="Addis Ababa",
            tls_confirmed_at=None,
        )
        api_client.defaults["HTTP_HOST"] = f"{unsecured_gym.subdomain}.localhost"
        response = api_client.get("/api/attendance/public-key/")
        assert response.status_code == 503
        assert response.json()["detail"] == "still_securing"

    def test_member_qr_token_endpoint_issues_asymmetric_jwt(
        self, api_client, gym_tenant, member_user, active_member
    ):
        client = auth_client(api_client, member_user, gym_tenant.subdomain)
        response = client.get("/api/members/me/qr-token/")
        assert response.status_code == 200
        data = response.data
        assert "token" in data
        assert data["valid_seconds"] == 90
        assert data["member_id"] == str(active_member.id)

        # Verify offline with public key
        public_key = get_rsa_public_key_pem()
        decoded = jwt.decode(
            data["token"],
            public_key,
            algorithms=["RS256"],
            options={"require": ["exp"]},
            leeway=0,
        )
        assert decoded["sub"] == str(active_member.id)
        assert decoded["gym_id"] == str(gym_tenant.id)
        assert decoded["type"] == "qr_checkin"

    def test_frozen_clock_valid_at_89s_rejected_at_91s(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """A token scanned 89 seconds after issue succeeds THROUGH the scan endpoint, and at 91 seconds fails with token_expired."""
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        initial_time = timezone.now()

        m2 = create_test_member(
            gym_tenant, "m2_expire@bolehub.com", "Member M2", "+251911990011"
        )

        # Issue both tokens at initial_time
        with freeze_time(initial_time):
            token_89, _ = issue_member_qr_token(active_member, valid_seconds=90)
            token_91, _ = issue_member_qr_token(m2, valid_seconds=90)

        # Scanned at 89 seconds through scan endpoint -> succeeds (200)
        with freeze_time(initial_time + timedelta(seconds=89)):
            resp_89 = client.post(
                "/api/gym/attendance/scan/",
                {"token": token_89},
                format="json",
            )
            assert resp_89.status_code == 200
            assert resp_89.data["status"] == "success"

        # Scanned at 91 seconds through scan endpoint -> fails with token_expired (400)
        with freeze_time(initial_time + timedelta(seconds=91)):
            resp_91 = client.post(
                "/api/gym/attendance/scan/",
                {"token": token_91},
                format="json",
            )
            assert resp_91.status_code == 400
            assert resp_91.data["reason"] == "token_expired"

    def test_tampered_token_is_rejected(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """Tampered JWT signature or payload is rejected."""
        token_str, _ = issue_member_qr_token(active_member)
        tampered_token = token_str[:-4] + "wxyz"

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": tampered_token},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "invalid_token"

    def test_validly_signed_token_without_exp_claim_rejected(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """A validly signed RS256 token without exp claim is rejected (options={'require': ['exp']})."""
        now = timezone.now()
        payload_no_exp = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "type": "qr_checkin",
            # NOTE: "exp" claim is intentionally omitted
        }
        priv_pem = get_rsa_private_key_pem()
        token_no_exp = jwt.encode(payload_no_exp, priv_pem, algorithm="RS256")

        # 1. Direct crypto verify raises InvalidTokenError
        with pytest.raises(InvalidTokenError):
            verify_qr_jwt(token_no_exp)

        # 2. Scan endpoint rejects with 400 invalid_token
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_no_exp},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "invalid_token"

    def test_reusing_consumed_token_is_rejected_and_new_token_issued_on_valid_scan(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """
        Reusing an already-consumed token is rejected.
        A new token is issued after each valid use.
        """
        token_str, _ = issue_member_qr_token(active_member)
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        # First scan succeeds
        first_resp = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert first_resp.status_code == 200
        assert "next_token" in first_resp.data
        next_token = first_resp.data["next_token"]
        assert next_token != token_str

        # Reusing the original token fails with token_consumed
        second_resp = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert second_resp.status_code == 400
        assert second_resp.data["reason"] == "token_consumed"


@pytest.mark.django_db
class TestScanEndpointAndDuplicateHandling:
    """Tests for scan endpoint, member card results, and duplicate attempt handling."""

    def test_valid_scan_returns_member_details_and_creates_single_attendance_row(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        token_str, _ = issue_member_qr_token(active_member)
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        assert Attendance.all_objects.count() == 0

        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 200
        assert response.data["status"] == "success"
        member_data = response.data["member"]
        assert member_data["full_name"] == active_member.full_name
        assert member_data["status"] == Member.STATUS_ACTIVE

        # Photo must be a backend route path through permission-checked photo view, never Cloudinary/storage URL
        photo_url = member_data["photo_url"]
        assert photo_url.startswith(f"/api/media/member-photos/{gym_tenant.id}/")
        assert not photo_url.startswith("http://")
        assert not photo_url.startswith("https://")
        assert "cloudinary" not in photo_url

        # Exactly one Attendance row created
        assert Attendance.all_objects.count() == 1
        att = Attendance.all_objects.first()
        assert att.member == active_member
        assert att.gym == gym_tenant
        assert att.date == timezone.localdate()
        assert not att.is_override

    def test_second_scan_same_day_denied_no_second_row_notifies_staff(
        self,
        api_client,
        gym_tenant,
        reception_user,
        owner_user,
        manager_user,
        active_member,
    ):
        """
        A legitimate single scan produces exactly one Attendance row.
        A second scan the same day is denied, produces no second row, and notifies staff.
        """
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        # First scan
        token1, _ = issue_member_qr_token(active_member)
        resp1 = client.post(
            "/api/gym/attendance/scan/", {"token": token1}, format="json"
        )
        assert resp1.status_code == 200
        assert Attendance.all_objects.count() == 1
        next_token = resp1.data["next_token"]

        Notification.all_objects.filter(gym=gym_tenant).delete()

        # Second scan on the same day with the new token
        resp2 = client.post(
            "/api/gym/attendance/scan/", {"token": next_token}, format="json"
        )
        assert resp2.status_code == 400
        assert resp2.data["reason"] == "already_checked_in"

        # Produces NO second row
        assert Attendance.all_objects.count() == 1

        # Notifies staff (Owner, Manager, Reception)
        staff_notifications = Notification.all_objects.filter(gym=gym_tenant)
        assert staff_notifications.count() >= 3
        recipient_emails = {n.recipient.email for n in staff_notifications}
        assert owner_user.email in recipient_emails
        assert manager_user.email in recipient_emails
        assert reception_user.email in recipient_emails

    @pytest.mark.parametrize(
        "sub_status,expected_reason",
        [
            (MemberSubscription.STATUS_EXPIRED, "expired"),
            (MemberSubscription.STATUS_FROZEN, "frozen"),
            (MemberSubscription.STATUS_SUSPENDED, "suspended"),
        ],
    )
    def test_scan_rejected_with_distinguishable_reasons_for_inactive_subscriptions(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        sub_status,
        expected_reason,
    ):
        """Scan for member without active subscription rejected with distinguishable reason."""
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        sub.status = sub_status
        sub.save()

        now = timezone.now()
        payload = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=90)).timestamp()),
            "type": "qr_checkin",
        }
        priv_pem = get_rsa_private_key_pem()
        token_str = jwt.encode(payload, priv_pem, algorithm="RS256")
        token_hex = hash_token(token_str)

        QRToken.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            token_hash=token_hex,
            issued_at=now,
            expires_at=now + timedelta(seconds=90),
            is_active=True,
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == expected_reason
        assert Attendance.all_objects.count() == 0

    @pytest.mark.parametrize(
        "sub_status,expected_reason",
        [
            (MemberSubscription.STATUS_EXPIRED, "expired"),
            (MemberSubscription.STATUS_FROZEN, "frozen"),
            (MemberSubscription.STATUS_SUSPENDED, "suspended"),
        ],
    )
    def test_inactive_member_leaves_qr_token_unconsumed(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        sub_status,
        expected_reason,
    ):
        """An inactive member (expired/frozen/suspended) leaves the QRToken unconsumed."""
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        sub.status = sub_status
        sub.save()

        now = timezone.now()
        payload = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=90)).timestamp()),
            "type": "qr_checkin",
        }
        priv_pem = get_rsa_private_key_pem()
        token_str = jwt.encode(payload, priv_pem, algorithm="RS256")
        token_hex = hash_token(token_str)

        qr_row = QRToken.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            token_hash=token_hex,
            issued_at=now,
            expires_at=now + timedelta(seconds=90),
            is_active=True,
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == expected_reason

        qr_row.refresh_from_db()
        assert qr_row.is_active is True
        assert qr_row.used_at is None

    def test_scan_no_subscription_row_rejected_expired_token_unconsumed(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
    ):
        """Member with NO MemberSubscription row is rejected with reason 'expired' and token remains unconsumed."""
        MemberSubscription.all_objects.filter(member=active_member).delete()
        assert MemberSubscription.all_objects.filter(member=active_member).count() == 0

        now = timezone.now()
        payload = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=90)).timestamp()),
            "type": "qr_checkin",
        }
        priv_pem = get_rsa_private_key_pem()
        token_str = jwt.encode(payload, priv_pem, algorithm="RS256")
        token_hex = hash_token(token_str)

        qr_token = QRToken.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            token_hash=token_hex,
            issued_at=now,
            expires_at=now + timedelta(seconds=90),
            is_active=True,
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "expired"
        assert Attendance.all_objects.count() == 0

        qr_token.refresh_from_db()
        assert qr_token.is_active is True
        assert qr_token.used_at is None

    @pytest.mark.parametrize(
        "inactive_scenario,expected_reason",
        [
            ("member_suspended", "suspended"),
            ("sub_expired", "expired"),
            ("sub_frozen", "frozen"),
            ("sub_suspended", "suspended"),
        ],
    )
    def test_deactivated_token_on_inactive_member_returns_inactive_status_not_token_consumed(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        inactive_scenario,
        expected_reason,
    ):
        """
        Check order: member and subscription status checks execute BEFORE token is_active/used_at check.
        A frozen/suspended/expired member whose token was deactivated sees frozen/suspended/expired,
        NOT token_consumed. The token remains unconsumed.
        """
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        if inactive_scenario == "member_suspended":
            active_member.status = Member.STATUS_SUSPENDED
            active_member.save(update_fields=["status"])
        elif inactive_scenario == "sub_expired":
            sub.status = MemberSubscription.STATUS_EXPIRED
            sub.save(update_fields=["status"])
        elif inactive_scenario == "sub_frozen":
            sub.status = MemberSubscription.STATUS_FROZEN
            sub.save(update_fields=["status"])
        elif inactive_scenario == "sub_suspended":
            sub.status = MemberSubscription.STATUS_SUSPENDED
            sub.save(update_fields=["status"])

        now = timezone.now()
        payload = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=90)).timestamp()),
            "type": "qr_checkin",
        }
        priv_pem = get_rsa_private_key_pem()
        token_str = jwt.encode(payload, priv_pem, algorithm="RS256")
        token_hex = hash_token(token_str)

        # Deactivated token (is_active=False)
        qr_token = QRToken.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            token_hash=token_hex,
            issued_at=now,
            expires_at=now + timedelta(seconds=90),
            is_active=False,
            used_at=None,
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == expected_reason
        assert Attendance.all_objects.count() == 0

        qr_token.refresh_from_db()
        assert qr_token.used_at is None

    def test_real_replay_with_active_member_returns_token_consumed(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
    ):
        """
        A real replay (token consumed with used_at set, while member is active with active subscription)
        returns token_consumed.
        """
        now = timezone.now()
        payload = {
            "sub": str(active_member.id),
            "member_id": str(active_member.id),
            "gym_id": str(gym_tenant.id),
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(seconds=90)).timestamp()),
            "type": "qr_checkin",
        }
        priv_pem = get_rsa_private_key_pem()
        token_str = jwt.encode(payload, priv_pem, algorithm="RS256")
        token_hex = hash_token(token_str)

        QRToken.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            token_hash=token_hex,
            issued_at=now - timedelta(seconds=10),
            expires_at=now + timedelta(seconds=80),
            is_active=False,
            used_at=now - timedelta(seconds=5),
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "token_consumed"
        assert Attendance.all_objects.count() == 0

    def test_scan_returned_photo_url_access_control(
        self,
        api_client,
        gym_tenant,
        other_gym_tenant,
        reception_user,
        active_member,
        tmp_path,
        settings,
    ):
        """
        Photo security test against the REAL URL returned by a scan:
        - Staff of that gym -> 200 (or local-storage equivalent)
        - Staff of another gym -> 403/404
        - Anonymous -> 401
        """
        settings.MEDIA_ROOT = tmp_path
        img = Image.new("RGB", (100, 100), color=(0, 255, 0))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        upload = SimpleUploadedFile(
            "avatar.png", buf.getvalue(), content_type="image/png"
        )
        rel_path = save_member_photo(gym_tenant.id, upload)
        active_member.photo_url = rel_path
        active_member.save(update_fields=["photo_url"])

        token_str, _ = issue_member_qr_token(active_member)
        scan_client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = scan_client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 200
        returned_photo_url = response.data["member"]["photo_url"]
        assert returned_photo_url.startswith(
            f"/api/media/member-photos/{gym_tenant.id}/"
        )

        # 1. Staff of that gym -> 200
        staff_client = auth_client(APIClient(), reception_user, gym_tenant.subdomain)
        resp_staff = staff_client.get(returned_photo_url)
        assert resp_staff.status_code == 200
        assert resp_staff["Content-Type"] == "image/webp"

        # 2. Staff of another gym -> 403 or 404
        other_staff = User.objects.create_user(
            email="other_reception@kazanchis.com",
            password="OtherReceptionPassword123!",
            gym=other_gym_tenant,
            role=User.ROLE_RECEPTION,
            must_change_password=False,
        )
        other_client = auth_client(APIClient(), other_staff, other_gym_tenant.subdomain)
        resp_other = other_client.get(returned_photo_url)
        assert resp_other.status_code in (403, 404)

        # 3. Anonymous -> 401
        anon_client = APIClient()
        resp_anon = anon_client.get(
            returned_photo_url, HTTP_HOST=f"{gym_tenant.subdomain}.localhost"
        )
        assert resp_anon.status_code == 401

    def test_gym_mismatch_leaves_qr_token_unconsumed(
        self, api_client, gym_tenant, other_gym_tenant, active_member
    ):
        """gym_mismatch leaves the QRToken row unconsumed (assert is_active and used_at)."""
        token_str, qr_row = issue_member_qr_token(active_member)
        assert qr_row.is_active is True
        assert qr_row.used_at is None

        other_staff = User.objects.create_user(
            email="reception@kazanchis.com",
            password="StaffPassword123!",
            gym=other_gym_tenant,
            role=User.ROLE_RECEPTION,
            must_change_password=False,
        )
        client = auth_client(api_client, other_staff, other_gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": token_str},
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == "gym_mismatch"

        qr_row.refresh_from_db()
        assert qr_row.is_active is True
        assert qr_row.used_at is None

    def test_scan_simulated_race_integrity_error_returns_already_checked_in(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        owner_user,
        manager_user,
    ):
        """A simulated race / IntegrityError on scan returns already_checked_in, notifies staff, and leaves token unconsumed."""
        token_str, qr_row = issue_member_qr_token(active_member)
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        with patch.object(
            Attendance.all_objects,
            "create",
            side_effect=IntegrityError(
                "duplicate key value violates unique constraint"
            ),
        ):
            response = client.post(
                "/api/gym/attendance/scan/",
                {"token": token_str},
                format="json",
            )

        assert response.status_code == 400
        assert response.data["reason"] == "already_checked_in"
        assert "has already checked in today" in response.data["detail"]

        # Token was rolled back and remains unconsumed
        qr_row.refresh_from_db()
        assert qr_row.is_active is True
        assert qr_row.used_at is None

        # Staff were notified of duplicate attempt
        notifications = Notification.all_objects.filter(gym=gym_tenant)
        assert notifications.count() >= 3

    def test_trainer_and_super_admin_get_403_on_scan(
        self, api_client, gym_tenant, trainer_user, super_admin_user, active_member
    ):
        """Trainer and Super Admin (at a gym host) get 403 on scan."""
        token_str, _ = issue_member_qr_token(active_member)

        # Trainer receives 403
        client_trainer = auth_client(api_client, trainer_user, gym_tenant.subdomain)
        resp_trainer = client_trainer.post(
            "/api/gym/attendance/scan/", {"token": token_str}, format="json"
        )
        assert resp_trainer.status_code == 403

        # Super Admin at gym host receives 403 via CanManageAttendance
        client_sa = APIClient()
        client_sa.force_authenticate(user=super_admin_user)
        client_sa.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"
        resp_sa = client_sa.post(
            "/api/gym/attendance/scan/", {"token": token_str}, format="json"
        )
        assert resp_sa.status_code == 403

        assert Attendance.all_objects.count() == 0

    def test_owner_manager_reception_each_allowed_on_scan(
        self, api_client, gym_tenant, owner_user, manager_user, reception_user
    ):
        """Owner, Manager and Reception are each allowed on scan (a real 200)."""
        m_owner = create_test_member(
            gym_tenant, "scan_owner@bolehub.com", "Scan Owner", "+251911333333"
        )
        m_mgr = create_test_member(
            gym_tenant, "scan_mgr@bolehub.com", "Scan Mgr", "+251911444444"
        )
        m_rec = create_test_member(
            gym_tenant, "scan_rec@bolehub.com", "Scan Rec", "+251911555555"
        )

        t_owner, _ = issue_member_qr_token(m_owner)
        t_mgr, _ = issue_member_qr_token(m_mgr)
        t_rec, _ = issue_member_qr_token(m_rec)

        # 1. Owner scan succeeds (200)
        c_owner = auth_client(api_client, owner_user, gym_tenant.subdomain)
        r_owner = c_owner.post(
            "/api/gym/attendance/scan/", {"token": t_owner}, format="json"
        )
        assert r_owner.status_code == 200
        assert r_owner.data["status"] == "success"

        # 2. Manager scan succeeds (200)
        c_mgr = auth_client(api_client, manager_user, gym_tenant.subdomain)
        r_mgr = c_mgr.post("/api/gym/attendance/scan/", {"token": t_mgr}, format="json")
        assert r_mgr.status_code == 200
        assert r_mgr.data["status"] == "success"

        # 3. Reception scan succeeds (200)
        c_rec = auth_client(api_client, reception_user, gym_tenant.subdomain)
        r_rec = c_rec.post("/api/gym/attendance/scan/", {"token": t_rec}, format="json")
        assert r_rec.status_code == 200
        assert r_rec.data["status"] == "success"

        assert Attendance.all_objects.count() == 3

    def test_must_change_password_blocked_on_scan_and_member_qr_endpoint(
        self, api_client, gym_tenant, active_member
    ):
        """A user with must_change_password=True is blocked on scan and the member QR endpoint."""
        token_str, _ = issue_member_qr_token(active_member)

        # 1. Staff with must_change_password=True blocked on scan
        staff_locked = User.objects.create_user(
            email="staff_locked@bolehub.com",
            password="StaffPassword123!",
            gym=gym_tenant,
            role=User.ROLE_RECEPTION,
            must_change_password=True,
        )
        c_staff = auth_client(api_client, staff_locked, gym_tenant.subdomain)
        r_staff = c_staff.post(
            "/api/gym/attendance/scan/", {"token": token_str}, format="json"
        )
        assert r_staff.status_code == 403
        assert r_staff.data["detail"] == "password_change_required"

        # 2. Member with must_change_password=True blocked on member QR endpoint
        member_locked = User.objects.create_user(
            email="member_locked@bolehub.com",
            password="MemberPassword123!",
            gym=gym_tenant,
            role=User.ROLE_MEMBER,
            must_change_password=True,
        )
        Member.all_objects.create(
            gym=gym_tenant,
            user=member_locked,
            full_name="Locked Member",
            phone="+251911887766",
            status=Member.STATUS_ACTIVE,
            waiver_accepted_at=timezone.now(),
        )
        c_member = auth_client(api_client, member_locked, gym_tenant.subdomain)
        r_member = c_member.get("/api/members/me/qr-token/")
        assert r_member.status_code == 403
        assert r_member.data["detail"] == "password_change_required"

    def test_anonymous_access_to_all_routes(
        self, api_client, gym_tenant, active_member
    ):
        """
        Verify anonymous access behavior across all routes:
        - Public key endpoint is AllowAny (200 OK)
        - All authenticated/staff routes return 401 Unauthorized
        """
        api_client.credentials()  # Unauthenticated
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        # 1. Public key route is AllowAny
        pub_resp = api_client.get("/api/attendance/public-key/")
        assert pub_resp.status_code == 200
        assert "BEGIN PUBLIC KEY" in pub_resp.data["public_key"]

        # 2. Protected routes require authentication (401)
        protected_routes = [
            ("get", "/api/members/me/qr-token/", {}),
            ("post", "/api/gym/attendance/scan/", {"token": "dummy"}),
            (
                "post",
                "/api/gym/attendance/manual-override/",
                {"member_id": str(active_member.id), "reason": "reason"},
            ),
            ("get", f"/api/gym/members/{active_member.id}/attendance/", {}),
            ("get", "/api/members/me/attendance/", {}),
        ]
        for method, path, payload in protected_routes:
            if method == "get":
                resp = api_client.get(path)
            else:
                resp = api_client.post(path, payload, format="json")
            assert (
                resp.status_code == 401
            ), f"Expected 401 for anonymous access to {path}, got {resp.status_code}"
