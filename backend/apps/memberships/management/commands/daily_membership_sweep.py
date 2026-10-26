"""
Daily membership sweep management command (automated nightly maintenance).
Runs nightly (e.g. 0 1 * * *) via cPanel cron.

Tasks performed:
1. Expiration of member subscriptions with end_date < sweep_date:
   - Updates MemberSubscription.status to 'expired'.
   - Derives Member.status strictly via the shared update_member_status() from Sprint 10.
2. Member subscription renewal reminders:
   - Follows each gym's reminder settings from GymConfig.
   - Dispatches reminder email strictly through send_fitgate_email.
   - Records reminder_sent_date and in-app notifications so running twice never emails or notifies twice.
3. Tenant isolation:
   - Each gym's settings only affect that gym's members.
   - Suspended gyms or gyms past their payment grace period send nothing.
4. Gym platform subscription monitoring:
   - Reminds gym owner of approaching platform subscription expiration.
   - Alerts platform administrator if gym exceeds payment grace period without payment (without abrupt mid-day shutoff).
5. Automatic unfreeze processing and payment housekeeping:
   - Reactivates memberships when freeze period completes (via process_unfreezes).
   - Flags lingering unreconciled bank transfers and abandoned online payments.
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.accounts.models import Notification, User
from apps.accounts.notifications import create_notification, send_fitgate_email
from apps.memberships.models import MemberSubscription
from apps.memberships.services import process_unfreezes, update_member_status
from apps.payments.services import flag_unfinished_payments, flag_unreconciled_transfers
from apps.tenants.models import GymTenant

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run nightly membership sweep: expire past subscriptions, dispatch reminders, and perform maintenance."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            default=None,
            help="Simulate execution on a specific date (YYYY-MM-DD) for testing.",
        )

    def handle(self, *args, **options):
        date_str = options.get("date")
        if date_str:
            sweep_date = parse_date(date_str)
            if not sweep_date:
                self.stderr.write(
                    f"Invalid date format: {date_str}. Expected YYYY-MM-DD."
                )
                return
        else:
            sweep_date = timezone.localdate()

        self.stdout.write(f"Starting daily membership sweep for date {sweep_date}...")

        # 1. Process membership unfreezes
        unfreeze_count = process_unfreezes(today=sweep_date)
        if unfreeze_count > 0:
            self.stdout.write(f"Processed {unfreeze_count} unfreeze(s).")

        expired_count = 0
        reminders_sent = 0
        gym_reminders_sent = 0

        # 2. Iterate across gym tenants
        gyms = GymTenant.objects.all().select_related("config")
        for gym in gyms:
            # Check gym suspension
            is_suspended = (
                gym.status == GymTenant.STATUS_SUSPENDED or gym.suspended_at is not None
            )

            # Check gym payment grace period
            is_past_grace = False
            grace_days = getattr(gym.config, "payment_grace_days", 7)
            if gym.subscription_expires_at:
                grace_cutoff = gym.subscription_expires_at.date() + timedelta(
                    days=grace_days
                )
                if sweep_date > grace_cutoff:
                    is_past_grace = True
                    # Alert platform administrator if grace period ended unpaid (and not yet flagged)
                    if gym.lapse_flagged_at is None:
                        gym.lapse_flagged_at = timezone.now()
                        gym.save(update_fields=["lapse_flagged_at"])
                        for admin in User.all_objects.filter(
                            role=User.ROLE_SUPER_ADMIN, is_active=True
                        ):
                            create_notification(
                                recipient=admin,
                                notification_type="gym_grace_period_expired",
                                message=f"Gym '{gym.name}' has exceeded its payment grace period without payment.",
                                gym=None,
                            )

            # Rule: Suspended gym or gym past its payment grace period sends nothing!
            if is_suspended or is_past_grace:
                logger.info(
                    "Skipping notifications and reminders for gym %s (suspended=%s, past_grace=%s).",
                    gym.name,
                    is_suspended,
                    is_past_grace,
                )
                continue

            # 2a. Gym Platform Subscription Expiration Reminder to Gym Owner
            if gym.subscription_expires_at:
                days_until_gym_expiry = (
                    gym.subscription_expires_at.date() - sweep_date
                ).days
                platform_reminder_days = getattr(
                    gym.config, "subscription_reminder_days", None
                ) or [14, 7]
                target_platform_days = set()
                if isinstance(platform_reminder_days, int):
                    target_platform_days.add(platform_reminder_days)
                elif isinstance(platform_reminder_days, (list, tuple)):
                    target_platform_days.update(int(x) for x in platform_reminder_days)

                if days_until_gym_expiry in target_platform_days:
                    already_notified = Notification.all_objects.filter(
                        gym=gym,
                        type="gym_subscription_reminder",
                        created_at__date=sweep_date,
                    ).exists()
                    if not already_notified:
                        owner = User.all_objects.filter(
                            gym=gym, role=User.ROLE_OWNER, is_active=True
                        ).first()
                        if owner and owner.email:
                            send_fitgate_email(
                                subject=f"FitGate: Your gym platform subscription for {gym.name} expires in {days_until_gym_expiry} days",
                                message=(
                                    f"Hello {owner.full_name or 'Gym Owner'},\n\n"
                                    f"Your annual platform subscription for '{gym.name}' expires on {gym.subscription_expires_at.date()} "
                                    f"({days_until_gym_expiry} days remaining).\n\n"
                                    f"Please ensure payment is settled to avoid platform disruption.\n\n"
                                    f"The FitGate Team\n"
                                ),
                                recipient_list=[owner.email],
                                gym=gym,
                            )
                            create_notification(
                                recipient=owner,
                                notification_type="gym_subscription_reminder",
                                message=f"Your gym platform subscription expires in {days_until_gym_expiry} days (on {gym.subscription_expires_at.date()}).",
                                gym=gym,
                            )
                            gym_reminders_sent += 1

            # 2b. Member Subscriptions Expiry
            # Subscriptions with end_date < sweep_date and status == active expire
            active_past_subs = list(
                MemberSubscription.all_objects.filter(
                    gym=gym,
                    status=MemberSubscription.STATUS_ACTIVE,
                    end_date__lt=sweep_date,
                ).select_related("member", "member__user")
            )
            for sub in active_past_subs:
                sub.status = MemberSubscription.STATUS_EXPIRED
                sub.save(update_fields=["status"])
                update_member_status(sub.member, today=sweep_date)
                expired_count += 1

            # 2c. Member Subscription Renewal Reminders
            # Follows gym's reminder settings from GymConfig
            target_reminder_days = set()
            member_reminders_raw = getattr(gym.config, "member_reminder_days", None)
            if isinstance(member_reminders_raw, int):
                target_reminder_days.add(member_reminders_raw)
            elif isinstance(member_reminders_raw, (list, tuple)):
                target_reminder_days.update(int(x) for x in member_reminders_raw)

            sub_reminders_raw = getattr(gym.config, "subscription_reminder_days", None)
            if isinstance(sub_reminders_raw, int):
                target_reminder_days.add(sub_reminders_raw)
            elif isinstance(sub_reminders_raw, (list, tuple)):
                target_reminder_days.update(int(x) for x in sub_reminders_raw)

            if not target_reminder_days:
                target_reminder_days = {7, 2}

            # Check active subscriptions expiring in the future
            active_future_subs = MemberSubscription.all_objects.filter(
                gym=gym,
                status=MemberSubscription.STATUS_ACTIVE,
                end_date__gte=sweep_date,
            ).select_related("member", "member__user")

            for sub in active_future_subs:
                days_left = (sub.end_date - sweep_date).days
                if days_left in target_reminder_days:
                    # Idempotency guard: never send reminder twice for the same subscription on the same sweep date
                    if sub.reminder_sent_date == sweep_date:
                        continue

                    member_user = getattr(sub.member, "user", None)
                    if (
                        member_user
                        and Notification.all_objects.filter(
                            recipient=member_user,
                            type="subscription_renewal_reminder",
                            created_at__date=sweep_date,
                        ).exists()
                    ):
                        sub.reminder_sent_date = sweep_date
                        sub.save(update_fields=["reminder_sent_date"])
                        continue

                    # Send reminder email strictly through send_fitgate_email
                    if member_user and member_user.email:
                        send_fitgate_email(
                            subject=f"Your membership at {gym.name} expires in {days_left} day{'s' if days_left != 1 else ''}",
                            message=(
                                f"Hello {sub.member.full_name},\n\n"
                                f"Your membership plan at {gym.name} will expire on {sub.end_date} "
                                f"({days_left} day{'s' if days_left != 1 else ''} left).\n\n"
                                f"Please renew your membership to maintain uninterrupted access.\n\n"
                                f"Best regards,\n{gym.name}\n"
                            ),
                            recipient_list=[member_user.email],
                            gym=gym,
                        )
                        create_notification(
                            recipient=member_user,
                            notification_type="subscription_renewal_reminder",
                            message=f"Your membership plan expires in {days_left} day{'s' if days_left != 1 else ''} (on {sub.end_date}).",
                            gym=gym,
                        )
                        reminders_sent += 1

                    # Notify gym reception staff
                    reception_users = User.all_objects.filter(
                        gym=gym,
                        role__in=[
                            User.ROLE_RECEPTION,
                            User.ROLE_MANAGER,
                            User.ROLE_OWNER,
                        ],
                        is_active=True,
                    )
                    for staff in reception_users:
                        create_notification(
                            recipient=staff,
                            notification_type="member_renewal_due",
                            message=f"Member {sub.member.full_name}'s plan expires in {days_left} day{'s' if days_left != 1 else ''} ({sub.end_date}).",
                            gym=gym,
                        )

                    sub.reminder_sent_date = sweep_date
                    sub.save(update_fields=["reminder_sent_date"])

        # 3. Payments housekeeping
        try:
            flag_unreconciled_transfers(days=7)
        except Exception as e:
            logger.warning("Error running flag_unreconciled_transfers: %s", e)

        try:
            flag_unfinished_payments(window_minutes=30)
        except Exception as e:
            logger.warning("Error running flag_unfinished_payments: %s", e)

        self.stdout.write(
            self.style.SUCCESS(
                f"Daily sweep completed: {expired_count} subscription(s) expired, "
                f"{reminders_sent} member reminder(s) sent, {gym_reminders_sent} gym reminder(s) sent."
            )
        )
