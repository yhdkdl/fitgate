"""Daily management command to flag unreconciled bank transfers older than 7 days."""

from django.core.management.base import BaseCommand

from apps.payments.services import flag_unreconciled_transfers


class Command(BaseCommand):
    help = "Flag unreconciled member bank-transfer payments older than 7 days and notify the gym owner."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=7,
            help="Number of days after which unreconciled bank transfers are flagged (default: 7).",
        )

    def handle(self, *args, **options):
        days = options.get("days", 7)
        self.stdout.write(
            f"Checking for unreconciled bank transfers older than {days} days..."
        )
        flagged_summary = flag_unreconciled_transfers(days=days)
        total = sum(flagged_summary.values())
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully flagged {total} unreconciled bank transfer(s) across {len(flagged_summary)} gym(s)."
            )
        )
