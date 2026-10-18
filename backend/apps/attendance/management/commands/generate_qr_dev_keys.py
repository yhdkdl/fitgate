"""
Management command to generate Ed25519 keypair for QR check-in token signing.

Usage:
    python manage.py generate_qr_dev_keys
"""

from django.core.management.base import BaseCommand

from apps.attendance.crypto import generate_ed25519_keypair


class Command(BaseCommand):
    help = "Generate an Ed25519 keypair in PEM format for QR check-in token signing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--key-size",
            type=int,
            default=None,
            help="Unused (retained for backward compatibility).",
        )

    def handle(self, *args, **options):
        self.stdout.write("Generating Ed25519 keypair...")
        private_pem, public_pem = generate_ed25519_keypair()

        private_oneline = private_pem.strip().replace("\n", "\\n")
        public_oneline = public_pem.strip().replace("\n", "\\n")

        self.stdout.write(
            self.style.SUCCESS(
                "\n--- ED25519 KEYPAIR (SINGLE-LINE ESCAPED FOR .ENV / CPANEL) ---"
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                "Paste into your .env or cPanel environment variables as:"
            )
        )
        self.stdout.write(f'QR_JWT_PRIVATE_KEY="{private_oneline}"')
        self.stdout.write(f'QR_JWT_PUBLIC_KEY="{public_oneline}"\n')
