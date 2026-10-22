"""
Management command to generate Ed25519 keypair for QR check-in token signing.

Alias for generate_qr_dev_keys for production use.

Usage:
    python manage.py generate_qr_keys
"""

from apps.attendance.management.commands.generate_qr_dev_keys import (
    Command as DevCommand,
)


class Command(DevCommand):
    help = "Generate a new Ed25519 keypair in PEM format for QR check-in token signing."
