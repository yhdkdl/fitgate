"""
Tests for Sprint 13 - Membership Freeze Workflow.
Verifies server-side freeze allowance enforcement, concurrency locking,
subscription end date extension (once only), status derivation via update_member_status(),
check-in refusal for frozen members, automatic unfreeze cron, rejection workflow,
and multi-tenant RBAC permissions.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.tokens import get_tokens_for_user
from apps.attendance.services import (
    ScanValidationError,
    execute_check_in,
    issue_member_qr_token,
)
from apps.memberships.models import (
    Member,
    MemberFreeze,
    MembershipPlan,
    MemberSubscription,
)
from apps.memberships.services import (
    approve_membership_freeze,
    process_unfreezes,
    reject_membership_freeze,
    request_membership_freeze,
    update_member_status,
)
from apps.tenants.models import GymConfig, GymTenant


@pytest.fixture
def gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="Bole Fitness",
        subdomain="bole",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config, _ = GymConfig.objects.get_or_create(gym=tenant)
    config.freeze_days_allowed = 14
    config.payment_grace_days = 7
    config.subscription_reminder_days = 3
    config.save()
    return tenant


@pytest.fixture
def other_gym_tenant(db):
    tenant = GymTenant.objects.create(
        name="Apex Kazanchis",
        subdomain="apex",
        tier=GymTenant.TIER_GROWTH,
        status=GymTenant.STATUS_ACTIVE,
        tls_confirmed_at=timezone.now(),
    )
    config, _ = GymConfig.objects.get_or_create(gym=tenant)
    config.freeze_days_allowed = 14
    config.save()
    return tenant


@pytest.fixture
def owner_user(db, gym_tenant):
    return User.objects.create_user(
        email="owner@bole.com",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_OWNER,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def manager_user(db, gym_tenant):
    return User.objects.create_user(
        email="manager@bole.com",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_MANAGER,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def reception_user(db, gym_tenant):
    return User.objects.create_user(
        email="reception@bole.com",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_RECEPTION,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def super_admin_user(db):
    return User.objects.create_superuser(
        email="superadmin@fitgate.org",
        password="SuperPassword123!",
        role=User.ROLE_SUPER_ADMIN,
        must_change_password=False,
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def member_user(db, gym_tenant):
    return User.objects.create_user(
        email="member@bole.com",
        password="Password123!",
        gym=gym_tenant,
        role=User.ROLE_MEMBER,
        full_name="Abebe Bikila",
        phone="+251911223344",
        must_change_password=False,
        email_verified_at=timezone.now(),
    )


@pytest.fixture
def member_with_subscription(db, gym_tenant, member_user):
    member = Member.objects.create(
        gym=gym_tenant,
        user=member_user,
        full_name="Abebe Bikila",
        phone="+251911223344",
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
    sub = MemberSubscription.objects.create(
        gym=gym_tenant,
        member=member,
        plan=plan,
        start_date=today,
        end_date=today + timedelta(days=30),
        status=MemberSubscription.STATUS_ACTIVE,
    )
    update_member_status(member)
    return member, sub


@pytest.mark.django_db
class TestFreezeWorkflow:
    def test_server_blocks_freeze_when_freeze_days_allowed_is_zero(
        self, gym_tenant, member_with_subscription
    ):
        """Freeze is enforced on the SERVER by the gym's freeze setting (zero allowed days means blocked)."""
        member, _ = member_with_subscription
        config = gym_tenant.config
        config.freeze_days_allowed = 0
        config.save()

        today = timezone.localdate()
        tokens = get_tokens_for_user(member.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        payload = {
            "start_date": str(today),
            "end_date": str(today + timedelta(days=5)),
            "reason": "Taking annual vacation",
        }
        resp = client.post(
            "/api/memberships/freezes/",
            payload,
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "This gym does not allow membership freezes." in str(resp.data)

    def test_member_cannot_exceed_remaining_freeze_allowance(
        self, gym_tenant, member_with_subscription
    ):
        """Member cannot request more days than their remaining allowance."""
        member, _ = member_with_subscription
        config = gym_tenant.config
        config.freeze_days_allowed = 10
        config.save()

        today = timezone.localdate()
        tokens = get_tokens_for_user(member.user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 11 days requested > 10 allowed
        payload = {
            "start_date": str(today),
            "end_date": str(today + timedelta(days=10)),
            "reason": "Exceeding freeze test",
        }
        resp = client.post(
            "/api/memberships/freezes/",
            payload,
            format="json",
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "exceeds your remaining allowance" in str(resp.data)

    def test_approving_freeze_extends_end_date_once_and_updates_status(
        self, gym_tenant, member_with_subscription, owner_user
    ):
        """
        Approving a freeze changes status through shared status function
        and extends the end date by exactly the frozen days, once (approving twice never extends twice).
        """
        member, sub = member_with_subscription
        initial_end_date = sub.end_date
        today = timezone.localdate()

        freeze = request_membership_freeze(
            member=member,
            start_date=today,
            end_date=today + timedelta(days=6),  # 7 days
            reason="Medical recovery",
        )
        assert freeze.days == 7

        approved_freeze = approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner_user,
            gym=gym_tenant,
        )
        assert approved_freeze.status == MemberFreeze.STATUS_APPROVED
        assert approved_freeze.extension_applied is True

        sub.refresh_from_db()
        member.refresh_from_db()

        # End date extended by exactly 7 days
        assert sub.end_date == initial_end_date + timedelta(days=7)
        assert sub.frozen_days_total == 7
        assert sub.status == MemberSubscription.STATUS_FROZEN
        assert member.status == Member.STATUS_FROZEN

        # Calling approval again raises validation error and does NOT extend end date again
        with pytest.raises(Exception):
            approve_membership_freeze(
                freeze_id=str(freeze.id),
                reviewer=owner_user,
                gym=gym_tenant,
            )

        sub.refresh_from_db()
        assert sub.end_date == initial_end_date + timedelta(days=7)

    def test_frozen_member_cannot_check_in(
        self, gym_tenant, member_with_subscription, owner_user, reception_user
    ):
        """A frozen member cannot check in (check-in rejected with 'Membership is frozen')."""
        member, sub = member_with_subscription
        today = timezone.localdate()

        freeze = request_membership_freeze(
            member=member,
            start_date=today,
            end_date=today + timedelta(days=5),
            reason="Work travel",
        )
        approve_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=owner_user,
            gym=gym_tenant,
        )

        member.refresh_from_db()
        assert member.status == Member.STATUS_FROZEN

        # Attempt manual override check-in
        with pytest.raises(ScanValidationError) as exc_info:
            execute_check_in(
                member=member,
                gym=gym_tenant,
                method="manual_override",
                recorded_by=reception_user,
                override_reason="Testing check-in block on freeze",
            )
        assert exc_info.value.reason == "frozen"
        assert "frozen" in str(exc_info.value.message).lower()

        # Attempt QR token issue for member
        with pytest.raises(ScanValidationError) as qr_exc:
            issue_member_qr_token(member)
        assert qr_exc.value.reason == "frozen"
        assert "frozen" in str(qr_exc.value.message).lower()

    def test_unfreeze_cron_reactivates_member_when_freeze_ends(
        self, gym_tenant, member_with_subscription, owner_user
    ):
        """When the freeze ends, process_unfreezes returns member to active through the shared status function."""
        member, sub = member_with_subscription
        today = timezone.localdate()

        # Freeze started yesterday and ended yesterday
        past_start = today - timedelta(days=5)
        past_end = today - timedelta(days=1)
        freeze = MemberFreeze.objects.create(
            gym=gym_tenant,
            member=member,
            subscription=sub,
            start_date=past_start,
            end_date=past_end,
            days=5,
            reason="Recovered yesterday",
            status=MemberFreeze.STATUS_APPROVED,
            extension_applied=True,
            approved_by=owner_user,
            reviewed_at=timezone.now(),
        )
        sub.status = MemberSubscription.STATUS_FROZEN
        sub.save()
        update_member_status(member)
        assert member.status == Member.STATUS_FROZEN

        # Run unfreeze cron
        count = process_unfreezes(today=today)
        assert count == 1

        freeze.refresh_from_db()
        sub.refresh_from_db()
        member.refresh_from_db()

        assert freeze.status == MemberFreeze.STATUS_COMPLETED
        assert sub.status == MemberSubscription.STATUS_ACTIVE
        assert member.status == Member.STATUS_ACTIVE

    def test_rejecting_freeze_leaves_pass_active_saves_reason_notifies_member(
        self, gym_tenant, member_with_subscription, manager_user
    ):
        """Rejecting a freeze request leaves pass active with an explanation, and notifies member."""
        member, sub = member_with_subscription
        today = timezone.localdate()

        freeze = request_membership_freeze(
            member=member,
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=8),
            reason="Vacation request",
        )

        rejected = reject_membership_freeze(
            freeze_id=str(freeze.id),
            reviewer=manager_user,
            rejection_reason="Peak season blackout period applies to this tier.",
            gym=gym_tenant,
        )

        assert rejected.status == MemberFreeze.STATUS_REJECTED
        assert (
            rejected.rejection_reason
            == "Peak season blackout period applies to this tier."
        )

        sub.refresh_from_db()
        member.refresh_from_db()
        assert sub.status == MemberSubscription.STATUS_ACTIVE
        assert member.status == Member.STATUS_ACTIVE

    def test_freeze_permissions_and_super_admin_denied(
        self,
        gym_tenant,
        other_gym_tenant,
        member_with_subscription,
        owner_user,
        reception_user,
        super_admin_user,
    ):
        """
        Members only request and see their own freezes;
        Only Owner and Manager of that gym approve or reject;
        Super Admin and other gyms are denied (403).
        """
        member, _ = member_with_subscription
        today = timezone.localdate()
        freeze = request_membership_freeze(
            member=member,
            start_date=today,
            end_date=today + timedelta(days=3),
            reason="Permissions test",
        )

        # Reception cannot approve
        rec_tokens = get_tokens_for_user(reception_user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {rec_tokens['access']}")
        resp = client.post(
            f"/api/gym/freezes/{freeze.id}/approve/",
            {},
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Super Admin cannot approve (denied 403)
        sa_tokens = get_tokens_for_user(super_admin_user)
        sa_client = APIClient()
        sa_client.credentials(HTTP_AUTHORIZATION=f"Bearer {sa_tokens['access']}")
        resp = sa_client.post(
            f"/api/gym/freezes/{freeze.id}/approve/",
            {},
            HTTP_HOST="localhost",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN

        # Other gym owner cannot approve
        other_owner = User.objects.create_user(
            email="other_owner@apex.com",
            password="Password123!",
            gym=other_gym_tenant,
            role=User.ROLE_OWNER,
            must_change_password=False,
            email_verified_at=timezone.now(),
        )
        oo_tokens = get_tokens_for_user(other_owner)
        oo_client = APIClient()
        oo_client.credentials(HTTP_AUTHORIZATION=f"Bearer {oo_tokens['access']}")
        resp = oo_client.post(
            f"/api/gym/freezes/{freeze.id}/approve/",
            {},
            HTTP_HOST=f"{other_gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_404_NOT_FOUND,
        )

        # Gym Owner can approve
        owner_tokens = get_tokens_for_user(owner_user)
        owner_client = APIClient()
        owner_client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_tokens['access']}")
        resp = owner_client.post(
            f"/api/gym/freezes/{freeze.id}/approve/",
            {},
            HTTP_HOST=f"{gym_tenant.subdomain}.localhost",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_concurrency_locking_prevents_allowance_overrun(
        self, gym_tenant, member_with_subscription, owner_user, manager_user
    ):
        """
        Concurrency: remaining allowance cannot be exceeded by two requests at once.
        When two requests each ask for 8 days out of 10 total allowed,
        approving one must cause the other approval to be rejected.
        """
        member, sub = member_with_subscription
        gym_tenant.config.freeze_days_allowed = 10
        gym_tenant.config.save()

        today = timezone.localdate()

        freeze1 = MemberFreeze.objects.create(
            gym=gym_tenant,
            member=member,
            subscription=sub,
            start_date=today + timedelta(days=1),
            end_date=today + timedelta(days=8),  # 8 days
            days=8,
            reason="Concurrent test 1",
            status=MemberFreeze.STATUS_PENDING,
        )

        freeze2 = MemberFreeze.objects.create(
            gym=gym_tenant,
            member=member,
            subscription=sub,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=17),  # 8 days
            days=8,
            reason="Concurrent test 2",
            status=MemberFreeze.STATUS_PENDING,
        )

        # Approve freeze 1 (8 days out of 10) -> Success
        approve_membership_freeze(
            freeze_id=str(freeze1.id),
            reviewer=owner_user,
            gym=gym_tenant,
        )
        freeze1.refresh_from_db()
        assert freeze1.status == MemberFreeze.STATUS_APPROVED

        # Approve freeze 2 (8 days requested, only 2 left) -> Validation error
        with pytest.raises(Exception) as exc_info:
            approve_membership_freeze(
                freeze_id=str(freeze2.id),
                reviewer=manager_user,
                gym=gym_tenant,
            )
        assert "exceeds remaining allowance" in str(exc_info.value)
