"""Management command to check pending TLS certificates for newly created gyms."""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.services import record_audit_log
from apps.tenants.models import GymTenant
from apps.tenants.services import verify_subdomain_tls

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Check TLS certificates for gyms with tls_confirmed_at null and confirm if valid."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=float,
            default=10.0,
            help="TLS connection timeout in seconds (default: 10.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=443,
            help="TLS port to connect to (default: 443)",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        port = options["port"]
        pending_gyms = GymTenant.objects.filter(tls_confirmed_at__isnull=True)
        count = pending_gyms.count()
        self.stdout.write(f"Checking TLS for {count} pending gym(s)...")

        confirmed_count = 0
        now = timezone.now()

        for gym in pending_gyms:
            is_valid, reason = verify_subdomain_tls(
                subdomain=gym.subdomain,
                port=port,
                timeout=timeout,
            )
            if is_valid:
                gym.tls_confirmed_at = now
                update_fields = ["tls_confirmed_at", "updated_at"]
                if gym.subscription_expires_at is None:
                    gym.subscription_expires_at = now + timedelta(days=365)
                    update_fields.append("subscription_expires_at")
                gym.save(update_fields=update_fields)

                record_audit_log(
                    action_type="gym_tls_confirmed",
                    affected_record_type="GymTenant",
                    affected_record_id=str(gym.id),
                    actor=None,
                    gym=gym,
                    metadata={
                        "subdomain": gym.subdomain,
                        "tls_confirmed_at": gym.tls_confirmed_at.isoformat(),
                        "reason": "confirmed by certificate check",
                    },
                )
                confirmed_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[CONFIRMED] {gym.subdomain}: TLS verified and confirmed."
                    )
                )
            else:
                self.stdout.write(
                    f"[PENDING] {gym.subdomain}: TLS not verified ({reason})."
                )

        self.stdout.write(
            f"Finished: {confirmed_count} confirmed, {count - confirmed_count} still pending."
        )
