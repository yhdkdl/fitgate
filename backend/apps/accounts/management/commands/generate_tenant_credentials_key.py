"""
Management command to generate a 32-byte TENANT_CREDENTIALS_KEY.

Usage:
    python manage.py generate_tenant_credentials_key
"""

import base64
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a new 32-byte TENANT_CREDENTIALS_KEY and print it without storing."

    def handle(self, *args, **options):
        key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.stdout.write(
            self.style.SUCCESS("\n--- TENANT CREDENTIALS ENCRYPTION KEY ---")
        )
        self.stdout.write(
            self.style.NOTICE("Paste into your .env or cPanel environment as:")
        )
        self.stdout.write(f'TENANT_CREDENTIALS_KEY="{key}"\n')
