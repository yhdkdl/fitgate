"""Management command to process membership unfreezes and activations (5-minute cron)."""

from django.core.management.base import BaseCommand

from apps.memberships.services import process_unfreezes


class Command(BaseCommand):
    help = "Process ended membership freezes, reactivate subscriptions, and activate today's freezes."

    def handle(self, *args, **options):
        self.stdout.write("Processing membership unfreezes...")
        count = process_unfreezes()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully processed {count} unfreeze(s).")
        )
