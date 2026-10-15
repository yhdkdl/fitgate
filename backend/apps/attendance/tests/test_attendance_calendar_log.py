"""
Tests for daily attendance calendar log (✓/✗ per day for date range).
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.memberships.models import Member, MemberSubscription
from apps.tenants.models import GymTenant


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
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bolehub.com",
        password="ReceptionPassword123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
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
class TestAttendanceCalendarLog:
    """Tests for attendance log endpoint (✓/✗ per day for date range)."""

    def test_attendance_log_derives_correct_symbols_and_blanks(
        self, api_client, gym_tenant, reception_user, active_member
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
