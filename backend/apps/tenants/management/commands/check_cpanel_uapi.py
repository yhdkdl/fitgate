"""
Management command to test host network connectivity to cPanel UAPI and list subdomains.

Usage:
    python manage.py check_cpanel_uapi
"""

import sys

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.tenants.uapi import CPanelUAPIClient, CPanelUAPIError


class Command(BaseCommand):
    help = "Verify host network path to cPanel UAPI and list configured subdomains (read-only)."

    def handle(self, *args, **options):
        host = getattr(settings, "CPANEL_HOST", None)
        username = getattr(settings, "CPANEL_USERNAME", None)

        self.stdout.write("=" * 60)
        self.stdout.write("  FitGate cPanel UAPI Host Connectivity Check")
        self.stdout.write("=" * 60)
        self.stdout.write(f"Target cPanel host: {host or 'NOT SET'}")
        self.stdout.write(f"cPanel username   : {username or 'NOT SET'}")
        self.stdout.write("Testing outbound connection to port 2083...")

        try:
            # Instantiate real client directly to test real host path regardless of CPANEL_USE_MOCK
            client = CPanelUAPIClient()
            subdomains = client.list_subdomains()

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n[OK] Host network path to cPanel UAPI (https://{client.host}:2083) is WORKING."
                )
            )
            self.stdout.write(f"Found {len(subdomains)} configured subdomain(s):")
            for sub in subdomains:
                name = sub.get("domain", "")
                root = sub.get("rootdomain", "")
                docroot = sub.get("dir", "")
                full = f"{name}.{root}" if root and not name.endswith(root) else name
                self.stdout.write(f"  - {full} (docroot: {docroot})")

        except CPanelUAPIError as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"\n[FAILED] Could not communicate with cPanel UAPI: {exc}"
                )
            )
            self.stderr.write(
                self.style.WARNING(
                    "\nNote: If outbound HTTPS to port 2083 is blocked by the host firewall, "
                    "a local CLI fallback (calling cPanel's local 'uapi' utility) may be required."
                )
            )
            sys.exit(1)
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(
                    f"\n[FAILED] Unexpected error connecting to cPanel UAPI: {exc}"
                )
            )
            sys.exit(1)
