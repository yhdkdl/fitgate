"""
Management command to generate RS256 keypair for QR check-in token signing.

Usage:
    python manage.py generate_qr_dev_keys
"""

from django.core.management.base import BaseCommand

from apps.attendance.crypto import generate_rsa_keypair


class Command(BaseCommand):
    help = "Generate an RSA 2048 keypair in PEM format for QR check-in token signing."

    def add_arguments(self, parser):
        parser.add_argument(
            "--key-size",
            type=int,
            default=2048,
            help="RSA key size in bits (default: 2048)",
        )

    def handle(self, *args, **options):
        key_size = options.get("key_size", 2048)
        self.stdout.write(f"Generating RSA {key_size}-bit keypair...")
        private_pem, public_pem = generate_rsa_keypair(key_size=key_size)

        self.stdout.write(self.style.SUCCESS("\n--- RSA PRIVATE KEY (PEM) ---"))
        self.stdout.write(private_pem)

        self.stdout.write(self.style.SUCCESS("--- RSA PUBLIC KEY (PEM) ---"))
        self.stdout.write(public_pem)

        self.stdout.write(self.style.NOTICE("Paste the above into your .env as:"))
        self.stdout.write(f'QR_JWT_PRIVATE_KEY="{private_pem.strip()}"')
        self.stdout.write(f'QR_JWT_PUBLIC_KEY="{public_pem.strip()}"\n')
