"""Management command to mark unverified member accounts older than 7 days as expired."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.memberships.models import Member


class Command(BaseCommand):
    help = "Mark unverified member accounts older than 7 days as expired"

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=7)
        unverified_users = User.all_objects.filter(
            role=User.ROLE_MEMBER,
            email_verified_at__isnull=True,
            created_at__lt=cutoff,
            is_active=True,
        )

        count = 0
        for user in unverified_users:
            user.is_active = False
            user.save(update_fields=["is_active"])
            member = Member.all_objects.filter(user=user).first()
            if member:
                member.status = Member.STATUS_EXPIRED
                member._status_update_allowed = True
                try:
                    member.save(update_fields=["status"])
                finally:
                    member._status_update_allowed = False
            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully marked {count} unverified member accounts as expired."
            )
        )
