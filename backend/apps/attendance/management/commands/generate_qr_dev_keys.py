"""
Backward-compatible alias for generate_qr_keys.

Usage:
    python manage.py generate_qr_dev_keys
"""

from apps.attendance.management.commands.generate_qr_keys import (
    Command as PrimaryCommand,
)


class Command(PrimaryCommand):
    help = "Deprecated alias for generate_qr_keys. Use generate_qr_keys instead."

    def handle(self, *args, **options):
        self.stderr.write(
            self.style.WARNING(
                "Note: 'generate_qr_dev_keys' is deprecated. Use 'generate_qr_keys' instead."
            )
        )
        return super().handle(*args, **options)
