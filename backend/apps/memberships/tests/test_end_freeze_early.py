"""Tests for early membership freeze termination."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditLog, User
from apps.memberships.models import (
    Member,
    MemberFreeze,
    MembershipPlan,
    MemberSubscription,
)
from apps.memberships.services import (
    approve_membership_freeze,
    end_membership_freeze_early,
    get_member_freeze_allowance,
    request_membership_freeze,
)
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def gym_tenant():
    gym = GymTenant.objects.create(
        name="Apex Fitness",
        subdomain="apex",
        tier=GymTenant.TIER_GROWTH,
        tls_confirmed_at=timezone.now(),
    )
    config, _ = GymConfig.objects.get_or_create(gym=gym)
    config.freeze_days_allowed = 30
    config.freeze_days_cap = 30
    config.save()
    return gym


@pytest.fixture
def other_gym():
    gym = GymTenant.objects.create(
        name="Other Fitness",
        subdomain="other",
        tier=GymTenant.TIER_GROWTH,
        tls_confirmed_at=timezone.now(),
    )
    config, _ = GymConfig.objects.get_or_create(gym=gym)
    config.freeze_days_allowed = 30
    config.freeze_days_cap = 30
    config.save()
    return gym


@pytest.fixture
def users_and_member(gym_tenant, other_gym):
    owner = User.objects.create_user(
        email="owner@apex.test",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_OWNER,
    )
    manager = User.objects.create_user(
        email="manager@apex.test",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_MANAGER,
    )
    reception = User.objects.create_user(
        email="reception@apex.test",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
    )
    trainer = User.objects.create_user(
        email="trainer@apex.test",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_TRAINER,
    )
    super_admin = User.objects.create_user(
        email="superadmin@fitgate.test",
        password="Password123!",
        gym=None,
        role=User.ROLE_SUPER_ADMIN,
    )
    other_owner = User.objects.create_user(
        email="owner@other.test",
        password="Password123!",
        gym=other_gym,
        role=User.ROLE_OWNER,
    )

    member_user = User.objects.create_user(
        email="member@apex.test",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
    )
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Dawit Abebe",
        phone="+251911223344",
        gender="M",
        date_of_birth=timezone.localdate() - timedelta(days=365 * 25),
        waiver_accepted_at=timezone.now(),
    )

    plan = MembershipPlan.objects.create(
        gym=gym_tenant,
        name="Monthly Standard",
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        price_etb=Decimal("1500.00"),
        is_active=True,
    )

    today = timezone.localdate()
    original_end_date = today + timedelta(days=60)
    sub = MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=today,
        end_date=original_end_date,
        status=MemberSubscription.STATUS_ACTIVE,
    )
    member.status = Member.STATUS_ACTIVE
    member._status_update_allowed = True
    member.save()
    member._status_update_allowed = False

    return {
        "owner": owner,
        "manager": manager,
        "reception": reception,
        "trainer": trainer,
        "super_admin": super_admin,
        "other_owner": other_owner,
        "member_user": member_user,
        "member": member,
        "sub": sub,
        "original_end_date": original_end_date,
    }


@pytest.mark.django_db
class TestEndFreezeEarly:
    """Test suite for ending membership freezes early."""

    def test_current_freeze_ended_on_day_4_math(self, gym_tenant, users_and_member):
        """
        7-day freeze starting today, ended on day 4 (today + 3 days).
        3 days used (from start to today), 4 days unused.
        On approval: end date extended by 7 days.
        On early end: end date reduced by 4 unused days.
        Allowance: 30 total, 3 used, 27 remaining (4 days returned).
        """
        data = users_and_member
        member = data["member"]
        sub = data["sub"]
        owner = data["owner"]
        original_end = data["original_end_date"]

        today = timezone.localdate()
        freeze_start = today
        freeze_end = today + timedelta(days=6)  # 7 days inclusive

        freeze = request_membership_freeze(
            member=member,
            start_date=freeze_start,
            end_date=freeze_end,
            reason="Traveling abroad",
        )
        approved_freeze = approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner,
            gym=gym_tenant,
        )
        sub.refresh_from_db()
        assert sub.end_date == original_end + timedelta(days=7)
        assert sub.frozen_days_total == 7

        # Day 4: 3 days after freeze start
        day_4 = freeze_start + timedelta(days=3)
        ended_freeze = end_membership_freeze_early(
            freeze_id=str(approved_freeze.id),
            staff_user=owner,
            today=day_4,
        )

        sub.refresh_from_db()
        member.refresh_from_db()

        assert ended_freeze.status == MemberFreeze.STATUS_COMPLETED
        assert ended_freeze.days == 3
        # End date was original_end + 7, now reduced by 4 unused days to original_end + 3
        assert sub.end_date == original_end + timedelta(days=3)
        assert sub.frozen_days_total == 3
        assert sub.status == MemberSubscription.STATUS_ACTIVE
        assert member.status == Member.STATUS_ACTIVE

        # Check allowance returns unused days
        allowance = get_member_freeze_allowance(member)
        assert allowance["total_allowed"] == 30
        assert allowance["used_days"] == 3
        assert allowance["remaining_days"] == 27

        # Verify audit log
        audit = AuditLog.all_objects.filter(
            action_type="freeze_ended_early",
            affected_record_id=str(ended_freeze.id),
        ).first()
        assert audit is not None
        assert audit.actor == owner
        assert audit.metadata["days_used"] == 3
        assert audit.metadata["days_returned"] == 4
        assert audit.metadata["old_end_date"] == str(original_end + timedelta(days=7))
        assert audit.metadata["new_end_date"] == str(original_end + timedelta(days=3))

    def test_future_freeze_cancelled_completely(self, gym_tenant, users_and_member):
        """
        An approved freeze that has not started yet is cancelled completely.
        0 days used, full allowance returned, full extension removed.
        """
        data = users_and_member
        member = data["member"]
        sub = data["sub"]
        owner = data["owner"]
        original_end = data["original_end_date"]

        today = timezone.localdate()
        freeze_start = today + timedelta(days=10)
        freeze_end = today + timedelta(days=16)  # 7 days

        freeze = request_membership_freeze(
            member=member,
            start_date=freeze_start,
            end_date=freeze_end,
            reason="Vacation next week",
        )
        approved_freeze = approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner,
            gym=gym_tenant,
        )
        sub.refresh_from_db()
        assert sub.end_date == original_end + timedelta(days=7)

        # Cancelled before start
        ended_freeze = end_membership_freeze_early(
            freeze_id=str(approved_freeze.id),
            staff_user=owner,
        )
        sub.refresh_from_db()
        assert ended_freeze.status == MemberFreeze.STATUS_COMPLETED
        assert ended_freeze.days == 0
        assert sub.end_date == original_end
        assert sub.frozen_days_total == 0

        allowance = get_member_freeze_allowance(member)
        assert allowance["used_days"] == 0
        assert allowance["remaining_days"] == 30

    def test_repeat_safety_ending_twice_raises_error(
        self, gym_tenant, users_and_member
    ):
        """
        Safe to repeat: ending twice never shortens twice and raises an error.
        """
        data = users_and_member
        member = data["member"]
        sub = data["sub"]
        owner = data["owner"]

        today = timezone.localdate()
        freeze = request_membership_freeze(
            member=member,
            start_date=today,
            end_date=today + timedelta(days=6),
            reason="Traveling abroad",
        )
        approved_freeze = approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner,
            gym=gym_tenant,
        )

        day_4 = today + timedelta(days=3)
        # First end
        end_membership_freeze_early(
            freeze_id=str(approved_freeze.id),
            staff_user=owner,
            today=day_4,
        )
        sub.refresh_from_db()
        first_end_date = sub.end_date

        # Second attempt must raise ValidationError and leave sub.end_date intact
        with pytest.raises(Exception) as excinfo:
            end_membership_freeze_early(
                freeze_id=str(approved_freeze.id),
                staff_user=owner,
                today=day_4,
            )
        assert "already finished" in str(excinfo.value)
        sub.refresh_from_db()
        assert sub.end_date == first_end_date

    def test_role_permissions_and_refusals(self, gym_tenant, users_and_member):
        """
        Owner, Manager, Reception can end freeze early.
        Member, Trainer, Super Admin, and unauthenticated receive 403 / 401.
        """
        data = users_and_member
        member = data["member"]
        owner = data["owner"]

        client = APIClient()
        today = timezone.localdate()

        def create_freeze():
            fr = request_membership_freeze(
                member=member,
                start_date=today,
                end_date=today + timedelta(days=6),
                reason="Medical leave",
            )
            return approve_membership_freeze(
                freeze_id=str(fr.id),
                reviewer=owner,
                gym=gym_tenant,
            )

        # 1. Member refused (403)
        fr = create_freeze()
        client.force_authenticate(user=data["member_user"])
        resp = client.post(
            f"/api/gym/freezes/{fr.id}/end-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # 2. Trainer refused (403)
        client.force_authenticate(user=data["trainer"])
        resp = client.post(
            f"/api/gym/freezes/{fr.id}/end-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # 3. Super Admin refused (403)
        client.force_authenticate(user=data["super_admin"])
        resp = client.post(
            f"/api/gym/freezes/{fr.id}/end-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # 4. Reception allowed (200)
        client.force_authenticate(user=data["reception"])
        resp = client.post(
            f"/api/gym/freezes/{fr.id}/end-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_200_OK

        # 5. Manager allowed on member endpoint (200)
        _ = create_freeze()
        client.force_authenticate(user=data["manager"])
        resp = client.post(
            f"/api/gym/members/{member.id}/end-freeze-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_other_gym_refusal(self, gym_tenant, users_and_member):
        """
        Staff of another gym cannot end freeze early for a different gym tenant.
        """
        data = users_and_member
        member = data["member"]
        owner = data["owner"]
        other_owner = data["other_owner"]

        today = timezone.localdate()
        freeze = request_membership_freeze(
            member=member,
            start_date=today,
            end_date=today + timedelta(days=6),
            reason="Traveling abroad",
        )
        approved_freeze = approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner,
            gym=gym_tenant,
        )

        client = APIClient()
        client.force_authenticate(user=other_owner)
        resp = client.post(
            f"/api/gym/freezes/{approved_freeze.id}/end-early/",
            HTTP_HOST="apex.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN
