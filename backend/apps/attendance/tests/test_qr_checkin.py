"""
Tests for Sprint 8: QR Check-in (GATE).

Covers:
1. Token issuance & rotation (90s window, asymmetric RS256).
2. Public key endpoint for offline verification (GET /api/attendance/public-key/).
3. Valid at 89s, rejected at 91s (tested with frozen clock via freezegun).
4. Tampered token rejected.
5. Reusing already-consumed token rejected (single-use).
6. Next token issued after valid scan.
7. Scan rejected with distinguishable reasons for inactive subscription (expired vs frozen vs suspended).
8. Scan success returns photo, name, status, attendance record, and replacement token.
9. Exactly one Attendance row created; duplicate scan same day denied, produces no second row, notifies staff.
10. Manual override by Reception: requires active subscription + reason; refused for expired/frozen/suspended;
    creates exactly one Attendance row (is_override=True) and an AuditLog entry.
11. Attendance calendar log: returns ✓/✗ per day for date range, days outside period are blank.
12. Cross-tenant isolation: gym A token scanned at gym B rejected with gym_mismatch.
"""

import uuid
from datetime import date, timedelta

import jwt
import pytest
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, Notification, User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.crypto import (
    get_rsa_private_key_pem,
    get_rsa_public_key_pem,
    hash_token,
    verify_qr_jwt,
)
from apps.attendance.models import Attendance, QRToken
from apps.attendance.services import issue_member_qr_token
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant


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
            leeway=0,
        )
        assert decoded["sub"] == str(active_member.id)
        assert decoded["gym_id"] == str(gym_tenant.id)
        assert decoded["type"] == "qr_checkin"

    def test_frozen_clock_valid_at_89s_rejected_at_91s(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """A token is valid at 89 seconds after issue and rejected at 91 — tested with a frozen clock."""
        initial_time = timezone.now()
        with freeze_time(initial_time):
            token_str, qr_record = issue_member_qr_token(
                active_member, valid_seconds=90
            )

        # Test at 89 seconds: valid
        with freeze_time(initial_time + timedelta(seconds=89)):
            payload = verify_qr_jwt(token_str)
            assert payload["sub"] == str(active_member.id)

        # Test at 91 seconds: rejected
        with freeze_time(initial_time + timedelta(seconds=91)):
            client = auth_client(api_client, reception_user, gym_tenant.subdomain)
            response = client.post(
                "/api/gym/attendance/scan/",
                {"token": token_str},
                format="json",
            )
            assert response.status_code == 400
            assert response.data["reason"] == "token_expired"

    def test_tampered_token_is_rejected(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        """Tampered JWT signature or payload is rejected."""
        token_str, _ = issue_member_qr_token(active_member)
        # Tamper token by mutating the signature suffix
        tampered_token = token_str[:-4] + "wxyz"

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/scan/",
            {"token": tampered_token},
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
        # Shows member's photo, name and status on success
        member_data = response.data["member"]
        assert member_data["full_name"] == active_member.full_name
        assert member_data["photo_url"] == active_member.photo_url
        assert member_data["status"] == Member.STATUS_ACTIVE

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

        # Ensure no notifications prior to second scan
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

        # Generate a signed token (bypass service subscription check to simulate scanning pre-issued token)
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

    def test_cross_tenant_scan_rejected(
        self, api_client, gym_tenant, other_gym_tenant, reception_user, active_member
    ):
        """QR token issued for gym A scanned at gym B is rejected."""
        token_str, _ = issue_member_qr_token(active_member)

        # Other gym reception staff
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
        assert Attendance.all_objects.count() == 0


@pytest.mark.django_db
class TestManualOverride:
    """Tests for manual override by Reception / staff."""

    def test_manual_override_success_creates_attendance_and_audit_log(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        assert Attendance.all_objects.count() == 0
        assert AuditLog.all_objects.count() == 0

        payload = {
            "member_id": str(active_member.id),
            "reason": "Member phone battery died at entrance",
        }
        response = client.post(
            "/api/gym/attendance/manual-override/",
            payload,
            format="json",
        )
        assert response.status_code == 201
        assert response.data["status"] == "success"
        assert response.data["attendance"]["is_override"] is True
        assert (
            response.data["attendance"]["override_reason"]
            == "Member phone battery died at entrance"
        )

        # Exactly one Attendance row created
        assert Attendance.all_objects.count() == 1
        att = Attendance.all_objects.first()
        assert att.member == active_member
        assert att.is_override is True
        assert att.override_reason == "Member phone battery died at entrance"
        assert att.recorded_by == reception_user

        # AuditLog entry created
        audit_entries = AuditLog.all_objects.filter(
            action_type="attendance_manual_override",
            affected_record_type="Attendance",
            affected_record_id=str(att.id),
        )
        assert audit_entries.count() == 1
        entry = audit_entries.first()
        assert entry.actor == reception_user
        assert entry.gym == gym_tenant
        assert entry.metadata["reason"] == "Member phone battery died at entrance"

    def test_manual_override_requires_non_empty_reason(
        self, api_client, gym_tenant, reception_user, active_member
    ):
        client = auth_client(api_client, reception_user, gym_tenant.subdomain)

        response = client.post(
            "/api/gym/attendance/manual-override/",
            {"member_id": str(active_member.id), "reason": "   "},
            format="json",
        )
        assert response.status_code == 400
        assert Attendance.all_objects.count() == 0

    @pytest.mark.parametrize(
        "sub_status,expected_reason",
        [
            (MemberSubscription.STATUS_EXPIRED, "expired"),
            (MemberSubscription.STATUS_FROZEN, "frozen"),
            (MemberSubscription.STATUS_SUSPENDED, "suspended"),
        ],
    )
    def test_manual_override_refused_for_inactive_member(
        self,
        api_client,
        gym_tenant,
        reception_user,
        active_member,
        sub_status,
        expected_reason,
    ):
        """Manual override is refused for expired, frozen or suspended members."""
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        sub.status = sub_status
        sub.save()

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        response = client.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(active_member.id),
                "reason": "Testing inactive member override attempt",
            },
            format="json",
        )
        assert response.status_code == 400
        assert response.data["reason"] == expected_reason
        assert Attendance.all_objects.count() == 0
        assert AuditLog.all_objects.count() == 0

    def test_member_role_denied_scan_and_manual_override(
        self, api_client, gym_tenant, member_user, active_member
    ):
        """Member role receives 403 Forbidden on staff scan and manual override routes."""
        client = auth_client(api_client, member_user, gym_tenant.subdomain)

        # 1. Member cannot call scan
        scan_resp = client.post(
            "/api/gym/attendance/scan/",
            {"token": "dummy.token.string"},
            format="json",
        )
        assert scan_resp.status_code == 403

        # 2. Member cannot call manual override
        override_resp = client.post(
            "/api/gym/attendance/manual-override/",
            {
                "member_id": str(active_member.id),
                "reason": "Self override attempt",
            },
            format="json",
        )
        assert override_resp.status_code == 403
        assert Attendance.all_objects.count() == 0

    def test_anonymous_access_to_all_new_routes_including_public_key(
        self, api_client, gym_tenant, active_member
    ):
        """
        Verify anonymous access behavior across all new routes in Sprint 8:
        - Public key endpoint is AllowAny and accessible anonymously (200 OK)
        - All authenticated/staff routes return 401 Unauthorized
        """
        api_client.credentials()  # Unauthenticated
        api_client.defaults["HTTP_HOST"] = f"{gym_tenant.subdomain}.localhost"

        # 1. Public key routes are AllowAny
        for path in ("/api/attendance/public-key/", "/api/gym/attendance/public-key/"):
            pub_resp = api_client.get(path)
            assert pub_resp.status_code == 200
            assert "BEGIN PUBLIC KEY" in pub_resp.data["public_key"]

        # 2. Protected routes require authentication (401)
        protected_routes = [
            ("get", "/api/members/me/qr-token/", {}),
            ("get", "/api/members/me/qr/", {}),
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


@pytest.mark.django_db
class TestAttendanceCalendarLog:
    """Tests for attendance log endpoint (✓/✗ per day for date range)."""

    def test_attendance_log_derives_correct_symbols_and_blanks(
        self, api_client, gym_tenant, reception_user, member_user, active_member
    ):
        """
        Attendance rows exist only for actual check-ins.
        An attendance-log endpoint returns ✓/✗ per day for a date range,
        derived from check-ins and the subscription period (days outside the period are blank).
        """
        # Member subscription period: Oct 10 to Oct 20
        sub = MemberSubscription.all_objects.filter(member=active_member).first()
        sub.start_date = date(2026, 10, 10)
        sub.end_date = date(2026, 10, 20)
        sub.save()

        # Check-ins exist on Oct 11 and Oct 15 ONLY
        Attendance.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            date=date(2026, 10, 11),
            status=Attendance.STATUS_CHECKED_IN,
        )
        Attendance.all_objects.create(
            gym=gym_tenant,
            member=active_member,
            date=date(2026, 10, 15),
            status=Attendance.STATUS_CHECKED_IN,
        )

        client = auth_client(api_client, reception_user, gym_tenant.subdomain)
        # Request range: Oct 8 to Oct 16
        response = client.get(
            f"/api/gym/members/{active_member.id}/attendance/?start_date=2026-10-08&end_date=2026-10-16"
        )
        assert response.status_code == 200
        days = response.data["days"]
        days_by_date = {d["date"]: d for d in days}

        # Oct 8 & Oct 9: outside subscription period -> blank ("")
        assert days_by_date["2026-10-08"]["status"] == "blank"
        assert days_by_date["2026-10-08"]["symbol"] == ""
        assert days_by_date["2026-10-09"]["status"] == "blank"
        assert days_by_date["2026-10-09"]["symbol"] == ""

        # Oct 10: in subscription, no check-in -> absent (✗)
        assert days_by_date["2026-10-10"]["status"] == "absent"
        assert days_by_date["2026-10-10"]["symbol"] == "✗"

        # Oct 11: in subscription, checked in -> present (✓)
        assert days_by_date["2026-10-11"]["status"] == "present"
        assert days_by_date["2026-10-11"]["symbol"] == "✓"

        # Oct 12: in subscription, no check-in -> absent (✗)
        assert days_by_date["2026-10-12"]["status"] == "absent"
        assert days_by_date["2026-10-12"]["symbol"] == "✗"

        # Oct 15: checked in -> present (✓)
        assert days_by_date["2026-10-15"]["status"] == "present"
        assert days_by_date["2026-10-15"]["symbol"] == "✓"

    def test_member_self_attendance_log(
        self, api_client, gym_tenant, member_user, active_member
    ):
        """Member can fetch their own attendance calendar log."""
        client = auth_client(api_client, member_user, gym_tenant.subdomain)
        response = client.get("/api/members/me/attendance/")
        assert response.status_code == 200
        assert "days" in response.data
        assert response.data["member_id"] == str(active_member.id)
