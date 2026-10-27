"""
Management command to generate a cryptographically strong SECRET_KEY.

Usage:
    python manage.py generate_secret_key
"""

from django.core.management.base import BaseCommand
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = "Generate a new cryptographic SECRET_KEY and print it without storing."

    def handle(self, *args, **options):
        key = get_random_secret_key()
        self.stdout.write(self.style.SUCCESS("\n--- DJANGO SECRET KEY ---"))
        self.stdout.write(
            self.style.NOTICE("Paste into your .env or cPanel environment as:")
        )
        self.stdout.write(f'SECRET_KEY="{key}"\n')
