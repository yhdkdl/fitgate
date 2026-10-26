"""Tests for Sprint 14 scheduled jobs and daily membership sweep."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import Notification, User
from apps.memberships.models import Member, MembershipPlan, MemberSubscription
from apps.memberships.services import update_member_status
from apps.tenants.models import GymTenant


@pytest.fixture
def sweep_setup(db):
    """Set up two tenants with plans, staff, and members."""
    # Gym Alpha
    gym_alpha = GymTenant.objects.create(
        name="Alpha Fitness",
        subdomain="alpha",
        status=GymTenant.STATUS_ACTIVE,
        subscription_expires_at=timezone.now() + timedelta(days=60),
    )
    gym_alpha.config.member_reminder_days = [7, 2]
    gym_alpha.config.save()

    owner_alpha = User.objects.create(
        email="owner@alpha.fitgate.et",
        role=User.ROLE_OWNER,
        gym=gym_alpha,
        is_active=True,
    )
    plan_alpha = MembershipPlan.objects.create(
        gym=gym_alpha,
        name="Alpha Monthly",
        duration_value=1,
        duration_unit=MembershipPlan.DURATION_MONTHS,
        price_etb="1000.00",
        is_active=True,
    )

    # Member 1 in Alpha (to expire)
    user_1 = User.objects.create(
        email="member1@alpha.fitgate.et",
        role=User.ROLE_MEMBER,
        gym=gym_alpha,
        is_active=True,
    )
    member_1 = Member.objects.create(
        user=user_1,
        gym=gym_alpha,
        full_name="Member One",
        phone="+251911000001",
        waiver_accepted_at=timezone.now(),
    )

    # Member 2 in Alpha (to remind in 7 days)
    user_2 = User.objects.create(
        email="member2@alpha.fitgate.et",
        role=User.ROLE_MEMBER,
        gym=gym_alpha,
        is_active=True,
    )
    member_2 = Member.objects.create(
        user=user_2,
        gym=gym_alpha,
        full_name="Member Two",
        phone="+251911000002",
        waiver_accepted_at=timezone.now(),
    )

    return {
        "gym_alpha": gym_alpha,
        "owner_alpha": owner_alpha,
        "plan_alpha": plan_alpha,
        "member_1": member_1,
        "member_2": member_2,
    }


@pytest.mark.django_db
class TestDailyMembershipSweep:
    """Test suite for daily_membership_sweep management command."""

    def test_sweep_twice_no_duplicate_expiry_notifications_or_emails(self, sweep_setup):
        today = timezone.localdate()
        gym = sweep_setup["gym_alpha"]
        member_1 = sweep_setup["member_1"]
        member_2 = sweep_setup["member_2"]
        plan = sweep_setup["plan_alpha"]

        # Sub 1: Ended yesterday -> should expire
        sub_1 = MemberSubscription.all_objects.create(
            gym=gym,
            member=member_1,
            plan=plan,
            start_date=today - timedelta(days=30),
            end_date=today - timedelta(days=1),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        update_member_status(member_1, today=today)

        # Sub 2: Ends in 7 days -> should trigger renewal reminder
        sub_2 = MemberSubscription.all_objects.create(
            gym=gym,
            member=member_2,
            plan=plan,
            start_date=today - timedelta(days=23),
            end_date=today + timedelta(days=7),
            status=MemberSubscription.STATUS_ACTIVE,
        )
        update_member_status(member_2, today=today)

        with patch(
            "apps.memberships.management.commands.daily_membership_sweep.send_fitgate_email"
        ) as mock_send_email:
            # First execution
            call_command("daily_membership_sweep", date=today.isoformat())

            # 1. Verify Member 1 expired properly
            sub_1.refresh_from_db()
            member_1.refresh_from_db()
            assert sub_1.status == MemberSubscription.STATUS_EXPIRED
            assert member_1.status == Member.STATUS_EXPIRED

            # 2. Verify Member 2 received 1 reminder email
            assert mock_send_email.call_count == 1
            call_kwargs = mock_send_email.call_args[1]
            assert "member2@alpha.fitgate.et" in call_kwargs["recipient_list"]
            assert call_kwargs["gym"] == gym

            # 3. Verify in-app notifications
            notif_count_first = Notification.all_objects.filter(
                recipient=member_2.user,
                type="subscription_renewal_reminder",
            ).count()
            assert notif_count_first == 1

            # 4. Run the sweep a SECOND time on the exact same date!
            call_command("daily_membership_sweep", date=today.isoformat())

            # Verify no second email sent (call count remains 1)
            assert mock_send_email.call_count == 1

            # Verify no second notification created
            notif_count_second = Notification.all_objects.filter(
                recipient=member_2.user,
                type="subscription_renewal_reminder",
            ).count()
            assert notif_count_second == 1

            # Verify member 1 status remains expired and member 2 sub remains active
            sub_1.refresh_from_db()
            member_1.refresh_from_db()
            sub_2.refresh_from_db()
            assert sub_1.status == MemberSubscription.STATUS_EXPIRED
            assert member_1.status == Member.STATUS_EXPIRED
            assert sub_2.status == MemberSubscription.STATUS_ACTIVE

    def test_suspended_gym_or_past_grace_period_sends_nothing(self, db):
        today = timezone.localdate()

        # Gym A: Suspended
        gym_suspended = GymTenant.objects.create(
            name="Suspended Gym",
            subdomain="suspended",
            status=GymTenant.STATUS_SUSPENDED,
            suspended_at=timezone.now(),
        )
        gym_suspended.config.member_reminder_days = [7, 2]
        gym_suspended.config.save()

        user_s = User.objects.create(
            email="member@suspended.fitgate.et",
            role=User.ROLE_MEMBER,
            gym=gym_suspended,
            is_active=True,
        )
        member_s = Member.objects.create(
            user=user_s,
            gym=gym_suspended,
            full_name="Suspended Member",
            phone="+251911000003",
            waiver_accepted_at=timezone.now(),
        )
        MemberSubscription.all_objects.create(
            gym=gym_suspended,
            member=member_s,
            start_date=today - timedelta(days=23),
            end_date=today + timedelta(days=7),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Gym B: Past payment grace period
        # Expiry was 15 days ago, grace period is 7 days -> cutoff was 8 days ago
        gym_past_grace = GymTenant.objects.create(
            name="Past Grace Gym",
            subdomain="pastgrace",
            status=GymTenant.STATUS_ACTIVE,
            subscription_expires_at=timezone.now() - timedelta(days=15),
        )
        gym_past_grace.config.payment_grace_days = 7
        gym_past_grace.config.member_reminder_days = [7, 2]
        gym_past_grace.config.save()

        user_g = User.objects.create(
            email="member@pastgrace.fitgate.et",
            role=User.ROLE_MEMBER,
            gym=gym_past_grace,
            is_active=True,
        )
        member_g = Member.objects.create(
            user=user_g,
            gym=gym_past_grace,
            full_name="Grace Member",
            phone="+251911000004",
            waiver_accepted_at=timezone.now(),
        )
        MemberSubscription.all_objects.create(
            gym=gym_past_grace,
            member=member_g,
            start_date=today - timedelta(days=23),
            end_date=today + timedelta(days=7),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        super_admin = User.all_objects.create(
            email="superadmin@platform.fitgate.et",
            role=User.ROLE_SUPER_ADMIN,
            is_active=True,
        )

        with patch(
            "apps.memberships.management.commands.daily_membership_sweep.send_fitgate_email"
        ) as mock_send_email:
            call_command("daily_membership_sweep", date=today.isoformat())

            # Neither suspended gym nor past-grace gym sends any reminder emails
            assert mock_send_email.call_count == 0

            # No member notifications created for suspended or past-grace gym members
            assert Notification.all_objects.filter(recipient=user_s).count() == 0
            assert Notification.all_objects.filter(recipient=user_g).count() == 0

            # Past grace period gym is flagged and platform admin alerted
            gym_past_grace.refresh_from_db()
            assert gym_past_grace.lapse_flagged_at is not None
            admin_notifs = Notification.all_objects.filter(
                recipient=super_admin,
                type="gym_grace_period_expired",
            )
            assert admin_notifs.exists()

    def test_tenant_isolation_of_reminder_settings(self, db):
        today = timezone.localdate()

        # Gym Alpha configured with reminder days: [5]
        gym_alpha = GymTenant.objects.create(
            name="Alpha Gym",
            subdomain="alpha-iso",
            status=GymTenant.STATUS_ACTIVE,
        )
        gym_alpha.config.member_reminder_days = [5]
        gym_alpha.config.subscription_reminder_days = []
        gym_alpha.config.save()

        # Gym Beta configured with reminder days: [3]
        gym_beta = GymTenant.objects.create(
            name="Beta Gym",
            subdomain="beta-iso",
            status=GymTenant.STATUS_ACTIVE,
        )
        gym_beta.config.member_reminder_days = [3]
        gym_beta.config.subscription_reminder_days = []
        gym_beta.config.save()

        # Member in Alpha with 5 days left
        user_alpha = User.objects.create(
            email="m_alpha@alpha.fitgate.et",
            role=User.ROLE_MEMBER,
            gym=gym_alpha,
            is_active=True,
        )
        member_alpha = Member.objects.create(
            user=user_alpha,
            gym=gym_alpha,
            full_name="Alpha Member",
            phone="+251911000005",
            waiver_accepted_at=timezone.now(),
        )
        MemberSubscription.all_objects.create(
            gym=gym_alpha,
            member=member_alpha,
            start_date=today - timedelta(days=25),
            end_date=today + timedelta(days=5),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        # Member in Beta with 5 days left (Beta reminds at 3 days, not 5!)
        user_beta = User.objects.create(
            email="m_beta@beta.fitgate.et",
            role=User.ROLE_MEMBER,
            gym=gym_beta,
            is_active=True,
        )
        member_beta = Member.objects.create(
            user=user_beta,
            gym=gym_beta,
            full_name="Beta Member",
            phone="+251911000006",
            waiver_accepted_at=timezone.now(),
        )
        MemberSubscription.all_objects.create(
            gym=gym_beta,
            member=member_beta,
            start_date=today - timedelta(days=25),
            end_date=today + timedelta(days=5),
            status=MemberSubscription.STATUS_ACTIVE,
        )

        with patch(
            "apps.memberships.management.commands.daily_membership_sweep.send_fitgate_email"
        ) as mock_send_email:
            call_command("daily_membership_sweep", date=today.isoformat())

            # Alpha member (5 days left, matches [5]) gets an email
            # Beta member (5 days left, does not match [3]) gets NO email
            assert mock_send_email.call_count == 1
            call_kwargs = mock_send_email.call_args[1]
            assert "m_alpha@alpha.fitgate.et" in call_kwargs["recipient_list"]
            assert call_kwargs["gym"] == gym_alpha

            # Check in-app notifications
            assert Notification.all_objects.filter(recipient=user_alpha).count() >= 1
            assert Notification.all_objects.filter(recipient=user_beta).count() == 0
