"""Management command to sweep online Chapa payments left pending beyond 30 minutes."""

from django.core.management.base import BaseCommand

from apps.payments.services import flag_unfinished_payments


class Command(BaseCommand):
    help = "Sweep online payments left pending beyond 30 minutes and flag them as abandoned."

    def add_arguments(self, parser):
        parser.add_argument(
            "--window-minutes",
            type=int,
            default=30,
            help="Number of minutes after which pending online payments are marked abandoned (default: 30).",
        )

    def handle(self, *args, **options):
        window_minutes = options.get("window_minutes", 30)
        self.stdout.write(
            f"Sweeping unfinished online payments pending beyond {window_minutes} minutes..."
        )
        count = flag_unfinished_payments(window_minutes=window_minutes)
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully flagged {count} unfinished payment(s) as abandoned."
            )
        )
