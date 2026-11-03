import concurrent.futures
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.models import Attendance
from apps.classes.constants import (
    BOOKING_STATUS_BOOKED,
    BOOKING_STATUS_CANCELLED,
    CLASS_TITLE_YOGA,
    CLASS_TITLE_ZUMBA,
    SESSION_STATUS_SCHEDULED,
)
from apps.classes.models import ClassBooking, ClassSession
from apps.classes.services import (
    book_class_session,
    cancel_class_booking,
    create_class_sessions,
    mark_class_attendance,
)
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.memberships.services import update_member_status
from apps.tenants.models import GymConfig, GymTenant
from apps.trainers.models import Trainer


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def growth_gym(db):
    gym = GymTenant.objects.create(
        name="FitGate Growth Bole",
        subdomain="growth-bole",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251911223344",
        location="Bole, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": True,
            "has_group_classes": True,
        },
    )
    return gym


@pytest.fixture
def starter_gym(db):
    gym = GymTenant.objects.create(
        name="FitGate Starter Piassa",
        subdomain="starter-piassa",
        tier=GymTenant.TIER_STARTER,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251922334455",
        location="Piassa, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": False,
            "has_group_classes": False,
        },
    )
    return gym


@pytest.fixture
def other_gym(db):
    gym = GymTenant.objects.create(
        name="FitGate Other Kazanchis",
        subdomain="other-kazanchis",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        contact_phone="+251933445566",
        location="Kazanchis, Addis Ababa",
        tls_confirmed_at=timezone.now(),
    )
    GymConfig.objects.update_or_create(
        gym=gym,
        defaults={
            "has_trainer_module": True,
            "has_group_classes": True,
        },
    )
    return gym


def create_user(gym, role, email, full_name=None):
    user = User.objects.create_user(
        email=email,
        password="ValidPassword123!",
        role=role,
        gym=gym,
        full_name=full_name or f"Test {role.capitalize()}",
        is_active=True,
    )
    user.force_password_change = False
    user.must_change_password = False
    user.save()
    return user


def auth_client(client, user, gym=None):
    tokens = get_tokens_for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
    if gym:
        client.defaults["HTTP_HOST"] = f"{gym.subdomain}.localhost"
    else:
        client.defaults["HTTP_HOST"] = "localhost"
    return client


def make_member(gym, full_name, email, phone, status="active"):
    user = create_user(gym, User.ROLE_MEMBER, email, full_name=full_name)
    member = Member.all_objects.create(
        gym=gym,
        user=user,
        full_name=full_name,
        phone=phone,
        gender="male",
        date_of_birth="1995-05-15",
        waiver_accepted_at=timezone.now(),
    )
    plan = MembershipPlan.all_objects.create(
        gym=gym,
        name=f"Standard Monthly {phone}",
        duration_value=1,
        duration_unit="months",
        price_etb=1500,
        is_active=True,
    )

    today = timezone.localdate()
    if status == "active":
        sub = MemberSubscription.all_objects.create(
            gym=gym,
            member=member,
            plan=plan,
            start_date=today - timedelta(days=5),
            end_date=today + timedelta(days=25),
            status=MemberSubscription.STATUS_ACTIVE,
        )
    elif status == "expired":
        sub = MemberSubscription.all_objects.create(
            gym=gym,
            member=member,
            plan=plan,
            start_date=today - timedelta(days=40),
            end_date=today - timedelta(days=10),
            status=MemberSubscription.STATUS_EXPIRED,
        )
    elif status == "frozen":
        sub = MemberSubscription.all_objects.create(
            gym=gym,
            member=member,
            plan=plan,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            status=MemberSubscription.STATUS_FROZEN,
        )
    elif status == "suspended":
        sub = MemberSubscription.all_objects.create(
            gym=gym,
            member=member,
            plan=plan,
            start_date=today - timedelta(days=10),
            end_date=today + timedelta(days=20),
            status=MemberSubscription.STATUS_SUSPENDED,
        )
    else:  # pending (no subscription)
        sub = None

    if sub:
        update_member_status(member)
    member.refresh_from_db()
    return member


def make_trainer(gym, full_name, email):
    user = create_user(gym, User.ROLE_TRAINER, email, full_name=full_name)
    trainer = Trainer.all_objects.filter(user=user).first()
    if not trainer:
        trainer = Trainer.all_objects.create(gym=gym, user=user)
    return trainer


@pytest.mark.django_db(transaction=True)
class TestClassesCapacityAndConcurrency:
    def test_capacity_boundary(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel@growth.com")
        start_time = timezone.now() + timedelta(days=2)

        sessions = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=start_time,
            duration_minutes=60,
            capacity=2,
            repeat_weeks=1,
        )
        session = sessions[0]

        m1 = make_member(growth_gym, "Member One", "m1@growth.com", "+251911000001")
        m2 = make_member(growth_gym, "Member Two", "m2@growth.com", "+251911000002")
        m3 = make_member(growth_gym, "Member Three", "m3@growth.com", "+251911000003")

        # Member 1 books (boundary: 1 of 2)
        b1 = book_class_session(growth_gym, session.id, m1)
        assert b1.status == BOOKING_STATUS_BOOKED
        assert session.booked_count == 1
        assert session.spots_remaining == 1

        # Member 2 books (boundary: 2 of 2 - full)
        b2 = book_class_session(growth_gym, session.id, m2)
        assert b2.status == BOOKING_STATUS_BOOKED
        assert session.booked_count == 2
        assert session.spots_remaining == 0
        assert session.is_full is True

        # Member 3 attempts to book -> rejected
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, m3)
        assert "Class is full" in str(exc.value)

    def test_simultaneous_booking_row_locking(self, growth_gym):
        """Simultaneous bookings at the boundary: exactly 1 succeeds when 1 spot remains."""
        trainer = make_trainer(growth_gym, "Coach Abel", "abel2@growth.com")
        start_time = timezone.now() + timedelta(days=2)

        sessions = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_ZUMBA,
            other_title="",
            trainer=trainer,
            start_time=start_time,
            duration_minutes=45,
            capacity=1,
            repeat_weeks=1,
        )
        session = sessions[0]

        m1 = make_member(
            growth_gym, "Concurrent Member 1", "c1@growth.com", "+251911000011"
        )
        m2 = make_member(
            growth_gym, "Concurrent Member 2", "c2@growth.com", "+251911000012"
        )

        results = []

        def try_book(member):
            connection.close()  # fresh DB connection per thread
            try:
                b = book_class_session(growth_gym, session.id, member)
                return ("success", b.id)
            except Exception as e:
                return ("error", str(e))
            finally:
                connection.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(try_book, m1)
            f2 = executor.submit(try_book, m2)
            results = [f1.result(), f2.result()]

        statuses = [r[0] for r in results]
        assert "success" in statuses
        assert "error" in statuses
        assert (
            ClassBooking.all_objects.filter(
                session=session, status=BOOKING_STATUS_BOOKED
            ).count()
            == 1
        )


@pytest.mark.django_db
class TestBookingRulesAndOverlaps:
    def test_one_booking_per_member(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel3@growth.com")
        start_time = timezone.now() + timedelta(days=1)

        sessions = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=start_time,
            duration_minutes=60,
            capacity=10,
        )
        session = sessions[0]
        member = make_member(
            growth_gym, "Dup Member", "dup@growth.com", "+251911000021"
        )

        book_class_session(growth_gym, session.id, member)

        # Attempt to book again
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, member)
        assert "already" in str(exc.value).lower()

    def test_trainer_overlapping_sessions_rejected(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel4@growth.com")
        start_time = timezone.now() + timedelta(days=3)

        # Session 1: 10:00 - 11:00 (duration 60)
        create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=start_time,
            duration_minutes=60,
            capacity=10,
        )

        # Session 2 overlap: 10:30 - 11:30 (starts before session 1 ends)
        overlap_start = start_time + timedelta(minutes=30)
        with pytest.raises(Exception) as exc:
            create_class_sessions(
                gym=growth_gym,
                title=CLASS_TITLE_ZUMBA,
                other_title="",
                trainer=trainer,
                start_time=overlap_start,
                duration_minutes=60,
                capacity=10,
            )
        assert "Trainer is already scheduled" in str(exc.value)

    def test_member_overlapping_sessions_rejected(self, growth_gym):
        t1 = make_trainer(growth_gym, "Coach One", "t1@growth.com")
        t2 = make_trainer(growth_gym, "Coach Two", "t2@growth.com")
        start_time = timezone.now() + timedelta(days=2)

        s1 = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=t1,
            start_time=start_time,
            duration_minutes=60,
            capacity=10,
        )[0]

        s2 = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_ZUMBA,
            other_title="",
            trainer=t2,
            start_time=start_time + timedelta(minutes=30),  # overlaps with s1
            duration_minutes=60,
            capacity=10,
        )[0]

        member = make_member(
            growth_gym, "Overlap Member", "overlap@growth.com", "+251911000031"
        )

        # Book s1
        book_class_session(growth_gym, s1.id, member)

        # Try to book overlapping s2
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, s2.id, member)
        assert "overlaps with this class" in str(exc.value)


@pytest.mark.django_db
class TestMemberEligibility:
    def test_member_status_eligibility(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel5@growth.com")
        session = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            capacity=10,
        )[0]

        m_active = make_member(
            growth_gym,
            "Active Member",
            "active@growth.com",
            "+251911000041",
            status="active",
        )
        m_expired = make_member(
            growth_gym,
            "Expired Member",
            "expired@growth.com",
            "+251911000042",
            status="expired",
        )
        m_frozen = make_member(
            growth_gym,
            "Frozen Member",
            "frozen@growth.com",
            "+251911000043",
            status="frozen",
        )
        m_suspended = make_member(
            growth_gym,
            "Suspended Member",
            "suspended@growth.com",
            "+251911000044",
            status="suspended",
        )
        m_pending = make_member(
            growth_gym,
            "Pending Member",
            "pending@growth.com",
            "+251911000045",
            status="pending",
        )

        # Active succeeds
        b = book_class_session(growth_gym, session.id, m_active)
        assert b.status == BOOKING_STATUS_BOOKED

        # Expired fails
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, m_expired)
        assert "not active" in str(exc.value).lower()
        assert "expired" in str(exc.value).lower()

        # Frozen fails
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, m_frozen)
        assert "not active" in str(exc.value).lower()
        assert "frozen" in str(exc.value).lower()

        # Suspended fails
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, m_suspended)
        assert "not active" in str(exc.value).lower()
        assert "suspended" in str(exc.value).lower()

        # Pending fails
        with pytest.raises(Exception) as exc:
            book_class_session(growth_gym, session.id, m_pending)
        assert "not active" in str(exc.value).lower()
        assert "pending" in str(exc.value).lower()


@pytest.mark.django_db
class TestTenancyAndRolePermissions:
    def test_plan_gate_starter_refused_growth_allowed(
        self, api_client, starter_gym, growth_gym
    ):
        # Starter gym owner
        starter_owner = create_user(starter_gym, User.ROLE_OWNER, "owner@starter.com")
        auth_client(api_client, starter_owner, starter_gym)

        res = api_client.get("/api/gym/classes/")
        assert res.status_code == 403
        assert "Group classes are not enabled" in str(res.data)

        # Growth gym owner
        growth_owner = create_user(growth_gym, User.ROLE_OWNER, "owner@growth.com")
        auth_client(api_client, growth_owner, growth_gym)

        res_growth = api_client.get("/api/gym/classes/")
        assert res_growth.status_code == 200

    def test_super_admin_refused(self, api_client, growth_gym):
        sa = User.objects.create_user(
            email="superadmin@platform.com",
            password="SuperPassword123!",
            role=User.ROLE_SUPER_ADMIN,
            gym=None,
            is_active=True,
        )
        sa.must_change_password = False
        sa.force_password_change = False
        sa.save()
        auth_client(api_client, sa, growth_gym)

        res = api_client.get("/api/gym/classes/")
        assert res.status_code in [401, 403]

    def test_cross_tenant_refused(self, api_client, growth_gym, other_gym):
        other_owner = create_user(other_gym, User.ROLE_OWNER, "owner@other.com")
        auth_client(api_client, other_owner, growth_gym)  # Acting on growth_gym

        res = api_client.get("/api/gym/classes/")
        assert res.status_code in [401, 403]

    def test_member_cannot_manage_or_view_roster(self, api_client, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel6@growth.com")
        session = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=timezone.now() + timedelta(days=2),
            duration_minutes=60,
            capacity=10,
        )[0]

        member = make_member(
            growth_gym, "Regular Member", "reg@growth.com", "+251911000051"
        )
        auth_client(api_client, member.user, growth_gym)

        # Member cannot create session
        res_create = api_client.post(
            "/api/gym/classes/",
            {
                "title": CLASS_TITLE_YOGA,
                "trainer_id": str(trainer.id),
                "start_time": (timezone.now() + timedelta(days=3)).isoformat(),
                "duration_minutes": 60,
                "capacity": 10,
            },
            format="json",
        )
        assert res_create.status_code == 403

        # Member cannot view roster
        res_roster = api_client.get(f"/api/gym/classes/{session.id}/roster/")
        assert res_roster.status_code == 403

        # Member cannot cancel session
        res_cancel = api_client.post(f"/api/gym/classes/{session.id}/cancel/")
        assert res_cancel.status_code == 403


@pytest.mark.django_db
class TestClassAttendanceAndCancellation:
    def test_class_attendance_creates_no_daily_attendance_row(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel7@growth.com")
        # Class that started 10 minutes ago
        start_time = timezone.now() - timedelta(minutes=10)
        session = ClassSession.objects.create(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            trainer=trainer,
            start_time=start_time,
            duration_minutes=60,
            end_time=start_time + timedelta(minutes=60),
            capacity=10,
            status=SESSION_STATUS_SCHEDULED,
        )

        member = make_member(
            growth_gym, "Class Member", "class_m@growth.com", "+251911000061"
        )
        ClassBooking.objects.create(
            gym=growth_gym,
            session=session,
            member=member,
            status=BOOKING_STATUS_BOOKED,
        )

        # Ensure 0 attendance rows initially
        assert Attendance.objects.count() == 0
        assert Attendance.all_objects.count() == 0

        # Trainer marks attendance
        owner_user = create_user(growth_gym, User.ROLE_OWNER, "owner_att@growth.com")
        updated_booking = mark_class_attendance(
            gym=growth_gym,
            session_id=session.id,
            member_id=member.id,
            attended=True,
            marked_by=owner_user,
        )

        assert updated_booking.attended is True
        assert updated_booking.marked_by == owner_user

        # STRICT ASSERTION: Marking class attendance creates NO daily attendance check-in row!
        assert Attendance.objects.count() == 0
        assert Attendance.all_objects.count() == 0

    def test_cancellation_2_hour_cutoff(self, growth_gym):
        trainer = make_trainer(growth_gym, "Coach Abel", "abel8@growth.com")
        member = make_member(
            growth_gym, "Cancel Member", "cancel_m@growth.com", "+251911000071"
        )

        # Session 1: 3 hours in future (member CAN cancel)
        s1 = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_YOGA,
            other_title="",
            trainer=trainer,
            start_time=timezone.now() + timedelta(hours=3),
            duration_minutes=60,
            capacity=10,
        )[0]
        b1 = book_class_session(growth_gym, s1.id, member)

        cancelled_b1 = cancel_class_booking(growth_gym, b1.id, member.user)
        assert cancelled_b1.status == BOOKING_STATUS_CANCELLED

        # Session 2: 1 hour in future (member CANNOT cancel; < 2 hours)
        s2 = create_class_sessions(
            gym=growth_gym,
            title=CLASS_TITLE_ZUMBA,
            other_title="",
            trainer=trainer,
            start_time=timezone.now() + timedelta(hours=1),
            duration_minutes=60,
            capacity=10,
        )[0]
        b2 = book_class_session(growth_gym, s2.id, member)

        with pytest.raises(Exception) as exc:
            cancel_class_booking(growth_gym, b2.id, member.user)
        assert "2 hours before the class begins" in str(exc.value)

        # Staff (Reception) CAN cancel on member's behalf even within 2 hours
        reception_user = create_user(
            growth_gym, User.ROLE_RECEPTION, "reception_cancel@growth.com"
        )
        staff_cancelled = cancel_class_booking(growth_gym, b2.id, reception_user)
        assert staff_cancelled.status == BOOKING_STATUS_CANCELLED
